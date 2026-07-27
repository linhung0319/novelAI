from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parse import (
    STATUSES,
    TARGET_ALL,
    Decision,
    ParseError,
    Pending,
    parse_decisions,
    parse_pending,
    parse_spine,
    select,
    select_pending,
)

# 2026-07-27（功能 04）**`.co.md` 這個檔類廢除**，裁決流改叫 `裁決流.md`。
# 依 `設計原則.md` A4：檔的第二個位元（程式會不會解析它）由**有沒有檢查器**
# 承擔，不由副檔名承擔。補上 `decision-lint` 之後，裁決流與幕綱、物件檔同格
# （可解析＋不被覆蓋＋有 lint），不需要獨立字位。
# 舊名 `裁決流.co.md` 保留相容——既有書不必為改名動書內檔。
STREAM_NAMES = ("裁決流.md", "裁決流.co.md")
STREAM_NAME = STREAM_NAMES[0]
PENDING_NAME = "待裁決.md"


def _force_utf8() -> None:
    """書內容是中文，主控台編碼（如 Windows cp950）不該決定工具能不能輸出。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def resolve_stream(book: Path) -> Path:
    ref = book / "story" / "參照"
    for name in STREAM_NAMES:
        p = ref / name
        if p.is_file():
            return p
    raise FileNotFoundError(f"找不到 {ref / STREAM_NAME}（舊名 {STREAM_NAMES[1]} 亦可）")


def resolve_pending(book: Path) -> Path | None:
    """待裁決佇列。**找不到不是錯**——一本還沒有任何回饋的書本來就沒有這支檔。

    這與裁決流不同：查裁決流是主要動作，檔不在要炸；待裁決是順帶吐的那一節，
    檔不在就印「（無）」。0 也印。
    """
    p = book / "story" / "參照" / PENDING_NAME
    return p if p.is_file() else None


def coverage(
    scanned: int, picked: int, targets: int, stale: int, pending_all: int, pending_hit: int
) -> str:
    """**我在這本書上掃了幾列。**（`設計原則.md` E2 可執行推論）

    在這一行之前，本工具對「空表／被 HTML 註解吞掉的表／根本沒建」印的是
    「（無符合的裁決）」**exit 0**，與「這本書真的沒有相關裁決」**逐字相同**——
    E2 最後一格（守衛回報正常的假陰性）。掃描數與命中數分開印就分得開了。

    **`待裁決 N 列／裁決 M 列` 並排印是刻意的**：歷史重放顯示 `f22082f` 那個
    commit 有 5 列回饋離開佇列、裁決流 +0 列、blockquote +4,903 字元。
    「N 在掉而 M 恆為 0」就是那個病徵，並排印讓它每次執行都看得見。
    這是 T5（回饋列離開 ⇄ 裁決軸 append 的對帳）改寫不成之後的替代品之一，
    **不等於守住了它**（那是跨時間斷言 → 功能 14）。**0 也印。**
    """
    return (
        f"掃描了 {scanned} 列裁決／命中 {picked} 列；"
        f"待裁決 {pending_all} 列／命中 {pending_hit} 列；"
        f"標的 {targets} 個（{stale} 個在書內找不到）"
    )


def format_decisions(
    decisions: list[Decision],
    target: str | None,
    active_only: bool,
    pending: list[Pending] | None = None,
) -> str:
    scope_note = f"標的 {target}" if target else "全部標的"
    state_note = "僅生效中" if active_only else f"全部狀態（{'／'.join(STATUSES)}）"
    lines = [f"## 裁決流查詢（{scope_note}·{state_note}）", ""]
    if not decisions:
        lines.append("（無符合的裁決）")
    for d in decisions:
        lines.append(f"### {d.date} · {d.source} → {d.target}")
        lines.append(f"- 裁決：{d.ruling}")
        lines.append(f"- 理由：{d.rationale}")
        lines.append(f"- 射程：{d.scope}　狀態：{d.status}")
        lines.append("")

    # 待裁決那一軸。**一律印這一節（0 列也印）**——兩軸選擇器相同（都是「這個標的
    # 相關的東西」），所以消化型 skill 跑一次查詢就同時看到「還沒裁決的」與「已經
    # 裁決過的」，不必記得跑第二支指令。這是抉擇 2 A 新增的那個步驟被吸收掉的方式：
    # 新增的不是一個新步驟，是既有步驟多吐一節。
    lines.append("")
    lines.append(f"## 待裁決（{scope_note}）")
    lines.append("")
    if pending:
        for q in pending:
            lines.append(f"- {q.date} · {q.source} → {q.target}")
            lines.append(f"  發現：{q.finding}")
    else:
        lines.append("（無——這個標的沒有待裁決的回饋）")
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

    _force_utf8()

    try:
        path = resolve_stream(args.book)
        decisions = parse_decisions(path.read_text(encoding="utf-8"))
        pending_path = resolve_pending(args.book)
        pending_all = (
            parse_pending(pending_path.read_text(encoding="utf-8"))
            if pending_path
            else []
        )
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

    picked_pending = select_pending(pending_all, args.target)
    notes = stale_targets(args.book, picked) + stale_pending_targets(
        args.book, picked_pending
    )
    print(
        coverage(
            scanned=len(decisions),
            picked=len(picked),
            targets=len({d.target for d in picked} | {q.target for q in picked_pending}),
            stale=len(notes),
            pending_all=len(pending_all),
            pending_hit=len(picked_pending),
        )
    )
    for note in notes:
        print(f"（資訊）{note}", file=sys.stderr)
    print(format_decisions(picked, args.target, args.active_only, picked_pending), end="")
    return 0


def stale_targets(book: Path, decisions: list[Decision]) -> list[str]:
    """標的路徑在書內已經不存在——append-only 不刪列，但壞標的要被看見。

    最常見的成因是角色源檔升級成目錄形態（`角色.schema.md` 明文建議的路徑）後，
    舊列的 `<名>.md` 已不存在。分段比對讓查詢照樣命中，本提示讓作者知道該順手改。
    """
    return _stale_targets(book, [(d.target, d.lineno) for d in decisions], "裁決流")


def stale_pending_targets(book: Path, rows: list[Pending]) -> list[str]:
    """待裁決那一軸的同一件事。診斷輪記的「`建議回寫` 欄指向已改名／不存在的源檔
    → 永遠不會發現」就是這一格：舊設計那一欄是散文，路徑寫錯無人知。改成
    `標的` 欄之後它與裁決流共用同一個存在性檢查。"""
    return _stale_targets(book, [(q.target, q.lineno) for q in rows], "待裁決")


def _stale_targets(book: Path, rows: list[tuple[str, int]], what: str) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for target, lineno in rows:
        t = target.strip()
        if t == TARGET_ALL or t in seen:
            continue
        seen.add(t)
        p = book / "story" / t
        if not p.exists() and not p.with_suffix("").is_dir():
            notes.append(
                f"{what}第 {lineno} 行的標的 `{t}` 在書內找不到（檔案改名或已移除？）"
            )
    return notes


def lint_main(argv: list[str] | None = None) -> int:
    """`decision-lint`：裁決軸與待裁決軸的格式閘門。

    輸出契約照抄 `fact_projection/cli.py:_print_lint`（`beat-lint`／`ch-lint`
    也是同一份）：覆蓋率行＋資訊走 **stdout**（**乾淨時也印、0 也印**），
    問題清單走 **stderr**，exit 0/1。
    """
    from .lint import lint_report

    ap = argparse.ArgumentParser(
        description="裁決軸格式閘門：驗 story/參照/裁決流.md 的七欄·日期·狀態·"
        "射程寫法·標的存在性·「一項裁決一列」·`已升為通則` 指向的檔存不存在，"
        "以及 story/參照/待裁決.md 的恰四欄（**不得有狀態欄**）·日期·標的·發現長度。"
        "由七支 append 型 skill 落檔後跑。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    args = ap.parse_args(argv)
    _force_utf8()

    problems, stats = lint_report(args.book)
    print(stats.render())
    for n in stats.notes:
        print(f"（資訊）{n}")
    if not problems:
        print("裁決軸格式乾淨。")
        return 0
    print(f"發現 {len(problems)} 個問題：", file=sys.stderr)
    for p in problems:
        print(f"  [x] {p}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
