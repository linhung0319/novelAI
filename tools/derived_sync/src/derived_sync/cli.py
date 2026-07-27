from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import check_book, content_hash, source_digest_for_derived, stamp
from .sentinel import run as run_sentinel
from .validate import validate_report

_MARK = {
    "fresh": "[ok]  ",
    "stale": "[STALE]",
    "unstamped": "[?]   ",
    "orphan": "[ORPH]",
    "declarative": "[decl]",  # 宣告式綜合檔：不走 hash，不計入需處理數
}


def _force_utf8() -> None:
    """Windows 主控台常是 cp950，會在印中文路徑時炸。強制 UTF-8 輸出。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def _print_sentinel(book: Path) -> None:
    """成長哨兵：advisory，**不計入需處理數、不影響 exit code**。

    量的是**「必須整檔讀的東西有多大」**（`共同約定.md` 零），不是「檔多大」——
    有投影工具可切片的 append log（事實流／裁決流）不受規範。四項：設計理由滲進
    幕綱、源檔該拆、衍生檔塞了不屬於它的東西、狀態格被當日誌。

    這不是「新鮮度」——兩者混在一起會讓 check 的契約變模糊，故分開印、分開計。
    """
    findings = run_sentinel(book)
    if not findings:
        return
    print("\n--- 成長哨兵（建議值，非門檻）---")
    for f in findings:
        rel = f.path.relative_to(book) if f.path.is_relative_to(book) else f.path
        print(f"[!]    {f.kind:<6} {rel}  {f.detail}")
        print(f"           {f.hint}")


def _cmd_check(args: argparse.Namespace) -> int:
    results = check_book(args.book)
    if not results:
        print("（此書無 .ai.md 衍生檔）")
        _print_sentinel(args.book)
        return 0
    problems = 0
    for r in results:
        rel = r.derived.relative_to(args.book)
        print(f"{_MARK.get(r.status, '?')} {r.status:<9} {rel}  ← {r.source}")
        if r.status in ("stale", "unstamped", "orphan"):
            problems += 1
    print(f"\n合計 {len(results)} 個衍生檔，{problems} 個需處理。", file=sys.stderr)
    if not args.no_sentinel:
        _print_sentinel(args.book)
    return 1 if problems else 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """格式閘門：`.ai.md` 宣稱保證格式，這裡是唯一在守那條保證的東西。

    與新鮮度分開跑、分開計——`check` 問「內容過期沒」，`validate` 問「形狀對不對」。
    """
    problems, stats = validate_report(args.book)
    print(stats.render())
    if not problems:
        print("所有 .ai.md 格式合規。")
        return 0
    for p in problems:
        rel = p.path.relative_to(args.book) if p.path.is_relative_to(args.book) else p.path
        # 整本聚合的問題（裁決 blockquote）path 就是書本身
        label = "（全書聚合）" if str(rel) == "." else str(rel)
        print(f"[x] {label}  {p.detail}")
        print(f"       {p.hint}")
    print(f"\n合計 {len(problems)} 個格式問題。", file=sys.stderr)
    return 1


def _cmd_stamp(args: argparse.Namespace) -> int:
    digest = stamp(args.derived, on=args.date)
    print(f"已封章 {args.derived.name}：generated-from={digest}")
    return 0


def _cmd_hash(args: argparse.Namespace) -> int:
    if args.source.name.endswith(".ai.md"):
        digest, desc = source_digest_for_derived(args.source)
        print(f"{digest}  （{args.source.name} 的源 digest：{desc}）")
    else:
        print(content_hash(args.source.read_text(encoding="utf-8")))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="源→衍生 過期偵測：比對 .ai.md 的 generated-from 與源檔正規化 hash。"
        "零 LLM、可覆算；重生內容仍由對應 skill（worldbuild/character/write…）負責。"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="掃一本書，列出所有衍生檔的新鮮度＋成長哨兵")
    p_check.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    p_check.add_argument(
        "--no-sentinel", action="store_true", help="不跑成長哨兵，只看新鮮度"
    )
    p_check.set_defaults(func=_cmd_check)

    p_validate = sub.add_parser(
        "validate", help="驗所有 .ai.md 的格式（front-matter 必填鍵＋節枚舉）"
    )
    p_validate.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    p_validate.set_defaults(func=_cmd_validate)

    p_stamp = sub.add_parser("stamp", help="重生某 .ai.md 後，把源 hash 封回其 front-matter")
    p_stamp.add_argument("derived", type=Path, help="欲封章的 .ai.md 路徑")
    p_stamp.add_argument("--date", default=None, help="generated-at 日期（預設今天）")
    p_stamp.set_defaults(func=_cmd_stamp)

    p_hash = sub.add_parser("hash", help="印出源檔的正規化 hash（.ai.md 則印其源 digest）")
    p_hash.add_argument("source", type=Path, help="源檔或 .ai.md 路徑")
    p_hash.set_defaults(func=_cmd_hash)

    _force_utf8()
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
