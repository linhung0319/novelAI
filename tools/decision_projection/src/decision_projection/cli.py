from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parse import STATUSES, Decision, ParseError, parse_decisions, select

STREAM_NAME = "裁決流.md"


def resolve_stream(book: Path) -> Path:
    p = book / "story" / "參照" / STREAM_NAME
    if not p.is_file():
        raise FileNotFoundError(f"找不到 {p}")
    return p


def format_decisions(
    decisions: list[Decision], target: str | None, active_only: bool
) -> str:
    scope_note = f"標的 {target}" if target else "全部標的"
    state_note = "僅生效中" if active_only else f"全部狀態（{'／'.join(STATUSES)}）"
    lines = [f"## 裁決流查詢（{scope_note}·{state_note}）", ""]
    if not decisions:
        lines.append("（無符合的裁決）")
        return "\n".join(lines) + "\n"
    for d in decisions:
        lines.append(f"### {d.date} · {d.source} → {d.target}")
        lines.append(f"- 裁決：{d.ruling}")
        lines.append(f"- 理由：{d.rationale}")
        lines.append(f"- 射程：{d.scope}　狀態：{d.status}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="裁決流查詢（零 LLM、可覆算）。"
        "查某個源檔／幕綱過去已經裁決過什麼，避免重新爭論已定案的事。"
        "消化待裁決回饋前先跑這個。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument(
        "--target",
        default=None,
        help="只看這個標的（相對 story/ 的路徑，如 設定/角色/少年/ 或 幕綱/arc07.md）。"
        "前綴雙向相符即命中；標的為『全書』的裁決一律命中。",
    )
    ap.add_argument(
        "--active-only", action="store_true", help="只回狀態＝生效中的（濾掉已過射程／已升為通則）"
    )
    ap.add_argument("--since", default=None, help="只看這個日期（含）之後的，格式 YYYY-MM-DD")
    args = ap.parse_args(argv)

    try:
        path = resolve_stream(args.book)
        decisions = parse_decisions(path.read_text(encoding="utf-8"))
        picked = select(
            decisions,
            target=args.target,
            active_only=args.active_only,
            since=args.since,
        )
    except FileNotFoundError as e:
        print(f"找不到檔案：{e}", file=sys.stderr)
        return 1
    except ParseError as e:
        print(f"裁決流解析錯誤：{e}", file=sys.stderr)
        return 1

    print(format_decisions(picked, args.target, args.active_only), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
