from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .char_lint import lint_book as char_lint_book
from .core import check_book, content_hash, source_digest_for_derived, stamp
from .sentinel import run as run_sentinel
from .style_lint import lint_book as style_lint_book
from .validate import validate_report
from .world_lint import lint_book as world_lint_book

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


def _cmd_world_lint(args: argparse.Namespace) -> int:
    """世界觀軸的格式閘門。與 `validate` 分開跑、分開計。

    `validate` 問「每支 `.ai.md` 的共通形狀對不對」；這支問「世界觀那幾欄的**語意**
    對不對」——`主題` ≡ 檔名、伏筆名在 registry 裡、rollup 的兩欄視圖 ≡ 資料夾、
    背景維度是封閉七維、幕綱的檔名引用不懸空。
    """
    problems, stats = world_lint_book(args.book)
    print(stats.render())
    if not problems:
        print("世界觀軸格式合規。")
        return 0
    for p in problems:
        rel = p.path.relative_to(args.book) if p.path.is_relative_to(args.book) else p.path
        print(f"[x] {rel}  {p.detail}")
        print(f"       {p.hint}")
    print(f"\n合計 {len(problems)} 個格式問題。", file=sys.stderr)
    return 1


def _cmd_char_lint(args: argparse.Namespace) -> int:
    """角色軸的格式閘門。與 `validate`／`world-lint` 分開跑、分開計。

    `validate` 問「每支 `.ai.md` 的共通形狀對不對」；這支問角色軸專屬的四件事——
    **每支源有沒有衍生檔**（從源側掃，`check` 在定義上看不到這一格）、**必填節
    是不是佔位**（`check` 對空殼檔報 fresh 且報得沒錯）、留下的四個 front-matter
    欄的語意、rollup 視圖 ≡ 各檔 front-matter。
    """
    problems, stats = char_lint_book(args.book)
    print(stats.render())
    if not problems:
        print("角色軸格式合規。")
        return 0
    for p in problems:
        rel = p.path.relative_to(args.book) if p.path.is_relative_to(args.book) else p.path
        print(f"[x] {rel}  {p.detail}")
        print(f"       {p.hint}")
    print(f"\n合計 {len(problems)} 個格式問題。", file=sys.stderr)
    return 1


def _cmd_style_lint(args: argparse.Namespace) -> int:
    """風格軸的格式閘門。與 `validate`／`world-lint`／`char-lint` 分開跑、分開計。

    `validate` 問「每支 `.ai.md` 的共通形狀對不對」；這支問風格軸專屬的一件事——
    **那五個 front-matter 欄裡的值，能不能真的被拿去核對**。它們的消費者是 LLM
    不是程式（`write`／`write-test`／`revise` 逐欄指名），而 LLM 讀壞格式會安靜地
    讀錯（`設計原則.md` A4 2026-07-27 改寫後的那一句）。

    **禁用詞的正文掃描是提示、不是判定**：命中不計入問題數、不影響 exit code
    ——「掃到即候選命中」是 schema 的原話，複判交 `write-test`。
    """
    problems, stats = style_lint_book(args.book)
    print(stats.render())
    if stats.notes:
        print("\n--- 禁用詞候選（提示，交 `write-test` 複判；不計入問題數）---")
        for n in stats.notes:
            print(f"[?]    {n}")
    if not problems:
        print("風格軸格式合規。")
        return 0
    for p in problems:
        rel = p.path.relative_to(args.book) if p.path.is_relative_to(args.book) else p.path
        print(f"[x] {rel}  {p.detail}")
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

    p_world = sub.add_parser(
        "world-lint",
        help="驗世界觀軸（front-matter 欄語意＋rollup 視圖＋伏筆歸一＋檔名引用）",
    )
    p_world.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    p_world.set_defaults(func=_cmd_world_lint)

    p_char = sub.add_parser(
        "char-lint",
        help="驗角色軸（源側存在性＋必填節不得是佔位＋front-matter 欄語意＋rollup 視圖）",
    )
    p_char.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    p_char.set_defaults(func=_cmd_char_lint)

    p_style = sub.add_parser(
        "style-lint",
        help="驗風格軸（五個 front-matter 欄的值可不可核對＋禁用詞正文掃描）",
    )
    p_style.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    p_style.set_defaults(func=_cmd_style_lint)

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


def world_lint_main(argv: list[str] | None = None) -> int:
    """`world-lint` 的獨立入口（同套件、自己一個指令）。

    與 `derived-sync world-lint` 完全等價。分成獨立指令的先例：`object-lint` 是
    `fact-lint` 的聚焦入口、`ch-lint` 與 `beat-lint` 同套件——**新增一個要記得跑的
    閘門，就是新增一個會被忘記的觸發時機**，所以它掛在寫它的那支 skill
    （`worldbuild`／`develop`）的落檔步驟上，指令名要短到不必查。
    """
    ap = argparse.ArgumentParser(
        description="世界觀軸格式閘門：驗 <主題>.ai.md 的 front-matter 欄語意"
        "（`主題` ≡ 檔名、已廢除的欄、伏筆名在 registry 裡）、"
        "`_總覽.ai.md` 的核心規則索引 ≡ 資料夾與背景維度封閉七維、"
        "以及幕綱裡的檔名引用不懸空。零 LLM、可覆算。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    _force_utf8()
    args = ap.parse_args(argv)
    try:
        return _cmd_world_lint(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 1


def char_lint_main(argv: list[str] | None = None) -> int:
    """`char-lint` 的獨立入口（同套件、自己一個指令）。

    與 `derived-sync char-lint` 完全等價。理由同 `world_lint_main`：**新增一個
    要記得跑的閘門，就是新增一個會被忘記的觸發時機**，所以它掛在寫它的那支 skill
    （`character`／`develop`／`organize`／`expand`）的落檔步驟上，指令名要短到
    不必查。
    """
    ap = argparse.ArgumentParser(
        description="角色軸格式閘門：**每支源檔都有衍生檔**（從源側掃，"
        "`check` 在定義上看不到這一格）、必填節不得是佔位、"
        "`<名>.ai.md` 的 front-matter 欄語意（已廢除的欄／`定位`·`暫定` 枚舉／"
        "`所屬arc` 可解析／`伏筆` 命中既有 registry）、"
        "`_index.ai.md` 的角色清單 ≡ 資料夾與各檔 front-matter、"
        "單檔與目錄形態不得並存、幕綱角色欄的未知 token。零 LLM、可覆算。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    _force_utf8()
    args = ap.parse_args(argv)
    try:
        return _cmd_char_lint(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 1


def style_lint_main(argv: list[str] | None = None) -> int:
    """`style-lint` 的獨立入口（同套件、自己一個指令）。

    與 `derived-sync style-lint` 完全等價。理由同 `world_lint_main`／`char_lint_main`：
    **新增一個要記得跑的閘門，就是新增一個會被忘記的觸發時機**——而這一支的觸發
    時機是硬的：`develop` 落檔前**必跑**（抉擇 1 B），`可用句式` 那三小條有命中就
    停下回問作者、不得直接封章。指令名要短到不必查。
    """
    ap = argparse.ArgumentParser(
        description="風格軸格式閘門：`風格.ai.md` 的五個 front-matter 欄"
        "（`禁用詞表` entry 可字面掃／`稱謂系統` 形狀／**`可用句式` 的顆粒度 token"
        "＋阿拉伯數字＋不得全落最粗一級**／`語域` 半形括號／`基調參照` ≡ "
        "`00-摘要.ai.md` 的 `基調`），另順帶掃正文的字面禁用詞"
        "（只印覆蓋率與候選，不做 pass/fail）。零 LLM、可覆算。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑")
    _force_utf8()
    args = ap.parse_args(argv)
    try:
        return _cmd_style_lint(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
