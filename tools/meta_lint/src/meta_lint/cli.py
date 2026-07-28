"""`meta-lint`：**唯一一支不吃 `--book` 的檢查器**。

它守的是 repo 自己。前十三輪補完的是「被守的東西」的守衛；這一輪要補的是
**守衛的守衛**——因為那一族有一個前七種形態都沒有的性質：

> 一支被改壞的 `char-lint` 仍然 exit 0、仍然印覆蓋率行、仍然被四支 SKILL.md 呼叫
> ——功能 06 那一輪立的每一條保證都還「在」，只是不再成立。

輸出契約與其他 11 支 lint 相同（`結構定義/共同約定.md`「輸出與 exit 契約」）：
覆蓋率行、問題、提示一律 stdout，stderr 只裝執行錯誤，exit 0／1。
**沒有 exit 2**——這支工具的「書」是 repo，而 repo 一定在。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checks import (
    MetaStats,
    check_coverage_on_every_path,
    check_named_commands,
    check_output_contract,
    check_parallel_lists,
    check_schema_guards,
    check_triggers,
    project_duplicates,
    project_tests,
    project_thresholds,
)
from .repo import find_repo, packages, schema_files, skill_files, workflow_files

EXIT_CLEAN = 0
EXIT_PROBLEMS = 1

CLEAN = "工具鏈格式乾淨（指令觸發者／指名的指令存在／schema 守衛／平行清單／覆蓋率行／輸出契約）"


def _force_utf8() -> None:
    """Windows 主控台常是 cp950，會在印中文時炸。強制 UTF-8 輸出。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def lint_repo(repo: Path, live: bool = True) -> tuple[list, MetaStats]:
    """九項。第 1–6 項進問題數，第 7–9 項只印。"""
    stats = MetaStats()
    stats.packages = len(packages(repo))
    stats.skills = len(skill_files(repo))
    stats.schemas = len(schema_files(repo))
    stats.workflows = len(workflow_files(repo))

    problems = (
        check_triggers(repo, stats)
        + check_named_commands(repo, stats)
        + check_schema_guards(repo, stats)
        + check_parallel_lists(repo, stats)
        + check_coverage_on_every_path(repo, stats)
        + check_output_contract(repo, stats, live)
    )
    return problems, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="工具鏈格式閘門（零 LLM、可覆算）：① 每支指令都有觸發者"
        "（SKILL.md 的某一步或某支 workflow）；② 每個被指名的指令都存在；"
        "③ 每支 schema 指名的守衛存在且有「檢查器與觸發時機」節；"
        "④ 三份平行清單的產物集合一致；⑤ 每個 CLI 入口的路徑上都印得出覆蓋率行；"
        "⑥ 輸出去向與 exit 語意（對 fixture 書實跑）。"
        "另投影三項（只印）：⑦ 門檻常數與樣本數宣告；⑧ 同形實作份數；⑨ 測試狀態。"
        "**它不吃 `--book`**——它守的是 repo 自己。",
    )
    ap.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="repo 根（預設由本檔位置往上找 `tools/` 與 `結構定義/`）",
    )
    ap.add_argument(
        "--no-live",
        action="store_true",
        help="跳過要 subprocess 的第 6／9 項（快，但覆蓋率行會印「未接」——**不假裝乾淨**）",
    )
    args = ap.parse_args(argv)

    _force_utf8()
    try:
        repo = args.repo.resolve() if args.repo else find_repo()
    except FileNotFoundError as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return EXIT_PROBLEMS

    live = not args.no_live
    problems, stats = lint_repo(repo, live=live)

    print(f"## 工具鏈檢查 {repo.name}（零 LLM、可覆算）")
    print()
    print(stats.render())
    for n in stats.notes:
        print(f"（資訊）{n}")
    for h in stats.hints:
        print(f"（提示）{h}")

    if problems:
        print(f"\n發現 {len(problems)} 個問題：")
        for p in problems:
            print(f"  [x] {p}")
            print(f"        {p.hint}")
    else:
        print(CLEAN)

    print("\n".join(project_thresholds(repo)))
    print("\n".join(project_duplicates(repo)))
    print("\n".join(project_tests(repo, stats, live)))
    return EXIT_PROBLEMS if problems else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
