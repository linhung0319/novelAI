from __future__ import annotations

import argparse
import re
import sys
from dataclasses import replace
from pathlib import Path

from .beats import BeatLookupError, arc_exclusions, find_beat
from .chapters import covering_chapter, load_chapter_meta
from .constraints import CONSTRAINT_SECTION, active_at
from .fold import (
    KIND_CONSTRAINT,
    KINDS,
    RELATION_SEP,
    Event,
    FoldError,
    Slot,
    parse_spine,
    project,
    spine_path as _spine_path,
)
from .objects import (
    KINDS as OBJECT_KINDS,
    OBJECT_DIRNAME,
    POLICY_NAME,
    objects_dir,
)
from .ops import SET_DIMENSIONS, render
from .refs import anchor_hits, entity_refs
from .sources import collect_constraints, collect_events, lint, lint_report

_ASOF_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）$")

_KIND_ORDER = {k: i for i, k in enumerate(KINDS)}


def _force_utf8() -> None:
    """書內容是中文，主控台編碼（如 Windows cp950）不該決定工具能不能輸出。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


_SOURCE_DESC = {
    "chapters": "衍生自章 delta＋物件檔的約束",
    "legacy": "含舊格式單檔事實流的行（逐行判世代）",
}


def format_projection(
    slots: list[Slot],
    target_beat: int,
    target_arc: str,
    entities: list[str] | None = None,
    mode: str = "chapters",
    exclusions: list[str] | None = None,
) -> str:
    # 書級方針**先抽出來，在實體過濾之前**。它們的實體是 `全書`，而 `--for-beat`
    # 的實體集是從幕綱的「角色」欄導出的——**沒有任何一幕的角色欄會是「全書」**，
    # 所以不先抽走，方針會被下面那道過濾靜默吃掉。
    #
    # 這正是抉擇 4 B（書級方針住 `story/物件/全書.md`）成立的必要條件：那個選項的
    # 決定性優點是「方針會自動被載入，不必有人記得查」，而在補上這一節之前**它是
    # 假的**。同一個形狀的先例是 arc 排除線（功能 02）：落點留在原處，載入靠查詢
    # 層合流（`設計原則.md` F2 第四格）。
    policies = [s for s in slots if s.entity == POLICY_NAME]
    slots = [s for s in slots if s.entity != POLICY_NAME]
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

    # arc 射程的排除線。**刻意與上面的實體節分開列**：它們沒有實體（射程是整個
    # arc、不是某個人），硬塞進某個 `### <實體>` 節會謊報它只管那一個人。
    # 一律印這一節（0 條也印）——「本 arc 沒有排除線」與「沒有人去讀排除線」是
    # 兩件事，而舊版連讀都沒讀（`設計原則.md` E2）。
    lines.append(f"### 本 arc 排除線（{target_arc} 承諾區·射程＝本 arc）")
    lines += [f"- 不得發生：{x}" for x in (exclusions or [])] or [
        "（無——該 arc 承諾區沒有「不得發生」條目）"
    ]

    # 書級方針（射程＝全書、不綁實體）。**一律印這一節（0 條也印）**——
    # 「這本書沒有書級方針」與「沒有人去讀書級方針」是兩件事。
    lines.append("")
    lines.append(
        f"### 全書方針（射程＝全書·{OBJECT_DIRNAME}/{POLICY_NAME}.md）"
    )
    lines += [f"- {s.token}：{s.content}" for s in policies] or [
        f"（無——這本書沒有 {OBJECT_DIRNAME}/{POLICY_NAME}.md，或該檔沒有生效中的方針）"
    ]
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

    spine_file = _spine_path(args.book)
    notes: list[str] = []
    try:
        events, mode = collect_events(args.book, orphans=notes)
        if mode == "legacy":
            legacy_lines = sum(1 for e in events if e.legacy)
            notes.append(
                f"本書仍有 2026-07-26 前的單檔事實流（{legacy_lines} 行走舊格式、"
                f"{len(events) - legacy_lines} 行走章 delta）。"
                "**世代是逐行判的**：舊格式那些行的集合維度不套操作串，其餘檢查照跑"
            )
        spine = parse_spine(spine_file.read_text(encoding="utf-8"))
        slots = project(
            events,
            spine,
            target_beat,
            target_arc,
            kinds=kinds,
            active_only=args.active_only,
            # 集合維度只套在新格式的行上，那個判斷在 fold 裡逐行做（見 GEN_LEGACY）。
            set_dims=SET_DIMENSIONS,
        )
        # 約束走規則表、不走 fold——它是一條一列的登記表，不是事件流
        # （見 constraints.py）。它住各支物件檔的「## 不得寫成什麼」。
        if kinds is None or KIND_CONSTRAINT in kinds:
            constraints = collect_constraints(args.book)
            slots += active_at(
                constraints,
                spine,
                target_beat,
                target_arc,
                origin="",  # 每條約束自帶它的物件檔，見 Constraint.to_slot
                notes=notes,
            )
            notes += _release_due(args.book, constraints, spine)
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
        format_projection(
            slots,
            target_beat,
            target_arc,
            entities,
            mode=mode,
            exclusions=arc_exclusions(args.book, target_arc),
        ),
        end="",
    )
    return 0


def _release_due(book: Path, constraints: list, spine: dict[str, int]) -> list[str]:
    """`解除於` 指向的幕已經寫成正文了 → 提示作者確認該解除了。

    **這是 E2 第六個永久盲點目前唯一的補償機制。** 約束刻意沒有「狀態」欄（狀態由
    `解除於` 導出，比照 `裁決流` 那個沒人維護的狀態欄不踩第二次），代價是「一條該
    解除的約束沒被解除」沒有任何東西會撞到它——`fact-project` 會忠實地繼續回報它、
    `write` 會忠實地繼續遵守它。至少在它的解除點已經成為既成正文時吭一聲。
    """
    metas = load_chapter_meta(book)
    if not metas:
        return []
    out: list[str] = []
    for c in constraints:
        if c.until is None or c.until.arc not in spine:
            continue
        stem = covering_chapter(metas, c.until.arc, c.until.beat)
        if stem:
            out.append(
                f"約束〔{c.name}〕· {c.entity} 的「解除於」{c.until} 已經寫成正文"
                f"（{stem}）——確認它真的解除了；還要繼續守就把那一格往後改"
                f"（{c.origin}）"
            )
    return out


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
        spine = parse_spine(_spine_path(args.book).read_text(encoding="utf-8"))
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
    g.add_argument(
        "--constraint",
        help="約束名。列出它的射程、射程內已寫成的章、那些章提到該實體的地方"
        "——改／解除一條約束之前要看的就是這個",
    )
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
        spine = parse_spine(_spine_path(args.book).read_text(encoding="utf-8"))
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

    if args.constraint:
        return _constraint_refs_main(args, events, spine)

    token = f"錨〔{args.anchor.strip('〔〕')}〕"
    values = [e.content for e in events if e.token == token]
    if not values and not args.was:
        print(f"查無錨 {token}——名字是不是打錯了？", file=sys.stderr)
        return 1
    values += [v for v in (args.was or []) if v not in values]
    print(_format_anchor_hits(token, values, anchor_hits(args.book, values)), end="")
    return 0


def _constraint_refs_main(
    args: argparse.Namespace, events: list[Event], spine: dict[str, int]
) -> int:
    """一條約束的下游依賴。

    **為什麼需要這支。** `設計原則.md` E3 明說約束不會自癒（它只被讀、不被再寫，
    沒有東西會撞到它），E4 明說「以後會發現」要成立的前提是有反向索引——兩條原則
    同時指名約束，而 `fact-refs` 原本只有 `--entity` 與 `--anchor` 兩條路。於是
    「改了一條約束的射程」之後，**已經按舊射程寫下去的正文沒有任何工具找得出來**。

    約束的「不得寫成 X」本身不會逐字出現在正文裡（它是負向的），所以查法不是 grep
    那句話，是：射程 → 射程內已寫成的章 → 那些章裡它管的那個實體出現在哪。
    """
    name = args.constraint.strip("〔〕")
    constraints = collect_constraints(args.book)
    picked = [c for c in constraints if c.name == name]
    if not picked:
        known = "、".join(sorted({c.name for c in constraints})) or "（一條都沒有）"
        print(
            f"查無約束〔{name}〕——名字是不是打錯了？全書現有：{known}",
            file=sys.stderr,
        )
        return 1

    metas = load_chapter_meta(args.book)
    lines: list[str] = []
    for c in picked:
        lines += [
            f"## 約束〔{c.name}〕· {c.entity} 的下游依賴（候選，交 LLM 複判）",
            "",
            f"- 不得寫成：{c.content}",
            f"- 射程：{c.since or '全書'} → {c.until or '（尚未解除）'}"
            f"　←{c.origin}",
            "",
        ]
        in_range = sorted(
            (m for m in metas.values() if _meta_in_scope(m, c, spine)),
            key=lambda m: m.stem,
        )
        lines.append(f"射程內已寫成的章（{len(in_range)} 支）：")
        if not in_range:
            lines.append("- （無——這條約束還沒有任何既成正文受它管）")
        for m in in_range:
            lines.append(
                f"- {m.stem}　幕{m.first_beat:03d}–幕{m.last_beat:03d}（{m.arc}）"
            )
        hits = [
            h
            for h in anchor_hits(args.book, [c.entity])
            if any(h.chapter == m.stem for m in in_range)
        ]
        lines += ["", f"射程內正文提到「{c.entity}」的地方："]
        if not hits:
            lines.append("- （無字面命中——實體名可能在正文裡是別的稱呼）")
        for h in hits:
            lines.append(f"- {h.chapter}　「{h.term}」×{h.count}")
        deltas = [
            e
            for e in events
            if c.entity in e.entity and _event_in_scope(e, c, spine)
        ]
        lines += ["", f"射程內動到「{c.entity}」的 delta（{len(deltas)} 筆）："]
        if not deltas:
            lines.append("- （無）")
        for e in deltas:
            lines.append(
                f"- {e.origin}　幕{e.beat:03d}（{e.arc}）　{e.token}：{e.content[:50]}"
            )
        lines.append("")
    print("\n".join(lines).rstrip() + "\n", end="")
    return 0


def _rank(spine: dict[str, int], arc: str, beat: int) -> tuple[int, int] | None:
    return (spine[arc], beat) if arc in spine else None


def _event_in_scope(e: Event, c, spine: dict[str, int]) -> bool:
    pos = _rank(spine, e.arc, e.beat)
    if pos is None:
        return False
    if c.since is not None:
        since = _rank(spine, c.since.arc, c.since.beat)
        if since is None or pos < since:
            return False
    if c.until is not None:
        until = _rank(spine, c.until.arc, c.until.beat)
        if until is not None and pos >= until:
            return False
    return True


def _meta_in_scope(meta, c, spine: dict[str, int]) -> bool:
    """這一章有任何一幕落在約束射程內嗎（章是幕區間，不是單點）。"""
    if meta.first_beat is None or meta.arc not in spine:
        return False
    lo = (spine[meta.arc], meta.first_beat)
    hi = (spine[meta.arc], meta.last_beat)
    if c.since is not None:
        since = _rank(spine, c.since.arc, c.since.beat)
        if since is None or hi < since:
            return False
    if c.until is not None:
        until = _rank(spine, c.until.arc, c.until.beat)
        if until is not None and lo >= until:
            return False
    return True


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
    """`fact-lint`：驗全書事實信封行與物件檔的格式與落點，一次報完所有問題。

    與 `derived-sync validate` 分工：那支管 `.ai.md` 的**結構**（front-matter、
    節枚舉），本支管**事實信封行與物件檔**。各自擁有自己那份格式的唯一真相。

    **一律先印檢查範圍**（`設計原則.md` E2）：只回答「發現幾個問題」的檢查器，
    在它自己被關掉的時候會印「乾淨」——實測就這樣讓 206 個問題報 0。
    """
    ap = argparse.ArgumentParser(
        description="事實軸格式閘門：驗 chapters/chNNNN.ai.md 的「## 本章事實」"
        f"與 story/{OBJECT_DIRNAME}/<名>.md，一次報完所有壞行與落錯地方的類型。"
        "輸出一律含「我檢查了幾筆」。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    args = ap.parse_args(argv)
    _force_utf8()

    problems, stats = lint_report(args.book)
    return _print_lint(problems, stats, "事實信封行與物件檔格式乾淨。")


def _print_lint(problems: list[str], stats, clean_msg: str) -> int:
    print(stats.render())
    for n in stats.notes:
        print(f"（資訊）{n}")
    for h in stats.hints:
        print(f"（提示）{h}")
    if not problems:
        print(clean_msg)
        return 0
    print(f"發現 {len(problems)} 個問題：", file=sys.stderr)
    for p in problems:
        print(f"  [x] {p}", file=sys.stderr)
    return 1


def object_lint_main(argv: list[str] | None = None) -> int:
    """`object-lint`：物件軸的聚焦入口。

    跑的是 `fact-lint` 的同一組檢查（同一份真相，不是第二套），只是把輸出收斂到
    物件檔那幾類，讓 `character`／`worldbuild` 這些**只動物件檔**的 skill 有一個
    對得上自己動作的閘門。要一次看全部就跑 `fact-lint`；`fact-project` 執行前的
    自檢也涵蓋這些，所以漏跑本支不會讓壞物件檔溜進投影。
    """
    ap = argparse.ArgumentParser(
        description=f"物件軸格式閘門：驗 story/{OBJECT_DIRNAME}/<名>.md 的檔名、"
        f"型別（封閉七型 {'／'.join(OBJECT_KINDS)}）、節枚舉、內容測試、"
        f"「## {CONSTRAINT_SECTION}」的約束表、以及揭示層級指向的收點存不存在。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    ap.add_argument(
        "--all",
        action="store_true",
        help="連事實信封行的問題一起印（＝等同 fact-lint）",
    )
    args = ap.parse_args(argv)
    _force_utf8()

    problems, stats = lint_report(args.book)
    if not args.all:
        problems = [p for p in problems if _is_object_problem(p)]
    d = objects_dir(args.book)
    if not d.is_dir():
        print(f"（資訊）{d} 不存在——這本書還沒有任何物件檔")
    return _print_lint(problems, stats, "物件檔格式乾淨。")


def _is_object_problem(problem: str) -> bool:
    """這個問題是物件軸的嗎（供 `object-lint` 收斂輸出）。

    比對**開頭**而不是「有沒有出現」——每個問題訊息都以它的位置起頭（物件檔的是
    `物件/<名>.md…`、近似名的是 `引用名〔…`）。用 `in` 會把純化違規全撈進來，
    因為它們的**修法提示**裡就寫著「排除線屬 story/物件/<實體>.md」。
    """
    return (
        problem.startswith(f"{OBJECT_DIRNAME}/")
        or problem.startswith("引用名〔")
        or "落點已廢除" in problem  # 約束的舊落點還在＝物件軸的遷移待辦
    )


if __name__ == "__main__":
    raise SystemExit(main())
