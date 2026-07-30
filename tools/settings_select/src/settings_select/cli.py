from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .select import FACETS, LayerMissing, Selection, SelectError, parse_facets, select


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

    **`其中 M 筆是空殼` 是 2026-07-27（功能 06）補的，理由同一個形狀但更嚴重**：
    `設計原則.md` E2 的新推論「覆蓋率行要能回答『命中的筆數裡，有幾筆是空的』」。
    實測本工具對 arc02 印「角色命中 7 筆」——**依據正確、數字正確，而其中 4 筆
    是四個必填節全為佔位字串的空殼檔**，`beat-test` 測試4 就拿它們當角色弧線的
    基準。三支守衛（`check` 報 fresh、`validate` 只驗結構、本工具只管選取）
    **各自都沒做錯**，合起來仍指向一份沒有內容的基準。只印命中率 ＝ 用命中率
    冒充可用率。修法不在這裡（跑 `character` 補實），這一行只負責讓它可見。
    """
    fn_only = [b for b in sel.world_basis if b.filename_only]
    out = [
        "",
        "### 覆蓋率（0 也印）",
        f"掃 {sel.beat_count} 幕；角色命中 {sel.char_count} 筆，"
        f"其中 {len(sel.char_hollow)} 筆是空殼（衍生檔缺失或必填節是佔位）；"
        f"世界觀命中 {len(sel.world_basis)} 筆，其中 {len(fn_only)} 筆僅因檔名被引用",
    ]
    if sel.char_hollow:
        out.append(
            f"- 空殼角色：{'、'.join(sel.char_hollow)}"
            "　※ 這幾筆被算進命中數，但 `需求四象限`／`預期弧線` 拿不到內容"
            "——跑 `character` 補實（`char-lint --book <書>` 會逐項列出）"
        )
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


# ---------------------------------------------------------------- 輸出與 exit 契約
#
# **唯一真相在 `結構定義/共同約定.md`「輸出與 exit 契約」**（2026-07-28 功能 14）。
# stdout 裝「人與 LLM 要看的一切」（覆蓋率行、問題、資訊、提示、投影輸出），
# stderr **只裝執行錯誤**。exit：0 乾淨／1 有格式問題／**2 這本書還沒有這一層
# （照樣印覆蓋率行）**。
#
# ⚠️ argparse 的用法錯誤也是 2（Python 標準行為，本輪不改）——分辨方式是
# **stdout 有沒有覆蓋率行**，`meta-lint` 第 6 項驗的就是這一條。
EXIT_CLEAN = 0
EXIT_PROBLEMS = 1
EXIT_LAYER_MISSING = 2

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
    except LayerMissing as e:
        # **exit 2 ＝這本書還沒有這一層，而且照樣印覆蓋率行**（`共同約定.md`）。
        # 覆蓋率行進 **stdout**：exit 2 不是錯誤，是一個關於這本書的事實。
        #
        # **刻意沿用成功路徑的抬頭形狀**（`（掃 N 幕；…）`），只是 N ＝ 0。
        # 第一版寫成 `選取範圍：…`，而 `meta-lint` 第 6 項的覆蓋率行 marker 認不得它
        # ——**正解不是去那份 marker 清單加一個字**（那是替一支工具放寬一個共用定義），
        # 是讓這條路印得跟自己的成功路徑一樣。exit 2 與 exit 0 的差別該在數字，不在句型。
        print(f"## {args.arc} 設定選取（掃 0 幕；這本書還沒有這一層）")
        print(f"（資訊）{e}")
        return EXIT_LAYER_MISSING
    except SelectError as e:
        print(f"選取錯誤：{e}", file=sys.stderr)
        return EXIT_PROBLEMS
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return EXIT_PROBLEMS

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
