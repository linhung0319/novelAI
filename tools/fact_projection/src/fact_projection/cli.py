from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .fold import KINDS, FoldError, Slot, parse_events, parse_spine, project

_ASOF_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）$")

# 新書一律 事實流.md；找不到才退回舊檔名（見 結構定義/事實流.schema.md 舊檔名相容）。
STREAM_NAMES = ("事實流.md", "狀態事件流.md")

_KIND_ORDER = {k: i for i, k in enumerate(KINDS)}


def resolve_stream(book: Path) -> Path:
    ref = book / "story" / "參照"
    for name in STREAM_NAMES:
        p = ref / name
        if p.is_file():
            return p
    raise FileNotFoundError(f"{ref} 下找不到 {' 或 '.join(STREAM_NAMES)}")


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
        f"## as-of 幕{target_beat:03d}（{target_arc}）事實投影"
        f"（衍生自事實流，零 LLM、可覆算）",
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
            lines.append(
                f"- {s.token}：{s.content}　←來源 幕{s.source_beat:03d}（{s.source_arc}）"
            )
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
        stream_path = resolve_stream(args.book)
        events = parse_events(stream_path.read_text(encoding="utf-8"))
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

    print(format_projection(slots, target_beat, target_arc, args.entities), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
