import pytest
from state_projection.fold import parse_events, DIMENSIONS, FoldError, Event
from state_projection.fold import parse_spine, project, Slot

SPINE_MULTI = """\
# 幕綱索引
- 全書順序：arc01 → arc02 → arc03
- arc01：幕001–幕100
- arc02：幕101–幕108
"""

SPINE_SINGLE = "- 全書順序：arcF（幕001–幕012，本 fixture 唯一 arc）"


def _slot(slots, entity, dim):
    return next(s for s in slots if s.entity == entity and s.dimension == dim)

STREAM = """\
# 狀態事件流（範例）
- 幕001（arcF）· 哈利↔榮恩 · 關係：初識 → 同行結伴
- 幕006（arcF）· 哈利 · 持有：獲得隱形斗篷（父親遺物）
- 幕008（arcF）· 尼樂·勒梅 · 知識前沿：身分對哈利揭曉＝魔法石唯一煉製者

（以上為範例）
"""


def test_dimensions_are_the_closed_six():
    assert DIMENSIONS == {"知識前沿", "關係", "持有", "位置", "能力", "所屬"}


def test_parse_skips_non_event_lines_and_reads_three_events():
    events = parse_events(STREAM)
    assert len(events) == 3


def test_parse_position_entity_dimension_content():
    e = parse_events(STREAM)[0]
    assert (e.beat, e.arc, e.entity, e.dimension) == (1, "arcF", "哈利↔榮恩", "關係")
    assert e.content == "初識 → 同行結伴"


def test_parse_entity_name_containing_middle_dot():
    e = parse_events(STREAM)[2]
    assert e.entity == "尼樂·勒梅"
    assert e.dimension == "知識前沿"


def test_unknown_dimension_raises():
    with pytest.raises(FoldError, match="未知變化維度"):
        parse_events("- 幕001（arcF）· 哈利 · 心情：開心")


def test_missing_content_colon_raises():
    with pytest.raises(FoldError, match="：|內容"):
        parse_events("- 幕001（arcF）· 哈利 · 持有 隱形斗篷")


def test_missing_dimension_separator_raises():
    with pytest.raises(FoldError, match="·|維度"):
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


def test_entity_dimension_grouping_independent():
    events = parse_events(
        "- 幕002（arcF）· 哈利 · 知識前沿：認定史奈普是嚴師\n"
        "- 幕006（arcF）· 哈利 · 持有：得斗篷\n"
    )
    slots = project(events, {"arcF": 0}, 12, "arcF")
    assert {(s.entity, s.dimension) for s in slots} == {("哈利", "知識前沿"), ("哈利", "持有")}


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
