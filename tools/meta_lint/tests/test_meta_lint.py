"""`meta-lint` 自己的測試。

**這支檔存在的理由與別支不同**：`meta-lint` 是「守衛的守衛」，所以**它壞了會讓
它守的九件事一起靜音**。第 4／8 項尤其——那兩項是純比對，寫錯一個 regex 就會
永遠印「0」，而 0 讀起來像「乾淨」（`設計原則.md` E2 最後一格）。

所以這裡的每一支都用**造出來的壞 repo**，而不是只跑真 repo 一次看它綠——
一個只在乾淨輸入上綠的檢查器測不出任何東西。
"""

from pathlib import Path

import pytest
from meta_lint.checks import (
    MetaStats,
    check_coverage_on_every_path,
    check_named_commands,
    check_parallel_lists,
    check_schema_guards,
    check_triggers,
    load_known_red,
    project_duplicates,
    project_thresholds,
)
from meta_lint.cli import lint_repo
from meta_lint.repo import commands, find_repo, packages

REPO = find_repo(Path(__file__))


# ---------------------------------------------------------------- 真 repo 的基準
#
# **這幾支釘的是「本輪之後的正常狀態」**，不是覆蓋率。


def test_the_repo_is_found():
    assert (REPO / "tools").is_dir() and (REPO / "結構定義").is_dir()


def test_every_command_has_a_trigger():
    """**本輪的重點項**：工具鏈的真正呼叫者是 AI 的 skill，不是 push。

    一支從不被呼叫的 lint 與一支不存在的 lint，在系統的行為上完全相同——
    而前者更糟，因為 schema 裡寫著它。
    """
    stats = MetaStats()
    assert check_triggers(REPO, stats) == []
    assert stats.cmd_without_trigger == 0


def test_no_schema_or_skill_names_a_dead_command():
    stats = MetaStats()
    assert check_named_commands(REPO, stats) == []


def test_every_schema_points_at_a_real_checker():
    stats = MetaStats()
    assert check_schema_guards(REPO, stats) == []


def test_the_three_parallel_lists_agree():
    """08 抉擇 7 把 `DERIVED_KEYS` 延到 14，理由正是「它會製造第三份平行清單」
    ——**本輪付了那筆代價，這一項就是配套**（E1）。"""
    stats = MetaStats()
    assert check_parallel_lists(REPO, stats) == []
    assert stats.parallel_lists == 3


def test_every_gate_prints_a_coverage_line():
    stats = MetaStats()
    assert check_coverage_on_every_path(REPO, stats) == []
    assert stats.cli_entries > 0  # 0 個入口＝掃描器壞了，不是「都合格」


def test_every_known_red_entry_carries_a_reason():
    """**進這份清單的門檻是「說得出為什麼現在不修」**，不是「還沒空修」。

    允許「同上」這種明確的回指（六支是同一個根因），但**至少要有一筆寫出根因**
    ——一份全是「同上」的清單指不出任何東西。
    """
    reds = load_known_red(REPO)
    assert reds, "已知紅清單空了——那要嘛 6 支測試修好了（該刪清單），要嘛清單讀不到"
    for kr in reds:
        assert kr.test and kr.reason.strip(), kr.test
    assert any(len(kr.reason.strip()) > 100 for kr in reds), "沒有任何一筆寫出根因"


def test_projections_print_even_when_nothing_is_wrong():
    """第 7–9 項是投影：**0 也印**。"""
    assert any("門檻常數" in ln for ln in project_thresholds(REPO))
    assert any("同形實作份數" in ln for ln in project_duplicates(REPO))


def test_no_in_package_duplicate_survives():
    """**「同一套件內超額」恆為 0**——那是抉擇 1 D 收掉的那一半。"""
    table = project_duplicates(REPO)
    excess = [ln for ln in table if ln.startswith("|") and "**" in ln.split("|")[-2]]
    assert excess == [], "同一個 import 空間裡又長出一份複製了：" + "；".join(excess)


# ---------------------------------------------------------------- 造出來的壞 repo
#
# 只在乾淨輸入上綠的檢查器測不出任何東西。


def _fake_repo(tmp_path: Path, *, scripts: str = "", skill: str = "", schema: str = "") -> Path:
    root = tmp_path / "repo"
    pkg = root / "tools" / "demo"
    (pkg / "src" / "demo").mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        f"[project.scripts]\n{scripts}",
        encoding="utf-8",
    )
    (root / "結構定義").mkdir(parents=True)
    (root / "結構定義" / "示範.schema.md").write_text(schema or "# 示範\n", encoding="utf-8")
    d = root / ".claude" / "skills" / "demo"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(skill or "# demo\n", encoding="utf-8")
    return root


def test_orphan_command_is_reported(tmp_path):
    repo = _fake_repo(tmp_path, scripts='demo-lint = "demo.cli:main"\n')
    stats = MetaStats()
    problems = check_triggers(repo, stats)
    assert len(problems) == 1 and "`demo-lint`" in problems[0].detail
    assert stats.cmd_without_trigger == 1


def test_command_named_in_a_workflow_counts_as_triggered(tmp_path):
    """`meta-lint` 自己的觸發者就是 workflow——**「或 workflow」不是放水**。"""
    repo = _fake_repo(tmp_path, scripts='demo-lint = "demo.cli:main"\n')
    wf = repo / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "tools.yml").write_text("run: uv run demo-lint\n", encoding="utf-8")
    assert check_triggers(repo, MetaStats()) == []


def test_dead_command_in_a_schema_is_reported(tmp_path):
    repo = _fake_repo(
        tmp_path,
        scripts='demo-lint = "demo.cli:main"\n',
        skill="跑 `demo-lint --book <書>`\n",
        schema="格式由 `demo-lint` 守；另見 `state-project`。\n",
    )
    problems = check_named_commands(repo, MetaStats())
    assert len(problems) == 1 and "`state-project`" in problems[0].detail


def test_a_schema_with_no_checker_is_reported(tmp_path):
    repo = _fake_repo(
        tmp_path,
        scripts='demo-lint = "demo.cli:main"\n',
        skill="跑 `demo-lint`\n",
        schema="# 示範\n\n本檔宣稱八欄固定、幕號唯一。\n",
    )
    problems = check_schema_guards(repo, MetaStats())
    assert len(problems) == 1 and "一個檢查器都指不出來" in problems[0].detail


def test_a_missing_guard_is_reported(tmp_path):
    repo = _fake_repo(
        tmp_path,
        scripts='demo-lint = "demo.cli:main"\n',
        skill="跑 `demo-lint`\n",
        schema="格式由 `demo-lint` 守。另一半格式由 `ghost-lint` 守。\n",
    )
    problems = check_schema_guards(repo, MetaStats())
    assert any("`ghost-lint`" in p.detail for p in problems)


def test_diverging_parallel_lists_are_reported(tmp_path):
    repo = _fake_repo(tmp_path)
    d = repo / "tools" / "derived_sync" / "src" / "derived_sync"
    d.mkdir(parents=True)
    (d / "validate.py").write_text(
        'SETTINGS_KINDS = ("角色",)\n'
        'DERIVED_SECTIONS = {"角色": ("需求四象限",), "摘要": ("壓縮",)}\n'
        'DERIVED_KEYS = {"角色": ("定位",)}\n',  # 少了「摘要」
        encoding="utf-8",
    )
    (repo / "tools" / "derived_sync" / "pyproject.toml").write_text(
        '[project]\nname = "derived-sync"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    problems = check_parallel_lists(repo, MetaStats())
    assert len(problems) == 1 and "摘要" in problems[0].detail


def test_a_gate_without_a_coverage_line_is_reported(tmp_path):
    repo = _fake_repo(tmp_path, scripts='demo-lint = "demo.cli:main"\n')
    (repo / "tools" / "demo" / "src" / "demo" / "cli.py").write_text(
        "def main(argv=None):\n    print('乾淨')\n    return 0\n", encoding="utf-8"
    )
    stats = MetaStats()
    problems = check_coverage_on_every_path(repo, stats)
    assert len(problems) == 1 and "demo:main" in problems[0].detail


def test_delegating_to_a_helper_still_counts(tmp_path):
    """入口常常只是分派給 `_cmd_*` helper——**不跟著呼叫鏈走就會誤報 15/24 個**，
    而一個會誤報的閘門就是下一個沒有人看的閘門。"""
    repo = _fake_repo(tmp_path, scripts='demo-lint = "demo.cli:main"\n')
    (repo / "tools" / "demo" / "src" / "demo" / "cli.py").write_text(
        "def _report(stats):\n    print(stats.render())\n\n\n"
        "def main(argv=None):\n    _report(None)\n    return 0\n",
        encoding="utf-8",
    )
    assert check_coverage_on_every_path(repo, MetaStats()) == []


# ---------------------------------------------------------------- 端到端


def test_lint_repo_runs_without_live(tmp_path):
    problems, stats = lint_repo(REPO, live=False)
    assert stats.live_skipped is True
    # **未接要說出來**，不能假裝乾淨（E2）
    assert any("未接" in h for h in stats.hints)
    assert isinstance(problems, list)


@pytest.mark.parametrize("pkg", [p.name for p in packages(REPO)])
def test_every_package_has_tests(pkg):
    """一個沒有 tests/ 的套件 ＝ CI 對它一句話都不會說。"""
    assert (REPO / "tools" / pkg / "tests").is_dir(), f"{pkg} 沒有 tests/"


def test_command_count_matches_the_registry():
    """22 個指令（21 ＋ `meta-lint`）。數字變了就是有人加/刪了 entry point。"""
    assert len(commands(REPO)) == 22
