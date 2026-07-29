from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .project import (
    CLOSED,
    OPEN_UNDECLARED,
    PAID_UNPLANTED,
    Report,
    Thread,
    build,
    entering,
)
from .scan import LayerMissing, Mark, ScanError


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

def _force_utf8() -> None:
    """Windows 主控台常是 cp950，會在印中文時炸。強制 UTF-8 輸出。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def _ref(m: Mark) -> str:
    return f"幕{m.beat:03d}（{m.arc}）"  # 幕號一律補零三位（系統慣例）


def _thread_line(t: Thread) -> str:
    plants = "／".join(_ref(m) for m in t.plants) or "—"
    pays = "／".join(_ref(m) for m in t.pays) or "—"
    flag = "  ← 可疑點" if t.suspect else ""
    return f"- [{t.status}] {t.name}　埋 {plants}　收 {pays}{flag}"


def format_report(rep: Report, threads: list[Thread], title: str) -> str:
    lines = [
        f"## {title}（掃 {len(rep.scanned_arcs)} 個 arc；{rep.spine_note}；零 LLM、可覆算）",
        "",
    ]
    if not threads:
        lines.append("（無符合條件的伏筆）")
    for t in threads:
        lines.append(_thread_line(t))

    suspects = [t for t in threads if t.suspect]
    lines += ["", f"小計：{len(threads)} 條，其中 {len(suspects)} 條為可疑點"]
    if suspects:
        lines.append(
            f"　- {OPEN_UNDECLARED}：埋了沒收、也沒在任何「本 arc 伏筆狀態」表誠實列出"
        )
        lines.append(f"　- {PAID_UNPLANTED}：有收無埋（疑似伏筆名不一致或漏埋）")

    if rep.expired_unbuilt:
        lines += ["", "### 跨 arc 待補已到期（可疑點）"]
        for row, arc in rep.expired_unbuilt:
            lines.append(
                f"- {row.arc} 狀態表「{row.name}」仍寫 {arc}（未拆），但 {arc} 已拆出幕號"
                f"　（第 {row.lineno} 行）"
            )

    if rep.violations:
        lines += ["", "### 標記寫錯地方（可疑點·會污染機械掃描）"]
        for v in rep.violations:
            lines.append(f"- [{v.kind}] {v.arc} 第 {v.lineno} 行：{v.detail}")

    lines += ["", _reveal_summary(rep)]
    for ice, why in rep.ice_resolved + rep.ice_pending:
        lines.append(f"- {ice.file.name} 第 {ice.lineno} 行：{why}")
    if rep.ice_suspect:
        lines += ["", "### 揭示層級無法解析（可疑點）"]
        for ice, why in rep.ice_suspect:
            lines.append(f"- {ice.file.name} 第 {ice.lineno} 行 `{ice.raw}`：{why}")

    return "\n".join(lines).rstrip() + "\n"


def _reveal_summary(rep: Report) -> str:
    """**掃到 N 處／解析 N 處／無法解析 N 處。**

    這一行是本工具最貴的一課換來的（`設計原則.md` E2）：舊版只印可疑點，而「可疑點」
    是從**已解析的**標記裡挑出來的——於是 92 處出現、91 處連標記都不算時，它印的是
    「0 條為可疑點」exit 0。一個檢查器必須能回答「我檢查了幾筆」，不能只回答
    「我發現幾個問題」。**0 處也要印**，那本身就是訊息。
    """
    return (
        f"### 揭示層級：掃到 {rep.ice_scanned} 處／"
        f"解析 {len(rep.ice_resolved)} 處／待落幕 {len(rep.ice_pending)} 處／"
        f"**無法解析 {rep.ice_unparsed} 處**"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="伏筆投影：跨 arc 掃描配對 埋/收[[伏筆:x]]（零 LLM、可覆算）。"
        "只認幕的「伏筆」欄為標記來源；定序走 幕綱/_順序.md 的「全書順序」"
        "（舊落點 幕綱/_index.md 2026-07-28 廢除，仍可回退、而回退在覆蓋率行上看得見），"
        "不比幕號大小。"
        "取代『為了配對伏筆而整批讀所有 arc 檔』。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument("--arc", default=None, help="只看進入這個 arc 時相關的伏筆（接口查詢）")
    ap.add_argument("--open-only", action="store_true", help="只列未收的")
    ap.add_argument("--suspect-only", action="store_true", help="只列可疑點")
    args = ap.parse_args(argv)

    _force_utf8()
    try:
        rep = build(args.book)
        if args.arc:
            threads = entering(rep, args.arc)
            title = f"進入 {args.arc} 的伏筆接口"
        else:
            threads = rep.threads
            title = "全書伏筆帳"
    except LayerMissing as e:
        # **exit 2 ＝跑不動，而且照樣印覆蓋率行**（抉擇 6 A）。
        print(f"檢查範圍：掃了 0 個 arc——這本書還沒有這一層（{e}）")
        return EXIT_LAYER_MISSING
    except ScanError as e:
        print(f"投影錯誤：{e}", file=sys.stderr)
        return EXIT_PROBLEMS
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return EXIT_PROBLEMS

    if args.open_only:
        threads = [t for t in threads if t.status != CLOSED]
    if args.suspect_only:
        threads = [t for t in threads if t.suspect]

    print(format_report(rep, threads, title), end="")
    has_problem = (
        any(t.suspect for t in threads)
        or rep.violations
        or rep.expired_unbuilt
        or rep.ice_suspect
    )
    return EXIT_PROBLEMS if has_problem else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
