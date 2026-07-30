"""`ch-lint` 的正反例。

每一項檢查都要有**反例會報、正例不報**兩個方向——只測「壞的會報」的檢查器，無法
分辨「它在守」與「它把全部東西都報成壞的」（同 `test_lint.py` 的紀律）。

fixture 一律自造：一世之尊在這支閘門的 8 項結構檢查上**全清**（108 個錨點 0 個對不到
registry、0 非單調、0 跨章、0 人性寫法、93 章對應幕 0 不一致），那正是它作為乾淨基準
的價值——真實語料的回歸走 `test_golden_ch_lint.py`。
"""

from __future__ import annotations

import pytest

from beat_metrics.chapters import NOTE_CHARS, lint_report
from beat_metrics.scan import ScanError

INDEX = "# 幕綱索引\n\n- 全書順序：arc01 → arc02\n"

ARC01 = """# arc01 · 起

## 本 arc 承諾

- 節奏檔位：開頭段

## 幕001 · 開場
- 角色：林小凡
- 時空：老宅／清晨
- 行動：翻遍藥典找解毒法
- 衝突：藥石罔效
- 結果：確認無解
- 前因：—
- 伏筆：—
- 結構階段：平凡失衡

## 幕002 · 立誓
- 角色：林小凡、母親
- 時空：老宅／夜
- 行動：向母親發誓親自去取寒髓
- 衝突：取者無人生還
- 結果：立誓獨力奪髓
- 前因：[[幕001]]
- 伏筆：—
- 結構階段：召喚衝突
"""

ARC02 = """# arc02 · 承

## 本 arc 承諾

- 節奏檔位：常態段

## 幕101 · 奪髓
- 角色：林小凡、血衣老者
- 時空：北域冰原／第三夜
- 行動：闖禁地取寒髓
- 衝突：老者出手阻攔
- 結果：奪得寒髓
- 前因：[[幕002]]
- 伏筆：—
- 結構階段：磨練成長
"""

FM = """---
generated-from: deadbeef
generated-at: 2026-07-27
對應幕: {beats}
所屬arc: {arc}
POV: {{ 角色: 林小凡, 人稱: 第三人稱有限, 距離: Deep POV }}
基調參照: 00-摘要.md「基調」
風格: 風格.ai.md
狀態: 草稿
---
"""

INDEX_HEAD = """---
generated-from: cafe
generated-at: 2026-07-27
---
## 章節索引
| 章 | 對應幕 | 所屬 arc | POV | 風格 | 狀態 | 備註 |
|----|--------|----------|-----|------|------|------|
"""


def _book(tmp_path, chapters=None, index_rows=None, arcs=None, style=True):
    """造一本最小的書。`chapters` ＝ {stem: (正文, 對應幕, arc)}。

    `style=False` 造一本**沒有風格檔**的書——那是第 11 項（`風格` 欄的目的地
    存在性，2026-07-27 功能 07）要抓的狀態。
    """
    if style:
        d_style = tmp_path / "story" / "設定" / "風格"
        d_style.mkdir(parents=True)
        (d_style / "風格.ai.md").write_text(
            "---\ngenerated-from: sty\ngenerated-at: 2026-07-27\n語域: 書面·古典\n---\n",
            encoding="utf-8",
        )
    beats = tmp_path / "story" / "幕綱"
    beats.mkdir(parents=True)
    (beats / "_順序.md").write_text(INDEX, encoding="utf-8")
    for name, text in (arcs or {"arc01": ARC01, "arc02": ARC02}).items():
        (beats / f"{name}.md").write_text(text, encoding="utf-8")

    d = tmp_path / "chapters"
    d.mkdir(parents=True)
    chapters = chapters or {}
    rows = []
    for stem, (prose, decl, arc) in chapters.items():
        (d / f"{stem}.md").write_text(prose, encoding="utf-8")
        (d / f"{stem}.ai.md").write_text(
            FM.format(beats=decl, arc=arc), encoding="utf-8"
        )
        shown = decl.strip("[]").replace(", ", "–")
        rows.append(f"| {stem} | {shown} | {arc} | 林小凡 | 風格.ai.md | 草稿 |  |")
    body = INDEX_HEAD + "\n".join(index_rows if index_rows is not None else rows) + "\n"
    (d / "_index.ai.md").write_text(body, encoding="utf-8")
    return tmp_path


def _only(problems, needle):
    return [p for p in problems if needle in p]


CLEAN = {
    "ch0001": ("# ch0001\n\n<!-- 幕001 -->\n正文。\n\n<!-- 幕002 -->\n正文。\n", "[幕001, 幕002]", "arc01"),
    "ch0002": ("# ch0002\n\n<!-- 幕101 -->\n正文。\n", "[幕101]", "arc02"),
}


# --------------------------------------------------------------- 正例

def test_clean_book_reports_nothing(tmp_path):
    problems, stats = lint_report(_book(tmp_path, dict(CLEAN)))
    assert problems == []
    assert (stats.sources, stats.anchors, stats.metas) == (2, 3, 2)
    assert (stats.beats_checked, stats.beats_mismatch) == (2, 0)
    assert (stats.rows_checked, stats.rows_mismatch) == (2, 0)


def test_transition_anchor_is_legal(tmp_path):
    """`<!-- 幕A→幕B -->` 是 schema 明訂的合法形，不進單調序列也不算跨章。"""
    ch = {
        "ch0001": (
            "# ch0001\n\n<!-- 幕001 -->\n甲。\n\n<!-- 幕001→幕002 -->\n過渡。\n\n<!-- 幕002 -->\n乙。\n",
            "[幕001, 幕002]",
            "arc01",
        )
    }
    problems, stats = lint_report(_book(tmp_path, ch))
    assert problems == []
    assert (stats.anchors, stats.transitions) == (2, 1)


def test_book_without_chapters_is_clean_and_says_so(tmp_path):
    """還沒動筆的書：0 也要印，不能靜默跳過（E2 推論）。"""
    problems, stats = lint_report(_book(tmp_path))
    assert problems == []
    assert stats.sources == 0 and stats.registry == 3
    assert "3 幕還沒寫成正文" in "".join(stats.notes)


# --------------------------------------------------------------- 反例：錨點

def test_anchor_pointing_at_unknown_beat(tmp_path):
    ch = {"ch0001": ("# ch0001\n\n<!-- 幕999 -->\n正文。\n", "[幕999]", "arc01")}
    problems, stats = lint_report(_book(tmp_path, ch))
    assert _only(problems, "幕999 指向不存在的幕")
    assert stats.unknown_beats == 1


def test_anchors_must_be_monotonic_within_a_chapter(tmp_path):
    ch = {
        "ch0001": (
            "# ch0001\n\n<!-- 幕002 -->\n乙。\n\n<!-- 幕001 -->\n甲。\n",
            "[幕001, 幕002]",
            "arc01",
        )
    }
    problems, _ = lint_report(_book(tmp_path, ch))
    assert _only(problems, "章內錨點須單調遞增")


def test_same_beat_split_across_two_chapters(tmp_path):
    ch = {
        "ch0001": ("# ch0001\n\n<!-- 幕001 -->\n前半。\n", "[幕001]", "arc01"),
        "ch0002": ("# ch0002\n\n<!-- 幕001 -->\n後半。\n", "[幕001]", "arc01"),
    }
    problems, _ = lint_report(_book(tmp_path, ch))
    assert _only(problems, "一幕不可跨章切開")


def test_transition_anchor_endpoints(tmp_path):
    ch = {
        "ch0001": (
            "# ch0001\n\n<!-- 幕001 -->\n甲。\n\n<!-- 幕001→幕888 -->\n過渡。\n",
            "[幕001]",
            "arc01",
        ),
        "ch0002": (
            "# ch0002\n\n<!-- 幕002 -->\n乙。\n\n<!-- 幕002→幕001 -->\n倒退。\n",
            "[幕002]",
            "arc01",
        ),
    }
    problems, _ = lint_report(_book(tmp_path, ch))
    assert _only(problems, "的終點指向不存在的幕")
    assert _only(problems, "兩端不是遞增的")


def test_human_written_anchor_is_reported_not_rewritten(tmp_path):
    ch = {
        "ch0001": (
            "# ch0001\n\n<!-- 幕001 -->\n甲。\n\n--- 幕002 ---\n\n乙。\n",
            "[幕001, 幕002]",
            "arc01",
        )
    }
    problems, stats = lint_report(_book(tmp_path, ch))
    hit = _only(problems, "是人性寫法")
    assert hit and "本閘門只報、不代改" in hit[0]
    assert stats.normalize_candidates == 1
    # 正規化候選**不**算成錨點：它還沒是錨點，算進去會讓覆蓋率行說謊。
    assert stats.anchors == 1


def test_malformed_comment_with_a_beat_number(tmp_path):
    ch = {
        "ch0001": (
            "# ch0001\n\n<!-- 幕001 -->\n甲。\n\n<!-- 幕 2 -->\n乙。\n",
            "[幕001]",
            "arc01",
        )
    }
    problems, _ = lint_report(_book(tmp_path, ch))
    assert _only(problems, "含幕號卻不是標準錨點")


def test_ordinary_editorial_comment_is_not_flagged(tmp_path):
    """一般註解不冤枉——只有「註解裡有幕號」才算疑似錨點。"""
    ch = {
        "ch0001": (
            "# ch0001\n\n<!-- 幕001 -->\n甲。\n\n<!-- 這段待改 -->\n乙。\n",
            "[幕001]",
            "arc01",
        )
    }
    problems, _ = lint_report(_book(tmp_path, ch))
    assert problems == []


def test_four_digit_beat_number_is_not_truncated(tmp_path):
    """V9 的回歸：schema 曾寫「三位數」，而 arc10 之後必然溢出。

    照舊 schema 寫成 `幕(\\d{3})` 的解析器會把 `幕1001` 讀成 `幕100`——不報錯，
    給出一整批假的不一致。本輪第一次量測就踩過。
    """
    arc11 = ARC01.replace("# arc01", "# arc11").replace("幕001", "幕1001").replace(
        "幕002", "幕1002"
    )
    ch = {
        "ch0001": (
            "# ch0001\n\n<!-- 幕1001 -->\n甲。\n\n<!-- 幕1002 -->\n乙。\n",
            "[幕1001, 幕1002]",
            "arc11",
        )
    }
    book = _book(tmp_path, ch, arcs={"arc11": arc11})
    (book / "story" / "幕綱" / "_順序.md").write_text(
        "# 幕綱索引\n\n- 全書順序：arc11\n", encoding="utf-8"
    )
    problems, stats = lint_report(book)
    assert problems == []
    assert stats.registry == 2


# --------------------------------------------------------------- 反例：對應幕

def test_declared_beat_without_anchor(tmp_path):
    """`write-test` 測試1 說這是「最高優先級的機械事實」——2026-07-27 前無工具。"""
    ch = {
        "ch0001": ("# ch0001\n\n<!-- 幕001 -->\n甲。\n", "[幕001, 幕002]", "arc01")
    }
    problems, stats = lint_report(_book(tmp_path, ch))
    assert _only(problems, "宣告涵蓋 幕002，正文找不到")
    assert stats.beats_mismatch == 1


def test_anchor_outside_declared_range(tmp_path):
    ch = {
        "ch0001": (
            "# ch0001\n\n<!-- 幕001 -->\n甲。\n\n<!-- 幕002 -->\n乙。\n",
            "[幕001]",
            "arc01",
        )
    }
    problems, _ = lint_report(_book(tmp_path, ch))
    assert _only(problems, "卻不在")


def test_arc_must_match_where_the_anchors_live(tmp_path):
    ch = {"ch0001": ("# ch0001\n\n<!-- 幕101 -->\n甲。\n", "[幕101]", "arc01")}
    problems, _ = lint_report(_book(tmp_path, ch))
    assert _only(problems, "`所屬arc` 寫 arc01，但正文錨點落在 arc02")


def test_single_beat_written_as_a_same_valued_pair(tmp_path):
    """抉擇 5 B：單幕寫 `[幕N]`。同型問題**聚合成一行**，不是一支檔一行。"""
    ch = {
        "ch0001": ("# ch0001\n\n<!-- 幕001 -->\n甲。\n", "[幕001, 幕001]", "arc01"),
        "ch0002": ("# ch0002\n\n<!-- 幕101 -->\n乙。\n", "[幕101, 幕101]", "arc02"),
    }
    problems, _ = lint_report(_book(tmp_path, ch))
    hit = _only(problems, "把單幕寫成")
    assert len(hit) == 1 and "2 支章衍生檔" in hit[0]
    assert "ch0001、ch0002" in hit[0]


def test_loose_beat_form(tmp_path):
    ch = {"ch0001": ("# ch0001\n\n<!-- 幕001 -->\n甲。\n", "幕001", "arc01")}
    problems, _ = lint_report(_book(tmp_path, ch))
    assert _only(problems, "不是標準寫法")


def test_unparsable_beat_form(tmp_path):
    ch = {"ch0001": ("# ch0001\n\n<!-- 幕001 -->\n甲。\n", "待補", "arc01")}
    problems, _ = lint_report(_book(tmp_path, ch))
    assert _only(problems, "`對應幕` 解析不了")


# --------------------------------------------------------------- 反例：front-matter

def test_missing_required_keys(tmp_path):
    book = _book(tmp_path, dict(CLEAN))
    p = book / "chapters" / "ch0001.ai.md"
    p.write_text(
        p.read_text(encoding="utf-8").replace("風格: 風格.ai.md\n", ""), encoding="utf-8"
    )
    problems, _ = lint_report(book)
    assert _only(problems, "front-matter 缺 風格")


def test_style_reference_must_point_at_an_existing_file(tmp_path):
    """第 11 項（2026-07-27 功能 07 抉擇 6 A）：`風格` 欄指向的檔要真的在。

    **schema 的多世界 forward-compat（`風格/主世界.md`）0 本書用過**，那條路徑
    一旦有人走，全書每一章的指標會同時落空——而在這一項之前**零報告**：
    `REQUIRED_KEYS` 只驗它非空、`_index` 只驗兩邊寫得一樣。
    """
    book = _book(tmp_path, dict(CLEAN), style=False)
    problems, stats = lint_report(book)
    (msg,) = _only(problems, "指向不存在的檔")
    assert "2 支章衍生檔的 `風格: 風格.ai.md`" in msg  # 聚合成一行，不是 2 行
    assert stats.style_refs == 2
    assert stats.style_refs_dangling == 2


def test_style_reference_is_counted_even_when_clean(tmp_path):
    """**0 也印**：「93 個 `風格` 欄指向的檔（0 個不存在）」才是可用的訊息。"""
    problems, stats = lint_report(_book(tmp_path, dict(CLEAN)))
    assert _only(problems, "指向不存在的檔") == []
    assert stats.style_refs == 2
    assert stats.style_refs_dangling == 0
    assert "2 個 `風格` 欄指向的檔（0 個不存在）" in stats.render()


def test_status_must_be_enumerated(tmp_path):
    book = _book(tmp_path, dict(CLEAN))
    p = book / "chapters" / "ch0001.ai.md"
    p.write_text(
        p.read_text(encoding="utf-8").replace("狀態: 草稿", "狀態: 寫到一半"),
        encoding="utf-8",
    )
    problems, _ = lint_report(book)
    assert _only(problems, "`狀態` 是")


def test_pov_needs_all_three_subkeys(tmp_path):
    book = _book(tmp_path, dict(CLEAN))
    p = book / "chapters" / "ch0001.ai.md"
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            "POV: { 角色: 林小凡, 人稱: 第三人稱有限, 距離: Deep POV }",
            "POV: { 角色: 林小凡 }",
        ),
        encoding="utf-8",
    )
    problems, _ = lint_report(book)
    assert _only(problems, "`POV` 缺子欄 人稱、距離")


def test_derived_without_source(tmp_path):
    book = _book(tmp_path, dict(CLEAN))
    (book / "chapters" / "ch0002.md").unlink()
    problems, _ = lint_report(book)
    assert _only(problems, "找不到對應的正文源")


# --------------------------------------------------------------- 反例：_index.ai.md

def test_index_row_must_match_the_chapter_frontmatter(tmp_path):
    """視圖不是第二個家——不一致就是有人只重生了一邊。"""
    rows = [
        "| ch0001 | 幕001–幕002 | arc01 | 別人 | 風格.ai.md | 草稿 |  |",
        "| ch0002 | 幕101 | arc02 | 林小凡 | 風格.ai.md | 已定稿 |  |",
    ]
    problems, stats = lint_report(_book(tmp_path, dict(CLEAN), index_rows=rows))
    assert _only(problems, "POV 表 '別人' vs 檔 '林小凡'")
    assert _only(problems, "狀態 表 '已定稿' vs 檔 '草稿'")
    assert stats.rows_mismatch == 2


def test_index_beat_range_compares_semantically_not_textually(tmp_path):
    """表寫 `幕001–幕002`、檔寫 `[幕001, 幕002]`——同一件事，不該報。"""
    rows = [
        "| ch0001 | 幕001–幕002 | arc01 | 林小凡 | 風格.ai.md | 草稿 |  |",
        "| ch0002 | 幕101 | arc02 | 林小凡 | 風格.ai.md | 草稿 |  |",
    ]
    problems, _ = lint_report(_book(tmp_path, dict(CLEAN), index_rows=rows))
    assert problems == []


def test_chapter_missing_from_the_index(tmp_path):
    rows = ["| ch0001 | 幕001–幕002 | arc01 | 林小凡 | 風格.ai.md | 草稿 |  |"]
    problems, _ = lint_report(_book(tmp_path, dict(CLEAN), index_rows=rows))
    assert _only(problems, "ch0002 有章衍生檔卻不在章序表裡")


def test_index_lists_a_chapter_that_does_not_exist(tmp_path):
    rows = [
        "| ch0001 | 幕001–幕002 | arc01 | 林小凡 | 風格.ai.md | 草稿 |  |",
        "| ch0002 | 幕101 | arc02 | 林小凡 | 風格.ai.md | 草稿 |  |",
        "| ch0009 | 幕102 | arc02 | 林小凡 | 風格.ai.md | 草稿 |  |",
    ]
    problems, _ = lint_report(_book(tmp_path, dict(CLEAN), index_rows=rows))
    assert _only(problems, "列了 ch0009，但沒有對應的 ch0009.ai.md")


def test_unwritten_row_is_not_compared(tmp_path):
    rows = [
        "| ch0001 | 幕001–幕002 | arc01 | 林小凡 | 風格.ai.md | 草稿 |  |",
        "| ch0002 | 幕101 | arc02 | 林小凡 | 風格.ai.md | 草稿 |  |",
        "| （未寫） | 幕102–… | arc02 | — | — | — | arc02 尚未寫完 |",
    ]
    problems, stats = lint_report(_book(tmp_path, dict(CLEAN), index_rows=rows))
    assert problems == []
    assert stats.index_rows == 3 and stats.rows_checked == 2


def test_note_column_must_not_host_foreshadow_markers(tmp_path):
    """V4：備註欄長出了伏筆軸的第二份帳，而且實測已經漂移。"""
    rows = [
        "| ch0001 | 幕001–幕002 | arc01 | 林小凡 | 風格.ai.md | 草稿 | 開場；埋[[伏筆:血玉墜]] |",
        "| ch0002 | 幕101 | arc02 | 林小凡 | 風格.ai.md | 草稿 | 奪髓；收[[伏筆:血玉墜]] |",
    ]
    problems, _ = lint_report(_book(tmp_path, dict(CLEAN), index_rows=rows))
    hit = _only(problems, "含 `埋|收[[伏筆:x]]` 標記")
    assert len(hit) == 1 and "2 列" in hit[0]
    assert "foreshadow-project" in hit[0]


def test_note_column_length_cap(tmp_path):
    """V3：不可重生的幕排序設計註住進了 rollup 衍生檔，重生一次就沒了。"""
    rows = [
        f"| ch0001 | 幕001–幕002 | arc01 | 林小凡 | 風格.ai.md | 草稿 | {'長' * (NOTE_CHARS + 1)} |",
        "| ch0002 | 幕101 | arc02 | 林小凡 | 風格.ai.md | 草稿 | 短的 |",
    ]
    problems, _ = lint_report(_book(tmp_path, dict(CLEAN), index_rows=rows))
    hit = _only(problems, f"備註欄超過 {NOTE_CHARS} 字")
    assert len(hit) == 1 and "1/2 列" in hit[0]


def test_only_the_first_table_in_the_section_is_the_index(tmp_path):
    """節底下可以有別的表（`書本模板` 就在那裡放了一張說明對照表）。

    **這個 bug 是工具自己在 `書本模板` 上抓到的**：掃到節尾會把說明表的每一列
    當成章序列，然後報「列了『結構階段（起／承／轉／合）』但沒有對應的 .ai.md」。
    """
    book = _book(tmp_path, dict(CLEAN))
    p = book / "chapters" / "_index.ai.md"
    p.write_text(
        p.read_text(encoding="utf-8")
        + "\n（說明）備註欄只住一行極短摘要。\n\n"
        "| 不得住這裡 | 它的家 |\n|---|---|\n| 伏筆標記 | 幕綱 |\n",
        encoding="utf-8",
    )
    problems, stats = lint_report(book)
    assert problems == []
    assert stats.index_rows == 2


def test_missing_index_is_the_new_normal(tmp_path):
    """**缺 `_index.ai.md` 不再是問題**（2026-07-28 功能 12 抉擇 1 A）。

    那支檔廢除了，章序的權威改由 `ch-lint --emit` 回答——它印的就是本函式為了
    比對而算出來的那一份（抉擇 4 C：誰重算誰印）。第 8 項因此降級成**殘留偵測**：
    舊檔還在才比對（既有書照抉擇 8 A 不遷移，那份視圖仍要與各章 front-matter 一致）。
    """
    book = _book(tmp_path, dict(CLEAN))
    (book / "chapters" / "_index.ai.md").unlink()
    problems, _ = lint_report(book)
    assert _only(problems, "章序的權威") == []
    assert problems == []


# --------------------------------------------------------------- 失效行為

def test_missing_beat_sheet_is_a_hard_error(tmp_path):
    """**沒有 registry 就硬報錯，不靜默退化。**

    退化的下場是第 1 項（幕號存在性）全部無聲通過而 exit 0——同 `beat_metrics`
    2026-07-27 修掉的那個 spine 假陰性。
    """
    (tmp_path / "chapters").mkdir()
    with pytest.raises(ScanError):
        lint_report(tmp_path)


# --------------------------------------------------------------- 測試執行紀錄（功能 10）

def test_write_test_record_is_optional(tmp_path):
    """**缺席合法、不計入問題數**——沒測過是真實狀態，缺幾支由覆蓋率行說（0 也印）。"""
    problems, stats = lint_report(_book(tmp_path, CLEAN))
    assert problems == []
    assert (stats.test_records, stats.test_records_bad) == (0, 0)
    assert "0/2 支章衍生有 `write-test` 紀錄" in stats.render()


def test_write_test_record_well_formed(tmp_path):
    book = _book(tmp_path, CLEAN)
    p = book / "chapters" / "ch0001.ai.md"
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            "狀態: 草稿", "狀態: 草稿\nwrite-test: 2026-07-28·0高3中3低"
        ),
        encoding="utf-8",
    )
    problems, stats = lint_report(book)
    assert problems == []
    assert (stats.test_records, stats.test_records_bad) == (1, 0)


def test_write_test_record_rejects_prose(tmp_path):
    """判準是**結構**：日期 ＋ 阿拉伯數字。中文數字與讀感形容詞一律不算。"""
    book = _book(tmp_path, CLEAN)
    p = book / "chapters" / "ch0001.ai.md"
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            "狀態: 草稿", "狀態: 草稿\nwrite-test: 跑過了，沒什麼大問題"
        ),
        encoding="utf-8",
    )
    problems, stats = lint_report(book)
    assert _only(problems, "不合形狀")
    assert stats.test_records_bad == 1
