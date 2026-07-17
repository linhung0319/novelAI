import pytest
from state_projection.fold import parse_events, DIMENSIONS, FoldError, Event

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
