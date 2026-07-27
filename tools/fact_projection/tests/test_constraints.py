"""約束規則表：解析、區間篩選、回溯生效、未排幕 arc 的處置。

2026-07-27 搬家：約束住 `story/物件/<名>.md` 的「## 不得寫成什麼」，表降成 4 欄
——**「實體」不再是欄位，它是檔名**（`parse_constraints` 的 `entity` 參數）。
"""

import pytest
from fact_projection.constraints import active_at, check_duplicates, parse_constraints
from fact_projection.fold import FoldError

SPINE = {"arc01": 0, "arc02": 1, "arc03": 2}

HEAD = "| 約束名 | 不得寫成 | 生效自 | 解除於 |\n|---|---|---|---|\n"


def _t(*rows: str) -> str:
    return "引言不是表格，應被跳過。\n\n" + HEAD + "".join(r + "\n" for r in rows)


def _parse(*rows: str, entity: str = "同伴", **kw):
    return parse_constraints(_t(*rows), entity=entity, **kw)


def _names(rows, beat, arc="arc02"):
    slots = active_at(_parse(*rows), SPINE, beat, arc)
    return sorted(s.name for s in slots)


# ------------------------------------------------------------ 解析

def test_parses_rows_and_skips_prose():
    cs = _parse("| 甲 | 只當是舊物 | 全書 | — |")
    assert len(cs) == 1
    assert cs[0].name == "甲" and cs[0].entity == "同伴"  # 實體來自檔名
    assert cs[0].since is None and cs[0].until is None
    assert cs[0].token == "約束〔甲〕"


def test_entity_comes_from_the_filename_not_a_column():
    """搬家的核心：實體不再是自由字串，所以不會有「真觀」與「真觀（少林）」並存。"""
    (c,) = parse_constraints(_t("| 甲 | 乙 | 全書 | — |"), entity="真觀")
    assert c.entity == "真觀"


def test_example_rows_in_html_comment_are_not_constraints():
    text = _t("| 甲 | 乙 | 全書 | — |") + ("<!--\n| 範例 | 某事 | 全書 | — |\n-->\n")
    assert [c.name for c in parse_constraints(text, entity="同伴")] == ["甲"]


@pytest.mark.parametrize("blank", ["—", "-", "", "無"])
def test_release_column_accepts_several_blank_spellings(blank):
    (c,) = _parse(f"| 甲 | 乙 | 全書 | {blank} |")
    assert c.until is None


def test_bad_header_is_rejected():
    text = "| 名 | 不得寫成 |\n|---|---|\n| 甲 | 乙 |\n"
    with pytest.raises(FoldError, match="表頭欄位不符"):
        parse_constraints(text, entity="同伴")


def test_old_five_column_header_says_the_entity_column_is_gone():
    """既有書若還是 5 欄，訊息要直接說破那一欄去哪了，不能只說「不符」。"""
    text = (
        "| 約束名 | 實體 | 不得寫成 | 生效自 | 解除於 |\n|---|---|---|---|---|\n"
        "| 甲 | 同伴 | 乙 | 全書 | — |\n"
    )
    errors: list[str] = []
    parse_constraints(text, entity="真觀", errors=errors)
    assert len(errors) == 1
    assert "「實體」欄已取消" in errors[0] and "真觀" in errors[0]


def test_wrong_column_count_is_rejected():
    with pytest.raises(FoldError, match="欄數"):
        _parse("| 甲 | 乙 | 全書 |")


def test_halfwidth_parens_get_a_pointed_hint():
    """中文 IME 下全形／半形誤打是高頻事件，訊息要直接說破。"""
    with pytest.raises(FoldError, match="全形／半形"):
        _parse("| 甲 | 乙 | 幕005(arc01) | — |")


def test_blank_since_is_rejected_with_a_pointer_to_全書():
    with pytest.raises(FoldError, match="全書"):
        _parse("| 甲 | 乙 |  | — |")


def test_blank_name_is_rejected():
    with pytest.raises(FoldError, match="約束名"):
        _parse("|  | 乙 | 全書 | — |")


def test_lint_mode_collects_every_bad_row():
    errors: list[str] = []
    _parse(
        "| 甲 | 乙 | 幕005(arc01) | — |",
        "| 乙 | 丙 | 全書 |",
        "| 丙 | 丁 | 全書 | — |",
        errors=errors,
    )
    assert len(errors) == 2


# ------------------------------------------------------------ 區間篩選

def test_全書_constraint_is_active_from_the_start():
    """回溯生效：作者寫到 arc05 才立的排除線，也能管住 arc01。"""
    rows = ["| 甲 | 乙 | 全書 | — |"]
    assert _names(rows, 1, "arc01") == ["甲"]
    assert _names(rows, 40, "arc02") == ["甲"]


def test_constraint_not_yet_in_effect_is_excluded():
    rows = ["| 甲 | 乙 | 幕040（arc02） | — |"]
    assert _names(rows, 10, "arc01") == []
    assert _names(rows, 40, "arc02") == ["甲"]


def test_released_constraint_drops_out_at_the_release_beat():
    rows = ["| 甲 | 乙 | 全書 | 幕040（arc02） |"]
    assert _names(rows, 39, "arc02") == ["甲"]
    assert _names(rows, 40, "arc02") == []  # 解除那一幕起就不再管事


def test_scope_extension_is_an_edit_not_a_new_row():
    """延長射程＝改「解除於」一格；舊值不留下死行（這正是改表的理由）。"""
    before = _parse("| 口子開著 | 不得死 | 幕005（arc01） | 幕040（arc02） |", entity="真觀")
    after = _parse("| 口子開著 | 不得死 | 幕005（arc01） | 幕050（arc03） |", entity="真觀")
    assert len(before) == len(after) == 1
    assert active_at(before, SPINE, 45, "arc02") == []
    assert len(active_at(after, SPINE, 45, "arc02")) == 1


# ------------------------------------------------------------ 未排幕的 arc

def test_constraint_pointing_at_unplanned_arc_is_info_not_error():
    """約束天生領先幕綱——character 替反派立排除線時那個 arc 常還沒排幕。

    比照 `共同約定.md` 六對揭示層級的處置：揭示點還不存在是合法狀態。
    """
    notes: list[str] = []
    cs = _parse("| 甲 | 不得現身 | 幕1201（arc12） | — |", entity="反派")
    slots = active_at(cs, SPINE, 40, "arc02", notes=notes)
    assert slots == []  # 尚未抵達
    assert len(notes) == 1 and "arc12" in notes[0]


def test_release_point_in_unplanned_arc_keeps_constraint_active():
    notes: list[str] = []
    cs = _parse("| 甲 | 不得現身 | 全書 | 幕1201（arc12） |", entity="反派")
    slots = active_at(cs, SPINE, 40, "arc02", notes=notes)
    assert [s.name for s in slots] == ["甲"]  # 解除點還沒到，仍生效
    assert len(notes) == 1


def test_unknown_target_arc_still_raises():
    with pytest.raises(FoldError, match="不在 spine"):
        active_at([], SPINE, 1, "arc99")


# ------------------------------------------------------------ 輸出形狀

def test_slot_source_label_handles_全書():
    (c,) = _parse("| 甲 | 乙 | 全書 | — |")
    assert c.to_slot().source_label == "全書"


def test_slot_source_label_handles_a_beat():
    (c,) = _parse("| 甲 | 乙 | 幕005（arc01） | — |")
    assert c.to_slot().source_label == "幕005（arc01）"


def test_slot_origin_defaults_to_the_object_file_that_holds_it():
    """每條約束自帶它的物件檔，投影不必再被告知來源。"""
    (c,) = parse_constraints(
        _t("| 甲 | 乙 | 全書 | — |"), entity="真觀", origin="物件/真觀.md"
    )
    assert c.to_slot().origin == "物件/真觀.md"


def test_duplicate_rows_are_reported():
    """「射程延長＝改一格」是紀律，得有東西在守，否則就退回死行累積。"""
    cs = _parse(
        "| 甲 | 乙 | 全書 | 幕040（arc02） |",
        "| 甲 | 乙 | 全書 | 幕050（arc03） |",
    )
    (problem,) = check_duplicates(cs, origin="物件/同伴.md")
    assert "重複" in problem and "改那一列" in problem


def test_same_name_on_different_entities_is_fine():
    """「不得升為隱藏高手」可以同時管好幾個配角——那不是重複（它們在不同檔）。"""
    cs = _parse("| 不得升為隱藏高手 | 就是看起來那樣 | 全書 | — |", entity="配角甲")
    cs += _parse("| 不得升為隱藏高手 | 就是看起來那樣 | 全書 | — |", entity="配角乙")
    assert check_duplicates(cs) == []
