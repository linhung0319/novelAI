"""`outline-lint` 的逐項測試。

**每一項都要有正反兩面**：只測「壞的會報」不夠——2026-07-27（功能 07）實測過一次
「閘門在自己身上重演 E2 最後一格」（判準寫得太寬，對著它誕生要抓的那一格報乾淨），
所以每一條也要測「好的不報」。
"""

from pathlib import Path

import pytest
from beat_metrics.outline import lint, lint_report
from conftest import plant_package_root

# ------------------------------------------------------------------ 語料建構


def _book(tmp_path: Path) -> Path:
    # **一定要種套件根**：不種的話 registry 回「未接」，第 12 項的 registry 那一半
    # 靜靜地不跑而測試全綠（見 `conftest.plant_package_root` 的註解）。
    plant_package_root(tmp_path)
    book = tmp_path / "書"
    (book / "story" / "大綱").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "chapters").mkdir(parents=True)
    (book / "story" / "幕綱" / "_順序.md").write_text(
        "# 幕綱索引\n全書順序：arc01 → arc02\n", encoding="utf-8"
    )
    (book / "story" / "幕綱" / "arc01.md").write_text(
        "# arc01\n\n## 本 arc 承諾\n- 不得發生：\n\n"
        "## 幕001 · 開場\n- 角色：甲\n- 時空：寺\n- 行動：走\n- 衝突：擋\n"
        "- 結果：過\n- 前因：—\n- 伏筆：埋[[伏筆:玉佛來歷]]\n- 結構階段：起\n",
        encoding="utf-8",
    )
    (book / "chapters" / "ch0001.md").write_text("正文\n", encoding="utf-8")
    return book


FULL_OK = """# 大綱

> 全書大綱。

## 選用結構公式
起承轉合。

## 故事全文（連續敘述）
從頭講一遍，涵蓋 arc01。

## 結局與題旨
- 結局：他看破機制（完整定義見 `00-摘要.md`「結局方向」）。
- 題旨：因為（先算計），導致（既救他也困他）。
"""

SCOPED_OK = """# arc02 · 走出去

> ⚠️ **暫定，待粗層鎖定**。
> 範圍說明：本 arc 涵蓋一段。

## 選用結構公式（本 arc 適用）
起承轉合套本 arc 一段（本段只走到「起」）。

## 本段全文（連續敘述）
這一段的情節，牽到 [[伏筆:玉佛來歷]]。

## 本段收束與鉤子
- 本段收束：站穩。
- 鉤子／懸而未決：他會不會被拉走。
- 對全書結局／題旨的關係：未定。
"""

INDEX_OK = "# 大綱索引（局部下沉）\n\n- arc02：走出去 —— 狀態：暫定，待粗層鎖定\n"


def _write(book: Path, full: str = FULL_OK, scoped: str = SCOPED_OK, index: str = INDEX_OK):
    (book / "story" / "01-大綱.md").write_text(full, encoding="utf-8")
    (book / "story" / "大綱" / "arc02.md").write_text(scoped, encoding="utf-8")
    (book / "story" / "大綱" / "_index.md").write_text(index, encoding="utf-8")


@pytest.fixture
def book(tmp_path: Path) -> Path:
    b = _book(tmp_path)
    _write(b)
    return b


# ------------------------------------------------------------------ 基準


def test_clean_book_reports_nothing(book: Path):
    assert lint(book) == []


def test_coverage_line_prints_even_when_clean(book: Path):
    """**0 也印。** 「我檢查了 0 筆」本身就是最有用的那一筆訊息（E2）。"""
    _, stats = lint_report(book)
    text = stats.render()
    assert "2 支大綱檔" in text
    assert "懸空 0" in text
    assert "卷級方向 0 節" in text


def test_missing_everything_raises(tmp_path: Path):
    """找不到任何大綱檔要硬報錯，不靜默回空集合（否則就是報平安的守衛）。"""
    from beat_metrics.scan import ScanError

    with pytest.raises(ScanError):
        lint(_book(tmp_path))


def test_skeleton_is_skipped(book: Path):
    (book / "story" / "大綱" / "arc03.md").write_text(
        "# arc03\n\n> ⚠️ **尚未產出**——空骨架。\n", encoding="utf-8"
    )
    problems, stats = lint_report(book)
    assert stats.skeletons == 1
    assert not any("arc03" in p for p in problems)


# ------------------------------------------------------------------ 第 1 項：節枚舉


def test_stray_section_is_reported_once_per_file(book: Path):
    _write(book, scoped=SCOPED_OK + "\n## 明確排除／壓著睡的線\n①…\n\n## fair-play 閉環\n②…\n")
    problems = [p for p in lint(book) if "枚舉外" in p]
    assert len(problems) == 1  # 一支檔一行（03 拍板的聚合判準）
    assert "2 個枚舉外" in problems[0]
    assert "明確排除" in problems[0] and "fair-play" in problems[0]


def test_section_label_ignores_parenthetical_and_bold(book: Path):
    _write(book, scoped=SCOPED_OK.replace("## 本段全文（連續敘述）", "## **本段全文**（連續敘述·暫定）"))
    assert not [p for p in lint(book) if "枚舉外" in p]


def test_status_table_section_is_now_enumerated(book: Path):
    """抉擇 2 B：`## 本 arc 伏筆狀態` 升格成 schema 定義的節，不再算枚舉外。"""
    _write(
        book,
        scoped=SCOPED_OK
        + "\n## 本 arc 伏筆狀態\n| 伏筆 | 本 arc 打算怎麼動 | 為什麼 |\n"
        "|---|---|---|\n| 玉佛來歷 | 不碰 | 留全書 |\n",
    )
    assert lint(book) == []


# ------------------------------------------------------------------ 第 2 項：檔頭狀態


def test_missing_header_status_is_reported(book: Path):
    _write(book, scoped=SCOPED_OK.replace("> ⚠️ **暫定，待粗層鎖定**。\n", ""))
    assert [p for p in lint(book) if "檔頭沒有狀態標記" in p]


def test_merged_file_still_in_place_is_a_note_not_a_problem(book: Path):
    """一世之尊不遷移，8 支報成問題只會製造警報疲勞——但它必須可見（A5）。"""
    _write(book, scoped=SCOPED_OK.replace("**暫定，待粗層鎖定**", "**已併入 `01-大綱.md`（2026-08-01）**"))
    problems, stats = lint_report(book)
    assert not [p for p in problems if "已併入" in p]
    assert stats.merged_in_place == ["arc02"]
    assert any("仍住在 `大綱/`" in n for n in stats.notes)


def test_retired_dir_requires_merged_mark(book: Path):
    retired = book / "story" / "大綱" / "_已併入"
    retired.mkdir()
    (retired / "arc01.md").write_text(SCOPED_OK, encoding="utf-8")
    assert [p for p in lint(book) if "住在 `_已併入/` 卻標" in p]


def test_retired_dir_with_merged_mark_is_clean(book: Path):
    retired = book / "story" / "大綱" / "_已併入"
    retired.mkdir()
    (retired / "arc01.md").write_text(
        SCOPED_OK.replace("**暫定，待粗層鎖定**", "**已併入 `01-大綱.md`（2026-08-01）**"),
        encoding="utf-8",
    )
    _write(book, index=INDEX_OK + "- arc01：起 —— 狀態：已併入 01-大綱.md（2026-08-01）\n")
    problems, stats = lint_report(book)
    assert stats.retired == 1
    # 索引列序：arc02 在 arc01 之前 → 該報，其餘乾淨
    assert [p for p in problems if "列序非遞增" in p]
    assert not [p for p in problems if "已併入" in p]


# ------------------------------------------------------------------ 第 3 項：索引視圖


def test_index_view_must_match_folder_both_ways(book: Path):
    _write(book, index="# 大綱索引\n\n- arc07：不存在的 —— 狀態：暫定\n")
    problems = lint(book)
    assert [p for p in problems if "沒有列" in p]
    assert [p for p in problems if "指向不存在的 arc 檔" in p]


def test_index_row_order_must_increase(book: Path):
    (book / "story" / "大綱" / "arc03.md").write_text(
        SCOPED_OK.replace("arc02", "arc03"), encoding="utf-8"
    )
    _write(
        book,
        index="# 大綱索引\n\n- arc03：後面的 —— 狀態：暫定\n- arc02：前面的 —— 狀態：暫定\n",
    )
    problems = [p for p in lint(book) if "列序非遞增" in p]
    assert len(problems) == 1
    assert "arc03 之後是 arc02" in problems[0]


def test_index_must_have_no_sections(book: Path):
    """索引的節枚舉是**空集合**（`大綱.schema.md`「索引檔」：一列只寫
    `arcNN：名稱 —— 狀態`），同 `DERIVED_SECTIONS["風格"]` ＝空 tuple 的作法。

    實測一世之尊長出了 `## 卷一整體結構`——**那是選用結構公式的第四份**（權威在
    各大綱檔的 `## 選用結構公式`，第 12 項守），而且它指向 11 已廢除的
    `參照/結構.md`。在功能 12 之前零守衛：`outline-lint` 的節枚舉只套 `OutlineFile`
    （arc／全書版），索引走 `_check_index` 另一條路。
    """
    _write(book, index=INDEX_OK + "\n## 卷一整體結構\n\n起承轉合：起＝arc01｜承＝arc02。\n")
    problems = [p for p in lint(book) if "`##` 節" in p]
    assert len(problems) == 1
    assert "卷一整體結構" in problems[0]
    assert "索引不複述" in problems[0]


def test_clean_index_has_no_sections(book: Path):
    """正例：只有清單列的索引不報，而覆蓋率行照樣印那個 0。"""
    _write(book)
    assert [p for p in lint(book) if "`##` 節" in p] == []
    _, stats = lint_report(book)
    assert stats.index_sections == 0
    assert "枚舉外的 `##` 節 0 個" in stats.render()


# ------------------------------------------------------------------ 第 4 項：引用


def test_dangling_beat_and_chapter_refs(book: Path):
    _write(book, scoped=SCOPED_OK.replace("這一段的情節", "接 幕999（正文 ch9999）"))
    problems = lint(book)
    assert [p for p in problems if "懸空的 幕 引用" in p and "幕999" in p]
    assert [p for p in problems if "懸空的 章 引用" in p and "ch9999" in p]


def test_bare_arc_token_is_never_reported(book: Path):
    """**裸 arc token 沒有可靠訊號，所以不報**（E1：驗不到就不宣稱）。

    三種合法狀態與打錯字在檔案系統上長得一模一樣：尚未下沉的未來 arc（實測 arc12
    被引用 70 次）／規劃中的中間段／全書模式寫的卷、那幾個 arc 從來沒有 scoped 檔。
    只有寫成路徑的那一半（`story/大綱/arcNN.md`）由第 9 項守。
    """
    _write(book, scoped=SCOPED_OK.replace("這一段的情節", "這條線留 arc09 收、arc03 起頭"))
    problems, stats = lint_report(book)
    assert not [p for p in problems if "arc 引用" in p]
    assert stats.arc_refs > stats.arc_resolved  # 誠實印出「有多少指不到」


# ------------------------------------------------------------------ 第 5 項：伏筆 registry


def test_unknown_foreshadow_name_is_reported(book: Path):
    _write(book, scoped=SCOPED_OK.replace("玉佛來歷", "沒人聽過的線"))
    problems = [p for p in lint(book) if "registry 查無" in p]
    assert len(problems) == 1
    assert "提示不是門檻" in problems[0]


def test_object_file_counts_as_registry(book: Path):
    (book / "story" / "物件").mkdir()
    (book / "story" / "物件" / "小玉佛.md").write_text("# 小玉佛\n", encoding="utf-8")
    _write(book, scoped=SCOPED_OK.replace("玉佛來歷", "小玉佛"))
    assert not [p for p in lint(book) if "registry 查無" in p]


# ------------------------------------------------------------------ 第 6 項：結局與題旨


def test_undecided_ending_is_reported(book: Path):
    _write(book, full=FULL_OK.replace("他看破機制", "大概是他看破機制，細節未定"))
    assert [p for p in lint(book) if "模糊字樣" in p]


def test_thesis_must_be_a_causal_sentence(book: Path):
    _write(book, full=FULL_OK.replace("因為（先算計），導致（既救他也困他）", "他漸漸長大"))
    assert [p for p in lint(book) if "不是可檢查的因果句" in p]


def test_ending_copy_state_is_printed_only(book: Path):
    """抉擇 5 A：`結局：` 有沒有回指摘要——**只印、不擋**。"""
    _, stats = lint_report(book)
    assert stats.ending_copy.startswith("否")
    _write(book, full=FULL_OK.replace("（完整定義見 `00-摘要.md`「結局方向」）", "（此處完整複述一遍）"))
    problems, stats = lint_report(book)
    assert stats.ending_copy.startswith("**是**")
    assert not [p for p in problems if "結局複本" in p]


# ------------------------------------------------------------------ 第 7 項：收束三欄


def test_closing_section_needs_three_labels(book: Path):
    _write(book, scoped=SCOPED_OK.replace("- 對全書結局／題旨的關係：未定。\n", ""))
    problems = [p for p in lint(book) if "本段收束與鉤子" in p]
    assert len(problems) == 1
    assert "對全書結局" in problems[0]


# ------------------------------------------------------------------ 第 8 項：並存


def test_coexistence_is_normal_information(book: Path):
    """抉擇 4 A：合法化。未併入的 scoped 只進覆蓋率行，不是問題。"""
    problems, stats = lint_report(book)
    assert stats.unmerged_scoped == 1
    assert stats.both_homed == 0
    assert not [p for p in problems if "兩邊都有內容" in p]


def test_same_arc_in_both_homes_is_a_problem(book: Path):
    _write(book, full=FULL_OK.replace("涵蓋 arc01", "涵蓋 arc01–arc02"))
    problems = [p for p in lint(book) if "兩邊都有內容" in p]
    assert len(problems) == 1 and "arc02" in problems[0]


def test_pointer_in_backticks_is_not_coverage(book: Path):
    """`story/大綱/arc02.md` 是指標，不是「本檔已涵蓋 arc02」——不剝反引號的話，
    這一項會把「守留白紀律、只指路」誤判成「兩個家」。"""
    _write(book, full=FULL_OK.replace("涵蓋 arc01。", "涵蓋 arc01。卷二方向見 `story/大綱/arc02.md`。"))
    assert not [p for p in lint(book) if "兩邊都有內容" in p]


# ------------------------------------------------------------------ 第 9 項：目的地


def test_missing_book_path_is_reported(book: Path):
    _write(book, scoped=SCOPED_OK.replace("這一段的情節", "理由見 `story/參照/裁決流.md`"))
    assert [p for p in lint(book) if "指名的路徑不存在" in p]


def test_schema_and_placeholder_refs_are_not_destinations(book: Path):
    """一支完全合法的大綱不該因為引用了自己的 schema 就被報成目的地不存在。"""
    _write(
        book,
        scoped=SCOPED_OK.replace(
            "這一段的情節",
            "格式見 `結構定義/大綱.schema.md`，未來的檔是 `story/大綱/arcNN.md`，"
            "卷一是 `story/大綱/arc01–arc04.md`",
        ),
    )
    assert not [p for p in lint(book) if "指名的路徑不存在" in p]


# ------------------------------------------------------------------ 第 10 項：伏筆意圖表


def test_status_table_must_be_three_columns(book: Path):
    _write(
        book,
        scoped=SCOPED_OK
        + "\n## 本 arc 伏筆狀態\n| 伏筆 | 埋設 | 收回 | 備註 |\n|---|---|---|---|\n"
        "| 玉佛來歷 | arc01 | 未收 | 留全書 |\n",
    )
    assert [p for p in lint(book) if "有 4 欄的列" in p]


def test_status_table_must_not_carry_settled_facts(book: Path):
    _write(
        book,
        scoped=SCOPED_OK
        + "\n## 本 arc 伏筆狀態\n| 伏筆 | 本 arc 打算怎麼動 | 為什麼 |\n|---|---|---|\n"
        "| 玉佛來歷 | 收 | 幕001 埋的，正文 ch0001 |\n",
    )
    problems = [p for p in lint(book) if "既成事實 token" in p]
    assert len(problems) == 1
    assert "幕001" in problems[0] and "ch0001" in problems[0]


# ------------------------------------------------------------------ 第 11 項：卷級方向

VOLUME = "\n## 卷級方向（卷一·本卷權威）\n本卷主事件：…\n"


def test_volume_section_needs_a_token(book: Path):
    _write(book, scoped=SCOPED_OK + "\n## 卷級方向（本卷權威）\n…\n")
    assert [p for p in lint(book) if "沒有卷 token" in p]


def test_volume_token_must_be_unique_across_files(book: Path):
    (book / "story" / "大綱" / "arc03.md").write_text(
        SCOPED_OK.replace("arc02", "arc03") + VOLUME, encoding="utf-8"
    )
    _write(
        book,
        scoped=SCOPED_OK + VOLUME,
        index="# 大綱索引\n\n- arc02：走出去 —— 狀態：暫定\n- arc03：再走 —— 狀態：暫定\n",
    )
    problems = [p for p in lint(book) if "出現在 2 支檔" in p]
    assert len(problems) == 1 and "卷一" in problems[0]


def test_other_files_may_only_point_at_the_volume_section(book: Path):
    (book / "story" / "大綱" / "arc03.md").write_text(
        SCOPED_OK.replace("arc02", "arc03").replace(
            "這一段的情節", "卷級方向：本卷要打的是同一件事（複述）"
        ),
        encoding="utf-8",
    )
    _write(
        book,
        scoped=SCOPED_OK + VOLUME,
        index="# 大綱索引\n\n- arc02：走出去 —— 狀態：暫定\n- arc03：再走 —— 狀態：暫定\n",
    )
    assert [p for p in lint(book) if "沒有帶指標" in p]


def test_pointer_to_the_volume_section_is_fine(book: Path):
    (book / "story" / "大綱" / "arc03.md").write_text(
        SCOPED_OK.replace("arc02", "arc03").replace(
            "這一段的情節", "卷級方向見 `story/大綱/arc02.md`，本檔不複述"
        ),
        encoding="utf-8",
    )
    _write(
        book,
        scoped=SCOPED_OK + VOLUME,
        index="# 大綱索引\n\n- arc02：走出去 —— 狀態：暫定\n- arc03：再走 —— 狀態：暫定\n",
    )
    assert not [p for p in lint(book) if "沒有帶指標" in p]


def test_retired_dir_must_not_hold_a_volume_section(book: Path):
    retired = book / "story" / "大綱" / "_已併入"
    retired.mkdir()
    (retired / "arc01.md").write_text(
        SCOPED_OK.replace("**暫定，待粗層鎖定**", "**已併入 `01-大綱.md`（2026-08-01）**") + VOLUME,
        encoding="utf-8",
    )
    _write(book, index=INDEX_OK + "- arc01：起 —— 狀態：已併入\n")
    problems = [p for p in lint(book) if "底下有 `## 卷級方向" in p]
    assert len(problems) == 1


# ------------------------------------------------------------------ 第 12 項
# `## 選用結構公式`（2026-07-28 功能 11）。它守的是本輪新增的兩條格式承諾：
# 公式名要命中 `技巧知識庫/結構公式.md` 的 registry、α 條目不得記沿革。


def test_missing_formula_section_is_reported(book: Path):
    _write(book, full=FULL_OK.replace("## 選用結構公式\n起承轉合。\n\n", ""))
    assert [p for p in lint(book) if "缺 `## 選用結構公式` 節" in p]


def test_formula_section_present_is_not_reported(book: Path):
    _write(book)
    assert not [p for p in lint(book) if "選用結構公式" in p]


def test_formula_name_must_hit_the_registry(book: Path):
    """**這是第 12 項的核心那一條。** 宣告一套沒登記的公式 ＝ `structure-project`
    查不到必要階段、集合差整節算不了，**而報表會印得完全正常**（E2 最後一格）。"""
    _write(book, full=FULL_OK.replace("起承轉合。", "英雄之旅十二段。"))
    problems = [p for p in lint(book) if "registry 裡的公式名" in p]
    assert len(problems) == 1 and "三幕劇" in problems[0]  # hint 要列出 registry


def test_registry_not_connected_means_the_check_is_skipped_not_passed(tmp_path: Path):
    """**找不到套件根 ≠ 0 個問題。** 覆蓋率行要說出「registry 未接」，
    否則「檢查過了、乾淨」與「檢查沒跑」印出來一模一樣。"""
    book = tmp_path / "孤島" / "書"
    (book / "story" / "大綱").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "_順序.md").write_text(
        "# 幕綱索引\n全書順序：arc01\n", encoding="utf-8"
    )
    (book / "story" / "幕綱" / "arc01.md").write_text("# arc01\n\n## 本 arc 承諾\n", encoding="utf-8")
    (book / "story" / "01-大綱.md").write_text(
        FULL_OK.replace("起承轉合。", "英雄之旅十二段。"), encoding="utf-8"
    )
    problems, stats = lint_report(book)
    assert not stats.registry_connected
    assert "registry **未接**" in stats.render()
    assert not [p for p in problems if "registry 裡的公式名" in p]


def test_alpha_bullet_must_not_carry_a_date(book: Path):
    """α **只標「這裡是變形、變成什麼」**；沿革屬裁決流。舊 `結構.ai.md` 的檔頭
    blockquote 就是這條規則零實作長出來的（111 → 6,323 字元＝57.0×）。"""
    _write(
        book,
        full=FULL_OK.replace(
            "起承轉合。",
            "起承轉合。\n- **α（變形）**：轉與合同落在 arc04（2026-07-21 作者拍板）。",
        ),
    )
    assert [p for p in lint(book) if "α 條目有 1 條帶日期" in p]


def test_alpha_bullet_without_a_date_is_fine(book: Path):
    _write(
        book,
        full=FULL_OK.replace(
            "起承轉合。", "起承轉合。\n- **α（變形）**：轉與合同落在 arc04，非錯序。"
        ),
    )
    assert not [p for p in lint(book) if "α 條目" in p]


def test_registry_problems_surface_as_problems(tmp_path: Path):
    """registry 自己壞掉（名稱重複）也要報——**它是 12 支大綱檔共用的那份真相**。"""
    plant_package_root(
        tmp_path,
        knowledge=(
            "# 結構公式\n\n## 二、起承轉合\n"
            "<!-- 結構公式: 起承轉合 | 必要階段: 起,承,轉,合 -->\n"
            "<!-- 結構公式: 起承轉合 | 必要階段: 起,承,轉 -->\n"
        ),
    )
    book = tmp_path / "書"
    (book / "story" / "大綱").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "_順序.md").write_text(
        "# 幕綱索引\n全書順序：arc01\n", encoding="utf-8"
    )
    (book / "story" / "幕綱" / "arc01.md").write_text("# arc01\n\n## 本 arc 承諾\n", encoding="utf-8")
    (book / "story" / "01-大綱.md").write_text(FULL_OK, encoding="utf-8")
    assert [p for p in lint(book) if "重複" in p]


def test_coverage_line_counts_declarations(book: Path):
    _write(book)
    _, stats = lint_report(book)
    assert stats.formula_files == 2 and stats.formula_unknown == 0
    assert stats.registry_connected and stats.registry_formulas == 3
    assert "`## 選用結構公式` 2 支檔宣告" in stats.render()
