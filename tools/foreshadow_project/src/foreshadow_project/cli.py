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
from .scan import Mark, ScanError


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
    lines = [f"## {title}（掃 {len(rep.scanned_arcs)} 個 arc；零 LLM、可覆算）", ""]
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

    if rep.ice_suspect:
        lines += ["", "### 🧊 指向不存在的伏筆名（可疑點）"]
        for ice in rep.ice_suspect:
            lines.append(f"- {ice.file.name} 第 {ice.lineno} 行 → 收[[伏筆:{ice.target}]]")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="伏筆投影：跨 arc 掃描配對 埋/收[[伏筆:x]]（零 LLM、可覆算）。"
        "只認幕的「伏筆」欄為標記來源；定序走 幕綱/_index.md「全書順序」，不比幕號大小。"
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
    except ScanError as e:
        print(f"投影錯誤：{e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"讀取失敗：{e}", file=sys.stderr)
        return 1

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
    return 1 if has_problem else 0


if __name__ == "__main__":
    raise SystemExit(main())
