from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parse import (
    STATUSES,
    TARGET_ALL,
    Decision,
    ParseError,
    parse_decisions,
    parse_spine,
    select,
)

# `.co.md` ＝ co-authored：AI 寫、作者改、兩邊都留、格式由檢查器守（`共同約定.md` 零）。
# 舊名 `裁決流.md` 保留相容——既有書不必為改名動書內檔。
STREAM_NAMES = ("裁決流.co.md", "裁決流.md")
STREAM_NAME = STREAM_NAMES[0]


def resolve_stream(book: Path) -> Path:
    ref = book / "story" / "參照"
    for name in STREAM_NAMES:
        p = ref / name
        if p.is_file():
            return p
    raise FileNotFoundError(f"找不到 {ref / STREAM_NAME}（舊名 {STREAM_NAMES[1]} 亦可）")


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
        "--active-only", action="store_true", help="只回仍生效的（濾掉已升為通則／已過射程）"
    )
    ap.add_argument(
        "--as-of",
        dest="as_of",
        default=None,
        help="目前寫到哪個 arc（如 arc11）。給了就**由程式**依「射程」欄自動判"
        "『至arcNN』過期沒，不必有人回頭維護「狀態」欄。需 --active-only 才生效。",
    )
    ap.add_argument("--since", default=None, help="只看這個日期（含）之後的，格式 YYYY-MM-DD")
    args = ap.parse_args(argv)

    # 書內容是中文，主控台編碼（如 Windows cp950）不該決定工具能不能輸出。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    try:
        path = resolve_stream(args.book)
        decisions = parse_decisions(path.read_text(encoding="utf-8"))
        spine = None
        if args.as_of:
            spine_path = args.book / "story" / "幕綱" / "_index.md"
            spine = parse_spine(spine_path.read_text(encoding="utf-8"))
            if args.as_of not in spine:
                print(f"arc {args.as_of!r} 不在 spine（全書順序）中", file=sys.stderr)
                return 1
        picked = select(
            decisions,
            target=args.target,
            active_only=args.active_only,
            since=args.since,
            spine=spine,
            as_of_arc=args.as_of,
        )
    except FileNotFoundError as e:
        print(f"找不到檔案：{e}", file=sys.stderr)
        return 1
    except ParseError as e:
        print(f"裁決流解析錯誤：{e}", file=sys.stderr)
        return 1

    for note in stale_targets(args.book, picked):
        print(f"（資訊）{note}", file=sys.stderr)
    print(format_decisions(picked, args.target, args.active_only), end="")
    return 0


def stale_targets(book: Path, decisions: list[Decision]) -> list[str]:
    """標的路徑在書內已經不存在——append-only 不刪列，但壞標的要被看見。

    最常見的成因是角色源檔升級成目錄形態（`角色.schema.md` 明文建議的路徑）後，
    舊列的 `<名>.md` 已不存在。分段比對讓查詢照樣命中，本提示讓作者知道該順手改。
    """
    notes: list[str] = []
    seen: set[str] = set()
    for d in decisions:
        t = d.target.strip()
        if t == TARGET_ALL or t in seen:
            continue
        seen.add(t)
        p = book / "story" / t
        if not p.exists() and not p.with_suffix("").is_dir():
            notes.append(f"第 {d.lineno} 行的標的 `{t}` 在書內找不到（檔案改名或已移除？）")
    return notes


if __name__ == "__main__":
    raise SystemExit(main())
