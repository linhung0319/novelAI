from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .chapters import lint_report as ch_lint_report
from .emit import emit_beats, emit_chapters, emit_outline
from .lint import lint_report
from .motif import ArcMotif, Finding, detect, measure
from .outline import lint_report as outline_lint_report
from .playability import HOLLOW_SHARE_CAP, RUN_CAP, ArcPlayability, analyse
from .scan import LayerMissing, ScanError, load_book, load_pov
from .structure_project import project


# ---------------------------------------------------------------- 輸出與 exit 契約
#
# **唯一真相在 `結構定義/共同約定.md`「輸出與 exit 契約」**（2026-07-28 功能 14）。
# 三個碼與兩個通道，全套件同一份語意；`meta-lint` 第 6 項對 fixture 書實跑比對
# stdout／stderr／exit。
#
# | 通道 | 裝什麼 |
# |---|---|
# | **stdout** | 覆蓋率行、問題、資訊、提示、投影輸出——**人與 LLM 要看的一切** |
# | **stderr** | **只裝執行錯誤**（讀不到檔、解析炸掉） |
#
# **為什麼問題要從 stderr 搬到 stdout**（V10）：實測
# `fact-lint --book 一世之尊 > report.txt` 只得到 2 行（412 B），而 206 個問題
# （47,547 B）全部落進 stderr——**在一個由 LLM 驅動、routinely 重導輸出的系統裡，
# 這是一個會安靜地讀成「乾淨」的介面**。
EXIT_CLEAN = 0
EXIT_PROBLEMS = 1
# **exit 2 ＝「這本書還沒有這一層」**，而且**照樣印覆蓋率行**（抉擇 6 A）。
# ⚠️ argparse 的**用法錯誤**也是 2（Python 標準行為，本輪不改）。
# **分辨方式是 stdout 有沒有覆蓋率行**：跑不動會印「掃了 0 支」，用法錯誤只印
# usage 到 stderr。`meta-lint` 第 6 項驗的就是這一條。
EXIT_LAYER_MISSING = 2

_EMPTY_COVERAGE = "檢查範圍：掃了 0 支——這本書還沒有這一層（{reason}）"


def _force_utf8() -> None:
    """Windows 主控台常是 cp950，會在印中文時炸。強制 UTF-8 輸出。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def _play_line(p: ArcPlayability, m: ArcMotif) -> str:
    runs = "／".join("–".join(f"幕{b}" for b in (r[0], r[-1])) for r in p.hollow_runs)
    return (
        f"{p.arc:<8} {p.total:>3} 幕  "
        f"空洞 {len(p.hollow_beats):>2}/{p.total:<2} {p.hollow_share:>4.0%}  "
        f"純內在 {len(p.solo_beats):>2}  "
        f"分區衛生 {len(p.meta_beats):>2} 幕  "
        f"母題重複 {m.repeat_rate:>5.1f}‰  "
        f"行動欄 {m.action_mean:>4.0f} 字/幕"
        + (f"  連續空洞 {runs}" if runs else "")
    )


def format_report(
    book: Path,
    pov: str | None,
    plays: list[ArcPlayability],
    motifs: list[ArcMotif],
    findings: list[Finding],
    base: ArcMotif | None,
    detail: bool,
) -> str:
    lines = [
        f"## 幕綱層統計 {book.name}（{len(plays)} 個 arc；零 LLM、可覆算）",
        "",
        f"主角（`00-摘要.ai.md` 視角結構.POV）：{pov or '（讀不到——空洞／純內在幕一律報不適用，不猜）'}",
        "",
        "### 分 arc",
    ]
    for p, m in zip(plays, motifs):
        lines.append("- " + _play_line(p, m))
    if base:
        lines.append(f"- 基準：母題重複 {base.repeat_rate:.1f}‰　行動欄 {base.action_mean:.0f} 字/幕")

    lines += ["", "### 可疑點（絕對門檻：可演性）"]
    hits = []
    for p in plays:
        if p.hollow_share > HOLLOW_SHARE_CAP:
            hits.append(
                f"- [空洞幕比例] {p.arc}：{len(p.hollow_beats)}/{p.total}"
                f"＝{p.hollow_share:.0%}，超過 {HOLLOW_SHARE_CAP:.0%}"
                f"（幕 {'、'.join(str(b) for b in p.hollow_beats)}）"
            )
        for r in p.hollow_runs:
            hits.append(
                f"- [連續空洞幕] {p.arc}：幕{r[0]}–幕{r[-1]} 連續 {len(r)} 幕"
                f"皆為「主角獨處＋行動欄只剩主題陳述」"
            )
        if p.meta_beats:
            hits.append(
                f"- [分區衛生] {p.arc}：{len(p.meta_beats)} 幕的八欄出現元管理字樣"
                f"（幕 {'、'.join(str(b) for b in p.meta_beats)}）——設計理由屬檔尾設計註"
            )
    lines += hits or ["（無）"]

    lines += ["", "### 可疑點（相對本書前段：母題自我複製／行動欄膨脹）"]
    if base is None:
        lines.append(f"（arc 數不足，不談漂移——需要至少 {3} 個有內容的 arc 才有基準可比）")
    elif not findings:
        lines.append("（無）")
    else:
        for f in findings:
            lines.append(f"- [{f.metric}] {f.arc}：{f.detail}")

    if detail:
        lines += ["", "### 各 arc 最常重複的八欄片段（供人眼認出是哪個母題在迴圈）", ""]
        for m in motifs:
            hot = "　".join(f"{g}×{c}" for c, g in m.hot) or "（無 ≥4 次者）"
            lines.append(f"- {m.arc}：{hot}")

    lines += [
        "",
        "> 空洞幕＝**角色欄只剩主角一人 ∧ 行動欄命中禁止清單詞式**（`幕綱.schema.md`"
        "「八欄只寫故事事實」四類）。**兩個條件缺一不可**：一個人在場不是病，一個人在場"
        "而且沒有東西可拍才是——純內在幕單獨列出只當資訊（實測 arc01 的 2 幕獨處是健康的，"
        "見 `playability.py` 檔頭）。",
        "> 母題重複率與行動欄長度用**相對本書前段**的判準（同 `prose-metrics` 漂移），"
        "不設絕對門檻——絕對值是書/文類相依的。",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="幕綱層機械統計（零 LLM、可覆算）：幕的可演性（beat-test 測試9）"
        "＋分區衛生＋母題自我複製＋行動欄膨脹。"
        "取代『為了數這幾個數字而整批讀 arc 檔』——確定性的計數進程式，LLM 只做判斷"
        "（`共同約定.md` 八）。",
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument("--arc", default=None, help="只印這個 arc（統計與基準一律仍看全書）")
    ap.add_argument("--detail", action="store_true", help="連各 arc 最常重複的八欄片段一起印")
    args = ap.parse_args(argv)

    _force_utf8()
    try:
        arcs = load_book(args.book)
        pov = load_pov(args.book)
    except LayerMissing as e:
        print(_EMPTY_COVERAGE.format(reason=e))
        return EXIT_LAYER_MISSING
    except ScanError as e:
        print(f"掃描錯誤：{e}", file=sys.stderr)
        return EXIT_PROBLEMS
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return EXIT_PROBLEMS

    plays = [analyse(a, pov) for a in arcs]
    motifs = [measure(a, p.action_mean) for a, p in zip(arcs, plays)]
    findings, base = detect(motifs)

    if args.arc:
        keep = {args.arc}
        shown_plays = [p for p in plays if p.arc in keep]
        shown_motifs = [m for m in motifs if m.arc in keep]
        findings = [f for f in findings if f.arc in keep]
    else:
        shown_plays, shown_motifs = plays, motifs

    print(
        format_report(args.book, pov, shown_plays, shown_motifs, findings, base, args.detail),
        end="",
    )

    suspect = bool(findings) or any(
        p.hollow_share > HOLLOW_SHARE_CAP or p.hollow_runs or p.meta_beats
        for p in shown_plays
    )
    return EXIT_PROBLEMS if suspect else EXIT_CLEAN


CLEAN = "幕綱格式乾淨（幕號／前因／八欄／spine／分區）"


def _emit(fn, book: Path) -> int:
    """投影模式的共用出口（`--emit`）。**一律 exit 0**——它是投影不是閘門
    （同 `structure-project`／`readiness`）。要驗格式就跑不帶 `--emit` 的同一支指令。
    """
    try:
        report, stats = fn(book)
    except LayerMissing as e:
        print(_EMPTY_COVERAGE.format(reason=e))
        return EXIT_LAYER_MISSING
    except ScanError as e:
        print(f"掃描錯誤：{e}", file=sys.stderr)
        return EXIT_CLEAN  # 投影不擋路：讀不到就說讀不到，不改變呼叫者的 exit code
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return EXIT_CLEAN
    # 覆蓋率行由投影自己嵌在表格與殘留節之間（同 `structure-project` 的第四節），
    # 這裡不再印一次——`stats` 留給測試斷言用。
    print(report, end="")
    _ = stats
    return EXIT_CLEAN


def lint_main(argv: list[str] | None = None) -> int:
    """格式閘門。輸出契約照抄 `fact_projection/cli.py:_print_lint`：

    覆蓋率行＋資訊＋提示走 **stdout**（乾淨時也印），問題清單走 **stderr**，exit 0/1。
    """
    ap = argparse.ArgumentParser(
        description="幕綱格式閘門（零 LLM、可覆算）：幕號唯一與號段、`前因 [[幕NNN]]` "
        "目標存在、八欄完整、`_順序.md` 的 spine 涵蓋所有 arc（舊落點 `_index.md` "
        "2026-07-28 廢除，只報殘留）、分區、伏筆近似名、設計註目的地。"
        "守的是「人破結構」那一側（`設計原則.md` B1），與 `derived-sync validate` 同類；"
        "內容好壞交 `beat-test`，漂移統計交 `beat-metrics`。",
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument(
        "--emit",
        action="store_true",
        help="（投影模式）印出這一軸的 rollup 視圖＋覆蓋率＋舊 rollup 殘留偵測，**不驗格式、一律 exit 0**（功能 12 抉擇 4 C：誰重算誰印）",
    )
    args = ap.parse_args(argv)

    _force_utf8()
    if args.emit:
        return _emit(emit_beats, args.book)
    try:
        problems, stats = lint_report(args.book)
    except LayerMissing as e:
        # **exit 2 ＝跑不動，而且照樣印覆蓋率行**（抉擇 6 A）：
        # 「我掃了 0 支」本身就是最有用的那一筆訊息（E2）。
        print(_EMPTY_COVERAGE.format(reason=e))
        return EXIT_LAYER_MISSING
    except ScanError as e:
        print(f"掃描錯誤：{e}", file=sys.stderr)
        return EXIT_PROBLEMS
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return EXIT_PROBLEMS

    print(stats.render())
    for n in stats.notes:
        print(f"（資訊）{n}")
    for h in stats.hints:
        print(f"（提示）{h}")
    if not problems:
        print(CLEAN)
        return EXIT_CLEAN
    print(f"發現 {len(problems)} 個問題：")
    for p in problems:
        print(f"  [x] {p}")
    return EXIT_PROBLEMS


CH_CLEAN = "正文層格式乾淨（幕錨點／對應幕／front-matter／章序視圖）"


def ch_lint_main(argv: list[str] | None = None) -> int:
    """正文層格式閘門。輸出契約與 `lint_main` 完全相同（同套件、兩個指令）。

    **為什麼不併成一個 `beat-lint`**（作者拍板抉擇 1 B 之下的實作選擇）：
    `write`／`revise` 落檔後要驗的是正文層，把幕綱那邊 15 條與它無關的問題一起噴出來
    只會讓人學會忽略輸出。先例是 `object-lint`——它跑 `fact-lint` 的同一組檢查、
    只印物件檔那幾類。**解析層仍然只有一份**（`structure.parse_book` 的幕號 registry），
    那才是抉擇 1 B 要的東西。
    """
    ap = argparse.ArgumentParser(
        description="正文層格式閘門（零 LLM、可覆算）：幕錨點的幕號存在／章內單調／"
        "一幕不跨章／過渡錨點兩端／人性寫法正規化候選、`對應幕` ≡ 正文錨點集合、"
        "章衍生檔 front-matter 六鍵、`風格` 欄指向的檔存在（舊 `_index.ai.md` "
        "2026-07-28 廢除，只報殘留；章序改跑 `--emit`）。"
        "守的是「人破結構」那一側（`設計原則.md` B1），與 `beat-lint`／"
        "`derived-sync validate` 同類；內容好壞交 `write-test`，漂移統計交 `prose-metrics`。",
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 chapters/）")
    ap.add_argument(
        "--emit",
        action="store_true",
        help="（投影模式）印出這一軸的 rollup 視圖＋覆蓋率＋舊 rollup 殘留偵測，**不驗格式、一律 exit 0**（功能 12 抉擇 4 C：誰重算誰印）",
    )
    args = ap.parse_args(argv)

    _force_utf8()
    if args.emit:
        return _emit(emit_chapters, args.book)
    try:
        problems, stats = ch_lint_report(args.book)
    except LayerMissing as e:
        # **exit 2 ＝跑不動，而且照樣印覆蓋率行**（抉擇 6 A）：
        # 「我掃了 0 支」本身就是最有用的那一筆訊息（E2）。
        print(_EMPTY_COVERAGE.format(reason=e))
        return EXIT_LAYER_MISSING
    except ScanError as e:
        print(f"掃描錯誤：{e}", file=sys.stderr)
        return EXIT_PROBLEMS
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return EXIT_PROBLEMS

    print(stats.render())
    for n in stats.notes:
        print(f"（資訊）{n}")
    for h in stats.hints:
        print(f"（提示）{h}")
    if not problems:
        print(CH_CLEAN)
        return EXIT_CLEAN
    print(f"發現 {len(problems)} 個問題：")
    for p in problems:
        print(f"  [x] {p}")
    return EXIT_PROBLEMS


OUTLINE_CLEAN = (
    "大綱層格式乾淨（節枚舉／檔頭狀態／引用／伏筆意圖表／卷級方向／索引視圖／選用結構公式）"
)


def outline_lint_main(argv: list[str] | None = None) -> int:
    """大綱層格式閘門。輸出契約與 `lint_main`／`ch_lint_main` 完全相同。

    **第三個指令，同一份解析層**（作者拍板抉擇 1 B）：第 4 項要的幕號 registry 就是
    `structure.parse_book()`、第 5 項要的伏筆 regex `beat-lint` 已經在用。另開套件
    ＝新增第 7 份幕號集合實作。套件名（`beat_metrics`）因此更不準了，那是可接受的
    代價——**零複製是選它的唯一理由**；要重新命名／拆分交功能 14，三個指令一起處理。
    """
    ap = argparse.ArgumentParser(
        description="大綱層格式閘門（零 LLM、可覆算）：節枚舉、檔頭狀態二選一、"
        "`本 arc 伏筆狀態` 的三欄意圖表、卷級方向的卷 token 唯一與指路紀律、"
        "`幕NNN`／`chNNNN`／`arcNN` 引用不懸空、`[[伏筆:x]]` 命中 registry、"
        "`結局與題旨` 與 `本段收束與鉤子` 的形狀（舊 `_index.md` 2026-07-28 廢除，"
        "只報殘留；arc 清單改跑 `--emit`）、"
        "檔內路徑的目的地存在、**`選用結構公式` 的公式名命中 `結構公式.md` registry "
        "且 α 不記沿革**。守的是「人破結構」那一側（`設計原則.md` B1），"
        "與 `beat-lint`／`ch-lint` 同類；內容好壞交 `outline-test`。",
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument(
        "--emit",
        action="store_true",
        help="（投影模式）印出這一軸的 rollup 視圖＋覆蓋率＋舊 rollup 殘留偵測，**不驗格式、一律 exit 0**（功能 12 抉擇 4 C：誰重算誰印）",
    )
    args = ap.parse_args(argv)

    _force_utf8()
    if args.emit:
        return _emit(emit_outline, args.book)
    try:
        problems, stats = outline_lint_report(args.book)
    except LayerMissing as e:
        # **exit 2 ＝跑不動，而且照樣印覆蓋率行**（抉擇 6 A）：
        # 「我掃了 0 支」本身就是最有用的那一筆訊息（E2）。
        print(_EMPTY_COVERAGE.format(reason=e))
        return EXIT_LAYER_MISSING
    except ScanError as e:
        print(f"掃描錯誤：{e}", file=sys.stderr)
        return EXIT_PROBLEMS
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return EXIT_PROBLEMS

    print(stats.render())
    for n in stats.notes:
        print(f"（資訊）{n}")
    for h in stats.hints:
        print(f"（提示）{h}")
    if not problems:
        print(OUTLINE_CLEAN)
        return EXIT_CLEAN
    print(f"發現 {len(problems)} 個問題：")
    for p in problems:
        print(f"  [x] {p}")
    return EXIT_PROBLEMS


def structure_project_main(argv: list[str] | None = None) -> int:
    """結構軸投影。**它不是閘門**——一律 exit 0，可疑點交 `outline-test`／`beat-test` 判。

    **第四個指令，同一份解析層**（作者拍板抉擇 3 A）：幕綱八欄的 `結構階段` 在
    `scan.scan_arc()`、幕號 registry 與 spine 定序在 `scan.load_book()`、大綱檔與節內容在
    `outline.load_files()`——**兩個輸入都已經在這個套件裡解析，零複製**。另開套件＝新增
    第 8 份幕號集合實作（同 09 抉擇 1 B 對 `outline-lint` 的理由，逐字相同）。

    它取代已廢除的 `story/參照/結構.ai.md`：那支檔的對應表實測 108/108 幕可從幕綱重算，
    而它宣稱「無單一源檔可 hash」——`設計原則.md` A6 那個空訊號的唯一支柱，實測撐不住。
    """
    ap = argparse.ArgumentParser(
        description="結構軸投影（零 LLM、可覆算）：大綱宣告的選用公式、幕綱 `結構階段` 欄"
        "投影出的「階段 ↔ 幕」對應表、對照 `技巧知識庫/結構公式.md` registry 算出的"
        "「缺哪個必要階段／階段序非遞增」，以及舊 `story/參照/結構.{md,ai.md}` 的殘留偵測。"
        "**投影不是閘門**（一律 exit 0，不做 pass/fail）：格式那一側由 `outline-lint` "
        "第 12 項守，內容好壞交 `outline-test` 測試4／`beat-test` 測試3。",
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument("--arc", default=None, help="對應表只印這個 arc（覆蓋率仍看全書）")
    args = ap.parse_args(argv)

    _force_utf8()
    try:
        report, _stats = project(args.book, args.arc)
    except LayerMissing as e:
        # **投影也要能說「這本書還沒有這一層」**，而且照樣印覆蓋率（抉擇 6 A）。
        print(_EMPTY_COVERAGE.format(reason=e))
        return EXIT_LAYER_MISSING
    except ScanError as e:
        print(f"掃描錯誤：{e}", file=sys.stderr)
        return EXIT_PROBLEMS
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return EXIT_PROBLEMS

    print(report, end="")
    return EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
