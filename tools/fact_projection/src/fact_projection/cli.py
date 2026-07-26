from __future__ import annotations

import argparse
import re
import sys
from dataclasses import replace
from pathlib import Path

from .beats import BeatLookupError, find_beat
from .constraints import active_at
from .fold import (
    KIND_CONSTRAINT,
    KINDS,
    RELATION_SEP,
    Event,
    FoldError,
    Slot,
    parse_spine,
    project,
)
from .ops import SET_DIMENSIONS, render
from .refs import anchor_hits, entity_refs
from .sources import CONSTRAINT_TABLE, collect_constraints, collect_events, lint

_ASOF_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）$")

_KIND_ORDER = {k: i for i, k in enumerate(KINDS)}


def _force_utf8() -> None:
    """書內容是中文，主控台編碼（如 Windows cp950）不該決定工具能不能輸出。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


_SOURCE_DESC = {
    "chapters": "衍生自章 delta＋約束表",
    "legacy": "衍生自舊格式單檔事實流",
}


def format_projection(
    slots: list[Slot],
    target_beat: int,
    target_arc: str,
    entities: list[str] | None = None,
    mode: str = "chapters",
) -> str:
    if entities:
        wanted = set(entities)
        # 關係型 slot 是 `A↔B`，任一端命中就要留。用完全相等比對會讓 `關係` 這一
        # 整維在 `--for-beat` 這條路上靜默消失——幕綱的角色欄寫的是單個名字，
        # 永遠不會是 `A↔B`。
        slots = [
            s
            for s in slots
            if s.entity in wanted or (wanted & set(s.entity.split(RELATION_SEP)))
        ]
    lines = [
        f"## as-of 幕{target_beat:03d}（{target_arc}）事實投影"
        f"（{_SOURCE_DESC.get(mode, mode)}，零 LLM、可覆算）",
        "",
    ]
    by_entity: dict[str, list[Slot]] = {}
    for s in slots:
        by_entity.setdefault(s.entity, []).append(s)
    if not by_entity:
        lines.append("（此 as-of 無相關事實）")
    for entity, es in by_entity.items():
        lines.append(f"### {entity}")
        # 狀態 → 錨 → 約束；同類型維持原出現序（sorted 穩定）
        for s in sorted(es, key=lambda x: _KIND_ORDER[x.kind]):
            src = s.source_label
            if s.origin:
                src += f"· {s.origin}"
            lines.append(f"- {s.token}：{s.content}　←來源 {src}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_history(events: list[Event], entity: str, token: str) -> str:
    """單一 slot 的完整事件序列。

    **這支查詢是「每筆 delta 只寫增量」得以成立的前提。** 沒有它，「不重抄舊事」
    就等於要求 LLM 丟資訊——因為投影只回當下值，舊那筆再也沒人看得到。有了它，
    歷史查得到，重抄的壓力才真的解除（見 `結構定義/事實流.schema.md`「純化紀律」）。
    """
    lines = [f"## {entity} · {token} 的完整歷史（{len(events)} 筆，零 LLM、可覆算）", ""]
    if not events:
        lines.append("（查無此 slot——實體名或維度是不是打錯了？）")
        return "\n".join(lines) + "\n"
    for e in events:
        src = f"幕{e.beat:03d}（{e.arc}）"
        if e.origin:
            src += f"· {e.origin}"
        lines.append(f"- {src}　{e.content}")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="事實流 as-of 投影（fold，零 LLM、可覆算）。"
        "投影含所有序位 ≤ 目標幕的事件；查『進場 幕N 章首』時，"
        "因 write 只在寫完章後追加事件，事實流自然只含 <幕N；傳 --as-of 幕N 即得。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument("--as-of", dest="as_of", help="目標位置，如 幕011（arcF）")
    ap.add_argument(
        "--for-beat",
        dest="for_beat",
        default=None,
        help="改由幕綱導出：如 幕042。程式讀該幕的『角色』欄自動展開 --entities、"
        "並以該幕為 --as-of。取代『由 LLM 自己填要哪些實體』。",
    )
    ap.add_argument(
        "--propositions",
        choices=("all", "relevant"),
        default="all",
        help="知識前沿的命題要給全部還是只給本幕動到的（需 --for-beat）。"
        "預設 all——漏一條「尚不知」可能讓 write 洩漏知識邊界，"
        "故縮減是 opt-in，且被藏起來的條數會列出來。",
    )
    ap.add_argument(
        "--history",
        default=None,
        help="改查單一 slot 的完整事件序列，格式 `實體/維度`（如 少年/知識前沿）。"
        "投影只回當下值；要看演變軌跡走這個。",
    )
    ap.add_argument(
        "--entities", nargs="*", default=None, help="只輸出這些實體（如 哈利 哈利↔榮恩）"
    )
    ap.add_argument(
        "--kinds",
        default=None,
        help=f"只輸出這些類型，逗號分隔（{'／'.join(KINDS)}）。預設全開。",
    )
    ap.add_argument(
        "--active-only",
        action="store_true",
        help="剔除已解除的（舊格式：內容以「（解除）」起頭）。"
        "新格式的約束射程由規則表的『生效自／解除於』兩欄決定，本旗標對它是預設行為。",
    )
    ap.add_argument(
        "--ignore-lint",
        action="store_true",
        help="略過投影前的格式自檢（預設會先跑一次 fact-lint，有問題就擋下）",
    )
    args = ap.parse_args(argv)
    _force_utf8()

    if args.history:
        return _history_main(args)

    entities = args.entities
    beat_ctx = None
    if args.for_beat:
        bm = re.match(r"^幕?(\d+)$", args.for_beat.strip())
        if not bm:
            print(f"--for-beat 格式須為『幕NNN』，得到 {args.for_beat!r}", file=sys.stderr)
            return 1
        try:
            beat_ctx = find_beat(args.book, int(bm.group(1)))
        except BeatLookupError as e:
            print(f"{e}", file=sys.stderr)
            return 1
        target_beat, target_arc = beat_ctx.beat, beat_ctx.arc
        if entities is None:  # 顯式 --entities 仍可覆寫程式的選取
            entities = beat_ctx.entities
    elif not args.as_of:
        print(
            "需要 --as-of 幕NNN（arcAA）、--for-beat 幕NNN，或 --history 實體/維度",
            file=sys.stderr,
        )
        return 1
    else:
        m = _ASOF_RE.match(args.as_of.strip())
        if not m:
            print(f"--as-of 格式須為『幕NNN（arcAA）』，得到 {args.as_of!r}", file=sys.stderr)
            return 1
        target_beat, target_arc = int(m.group(1)), m.group(2)

    if args.propositions == "relevant" and beat_ctx is None:
        print("--propositions relevant 需要 --for-beat（本幕動到哪些伏筆才有得比對）", file=sys.stderr)
        return 1

    kinds: tuple[str, ...] | None = None
    if args.kinds:
        kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
        unknown = [k for k in kinds if k not in KINDS]
        if unknown:
            print(f"--kinds 含未知類型 {unknown}（限 {'／'.join(KINDS)}）", file=sys.stderr)
            return 1

    # 投影前先自 lint。副檔名 `.co.md` 保證格式，但保證得有人守——實測作者把一個
    # 全形括號打成半形，整本書的投影就 raise，而錯誤訊息只說「格式不符」。先跑一次
    # lint，把所有壞行連同修法印在最前面，比讓它在投影中途炸掉有用得多。
    if not args.ignore_lint:
        problems = lint(args.book)
        if problems:
            print(f"格式閘門擋下 {len(problems)} 個問題（--ignore-lint 可略過）：", file=sys.stderr)
            for p in problems:
                print(f"  [x] {p}", file=sys.stderr)
            return 1

    spine_path = args.book / "story" / "幕綱" / "_index.md"
    notes: list[str] = []
    try:
        events, mode = collect_events(args.book, orphans=notes)
        if mode == "legacy":
            print(
                "（此書仍是 2026-07-26 前的單檔事實流；新書走 章 delta＋約束表）",
                file=sys.stderr,
            )
        spine = parse_spine(spine_path.read_text(encoding="utf-8"))
        slots = project(
            events,
            spine,
            target_beat,
            target_arc,
            kinds=kinds,
            active_only=args.active_only,
            # 舊格式書的知識前沿是自由 prose，折不成集合——只有新格式走集合維度。
            set_dims=frozenset() if mode == "legacy" else SET_DIMENSIONS,
        )
        # 約束走規則表、不走 fold——它是一條一列的登記表，不是事件流
        # （見 constraints.py）。舊格式書的約束仍在 events 裡，這裡自然回空。
        if kinds is None or KIND_CONSTRAINT in kinds:
            slots += active_at(
                collect_constraints(args.book),
                spine,
                target_beat,
                target_arc,
                origin=CONSTRAINT_TABLE,
                notes=notes,
            )
    except FileNotFoundError as e:
        print(f"找不到檔案：{e}", file=sys.stderr)
        return 1
    except FoldError as e:
        print(f"投影錯誤：{e}", file=sys.stderr)
        return 1

    if beat_ctx is not None:
        notes.insert(
            0,
            f"--for-beat 幕{beat_ctx.beat:03d} → {beat_ctx.arc}；"
            f"由該幕「角色」欄導出實體：{'、'.join(beat_ctx.entities) or '（無）'}",
        )
    if args.propositions == "relevant" and beat_ctx is not None:
        slots = _narrow_propositions(slots, set(beat_ctx.foreshadows), notes)

    for n in notes:
        print(f"（資訊）{n}", file=sys.stderr)

    print(
        format_projection(slots, target_beat, target_arc, entities, mode=mode),
        end="",
    )
    return 0


def _narrow_propositions(
    slots: list[Slot], relevant: set[str], notes: list[str]
) -> list[Slot]:
    """只留本幕動到的知識命題，其餘標成休眠。

    **被藏起來的一定要報數。** 知識前沿是最承重的一維——漏一條「尚不知」可能讓
    `write` 寫出角色不該知道的事。縮減 context 不能是靜默的。
    """
    out: list[Slot] = []
    for s in slots:
        if s.name != "知識前沿" or not s.items:
            out.append(s)
            continue
        kept = [(n, st) for n, st in s.items if n in relevant]
        hidden = len(s.items) - len(kept)
        if hidden:
            notes.append(
                f"{s.entity}·知識前沿：只列本幕動到的 {len(kept)} 條，"
                f"另 {hidden} 條休眠中（要全部走 --propositions all）"
            )
        out.append(
            replace(s, items=tuple(kept), content=render(list(kept), "知識前沿"))
        )
    return out


def _history_main(args: argparse.Namespace) -> int:
    if "/" not in args.history:
        print(
            f"--history 格式須為 `實體/維度`（如 少年/知識前沿），得到 {args.history!r}",
            file=sys.stderr,
        )
        return 1
    entity, _, token = args.history.rpartition("/")
    entity, token = entity.strip(), token.strip()
    try:
        events, _mode = collect_events(args.book)
        spine = parse_spine(
            (args.book / "story" / "幕綱" / "_index.md").read_text(encoding="utf-8")
        )
    except FileNotFoundError as e:
        print(f"找不到檔案：{e}", file=sys.stderr)
        return 1
    except FoldError as e:
        print(f"投影錯誤：{e}", file=sys.stderr)
        return 1

    picked = [e for e in events if e.entity == entity and e.token == token]
    unknown = sorted({e.arc for e in picked if e.arc not in spine})
    if unknown:
        print(f"投影錯誤：arc {unknown} 不在 spine（全書順序）中，無法定位", file=sys.stderr)
        return 1
    picked.sort(key=lambda e: (spine[e.arc], e.beat, e.order))
    print(format_history(picked, entity, token), end="")
    return 0


def refs_main(argv: list[str] | None = None) -> int:
    """`fact-refs`：反向索引——誰依賴了這條事實。

    與 `derived-sync check` 互補：那支報「釘下事實的正文變了」，本支報「**哪些下游
    已經按舊事實寫下去了**」。少了本支，改一個錨只會修好 ledger，下游正文的矛盾
    無人察覺——而那才是讀者看得到的那一種。
    """
    ap = argparse.ArgumentParser(
        description="反向索引（零 LLM、可覆算）：某條事實有哪些下游依賴。"
        "輸出是候選清單交 LLM 複判，不自動改任何檔。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--entity", help="掃各章 delta 的實體欄（結構化欄位，精確）")
    g.add_argument("--anchor", help="錨名，如 信物的形制。拿它登記過的值 grep 全書正文")
    ap.add_argument("--after", default=None, help="只看這個位置之後的，如 幕021（arc01）")
    ap.add_argument(
        "--was",
        action="append",
        default=None,
        metavar="舊值",
        help="錨的舊值（可重複）。錨**改版時若是就地改掉那一行**，舊值就從 ledger 消失了"
        "——而要找的正是「還寫著舊值」的下游正文，所以得把它傳進來。"
        "（改版時另發一行同名事件則不需要：新舊兩個值都在，工具自己看得到。）",
    )
    args = ap.parse_args(argv)
    _force_utf8()

    try:
        events, _mode = collect_events(args.book)
        spine = parse_spine(
            (args.book / "story" / "幕綱" / "_index.md").read_text(encoding="utf-8")
        )
    except FileNotFoundError as e:
        print(f"找不到檔案：{e}", file=sys.stderr)
        return 1
    except FoldError as e:
        print(f"解析錯誤：{e}", file=sys.stderr)
        return 1

    after = None
    if args.after:
        m = _ASOF_RE.match(args.after.strip())
        if not m:
            print(f"--after 格式須為『幕NNN（arcAA）』，得到 {args.after!r}", file=sys.stderr)
            return 1
        if m.group(2) not in spine:
            print(f"arc {m.group(2)!r} 不在 spine（全書順序）中", file=sys.stderr)
            return 1
        after = (spine[m.group(2)], int(m.group(1)))

    if args.entity:
        found = entity_refs(events, args.entity, spine, after)
        print(_format_entity_refs(args.entity, found), end="")
        return 0

    token = f"錨〔{args.anchor.strip('〔〕')}〕"
    values = [e.content for e in events if e.token == token]
    if not values and not args.was:
        print(f"查無錨 {token}——名字是不是打錯了？", file=sys.stderr)
        return 1
    values += [v for v in (args.was or []) if v not in values]
    print(_format_anchor_hits(token, values, anchor_hits(args.book, values)), end="")
    return 0


def _format_entity_refs(entity: str, refs: list) -> str:
    lines = [f"## 提到「{entity}」的章 delta（{len(refs)} 筆·候選，交 LLM 複判）", ""]
    if not refs:
        lines.append("（無）")
        return "\n".join(lines) + "\n"
    for r in refs:
        where = f"幕{r.beat:03d}（{r.arc}）"
        lines.append(f"- {r.origin}　{where}　{r.token}：{r.content[:60]}")
    return "\n".join(lines).rstrip() + "\n"


def _format_anchor_hits(token: str, values: list[str], hits: list) -> str:
    lines = [f"## {token} 的下游字面依賴（候選，交 LLM 複判）", ""]
    lines.append(f"登記過的值（新舊共 {len(values)} 筆）：")
    for v in values:
        lines.append(f"- {v}")
    lines += ["", "正文裡的字面出現："]
    if not hits:
        lines.append("（無——可能是錨的值本來就不會逐字出現在正文裡）")
        return "\n".join(lines).rstrip() + "\n"
    by_term: dict[str, list] = {}
    for h in hits:
        by_term.setdefault(h.term, []).append(h)
    for term, hs in by_term.items():
        where = "、".join(f"{h.chapter}×{h.count}" for h in hs)
        lines.append(f"- 「{term}」：{where}")
    return "\n".join(lines).rstrip() + "\n"


def lint_main(argv: list[str] | None = None) -> int:
    """`fact-lint`：驗全書事實信封行的格式與落點，一次報完所有問題。

    與 `derived-sync validate` 分工：那支管 `.ai.md` 的**結構**（front-matter、
    節枚舉），本支管**事實信封行**。各自擁有自己那份格式的唯一真相。
    """
    ap = argparse.ArgumentParser(
        description="事實信封行格式閘門：驗 chapters/chNNNN.ai.md 的「## 本章事實」"
        "與 story/參照/約束.md，一次報完所有壞行與落錯地方的類型。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    args = ap.parse_args(argv)
    _force_utf8()

    problems = lint(args.book)
    if not problems:
        print("事實信封行格式乾淨。")
        return 0
    print(f"發現 {len(problems)} 個問題：", file=sys.stderr)
    for p in problems:
        print(f"  [x] {p}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
