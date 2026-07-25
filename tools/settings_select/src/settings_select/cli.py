from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .select import Selection, SelectError, select


def _beats_label(beats: tuple[int, ...], limit: int = 4) -> str:
    shown = [f"幕{b}" for b in beats[:limit]]
    if len(beats) > limit:
        shown.append(f"…共{len(beats)}幕")
    return "／".join(shown)


def format_selection(sel: Selection, book: Path, show_bytes: bool = True) -> str:
    lines = [
        f"## {sel.arc} 設定選取（掃 {sel.beat_count} 幕；零 LLM、可覆算）",
        "",
        "### 要讀的設定檔",
    ]
    if not sel.selected:
        lines.append("（本範圍的幕沒有命中任何設定層實體——請確認幕綱「角色」欄有填）")
    total = 0
    for hit in sel.selected:
        p = hit.entity.read_path
        size = p.stat().st_size if p.exists() else 0
        total += size
        rel = p.relative_to(book) if p.is_relative_to(book) else p
        tag = "" if hit.entity.derived else "　※衍生檔未生成，退回源檔"
        sz = f"　{size:>6}B" if show_bytes else ""
        lines.append(f"- [{hit.entity.kind}] {rel}{sz}　←{_beats_label(hit.beats)}{tag}")

    if show_bytes:
        lines += ["", f"合計 {total} bytes（{len(sel.selected)} 檔）"]

    if sel.mentioned_only:
        lines += [
            "",
            "### ※ 只在角色欄以外出現的角色（**不列入選取**，交作者判斷）",
            "幕綱「角色」欄是「這一幕有誰」的正式宣告。以下角色在幕的內文被提到、"
            "卻沒寫進角色欄——可能是幕綱漏填，也可能只是被談論而非在場：",
        ]
        for hit in sel.mentioned_only:
            lines.append(f"- {hit.entity.name}　←{_beats_label(hit.beats)}")

    for kind in sel.unknown_dir:
        lines += ["", f"※ 找不到 story/設定/{kind}/ 目錄"]

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="依幕綱選取相關設定檔（零 LLM、可覆算）。"
        "取代 skill 步驟1 的 `讀 設定/角色/*.ai.md` wildcard——"
        "只吐這個 arc／幕範圍真正涉及的實體，讓 context 載入量與書長度無關。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument("--arc", required=True, help="arc 編號，如 arc12")
    ap.add_argument(
        "--beats", default=None, help="只看這個幕號範圍，如 幕1001-1005（預設整個 arc）"
    )
    ap.add_argument(
        "--paths-only",
        action="store_true",
        help="只印檔案路徑，一行一個（供 shell 串接）",
    )
    args = ap.parse_args(argv)

    # 書內容是中文，主控台編碼（如 Windows cp950）不該決定工具能不能輸出。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    try:
        sel = select(args.book, args.arc, args.beats)
    except SelectError as e:
        print(f"選取錯誤：{e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return 1

    if args.paths_only:
        for hit in sel.selected:
            print(hit.entity.read_path)
        return 0

    print(format_selection(sel, args.book), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
