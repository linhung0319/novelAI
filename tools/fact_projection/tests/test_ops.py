"""集合維度的內容欄語法（知識前沿／持有／能力）。"""

import pytest
from fact_projection.fold import FoldError, parse_events, project
from fact_projection.ops import (
    SET_DIMENSIONS,
    OpError,
    apply_ops,
    parse_ops,
    render,
)

SPINE = {"arc01": 0, "arc02": 1}


def _fold(text: str, beat: int = 999, arc: str = "arc02"):
    slots = project(
        parse_events(text), SPINE, beat, arc, set_dims=SET_DIMENSIONS
    )
    return {s.token: s for s in slots}


# ------------------------------------------------------------ 解析

def test_add_known_and_unknown():
    ops = parse_ops("＋已知〔主宰存在〕、＋尚不知〔主宰目的〕", "知識前沿")
    assert [(o.action, o.name, o.state) for o in ops] == [
        ("set", "主宰存在", "已知"),
        ("set", "主宰目的", "尚不知"),
    ]


def test_halfwidth_plus_also_works():
    (op,) = parse_ops("+已知〔主宰存在〕", "知識前沿")
    assert op.state == "已知"


def test_transition():
    (op,) = parse_ops("〔信物用途〕→已知", "知識前沿")
    assert (op.action, op.name, op.state) == ("set", "信物用途", "已知")


def test_drop():
    (op,) = parse_ops("−〔信物用途〕", "知識前沿")
    assert (op.action, op.name) == ("drop", "信物用途")


def test_plain_set_dimension_takes_no_state():
    ops = parse_ops("＋〔師傳舊劍〕、−〔護身玉牌〕", "持有")
    assert [(o.action, o.name) for o in ops] == [
        ("set", "師傳舊劍"),
        ("drop", "護身玉牌"),
    ]


def test_short_note_is_allowed_and_kept():
    (op,) = parse_ops("＋〔護身玉牌〕（借）", "持有")
    assert op.note == "借"


# ------------------------------------------------------------ 拒絕自由文字（純化紀律）

def test_free_prose_is_rejected():
    with pytest.raises(OpError, match="須為集合運算"):
        parse_ops("得知信物存在，尚不知其真正用途", "知識前沿")


def test_prose_smuggled_between_ops_is_rejected():
    """夾帶正是實測到的第二個成長機制——內容欄變成什麼都能塞的自由欄位。"""
    with pytest.raises(OpError, match="夾了非操作文字"):
        parse_ops("＋已知〔甲〕 這一幕他還順便想通了很多事 ＋已知〔乙〕", "知識前沿")


def test_trailing_prose_is_rejected():
    with pytest.raises(OpError, match="結尾有非操作文字"):
        parse_ops("＋已知〔甲〕，另外守死排除線②不得外泄", "知識前沿")


def test_state_on_plain_set_dimension_is_rejected():
    with pytest.raises(OpError, match="沒有已知／尚不知兩態"):
        parse_ops("＋已知〔舊劍〕", "持有")


def test_missing_sign_on_plain_set_is_rejected():
    with pytest.raises(OpError, match="缺少"):
        parse_ops("〔舊劍〕", "持有")


def test_bare_proposition_without_state_is_rejected():
    with pytest.raises(OpError, match="語法不完整"):
        parse_ops("〔甲〕", "知識前沿")


# ------------------------------------------------------------ 折疊

def test_apply_ops_keeps_insertion_order():
    items = apply_ops([], parse_ops("＋已知〔甲〕、＋尚不知〔乙〕", "知識前沿"))
    items = apply_ops(items, parse_ops("＋尚不知〔丙〕", "知識前沿"))
    assert [n for n, _ in items] == ["甲", "乙", "丙"]


def test_transition_updates_in_place():
    items = apply_ops([], parse_ops("＋尚不知〔乙〕", "知識前沿"))
    items = apply_ops(items, parse_ops("〔乙〕→已知", "知識前沿"))
    assert items == [("乙", "已知")]


def test_drop_removes():
    items = apply_ops([], parse_ops("＋〔甲〕、＋〔乙〕", "持有"))
    items = apply_ops(items, parse_ops("−〔甲〕", "持有"))
    assert [n for n, _ in items] == ["乙"]


def test_render_groups_by_state():
    items = apply_ops([], parse_ops("＋已知〔甲〕、＋尚不知〔乙〕", "知識前沿"))
    assert render(items, "知識前沿") == "已知：〔甲〕｜尚不知：〔乙〕"


def test_render_plain_set():
    items = apply_ops([], parse_ops("＋〔甲〕", "持有"))
    assert render(items, "持有") == "〔甲〕"


# ------------------------------------------------------------ 端到端：投影不再需要重抄

def test_projection_accumulates_across_chapters():
    """這是本次改動的核心：每筆只寫這一幕改了什麼，當下狀態由 fold 算出來。"""
    slots = _fold(
        "- 幕001（arc01）· 少年 · 知識前沿：＋尚不知〔信物用途〕\n"
        "- 幕002（arc01）· 少年 · 知識前沿：＋已知〔主宰存在〕、＋尚不知〔主宰目的〕\n"
        "- 幕010（arc02）· 少年 · 知識前沿：〔信物用途〕→已知\n"
    )
    got = slots["知識前沿"]
    assert dict(got.items) == {
        "信物用途": "已知",
        "主宰存在": "已知",
        "主宰目的": "尚不知",
    }
    assert "已知：〔信物用途〕、〔主宰存在〕" in got.content


def test_asof_replays_only_up_to_target():
    slots = _fold(
        "- 幕001（arc01）· 少年 · 知識前沿：＋尚不知〔信物用途〕\n"
        "- 幕010（arc02）· 少年 · 知識前沿：〔信物用途〕→已知\n",
        beat=5,
        arc="arc01",
    )
    assert dict(slots["知識前沿"].items) == {"信物用途": "尚不知"}


def test_scalar_dimensions_still_overwrite():
    """位置／所屬／關係本來就是純量，維持覆蓋——實測它們成長也最小。"""
    slots = _fold(
        "- 幕001（arc01）· 少年 · 位置：雜役院\n"
        "- 幕002（arc01）· 少年 · 位置：藏經閣\n"
    )
    assert slots["位置"].content == "藏經閣"
    assert slots["位置"].items == ()


def test_bad_ops_raise_with_location():
    with pytest.raises(FoldError, match="第 1 行"):
        _fold("- 幕001（arc01）· 少年 · 知識前沿：得知信物存在\n")


def test_legacy_mode_leaves_prose_alone():
    """舊格式書（set_dims 空）照舊跑得動，不因新語法而炸。"""
    slots = {
        s.token: s
        for s in project(
            parse_events("- 幕001（arc01）· 少年 · 知識前沿：得知信物存在\n"),
            SPINE,
            999,
            "arc02",
        )
    }
    assert slots["知識前沿"].content == "得知信物存在"
