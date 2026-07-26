from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .fold import KINDS, FoldError, Slot, parse_spine, project
from .sources import collect_events, lint

_ASOF_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）$")

_KIND_ORDER = {k: i for i, k in enumerate(KINDS)}


def _force_utf8() -> None:
    """書內容是中文，主控台編碼（如 Windows cp950）不該決定工具能不能輸出。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


_SOURCE_DESC = {
    "chapters": "衍生自章 delta＋約束 log",
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
        slots = [s for s in slots if s.entity in wanted]
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
            src = f"幕{s.source_beat:03d}（{s.source_arc}）"
            if s.origin:
                src += f"· {s.origin}"
            lines.append(f"- {s.token}：{s.content}　←來源 {src}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="事實流 as-of 投影（fold，零 LLM、可覆算）。"
        "三類型（狀態／錨／約束）共用同一套 fold。"
        "投影含所有序位 ≤ 目標幕的事件；查『進場 幕N 章首』時，"
        "因 write 只在寫完章後追加事件，事實流自然只含 <幕N；傳 --as-of 幕N 即得。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument("--as-of", required=True, dest="as_of", help="目標位置，如 幕011（arcF）")
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
        help="剔除已解除的（內容以「（解除）」起頭）——查生效中的約束用。",
    )
    args = ap.parse_args(argv)
    _force_utf8()

    m = _ASOF_RE.match(args.as_of.strip())
    if not m:
        print(f"--as-of 格式須為『幕NNN（arcAA）』，得到 {args.as_of!r}", file=sys.stderr)
        return 1
    target_beat, target_arc = int(m.group(1)), m.group(2)

    kinds: tuple[str, ...] | None = None
    if args.kinds:
        kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
        unknown = [k for k in kinds if k not in KINDS]
        if unknown:
            print(f"--kinds 含未知類型 {unknown}（限 {'／'.join(KINDS)}）", file=sys.stderr)
            return 1

    spine_path = args.book / "story" / "幕綱" / "_index.md"
    try:
        events, mode = collect_events(args.book)
        if mode == "legacy":
            print(
                "（此書仍是 2026-07-26 前的單檔事實流；新書走 章 delta＋約束 log）",
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
        )
    except FileNotFoundError as e:
        print(f"找不到檔案：{e}", file=sys.stderr)
        return 1
    except FoldError as e:
        print(f"投影錯誤：{e}", file=sys.stderr)
        return 1

    print(
        format_projection(slots, target_beat, target_arc, args.entities, mode=mode),
        end="",
    )
    return 0


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
