from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .select import FACETS, Selection, SelectError, parse_facets, select


def _beats_label(beats: tuple[int, ...], limit: int = 4) -> str:
    shown = [f"幕{b}" for b in beats[:limit]]
    if len(beats) > limit:
        shown.append(f"…共{len(beats)}幕")
    return "／".join(shown)


def format_selection(
    sel: Selection,
    book: Path,
    show_bytes: bool = True,
    facets: tuple[str, ...] | None = None,
    include_underwater: bool = False,
) -> str:
    facet_note = f"；切面 {'／'.join(facets)}" if facets else ""
    if include_underwater:
        facet_note += "；含水下"
    lines = [
        f"## {sel.arc} 設定選取（掃 {sel.beat_count} 幕{facet_note}；零 LLM、可覆算）",
        "",
        "### 要讀的設定檔",
    ]
    if not sel.selected:
        lines.append("（本範圍的幕沒有命中任何設定層實體——請確認幕綱「角色」欄有填）")
    total = 0
    files = 0
    for hit in sel.selected:
        paths = hit.entity.read_paths(facets, include_underwater)
        tag = "" if hit.entity.derived else "　※衍生檔未生成，只有源"
        for i, p in enumerate(paths):
            size = p.stat().st_size if p.exists() else 0
            total += size
            files += 1
            rel = p.relative_to(book) if p.is_relative_to(book) else p
            sz = f"　{size:>6}B" if show_bytes else ""
            beats = f"　←{_beats_label(hit.beats)}{tag}" if i == 0 else ""
            lines.append(f"- [{hit.entity.kind}] {rel}{sz}{beats}")

    if show_bytes:
        lines += ["", f"合計 {total} bytes（{files} 檔／{len(sel.selected)} 個實體）"]

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

    lines += _coverage_lines(sel)
    return "\n".join(lines).rstrip() + "\n"


def _coverage_lines(sel: Selection) -> list[str]:
    """**我在這個 arc 上命中幾筆、命中的依據是什麼**（`設計原則.md` D2／E2）。

    2026-07-27（功能 05 抉擇 2 D）新增。一律印、**0 也印**——「命中 0 筆」本身
    就是最有用的那一筆訊息（實測教訓：只回答「找到什麼」的工具，在它自己失效時
    印的是一份看起來正常的結果）。

    `僅因檔名` 那個數字是這一行存在的理由：世界觀的 selector 比對的是檔名字串，
    所以幕綱散文裡的 `見 \\`X.ai.md\\`` 註腳會讓那支檔被選中，而幕本身可能根本
    沒在講那個主題。02 要把那些註腳從八欄清掉，清完命中就會掉——**先讓數字可見，
    再決定選擇器怎麼修**（抉擇 2 的 A／C 刻意延後，等這一行量出數字再判）。
    """
    fn_only = [b for b in sel.world_basis if b.filename_only]
    out = [
        "",
        "### 覆蓋率（0 也印）",
        f"掃 {sel.beat_count} 幕；角色命中 {sel.char_count} 筆；"
        f"世界觀命中 {len(sel.world_basis)} 筆，其中 {len(fn_only)} 筆僅因檔名被引用",
    ]
    for b in sorted(sel.world_basis, key=lambda x: (not x.filename_only, x.name)):
        tag = "　※僅因檔名" if b.filename_only else ""
        out.append(f"- {b.name}　檔名引用 {b.by_filename} 次／裸提及 {b.bare} 次{tag}")
    if fn_only:
        out.append(
            "> ※「僅因檔名」＝這個主題之所以被選中，只因為幕綱散文寫了 "
            "`X.ai.md` 這類引用，幕的內文沒有一處真的提到它。"
            "那些引用一旦從幕綱八欄清掉（02 的目標），這幾筆會靜默地從選取結果消失"
            "——選擇器怎麼修見 `功能報告/05-設定層-世界觀.md` 抉擇 2（A／C 刻意延後）。"
        )
    return out


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
        "--facets",
        default=None,
        help=f"角色目錄形態只取這些切面，逗號分隔（{'／'.join(FACETS)}）。"
        "預設取全部（水下除外）。單檔形態的角色切不動，一律整檔。",
    )
    ap.add_argument(
        "--include-underwater",
        action="store_true",
        help="連「水下」切面一起給（揭底資訊）。預設不給——這是存取控制，"
        "讓 write 在揭底前的章節拿不到它。character／beat-sheet 才該開。",
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
        facets = parse_facets(args.facets)
        sel = select(args.book, args.arc, args.beats)
    except SelectError as e:
        print(f"選取錯誤：{e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return 1

    if args.paths_only:
        for hit in sel.selected:
            for p in hit.entity.read_paths(facets, args.include_underwater):
                print(p)
        return 0

    print(
        format_selection(
            sel, args.book, facets=facets, include_underwater=args.include_underwater
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
