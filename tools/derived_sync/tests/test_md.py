"""`md.py`：本套件唯一一份 Markdown 解析層（2026-07-28 功能 14，抉擇 1 D）。

**這支測試檔存在的理由是一個實測過的分歧，不是覆蓋率**：在 `md.py` 之前，同一個
套件裡有六份 front-matter 解析器，沿三個獨立軸分歧，而**沒有任何守衛**——一支
合法的 `主題: 修煉體系   # 檔名即 ID` 會讓 `world-lint` 報「與檔名不一致」，而
`style-lint`／`summary-lint` 的同名函式會正確處理，**`世界觀.schema.md:57` 的範例
自己就是這樣寫的**。

所以這裡釘的是**「四支 lint 對同一份輸入必須得到同一個 dict」**：不是測 `md.py`
自己，是測「沒有人又長出第七份」。
"""

from pathlib import Path

import pytest
from derived_sync import char_lint, emit, style_lint, summary_lint, world_lint
from derived_sync.md import (
    front_matter,
    front_matter_of,
    lede_of,
    section_body,
    split_frontmatter,
    table_rows,
)

# 三個分歧軸各出一格：`#` 註解／全形冒號／中文鍵
DIVERGENT = """\
---
主題: 修煉體系   # 檔名即 ID，這裡只是複述
基調： 哥特恐怖＋黑色幽默
generated-from: abc123def456
---

# 修煉體系

第一段。
"""


def test_all_four_lints_share_one_front_matter_parser():
    """**這一格是本檔的全部理由。** 四支 lint 曾各有一份，答案不同。"""
    parsers = [
        char_lint.front_matter_of,
        world_lint.front_matter_of,
        style_lint.front_matter_of,
        summary_lint.front_matter_of,
        emit.front_matter_of,
    ]
    assert len({id(f) for f in parsers}) == 1, (
        "有人又長出第二份 front-matter 解析器。"
        "同一個 import 空間裡的複製沒有任何政策在支持它（零相依只解釋得了跨套件那 42 份）"
    )


def test_comment_is_stripped(tmp_path: Path):
    """`#` 之後是註解——`char`／`world` 那兩份在功能 14 之前不剝，於是跨檔比對對著註解比。"""
    fm = front_matter(DIVERGENT)
    assert fm is not None
    assert fm["主題"] == "修煉體系"


def test_fullwidth_colon_and_chinese_keys():
    """作者會把冒號打成全形；而 `00-摘要.ai.md` 的鍵**全部是中文**。

    `validate` 在功能 14 之前用 `^([A-Za-z0-9_-]+):`——對這兩格**一個字都讀不到**，
    於是「front-matter 缺某鍵」那條檢查在摘要軸上是空頭承諾（V13）。
    """
    fm = front_matter(DIVERGENT)
    assert fm is not None
    assert fm["基調"] == "哥特恐怖＋黑色幽默"
    assert set(fm) == {"主題", "基調", "generated-from"}


def test_no_front_matter_is_none_not_empty_dict():
    """「沒有 front-matter」與「front-matter 是空的」是兩件事（前者＝骨架）。"""
    assert front_matter("# 標題\n\n內文\n") is None
    assert front_matter("---\n---\n\n內文\n") == {}


def test_unclosed_front_matter_counts_as_none():
    assert split_frontmatter("---\n主題: X\n\n沒有收尾\n") == (
        None,
        "---\n主題: X\n\n沒有收尾\n",
    )


def test_front_matter_of_missing_file_is_none(tmp_path: Path):
    assert front_matter_of(tmp_path / "不存在.ai.md") is None


def test_section_body_distinguishes_absent_from_empty():
    text = "# T\n\n## 甲\n\n內容\n\n## 乙\n"
    assert [ln for ln in section_body(text, "甲") or [] if ln.strip()] == ["內容"]
    assert [ln for ln in section_body(text, "乙") or [] if ln.strip()] == []
    assert section_body(text, "乙") is not None  # 節在但空的
    assert section_body(text, "丙") is None  # 節根本不存在


def test_section_title_matches_by_prefix():
    """作者會在標題後加註記（`## 基調（氛圍／筆調）`）。"""
    body = section_body("## 基調（氛圍／筆調）\n一句\n", "基調")
    assert [ln for ln in body or [] if ln.strip()] == ["一句"]


def test_table_rows_skips_header_not_only_the_separator():
    """只跳分隔列會把**表頭**當成一筆資料——`world_lint` 實作時實測到的第一版 bug。"""
    lines = "| 主題 | 維度 |\n|---|---|\n| 修煉體系 | 自身 |".split("\n")
    assert table_rows(lines) == [["修煉體系", "自身"]]


def test_table_without_separator_yields_zero_rows():
    """缺分隔列時回 0 列，而那個 0 會出現在覆蓋率行，不是靜默通過。"""
    assert table_rows(["| 甲 | 乙 |", "| 丙 | 丁 |"]) == []


def test_lede_skips_h1_and_bullet():
    assert lede_of("# 修煉體系\n\n- 一句話定位\n") == "一句話定位"
    assert lede_of("# 只有標題\n") == ""


@pytest.mark.parametrize(
    "mod",
    [char_lint, world_lint, style_lint, summary_lint, emit],
    ids=["char", "world", "style", "summary", "emit"],
)
def test_no_module_keeps_a_private_key_regex(mod):
    """第七份複製最可能的長法是「只複製那個 regex」。"""
    assert not hasattr(mod, "_KEY_RE"), f"{mod.__name__} 又有一份私有的鍵 regex"
