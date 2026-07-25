from __future__ import annotations

import argparse
import sys
from pathlib import Path

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

    lines += ["", "### 解說段（R4·段落級）"]
    for e in expo_stats:
        lines.append(
            f"- {e.group:<26} {e.chapters:>3} 章  "
            f"{e.paragraph_hits:>3} 段級候選  {e.density:>5.2f} 候選/千字  "
            f"（句級 {e.sentence_hits}）"
        )
    if expo_base is not None:
        lines.append(f"- 基準密度 {expo_base:.2f} 候選/千字")

    lines += ["", "### 漂移可疑點"]
    all_findings = list(findings) + list(expo_findings)
    if base is None:
        lines.append("（分段數不足，不談漂移——需要至少 3 段才有基準可比）")
    elif not all_findings:
        lines.append("（無）")
    else:
        for f in all_findings:
            lines.append(f"- [{f.metric}] {f.group}：{f.detail}")

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
        else:
            chapters = load_plain_chapters(args.plain_dir)
            vocab = load_vocab(args.vocab_from) if args.vocab_from else []
            title = f"{args.plain_dir.name} 正文結構（對照語料）"
        rows = [chapter_metrics(c, vocab) for c in chapters]
        expo_rows = [scan_chapter(c) for c in chapters]
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
        ),
        end="",
    )
    return 1 if findings or expo_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
