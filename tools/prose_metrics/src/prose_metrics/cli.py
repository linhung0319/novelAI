from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .density import Density, measure as measure_density, render as render_density
from .drift import GroupStat, detect, summarize
from .exposition import (
    Candidate,
    ChapterExposition,
    ExpoStat,
    detect_exposition,
    scan_chapter,
    summarize_exposition,
)
from .metrics import (
    Chapter,
    MetricsError,
    chapter_metrics,
    load_book_chapters,
    load_plain_chapters,
    load_vocab,
)
from .rhythm import (
    MIN_ECHO_SAMPLE,
    RhythmStat,
    combine,
    detect_rhythm,
    scan_rhythm,
    summarize_rhythm,
)


def _force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def _stat_line(s: GroupStat) -> str:
    return (
        f"{s.group:<26} {s.chapters:>3} 章  "
        f"{s.chars:>7.0f} 字/章  "
        f"{s.quote_density:>5.1f} 引號/千字  "
        f"{s.cast:>4.1f} 人/章  "
        f"獨白章 {s.solo_share:>4.0%}"
    )


def in_range(label: str, span: tuple[str, str] | None) -> bool:
    return span is None or span[0] <= label <= span[1]


def _rhythm_line(s: RhythmStat) -> str:
    # 回聲**連分母一起印**：佔比的分母是「≤12字非對白段」，短段少的書分母極小，
    # 樣本不足時的 0.0% 是「沒得測」不是「測出零」。只印百分比會讓人把前者讀成後者
    # （實測踩過：13 個短段的 0.0% 被當成合格）。`*`＝分母 <20，不列入判讀。
    echo = f"{s.echo_share:.1%}({s.echoes}/{s.short_paras})" if s.short_paras else "—"
    thin = "*" if 0 < s.short_paras < MIN_ECHO_SAMPLE else " "
    return (
        f"{s.group:<26} {s.chapters:>3} 章  "
        f"{s.dash_density:>5.2f} 破折號  "
        f"{s.jolt_index:>5.2f} 顛簸  "
        f"句/段 {s.sent_per_para:>4.2f}  "
        f"回聲 {echo:>13}{thin}"
        f"｜句長中位 {s.sent_median:>4.0f}  "
        f"≥40字句佔 {s.long_sent_share:>4.0%}  "
        f"逗號:句號 {s.comma_period:>4.2f}  "
        f"分句均長 {s.clause_mean:>4.1f}"
    )


def _corpus_lines(book: RhythmStat, corpus: RhythmStat, name: str) -> list[str]:
    """語料對照。**只印數字，不引原文片段。**"""
    rows = [
        ("破折號/千漢字", book.dash_density, corpus.dash_density, "{:.2f}"),
        ("顛簸/千漢字", book.jolt_index, corpus.jolt_index, "{:.2f}"),
        ("句/段", book.sent_per_para, corpus.sent_per_para, "{:.2f}"),
        ("回聲佔比", book.echo_share * 100, corpus.echo_share * 100, "{:.1f}%"),
        ("句長中位數", book.sent_median, corpus.sent_median, "{:.0f}"),
        ("≥40字句字數佔比", book.long_sent_share * 100, corpus.long_sent_share * 100, "{:.1f}%"),
        ("逗號:句號", book.comma_period, corpus.comma_period, "{:.2f}"),
        ("分句平均長度", book.clause_mean, corpus.clause_mean, "{:.1f}"),
    ]
    lines = [
        f"### 語料對照（{name}；{corpus.chapters} 章）",
        "",
        "> 用途：`可用句式` 宣告的是**讀感**，這張表給的是它由哪一級標點承擔。"
        "宣告「短句為主」而語料的句長中位是它的兩倍，就是宣告寫錯了（診斷03 R12-a）。"
        "前四項有絕對門檻（跨文類收斂），後四項是文類自由、只供對照，別當門檻用。",
        "",
        "> **後四項正是這張表存在的理由**：「該長的地方要長」**沒有普世判準**——長句"
        "佔比六本從 17% 到 62% 全是好書，句長離散度兩組完全重疊（見 `rhythm.py` 檔頭"
        "「已測過但不成立」）。它只能對著本書的參照語料或 `可用句式` 宣告判，"
        "所以要看這幾項就得跑 `--corpus`。",
        "",
        "| 指標 | 本書 | 語料 | 倍數 |",
        "|---|---|---|---|",
    ]
    for label, b, c, fmt in rows:
        ratio = f"{b / c:.1f}×" if c else "—"
        lines.append(f"| {label} | {fmt.format(b)} | {fmt.format(c)} | {ratio} |")
    return lines


def _candidate_lines(
    header: str, cands: list[Candidate], note: str
) -> list[str]:
    lines = [f"#### {header}", note]
    if not cands:
        return lines + ["（無）"]
    for c in cands:
        lines.append(f"- {c.label} 第{c.index + 1}段 [{'／'.join(c.kinds)}] {c.text}")
    return lines


def format_report(
    title: str,
    chapters: list[Chapter],
    rows,
    stats,
    findings,
    base,
    per_chapter: bool,
    expo_stats: list[ExpoStat],
    expo_findings,
    expo_base: float | None,
    expo_rows: list[ChapterExposition],
    expo_list: bool,
    span: tuple[str, str] | None,
    rhythm_stats: list[RhythmStat],
    rhythm_findings,
    corpus: tuple[RhythmStat, RhythmStat, str] | None = None,
    density: Density | None = None,
) -> str:
    lines = [f"## {title}（{len(chapters)} 章；零 LLM、可覆算）", ""]
    if per_chapter:
        lines.append("### 逐章")
        for m in rows:
            flag = "  ←獨白章" if m.solo else ""
            lines.append(
                f"- {m.label:<16} {m.group:<10} {m.chars:>6} 字  "
                f"{m.quotes:>3} 引號  {m.cast:>2} 人{flag}"
            )
        lines.append("")

    lines.append("### 分段")
    for s in stats:
        lines.append("- " + _stat_line(s))
    if base:
        lines += ["", "- " + _stat_line(base)]

    # 章密度對照緊接在「分段」之後：它與上一節同屬篇幅這條軸，只是判準不同
    # （上面相對本書前段、這裡對照 schema 的參考體例）。**不進可疑點**。
    if density is not None:
        lines += [""] + render_density(density)

    lines += ["", "### 解說段（R4·段落級）"]
    for e in expo_stats:
        lines.append(
            f"- {e.group:<26} {e.chapters:>3} 章  "
            f"{e.paragraph_hits:>3} 段級候選  {e.density:>5.2f} 候選/千字  "
            f"（句級 {e.sentence_hits}）"
        )
    if expo_base is not None:
        lines.append(f"- 基準密度 {expo_base:.2f} 候選/千字")

    lines += ["", "### 行文節奏（P8·每千漢字）"]
    for r in rhythm_stats:
        lines.append("- " + _rhythm_line(r))
    lines.append(
        "> 門檻 破折號 ≤0.5／顛簸 ≤0.3／句/段 ≤1.35／回聲 ≤1.5%"
        "（六本 known-good 語料 max 0.38／0.23／1.25／0.6%）。"
        "回聲括號內是分子/分母（分母＝≤12字非對白段）；"
        "`*`＝分母不足 20，佔比樣本不足、不報也**不算過關**。"
        "後四項是輔助量、**無門檻**（長句佔比是文類自由的量，六本 17–62% 全是好書），"
        "供對照 `可用句式` 宣告用。"
    )

    lines += ["", "### 漂移可疑點（相對本書前段）"]
    all_findings = list(findings) + list(expo_findings)
    if base is None:
        lines.append("（分段數不足，不談漂移——需要至少 3 段才有基準可比）")
    elif not all_findings:
        lines.append("（無）")
    else:
        for f in all_findings:
            lines.append(f"- [{f.metric}] {f.group}：{f.detail}")

    # 與上一節分開印：判準基礎不同。上面相對本書前段（篇幅／對白密度是文類相依的），
    # 這裡是絕對門檻（三項簽名跨文類收斂，見 rhythm.py 檔頭）。兩套並存，互不取代。
    lines += ["", "### 行文節奏可疑點（絕對門檻）"]
    if not rhythm_findings:
        lines.append("（無）")
    else:
        for f in rhythm_findings:
            lines.append(f"- [{f.metric}] {f.group}：{f.detail}")

    if corpus is not None:
        lines += [""] + _corpus_lines(*corpus)

    if expo_list:
        scope = f"（範圍 {span[0]}–{span[1]}）" if span else "（全書）"
        lines += ["", f"### 解說段候選清單{scope}", ""]
        lines += _candidate_lines(
            "段級（主訊號）",
            [c for r in expo_rows for c in r.paragraph if in_range(c.label, span)],
            "> 整段在解說剛才那一手的用意，或把推理結算成條列。**候選非判定**，交 LLM 複核。",
        )
        lines += [""]
        lines += _candidate_lines(
            "句級反射式收尾（低產出）",
            [c for r in expo_rows for c in r.sentence if in_range(c.label, span)],
            "> 實測對本病徵**反相關**（原著 0.002／千字 > 生成 0.000）。**別當主訊號**，見 exposition.py 檔頭。",
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="正文結構統計＋跨 arc 漂移偵測（零 LLM、可覆算）。"
        "判準是相對的——拿這本書自己的前段當基準，故不內建任何文類詞表。"
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--book", type=Path, help="書資料夾（含 chapters/ 與 story/）")
    src.add_argument(
        "--plain-dir", type=Path, help="對照語料目錄（子目錄即分組，如原著的 卷一/卷二）"
    )
    ap.add_argument(
        "--vocab-from", type=Path, default=None, help="借用某本書的角色詞彙表（供對照語料用）"
    )
    ap.add_argument(
        "--corpus",
        type=Path,
        default=None,
        metavar="目錄",
        help="拿一份參照語料對照行文節奏（任何含 .txt/.md 的目錄；只輸出數字，不引原文）",
    )
    ap.add_argument("--per-chapter", action="store_true", help="連逐章明細一起印")
    ap.add_argument(
        "--exposition-list",
        action="store_true",
        help="連解說段候選的段落全文一起印（供 write-test 測試8 複核）",
    )
    ap.add_argument(
        "--range",
        dest="span",
        default=None,
        metavar="chNNNN-chNNNN",
        help="只印這個章範圍的候選清單（統計與漂移一律仍看全書）",
    )
    args = ap.parse_args(argv)

    _force_utf8()
    span: tuple[str, str] | None = None
    if args.span:
        parts = args.span.split("-")
        if len(parts) != 2 or not all(p.strip() for p in parts):
            print("--range 格式為 chNNNN-chNNNN", file=sys.stderr)
            return 1
        span = (parts[0].strip(), parts[1].strip())
    try:
        if args.book:
            chapters = load_book_chapters(args.book)
            vocab = load_vocab(args.book)
            title = f"{args.book.name} 正文結構"
            plain = False
        else:
            chapters = load_plain_chapters(args.plain_dir)
            vocab = load_vocab(args.vocab_from) if args.vocab_from else []
            title = f"{args.plain_dir.name} 正文結構（對照語料）"
            plain = True
        rows = [chapter_metrics(c, vocab) for c in chapters]
        # 對照語料沒有 `story/00-摘要.ai.md`，也沒有「這本書宣告了什麼」可對——
        # 章密度對照只對書印。
        density = measure_density(rows, args.book) if args.book else None
        expo_rows = [scan_chapter(c) for c in chapters]
        rhythm_rows = [scan_rhythm(c, drop_title=plain) for c in chapters]
        corpus = None
        if args.corpus:
            corpus_rows = [
                scan_rhythm(c, drop_title=True) for c in load_plain_chapters(args.corpus)
            ]
            corpus = (
                combine(rhythm_rows, "本書"),
                combine(corpus_rows, "語料"),
                args.corpus.name,
            )
    except MetricsError as e:
        print(f"統計錯誤：{e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return 1

    # 借來的詞彙表屬於**另一套語料**：拿 A 書的角色名去量 B 書，覆蓋率天生不足，
    # 「在場角色／獨白章」會系統性偏低。那是誤用，不是漂移，故整組停用。
    borrowed = args.vocab_from is not None
    if not vocab:
        print("（注意：無角色詞彙表，「在場角色／獨白章」兩項已停用）", file=sys.stderr)
    elif borrowed:
        print(
            "（注意：詞彙表借自其他書，「在場角色／獨白章」兩項已停用——"
            "跨語料借用時覆蓋率不足，數字僅供參考）",
            file=sys.stderr,
        )

    stats = summarize(rows)
    findings, base = detect(stats, cast_metrics=not borrowed)
    expo_stats = summarize_exposition(expo_rows)
    expo_findings, expo_base = detect_exposition(expo_stats)
    rhythm_stats = summarize_rhythm(rhythm_rows)
    rhythm_findings = detect_rhythm(rhythm_stats)
    print(
        format_report(
            title,
            chapters,
            rows,
            stats,
            findings,
            base,
            args.per_chapter,
            expo_stats,
            expo_findings,
            expo_base,
            expo_rows,
            args.exposition_list,
            span,
            rhythm_stats,
            rhythm_findings,
            corpus,
            density,
        ),
        end="",
    )
    return 1 if findings or expo_findings or rhythm_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
