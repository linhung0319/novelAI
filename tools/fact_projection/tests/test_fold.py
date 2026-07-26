import pytest
from fact_projection.fold import (
    DIMENSIONS,
    KIND_ANCHOR,
    KIND_CONSTRAINT,
    KIND_STATE,
    FoldError,
    classify_token,
    parse_events,
    parse_spine,
    project,
)

SPINE_MULTI = """\
# 幕綱索引
- 全書順序：arc01 → arc02 → arc03
- arc01：幕001–幕100
- arc02：幕101–幕108
"""

SPINE_SINGLE = "- 全書順序：arcF（幕001–幕012，本 fixture 唯一 arc）"


def _slot(slots, entity, token):
    return next(s for s in slots if s.entity == entity and s.token == token)


STREAM = """\
# 事實流（範例）
- 幕001（arcF）· 哈利↔榮恩 · 關係：初識 → 同行結伴
- 幕006（arcF）· 哈利 · 持有：獲得隱形斗篷（父親遺物）
- 幕008（arcF）· 尼樂·勒梅 · 知識前沿：身分對哈利揭曉＝魔法石唯一煉製者

（以上為範例）
"""


# ---------------------------------------------------------------- 6 維（原語意，不得回歸）

def test_dimensions_are_the_closed_six():
    assert DIMENSIONS == {"知識前沿", "關係", "持有", "位置", "能力", "所屬"}


def test_parse_skips_non_event_lines_and_reads_three_events():
    events = parse_events(STREAM)
    assert len(events) == 3


def test_parse_position_entity_token_content():
    e = parse_events(STREAM)[0]
    assert (e.beat, e.arc, e.entity, e.token) == (1, "arcF", "哈利↔榮恩", "關係")
    assert e.kind == KIND_STATE and e.name == "關係"
    assert e.content == "初識 → 同行結伴"


def test_parse_entity_name_containing_middle_dot():
    e = parse_events(STREAM)[2]
    assert e.entity == "尼樂·勒梅"
    assert e.token == "知識前沿"


def test_unknown_token_raises():
    with pytest.raises(FoldError, match="未知類型 token"):
        parse_events("- 幕001（arcF）· 哈利 · 心情：開心")


def test_missing_content_colon_raises():
    with pytest.raises(FoldError, match="：|內容"):
        parse_events("- 幕001（arcF）· 哈利 · 持有 隱形斗篷")


def test_missing_token_separator_raises():
    with pytest.raises(FoldError, match="·|類型"):
        parse_events("- 幕001（arcF） 哈利 持有：斗篷")


def test_parse_spine_multi_arc_ranks_in_order():
    assert parse_spine(SPINE_MULTI) == {"arc01": 0, "arc02": 1, "arc03": 2}


def test_parse_spine_single_arc():
    assert parse_spine(SPINE_SINGLE) == {"arcF": 0}


def test_parse_spine_no_line_raises():
    with pytest.raises(FoldError, match="全書順序"):
        parse_spine("# 沒有 spine 的檔")


def test_asof_boundary_includes_target_excludes_later():
    events = parse_events(
        "- 幕006（arcF）· 哈利 · 持有：得斗篷\n"
        "- 幕009（arcF）· 哈利 · 持有：斗篷遭沒收（此後無）\n"
    )
    spine = {"arcF": 0}
    at7 = _slot(project(events, spine, 7, "arcF"), "哈利", "持有")
    assert "得斗篷" in at7.content and at7.source_beat == 6
    at10 = _slot(project(events, spine, 10, "arcF"), "哈利", "持有")
    assert "沒收" in at10.content and at10.source_beat == 9


def test_lose_after_gain_latest_wins():  # 得而復失
    events = parse_events(
        "- 幕006（arcF）· 哈利 · 持有：得斗篷\n"
        "- 幕009（arcF）· 哈利 · 持有：斗篷遭沒收\n"
    )
    slots = project(events, {"arcF": 0}, 12, "arcF")
    assert _slot(slots, "哈利", "持有").content == "斗篷遭沒收"


def test_relationship_bidirectional_slot_evolves():  # 關係雙向
    events = parse_events(
        "- 幕001（arcF）· 哈利↔榮恩 · 關係：初識結伴\n"
        "- 幕009（arcF）· 哈利↔榮恩 · 關係：摯友 → 鬧翻冷戰\n"
        "- 幕011（arcF）· 哈利↔榮恩 · 關係：鬧翻冷戰 → 和好\n"
    )
    spine = {"arcF": 0}
    assert _slot(project(events, spine, 10, "arcF"), "哈利↔榮恩", "關係").content == "摯友 → 鬧翻冷戰"
    assert _slot(project(events, spine, 11, "arcF"), "哈利↔榮恩", "關係").content == "鬧翻冷戰 → 和好"


def test_entity_token_grouping_independent():
    events = parse_events(
        "- 幕002（arcF）· 哈利 · 知識前沿：認定史奈普是嚴師\n"
        "- 幕006（arcF）· 哈利 · 持有：得斗篷\n"
    )
    slots = project(events, {"arcF": 0}, 12, "arcF")
    assert {(s.entity, s.token) for s in slots} == {("哈利", "知識前沿"), ("哈利", "持有")}


def test_cross_arc_ordering_uses_spine_rank_not_beat_number():
    # 幕101（arc02）序位晚於 幕900（arc01），因 arc01 rank 較小 → 幕900 不因號大而較晚
    events = parse_events(
        "- 幕900（arc01）· 哈利 · 位置：城堡\n"
        "- 幕101（arc02）· 哈利 · 位置：斜角巷\n"
    )
    spine = {"arc01": 0, "arc02": 1}
    at_arc01 = _slot(project(events, spine, 950, "arc01"), "哈利", "位置")
    assert at_arc01.content == "城堡"  # arc02 的 幕101 序位在其後，被排除
    at_arc02 = _slot(project(events, spine, 108, "arc02"), "哈利", "位置")
    assert at_arc02.content == "斜角巷"


def test_event_arc_not_in_spine_raises():
    events = parse_events("- 幕001（arcX）· 哈利 · 持有：斗篷")
    with pytest.raises(FoldError, match="不在 spine|無法定位"):
        project(events, {"arcF": 0}, 12, "arcF")


def test_target_arc_not_in_spine_raises():
    events = parse_events("- 幕001（arcF）· 哈利 · 持有：斗篷")
    with pytest.raises(FoldError, match="不在 spine|無法定位"):
        project(events, {"arcF": 0}, 1, "arcZZ")


# ---------------------------------------------------------------- 錨／約束（2026-07-26 擴充）

TYPED = """\
- 幕002（arcF）· 哈利 · 知識前沿：尚不知斗篷來歷
- 幕006（arcF）· 哈利 · 錨〔年齡〕：十一（ch0003 寫死）
- 幕009（arcF）· 哈利 · 錨〔年齡〕：十二（ch0020 過生日）
- 幕004（arcF）· 榮恩 · 約束〔不得先於哈利識破斗篷〕：他到收束前只當那是舊布
"""


def test_classify_token_three_kinds():
    assert classify_token("持有") == (KIND_STATE, "持有")
    assert classify_token("錨〔年齡〕") == (KIND_ANCHOR, "年齡")
    assert classify_token("約束〔不得登場〕") == (KIND_CONSTRAINT, "不得登場")


def test_classify_token_rejects_unbracketed_and_nested():
    for bad in ("錨", "錨〔〕", "約束〔a〔b〕〕", "錨【年齡】"):
        with pytest.raises(FoldError, match="未知類型 token"):
            classify_token(bad)


def test_anchor_slot_latest_version_wins():
    """錨改版＝再發一行同名事件，不必回頭改舊行，也不會兩個數字並存。"""
    events = parse_events(TYPED)
    spine = {"arcF": 0}
    assert _slot(project(events, spine, 7, "arcF"), "哈利", "錨〔年齡〕").content.startswith("十一")
    at12 = project(events, spine, 12, "arcF")
    assert _slot(at12, "哈利", "錨〔年齡〕").content.startswith("十二")
    assert len([s for s in at12 if s.token == "錨〔年齡〕"]) == 1


def test_anchor_and_state_are_separate_slots_on_same_entity():
    slots = project(parse_events(TYPED), {"arcF": 0}, 12, "arcF")
    assert {s.token for s in slots if s.entity == "哈利"} == {"知識前沿", "錨〔年齡〕"}


def test_kinds_filter():
    events = parse_events(TYPED)
    spine = {"arcF": 0}
    only_state = project(events, spine, 12, "arcF", kinds=(KIND_STATE,))
    assert {s.kind for s in only_state} == {KIND_STATE}
    two = project(events, spine, 12, "arcF", kinds=(KIND_ANCHOR, KIND_CONSTRAINT))
    assert {s.kind for s in two} == {KIND_ANCHOR, KIND_CONSTRAINT}


def test_constraint_release_is_explicit_and_active_only_filters_it():
    events = parse_events(
        TYPED
        + "- 幕011（arcF）· 榮恩 · 約束〔不得先於哈利識破斗篷〕：（解除）本幕已對全員揭曉\n"
    )
    spine = {"arcF": 0}
    tok = "約束〔不得先於哈利識破斗篷〕"
    before = project(events, spine, 10, "arcF", active_only=True)
    assert any(s.token == tok for s in before)
    after = project(events, spine, 12, "arcF", active_only=True)
    assert not any(s.token == tok for s in after)
    # 不加 --active-only 時解除列仍看得到（審稿要知道它曾經在）
    released = _slot(project(events, spine, 12, "arcF"), "榮恩", tok)
    assert released.released and released.content.startswith("（解除）")
