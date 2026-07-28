"""`structure-project` 與 `formula` registry 的逐項測試（2026-07-28 功能 11）。

**每一項都要有正反兩面**（同 `test_outline_lint.py` 的紀律）：只測「壞的會報」不夠。
本輪特別要盯的是**射程**——本輪刪掉的那五支 `_is_declarative` 測試全部用 `tmp_path`
造 `結構.ai.md`，而唯一的活書叫 `結構.md`，於是**測試是綠的、射程是空的**。所以這裡：

- 每個用到 registry 的案例都**明確種一個套件根**（`conftest.plant_package_root`）；
- 另外有一支專門驗「沒種套件根時 registry 印『未接』而不是 0 套」。
"""

from pathlib import Path

import pytest
from beat_metrics.formula import leading_stage, load, package_root
from beat_metrics.structure_project import project
from conftest import plant_package_root

# ------------------------------------------------------------------ 語料建構

FULL = """# 大綱

## 選用結構公式
起承轉合（單場任務內部另套序破急）。

## 故事全文（連續敘述）
從頭講一遍。

## 結局與題旨
- 結局：見 `00-摘要.md`。
- 題旨：因為（算計），導致（孤立）。
"""

# 一個完整跑完起承轉合的 arc（四幕）。
ARC_OK = """# arc01

## 本 arc 承諾
- 不得發生：

## 幕001 · 開場
- 角色：甲
- 時空：寺
- 行動：走
- 衝突：擋
- 結果：過
- 前因：—
- 伏筆：—
- 結構階段：起·失衡開場（日常被打破）

## 幕002 · 爬升
- 角色：甲
- 時空：寺
- 行動：走
- 衝突：擋
- 結果：過
- 前因：—
- 伏筆：—
- 結構階段：承·順境（爬升）

## 幕003 · 逆境
- 角色：甲
- 時空：寺
- 行動：走
- 衝突：擋
- 結果：過
- 前因：—
- 伏筆：—
- 結構階段：轉·露餡

## 幕004 · 收束
- 角色：甲
- 時空：寺
- 行動：走
- 衝突：擋
- 結果：過
- 前因：—
- 伏筆：—
- 結構階段：合·重整
"""


def _book(tmp_path: Path, arc: str = ARC_OK, full: str = FULL, root: bool = True) -> Path:
    if root:
        plant_package_root(tmp_path)
    book = tmp_path / "書"
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "_index.md").write_text(
        "# 幕綱索引\n全書順序：arc01\n", encoding="utf-8"
    )
    (book / "story" / "幕綱" / "arc01.md").write_text(arc, encoding="utf-8")
    (book / "story" / "01-大綱.md").write_text(full, encoding="utf-8")
    return book


@pytest.fixture
def book(tmp_path: Path) -> Path:
    return _book(tmp_path)


# ------------------------------------------------------------------ registry


def test_registry_parses_names_and_stages(tmp_path: Path):
    plant_package_root(tmp_path)
    reg = load(tmp_path / "書")
    assert reg.connected
    assert reg.formulas["起承轉合"].stages == ("起", "承", "轉", "合")
    assert reg.formulas["雪花法"].stages == ()  # `必要階段: —` ＝流程型
    assert not reg.formulas["雪花法"].is_staged
    assert reg.problems == []


def test_registry_not_found_is_unconnected_not_empty(tmp_path: Path):
    """**「讀不到」與「0 套」是兩件事。** 混在一起就是新的假陰性（E2）。"""
    reg = load(tmp_path / "孤島" / "書")
    assert not reg.connected and not reg.formulas and reg.problems == []


def test_package_root_walks_up(tmp_path: Path):
    plant_package_root(tmp_path)
    deep = tmp_path / "書" / "story" / "大綱"
    deep.mkdir(parents=True)
    assert package_root(deep) == tmp_path


def test_registry_reports_duplicate_names(tmp_path: Path):
    plant_package_root(
        tmp_path,
        knowledge=(
            "# 結構公式\n\n## 二\n"
            "<!-- 結構公式: 起承轉合 | 必要階段: 起,承,轉,合 -->\n"
            "<!-- 結構公式: 起承轉合 | 必要階段: 起,承 -->\n"
        ),
    )
    reg = load(tmp_path / "書")
    assert len(reg.formulas) == 1 and any("重複" in p for p in reg.problems)


def test_registry_reports_empty_file(tmp_path: Path):
    plant_package_root(tmp_path, knowledge="# 結構公式\n\n## 一、三幕劇\n（沒有註記）\n")
    reg = load(tmp_path / "書")
    assert reg.connected and not reg.formulas
    assert any("一行" in p for p in reg.problems)


def test_registry_counts_annotated_sections(tmp_path: Path):
    plant_package_root(tmp_path)
    reg = load(tmp_path / "書")
    assert reg.sections == 3 and reg.annotated_sections == 3


def test_match_returns_primary_first(tmp_path: Path):
    plant_package_root(tmp_path)
    reg = load(tmp_path / "書")
    hits = reg.match("本 arc 用雪花法展開，骨架仍是起承轉合。")
    assert [f.name for f in hits] == ["雪花法", "起承轉合"]


# ------------------------------------------------------------------ 頂層階段 token


@pytest.mark.parametrize(
    "value,expected",
    [
        ("起·失衡開場（日常被打破）", "起"),
        ("承·上·召喚兌現", "承"),
        ("平凡失衡", "平凡失衡"),
        ("**轉**·露餡", "轉"),
        ("（輪回世界任務）破·瀕死低點", None),  # 只寫巢狀子公式，沒有頂層 token
        ("（未歸類）", None),
        ("", None),
    ],
)
def test_leading_stage_is_a_position_judgement(value: str, expected: str | None):
    """**位置判準**：token 必須在值的開頭。認不出來就回 None、不猜——
    **不得改成語意判準**（那是被駁回過三次的形狀）。"""
    assert leading_stage(value, ("起", "承", "轉", "合", "平凡失衡")) == expected


def test_leading_stage_prefers_the_longest_match():
    assert leading_stage("平凡失衡（開場）", ("平", "平凡失衡")) == "平凡失衡"


# ------------------------------------------------------------------ 投影本體


def test_projection_renders_the_correspondence_table(book: Path):
    report, stats = project(book)
    assert "| 起 | arc01 | 幕001 | 1 幕 |" in report
    assert stats.beats == 4 and stats.with_field == 4 and stats.no_token == 0


def test_consecutive_same_stage_beats_merge_into_one_row(tmp_path: Path):
    """**19.6× 壓縮的來源就是這個合併**（舊那支 58 KB 的檔投影出來 ≈1,300 字元）。"""
    arc = ARC_OK.replace("- 結構階段：承·順境（爬升）", "- 結構階段：起·再一格")
    report, _ = project(_book(tmp_path, arc=arc))
    assert "| 起 | arc01 | 幕001–幕002 | 2 幕 |" in report


def test_beat_numbers_keep_the_canonical_three_digit_form(book: Path):
    """`幕001` 不是 `幕1`——後者貼進別的檔就是一個懸空引用。"""
    report, _ = project(book)
    assert "幕1 " not in report and "幕001" in report


def test_missing_required_stage_is_a_suspect(tmp_path: Path):
    """**`outline-test:27` 自稱十天的那條集合差，第一次真的跑得動。**"""
    arc = "\n".join(
        ln for ln in ARC_OK.splitlines() if "轉·露餡" not in ln
    ).replace("## 幕003 · 逆境", "## 幕003 · 逆境\n- 結構階段：合·提早收")
    report, _ = project(_book(tmp_path, arc=arc))
    assert "[缺必要階段]" in report and "缺 **轉**" in report


def test_complete_coverage_reports_no_suspect(book: Path):
    report, _ = project(book)
    assert "### 三、可疑點" in report and "（無）" in report


def test_out_of_order_stages_are_reported_within_an_arc(tmp_path: Path):
    arc = ARC_OK.replace("- 結構階段：轉·露餡", "- 結構階段：起·倒回去")
    report, _ = project(_book(tmp_path, arc=arc))
    assert "[階段序非遞增]" in report


def test_a_new_cycle_in_the_next_arc_is_not_out_of_order(tmp_path: Path):
    """**跨 arc 不驗序。** 「這一次套的範圍是一整卷還是一個 arc」系統裡沒有機讀宣告，
    跨 arc 驗會把「arc01 收在合、arc02 從起重來」報成錯序——**正好與它要抓的病相反**。
    """
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc02.md").write_text(
        ARC_OK.replace("# arc01", "# arc02").replace("幕00", "幕10"), encoding="utf-8"
    )
    (book / "story" / "幕綱" / "_index.md").write_text(
        "# 幕綱索引\n全書順序：arc01 → arc02\n", encoding="utf-8"
    )
    report, stats = project(book)
    assert stats.arcs == 2 and "[階段序非遞增]" not in report


def test_flow_type_formula_does_no_set_difference(tmp_path: Path):
    book = _book(tmp_path, full=FULL.replace("起承轉合（單場任務內部另套序破急）。", "雪花法。"))
    report, _ = project(book)
    assert "（流程型公式·不對映幕）" in report
    assert "[缺必要階段]" not in report


# ------------------------------------------------------------------ 覆蓋率行


def test_beats_without_a_top_level_token_are_counted_not_guessed(tmp_path: Path):
    """**這是這支投影「看不見多少」的單一數字。** 不印它，就會拿部分覆蓋冒充全覆蓋。"""
    arc = ARC_OK.replace("- 結構階段：轉·露餡", "- 結構階段：（輪回世界任務）破·瀕死低點")
    report, stats = project(_book(tmp_path, arc=arc))
    assert stats.no_token == 1 and stats.no_token_beats == [3]
    assert "**1 幕的欄不以頂層階段 token 起頭**：幕003" in report
    assert "| （無頂層 token） | arc01 | 幕003 | 1 幕 |" in report


def test_unknown_formula_name_is_visible_in_coverage(tmp_path: Path):
    book = _book(tmp_path, full=FULL.replace("起承轉合（單場任務內部另套序破急）。", "英雄之旅十二段。"))
    report, stats = project(book)
    assert stats.unknown_names == 1
    assert "沒有一個 registry 裡的公式名" in report


def test_registry_unconnected_says_so_instead_of_zero_missing(tmp_path: Path):
    """**找不到 registry ≠ 「0 缺」。** 那一行要說出它算不了。"""
    book = _book(tmp_path / "孤島", root=False)
    report, _ = project(book)
    assert "registry：**未接**" in report
    assert "不是「0 缺」" in report


def test_missing_formula_section_is_shown_not_swallowed(tmp_path: Path):
    book = _book(tmp_path, full=FULL.replace("## 選用結構公式\n起承轉合（單場任務內部另套序破急）。\n\n", ""))
    report, stats = project(book)
    assert stats.with_section == 0 and "**缺 `## 選用結構公式` 節**" in report


# ------------------------------------------------------------------ 第五節：殘留偵測


def test_legacy_file_absent_still_prints_a_line(book: Path):
    """**0 也印**（抉擇 7）：不在時印「不在」，那一行才代表「這本書已經遷完了」。
    只在檔還在時才印，就是把「已遷移」與「工具沒讀到」變成同一個綠燈。"""
    report, stats = project(book)
    assert stats.legacy == []
    assert "舊檔：**不在**" in report
    assert "舊 `結構.{md,ai.md}`：0 支仍在" in report


@pytest.mark.parametrize("name", ["結構.md", "結構.ai.md"])
def test_legacy_file_present_is_reported_with_provenance(tmp_path: Path, name: str):
    """**兩種命名都要偵測到。** 舊名 `.md` 讓 `check`／`validate` 的 `rglob("*.ai.md")`
    掃不到，新名 `.ai.md` 曾讓 `_is_declarative` 早退三次——**沒有任何命名能讓它被驗**，
    那正是這一節存在的理由（`設計原則.md` A5：撤銷要從檔案系統看得出來）。
    """
    book = _book(tmp_path)
    d = book / "story" / "參照"
    d.mkdir(parents=True)
    (d / name).write_text("# 結構\n舊的手抄對應表\n", encoding="utf-8")
    report, stats = project(book)
    assert [n for n, _ in stats.legacy] == [name]
    assert f"`story/參照/{name}`" in report
    assert "**無機械來源**＝它是源" in report  # 戊 α 那一格要印出來
    assert "舊 `結構.{md,ai.md}`：1 支仍在" in report


def test_projection_scope_follows_the_beat_sheet_routing(tmp_path: Path):
    """路由沿用 `beat-sheet`：先找**未退役**的 `大綱/arcNN.md`，找不到才落 `01-大綱.md`。

    退役源（`已併入`）不是權威——判準與 `outline._check_coexistence` 同一個。
    """
    book = _book(tmp_path)
    d = book / "story" / "大綱"
    d.mkdir(parents=True)
    (d / "arc01.md").write_text(
        "# arc01\n\n> ⚠️ **已併入 `01-大綱.md`（2026-08-01）**。\n\n"
        "## 選用結構公式（本 arc 適用）\n雪花法。\n\n"
        "## 本段全文\n略\n\n## 本段收束與鉤子\n- 本段收束：站穩。\n",
        encoding="utf-8",
    )
    report, _ = project(book)
    # 退役檔宣告的「雪花法」不算數，落回 `01-大綱.md` 的「起承轉合」
    assert "← `01-大綱.md`：**起承轉合**" in report
    assert "雪花法" not in report
