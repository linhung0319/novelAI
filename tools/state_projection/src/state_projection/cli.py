from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .fold import FoldError, Slot, parse_events, parse_spine, project

_ASOF_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）$")


def format_projection(
    slots: list[Slot],
    target_beat: int,
    target_arc: str,
    entities: list[str] | None = None,
) -> str:
    if entities:
        wanted = set(entities)
        slots = [s for s in slots if s.entity in wanted]
    lines = [
        f"## as-of 幕{target_beat:03d}（{target_arc}）狀態投影"
        f"（衍生自事件流，零 LLM、可覆算）",
        "",
    ]
    by_entity: dict[str, list[Slot]] = {}
    for s in slots:
        by_entity.setdefault(s.entity, []).append(s)
    if not by_entity:
        lines.append("（此 as-of 無相關狀態事件）")
    for entity, es in by_entity.items():
        lines.append(f"### {entity}")
        for s in es:
            lines.append(
                f"- {s.dimension}：{s.content}　←來源 幕{s.source_beat:03d}（{s.source_arc}）"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="狀態事件流 as-of 投影（fold，零 LLM、可覆算）。"
        "投影含所有序位 ≤ 目標幕的事件；查『進場 幕N 章首』狀態時，"
        "因 write 只在寫完章後追加事件，事件流自然只含 <幕N；傳 --as-of 幕N 即得。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument("--as-of", required=True, dest="as_of", help="目標位置，如 幕011（arcF）")
    ap.add_argument(
        "--entities", nargs="*", default=None, help="只輸出這些實體（如 哈利 哈利↔榮恩）"
    )
    args = ap.parse_args(argv)

    m = _ASOF_RE.match(args.as_of.strip())
    if not m:
        print(f"--as-of 格式須為『幕NNN（arcAA）』，得到 {args.as_of!r}", file=sys.stderr)
        return 1
    target_beat, target_arc = int(m.group(1)), m.group(2)

    stream_path = args.book / "story" / "參照" / "狀態事件流.md"
    spine_path = args.book / "story" / "幕綱" / "_index.md"
    try:
        events = parse_events(stream_path.read_text(encoding="utf-8"))
        spine = parse_spine(spine_path.read_text(encoding="utf-8"))
        slots = project(events, spine, target_beat, target_arc)
    except FileNotFoundError as e:
        print(f"找不到檔案：{e}", file=sys.stderr)
        return 1
    except FoldError as e:
        print(f"投影錯誤：{e}", file=sys.stderr)
        return 1

    print(format_projection(slots, target_beat, target_arc, args.entities), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
