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
    CASE_BOOK,
    MetaStats,
    check_coverage_on_every_path,
    check_entry_table,
    check_kb_lists,
    check_named_commands,
    check_parallel_lists,
    check_schema_guards,
    check_skill_paths,
    check_triggers,
    emit_guards,
    emit_kb,
    empty_book,
    entry_table,
    kb_referrers,
    load_known_red,
    project_duplicates,
    project_thresholds,
)
from meta_lint.cli import lint_repo
from meta_lint.repo import (
    ABOLISHED,
    abolished_in,
    abolished_mentions,
    book_paths,
    commands,
    find_repo,
    landing_places,
    normalize_paths,
    packages,
)

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

    允許「同上」這種明確的回指（同一個根因的數支），但**至少要有一筆寫出根因**
    ——一份全是「同上」的清單指不出任何東西。

    **空清單是合法的**（2026-07-30 起實際就是 0 筆）。舊版這裡寫 `assert reds`，
    而那一行把「全綠」與「清單讀不到」壓成同一句紅字——**它自己就是 E2 第五格
    （假陰性的鏡像：假陽性）**。兩件事分開釘：這一支管「有的話要有理由」，
    `test_the_known_red_file_is_still_readable` 管「讀不讀得到」。
    """
    reds = load_known_red(REPO)
    for kr in reds:
        assert kr.test and kr.reason.strip(), kr.test
    if reds:
        assert any(len(kr.reason.strip()) > 100 for kr in reds), "沒有任何一筆寫出根因"


def test_the_known_red_file_is_still_readable():
    """**空清單 ≠ 檔不見了。**

    雙向擋的第一個方向（「紅而不在清單裡 → fail」）靠這支檔存在；檔被刪掉之後
    `load_known_red` 回 `[]`，與「清單清空了」完全同形——那正是這一整輪在追的
    「已遷移」與「守衛被關掉」共用一個綠燈。所以檔的存在性單獨釘一支。
    """
    p = REPO / "tools" / "meta_lint" / "known-red.toml"
    assert p.is_file(), "known-red.toml 不見了——雙向擋的第一個方向從此不存在"
    assert "known_red" in p.read_text(encoding="utf-8"), "清單的鍵不在，`.get` 會靜默回 []"


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


def _fake_repo(
    tmp_path: Path,
    *,
    scripts: str = "",
    skill: str = "",
    schema: str = "",
    devdoc: str = "",
    session_log: str = "",
) -> Path:
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
    if devdoc:
        dev = root / "情境測試"
        dev.mkdir(parents=True, exist_ok=True)
        (dev / "端到端貫穿測試流程.md").write_text(devdoc, encoding="utf-8")
    if session_log:
        logs = root / "情境測試" / "示範書"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "S12-write.md").write_text(session_log, encoding="utf-8")
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


# ================================================ 第 10–12 項（2026-07-29 功能 15）
#
# **對象是「讀」不是「寫」。** 前十四輪把每個產物軸的產出格式與守衛補齊了，而
# 「誰在什麼時候把什麼讀進來」從來沒有被任何檢查器碰過一次。


def test_no_skill_declaration_points_at_an_abolished_file():
    """**回歸數字 ①**：修完之後，12 支 SKILL.md 對已廢除的檔報 **0 筆**。

    診斷輪實測 24 條（9/12 支 skill 命中，一半是「重生它／封章它」的寫入命令），
    而 `meta-lint` 當時的覆蓋率行印「散文裡的指令 token 197 個（**0 個 registry
    查無**）」——**掃描對象是對的，掃描的欄位只有一格**。
    """
    stats = MetaStats()
    problems = check_skill_paths(REPO, stats)
    assert stats.skill_paths_abolished == 0, [p.detail for p in problems]
    assert stats.skill_paths_unlanded == 0, [p.detail for p in problems]
    assert stats.skill_paths > 0  # 0 條＝抓取器壞了，不是「都合格」
    assert problems == []


def test_the_entry_table_and_the_skills_agree_both_ways():
    """V3 的守衛：查詢入口表（產物側）↔ 12 支 SKILL.md（skill 側）。"""
    stats = MetaStats()
    problems = check_entry_table(REPO, stats)
    assert stats.entry_rows > 0
    assert stats.entry_rows_unread == 0, [p.detail for p in problems]
    assert stats.skill_axes_unlisted == 0, [p.detail for p in problems]


def test_every_referenced_kb_file_has_a_core_toc():
    """10/12 支 SKILL.md 寫著「先讀檔頭『目錄』標核心的小節」——**前提要為真**。"""
    stats = MetaStats()
    problems = check_kb_lists(REPO, stats)
    assert stats.kb_without_toc == 0, [p.detail for p in problems]
    assert problems == []


def test_the_two_unreferenced_kb_files_are_visible_not_hidden():
    """**「0 支」是儀表，不是待修的洞**（同功能 10 對「未接」的處置）。

    `角色關係網與群像.md`／`角色魅力與登場.md` 實測零 skill 引用，而舊 `_index.md`
    那一欄宣稱它們各有 6／7 支。這一支釘的是「投影看得見它們」，**不是**「它們必須
    被接上」——要不要接是內容決定，重構輪刻意不動。
    """
    refs = kb_referrers(REPO)
    assert refs["角色關係網與群像.md"] == set()
    assert refs["角色魅力與登場.md"] == set()
    assert any("0 支" in ln for ln in emit_kb(REPO))


def test_both_projections_print_and_exit_zero_shaped():
    """兩個 `--emit` 是投影：有表頭、有機械來源說明、0 也印。"""
    g = "\n".join(emit_guards(REPO))
    assert "| 指令 | 套件 | 守什麼 | 觸發者 | 覆蓋率行 |" in g
    assert "argparse" in g and "pyproject.toml" in g
    # **每一支指令都要有「守什麼」**——`fact-lint`／`object-lint` 是 f-string，
    # 而「讀不到 description」在一份取代了手抄清單的投影上是一個真的洞
    assert "讀不到 description" not in g
    k = "\n".join(emit_kb(REPO))
    assert "| 技法檔 | 幾支 | 哪幾支 |" in k


# ---------------------------------------------------------------- 造出來的壞輸入
#
# 只在乾淨輸入上綠的檢查器測不出任何東西。


def test_a_revived_abolished_file_in_a_skill_is_reported(tmp_path):
    repo = _fake_repo(tmp_path, skill="重生 `story/設定/角色/_index.ai.md` 並封章\n")
    stats = MetaStats()
    problems = check_skill_paths(repo, stats)
    assert stats.skill_paths_abolished == 1
    assert any("已廢除" in p.detail for p in problems)


def test_a_tombstoned_mention_on_the_same_line_is_allowed(tmp_path):
    """**墓碑刻意只有一個 token**，而它要在**同一行**。"""
    repo = _fake_repo(
        tmp_path,
        skill="`_index.ai.md` 2026-07-28 廢除，清單跑 `char-lint --emit`\n",
    )
    stats = MetaStats()
    assert check_skill_paths(repo, stats) == []
    assert stats.skill_paths_abolished == 0


def test_a_tombstone_on_a_different_line_does_not_launder_it(tmp_path):
    """下一行寫「廢除」救不了上一行的寫入命令——那正是實測 24 條裡最常見的形狀
    （`character:16`／`:60` 命令重生，`:67` 才說它廢除了）。"""
    repo = _fake_repo(
        tmp_path,
        skill="重生 `_index.ai.md` 並封章\n\n（其實 `_index.ai.md` 已廢除）\n",
    )
    stats = MetaStats()
    assert len(check_skill_paths(repo, stats)) == 1
    assert stats.skill_paths_abolished == 1


def test_a_path_with_no_landing_place_is_reported(tmp_path):
    repo = _fake_repo(tmp_path, skill="讀 `story/沒有這一層/東西.md`\n")
    stats = MetaStats()
    problems = check_skill_paths(repo, stats)
    assert stats.skill_paths_unlanded == 1
    assert any("沒有落點" in p.detail for p in problems)


# ------------------------------------------------ 第 6 項的 exit 2 樣本不再硬編書名


def test_the_exit_two_sample_is_discovered_not_hardcoded(tmp_path):
    """`raw/` 在、`story/` 不在 → 就是它。**書名不進程式碼。**"""
    repo = _fake_repo(tmp_path)
    (repo / "某本新書" / "raw").mkdir(parents=True)
    assert empty_book(repo) == "某本新書"


def test_a_book_that_started_writing_stops_being_the_sample(tmp_path):
    """**這一支釘的是那顆定時炸彈本身。**

    原本 `EMPTY_BOOK` 寫死 `gothic_witch`，而那是作者的實驗素材。它一旦長出 `story/`，
    舊寫法會**靜默**跳過整個 exit 2 分支——迴圈照跑、覆蓋率行照印、`live_checked`
    照加，而第 2 條契約再也沒有被驗過一次（`設計原則.md` E2 最糟那一格，觸發條件是
    「有人正常地開始寫一本書」）。現在它會改挑別本，挑不到則印「未接」。
    """
    repo = _fake_repo(tmp_path)
    (repo / "已開工的書" / "raw").mkdir(parents=True)
    (repo / "已開工的書" / "story").mkdir(parents=True)
    assert empty_book(repo) is None  # 不是「還是它」，也不是拋錯

    (repo / "還沒開工的書" / "raw").mkdir(parents=True)
    assert empty_book(repo) == "還沒開工的書"


def test_the_real_repo_still_has_an_exit_two_sample():
    """**射程非空的守衛**（同 devdoc 那一條的理由）。挑不到就是這一格空了。"""
    assert empty_book(REPO) is not None


# ------------------------------------------------ 墓碑那一格的第三個射程：`情境測試/`
#
# 2026-07-30 擴。**擴的理由是一個實測**：`端到端貫穿測試流程.md` 寫於 2026-07-20，
# 早於 07-26～29 的重構，於是它的「開場三讀」第 3 條在功能 10 廢除 `就緒儀表.md` 之後
# 還叫人去讀那支檔，**而覆蓋率行印「0 條指向已廢除的檔」**——射程少一個資料夾。


def test_a_stale_instruction_in_a_devdoc_is_reported(tmp_path):
    """開發期活指示檔指向已廢除的檔，要報，而且要指得出行號。"""
    repo = _fake_repo(tmp_path, devdoc="開場三讀：\n3. `story/參照/就緒儀表.md`（若已存在）\n")
    stats = MetaStats()
    problems = check_skill_paths(repo, stats)
    assert stats.devdocs == 1
    assert stats.skill_paths_abolished == 1
    assert any("端到端貫穿測試流程.md:2" in p.detail for p in problems)


def test_the_tombstone_rule_applies_to_devdocs_too(tmp_path):
    """同一行寫出「廢除」就放行——與 SKILL.md 那一側同一條規矩，不另立標準。"""
    repo = _fake_repo(
        tmp_path,
        devdoc="`就緒儀表.md` 功能 10 已廢除，改跑 `readiness` ＋源 `story/參照/就緒.md`\n",
    )
    stats = MetaStats()
    assert check_skill_paths(repo, stats) == []
    assert stats.devdocs == 1
    assert stats.skill_paths_abolished == 0


def test_historical_session_logs_are_deliberately_out_of_scope(tmp_path):
    """**`情境測試/<書>/` 底下的逐 session 紀錄不掃**——只掃頂層。

    那底下住的是 S1–S51 的歷史紀錄，而**歷史紀錄提到一支當時還活著的檔是正確的**：
    那是它當時的事實，不是今天的指示。把 append-only 的歷史納入墓碑檢查，等於要求
    歷史隨著今天的廢除而改寫，而「判例要能回查」正是 `CLAUDE.md` 第三問立事件流的
    理由本身。這一支釘的是**射程的邊界**，不是一個洞。
    """
    repo = _fake_repo(tmp_path, session_log="S12 當時讀了 `story/參照/就緒儀表.md`\n")
    stats = MetaStats()
    assert check_skill_paths(repo, stats) == []
    assert stats.devdocs == 0  # 頂層沒有 .md，所以掃了 0 支——**而 0 也印**
    assert stats.skill_paths_abolished == 0


def test_the_devdoc_scope_is_not_silently_empty():
    """**射程非空的守衛**：真 repo 上這一格必須掃到 > 0 支。

    這一條是針對 `設計原則.md` E2 第七形態的鏡像——**測試是綠的，射程是空的**
    （功能 11 實測過一次：五支測試全用 `tmp_path` 造 `結構.ai.md`，而唯一的活書叫
    `結構.md`）。`devdocs == 0` 而其他 assert 全綠，就是那個形態又發生一次。
    """
    stats = MetaStats()
    check_skill_paths(REPO, stats)
    assert stats.devdocs > 0, "情境測試/ 掃到 0 支＝射程空了，不是「都合格」"


def test_the_kb_index_column_is_detected_as_a_leftover(tmp_path):
    repo = _fake_repo(tmp_path)
    kb = repo / "技巧知識庫"
    kb.mkdir()
    (kb / "_index.md").write_text(
        "| 技法檔 | 層 | 何時查它 | 被哪些 skill 引用 |\n", encoding="utf-8"
    )
    (kb / "示範.md").write_text("# 示範\n## 目錄\n- **核心方法**：一 X\n", encoding="utf-8")
    problems = check_kb_lists(repo, MetaStats())
    assert any("被哪些 skill 引用" in p.detail for p in problems)


def test_a_kb_file_without_a_toc_is_reported_only_when_referenced(tmp_path):
    """**射程是「被引用的那幾支」**：沒有 skill 讀它，就沒有「前提為假」的問題。"""
    repo = _fake_repo(tmp_path, skill="讀 `示範.md`\n")
    kb = repo / "技巧知識庫"
    kb.mkdir()
    (kb / "示範.md").write_text("# 示範\n\n## 一、內容\n", encoding="utf-8")
    (kb / "沒人讀.md").write_text("# 沒人讀\n\n## 一、內容\n", encoding="utf-8")
    stats = MetaStats()
    problems = check_kb_lists(repo, stats)
    assert stats.kb_without_toc == 1
    assert "`示範.md`" in problems[-1].detail and "沒人讀" not in problems[-1].detail


def test_a_toc_without_the_word_core_is_still_reported(tmp_path):
    """「有目錄」不等於「標了核心」——SKILL.md 那句規勸要的是後者。"""
    repo = _fake_repo(tmp_path, skill="讀 `示範.md`\n")
    kb = repo / "技巧知識庫"
    kb.mkdir()
    (kb / "示範.md").write_text("# 示範\n\n## 目錄\n- 一 X／二 Y\n\n---\n\n## 一、X\n", encoding="utf-8")
    stats = MetaStats()
    assert len(check_kb_lists(repo, stats)) == 1
    assert stats.kb_without_toc == 1


def test_an_incomplete_enumeration_in_claude_md_is_reported(tmp_path):
    """**判準是位置不是總數**：同一行 ≥3 支＝列舉，1–2 支＝指路。"""
    repo = _fake_repo(tmp_path)
    kb = repo / "技巧知識庫"
    kb.mkdir()
    for n in ("甲.md", "乙.md", "丙.md", "丁.md"):
        (kb / n).write_text(f"# {n}\n", encoding="utf-8")
    doc = repo / "CLAUDE.md"

    doc.write_text("方法（甲.md／乙.md／丙.md）\n", encoding="utf-8")  # 3 支＝列舉、漏 1
    problems = check_kb_lists(repo, MetaStats())
    assert any("丁.md" in p.detail for p in problems)

    doc.write_text("公式名照 `甲.md` 的 registry 寫\n", encoding="utf-8")  # 1 支＝指路
    assert not any(p.where == "CLAUDE.md" for p in check_kb_lists(repo, MetaStats()))


def test_a_missing_entry_table_row_is_reported(tmp_path):
    """SKILL.md 讀的路徑不在表裡、也不在豁免裡 → 報（**兩份清單都沒有它**）。"""
    repo = _fake_repo(tmp_path, skill="讀 `story/設定/風格/風格.md`\n")
    d = repo / "結構定義"
    (d / "共同約定.md").write_text(
        "## 八、context 取用契約\n\n### 成長型產物與各自的查詢入口\n\n"
        "| 產物 | 為何成長 | 查詢入口 |\n|---|---|---|\n"
        "| `chapters/*.ai.md` | 每章 | `fact-project` |\n\n"
        "### 不受此限的\n\n- `raw/`：豁免查詢入口\n\n## 九、別的\n",
        encoding="utf-8",
    )
    stats = MetaStats()
    problems = check_entry_table(repo, stats)
    assert stats.skill_axes_unlisted == 1
    assert any("風格" in p.detail for p in problems)


def test_a_row_with_no_reader_is_reported(tmp_path):
    repo = _fake_repo(tmp_path, skill="（什麼都不讀）\n")
    d = repo / "結構定義"
    (d / "共同約定.md").write_text(
        "## 八、context 取用契約\n\n### 成長型產物與各自的查詢入口\n\n"
        "| 產物 | 為何成長 | 查詢入口 |\n|---|---|---|\n"
        "| `story/物件/*.md` | 每次拍板 | `fact-project` |\n\n## 九、別的\n",
        encoding="utf-8",
    )
    stats = MetaStats()
    problems = check_entry_table(repo, stats)
    assert stats.entry_rows == 1 and stats.entry_rows_unread == 1
    assert any("沒有任何 SKILL.md 讀它" in p.detail for p in problems)


def test_a_tombstoned_table_row_is_not_required_to_have_a_reader(tmp_path):
    """墓碑列（`~~…~~ 廢除`）留在表上是刻意的指路，**不該被要求有讀者**。"""
    repo = _fake_repo(tmp_path, skill="（什麼都不讀）\n")
    d = repo / "結構定義"
    (d / "共同約定.md").write_text(
        "## 八、context 取用契約\n\n### 成長型產物與各自的查詢入口\n\n"
        "| 產物 | 為何成長 | 查詢入口 |\n|---|---|---|\n"
        "| ~~`story/大綱/_index.md`~~ **2026-07-28 廢除** | 曾經 | `outline-lint --emit` |\n\n"
        "## 九、別的\n",
        encoding="utf-8",
    )
    rows, _ = entry_table(repo)
    assert rows == []


# ---------------------------------------------------------------- 正規化的單元
#
# 這幾支釘的是實作時實測到的三個坑——每一個都讓閘門誤報或漏報。


def test_braces_expand_rather_than_collapse():
    """`{md,ai.md}` 收成 `*` 會讓摘要軸同時被報成「無讀者」與「不在表裡」。"""
    assert normalize_paths("story/00-摘要.{md,ai.md}") == {
        "story/00-摘要.md",
        "story/00-摘要.ai.md",
    }
    assert normalize_paths("story/設定/{世界觀,角色}/<名>.ai.md") == {
        "story/設定/世界觀/*.ai.md",
        "story/設定/角色/*.ai.md",
    }


def test_the_star_survives_normalization():
    """濾掉 `*` 會把 `story/設定/角色/*` 截成目錄、於是每支角色檔都被報。"""
    assert book_paths("讀 `story/設定/角色/*` 與 `chapters/*.ai.md`") == {
        "story/設定/角色/*",
        "chapters/*.ai.md",
    }


def test_the_kb_index_is_not_mistaken_for_an_abolished_book_file():
    """`技巧知識庫/_index.md` 是活的檢索入口——**唯一與已廢除檔撞名的那一支**。"""
    assert "_index.md" in ABOLISHED
    assert abolished_mentions("入口見 `技巧知識庫/_index.md`") == []
    assert abolished_in("入口見 技巧知識庫/_index.md") == set()


def test_a_tombstone_in_one_clause_does_not_cover_another():
    """整串判墓碑會讓同一段 description 裡別的子句拿到免死金牌（實測 6 筆只抓到 4）。"""
    assert abolished_in("驗已廢除的欄、`_index.ai.md` 的清單 ≡ 資料夾") == {"_index.ai.md"}
    assert abolished_in("舊 `_index.ai.md` 2026-07-28 廢除，只報殘留") == set()


def test_landing_places_come_from_two_sources():
    """模板只有 15 支檔、沒有角色與世界觀資料夾——**只靠它會誤報**。"""
    places, notes = landing_places(REPO)
    assert "story/設定/角色" in places  # 來自 `SETTINGS_KINDS`，模板裡沒有
    assert "story/幕綱" in places
    assert "story/大綱/_已併入" in places  # 來自 `book_layout.OUTLINE_RETIRED`
    assert len(notes) >= 3


# ------------------------------------------ 第 6 項的第 4 條契約：病例書不吐 traceback
#
# 2026-07-30（驗證輪階段 1c）新增。那一輪移除了成組的 legacy 讀取路徑，
# 而拍板的硬驗收條件是「移除一條 legacy 讀取路徑必須降級成**被回報的問題**，
# 絕不能降級成 traceback」。這兩支把那條條件從「有人手動跑一次」變成守衛。


def test_the_case_book_scope_is_not_silently_empty():
    """**射程非空。** 病例書不在 → 第 4 條契約整格消失，而輸出會長得像「都合格」。

    這與 `test_the_real_repo_still_has_an_exit_two_sample` 是同一種釘法：
    新守衛最容易的死法是「測試是綠的，射程是空的」（E2 第七形態的鏡像）。
    `tools.yml` 也有一步 `test -d 一世之尊`，理由寫著「否則 17 份黃金檔的射程是
    空的」——那句話從今天起多守一格。
    """
    assert (REPO / CASE_BOOK).is_dir(), (
        f"病例書 `{CASE_BOOK}` 不在——第 6 項的第 4 條契約（不吐 traceback）"
        "與 17 份黃金檔的射程同時變成空的"
    )


def test_the_case_book_is_the_only_one_with_prose():
    """**它為什麼非得是這一本**：全 repo 只有它有正文。

    第 4 條契約要驗的分支（`prose-metrics` 的成功輸出、93 支章衍生、11 支 arc 幕綱）
    在別的書上一條都走不到——`書本模板` 與純 raw 書一律 exit 2 早退。
    這一支釘住那個前提：哪天別的書也長出 `chapters/`，這一格可以改成自動挑選
    （形狀照 `empty_book`），而在那之前硬編書名是誠實的。
    """
    # **判準是「有沒有 chNNNN.md」，不是「有沒有 chapters/」**：`書本模板/chapters/`
    # 是骨架資料夾（空的），而空資料夾走不到 `prose-metrics` 的成功分支——
    # 拿資料夾當判準正是 `prose_metrics` 那 6 支長期紅測試踩過的坑
    # （`skipif` 檢查 `芯片巫師/` 在不在，而測試要的是 `芯片巫師/chapters/`）。
    with_prose = sorted(
        p.name
        for p in REPO.iterdir()
        if p.is_dir()
        and not p.name.startswith((".", "_"))
        and any((p / "chapters").glob("ch*.md"))
    )
    assert with_prose == [CASE_BOOK], (
        f"有正文的書變成 {with_prose}——第 4 條契約的樣本可以（也應該）改成自動挑選"
    )
