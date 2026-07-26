import pytest
from decision_projection.parse import (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_PROMOTED,
    ParseError,
    matches_target,
    parse_decisions,
    select,
)

STREAM = """\
# 裁決流

> 依 `結構定義/裁決流.schema.md`：append-only、永不人工回收。

| 日期 | 來源 | 標的 | 裁決 | 理由 | 射程 | 狀態 |
|------|------|------|------|------|------|------|
| 2026-07-22 | write-test 測試9（ch0046） | 設定/角色/少年/核心.md | 年齡由區間收窄成定點 | 專名／數字登記防分裂 | 全書 | 生效中 |
| 2026-07-23 | beat-sheet arc07 | 幕綱/arc07.md | 本 arc 母題＝付現 | 三段論證略 | 至arc07 | 已過射程 |
| 2026-07-24 | beat-sheet arc11 | 全書 | 行動欄只寫故事事實 | 已寫進 schema | 全書 | 已升為通則 |
| 2026-07-25 | character | 設定/角色/少年/水下.md | 底身份留卷三以後 | 避免全塞一個底顯機械 | 全書 | 生效中 |
"""


def test_parses_four_rows_and_skips_prose():
    ds = parse_decisions(STREAM)
    assert len(ds) == 4
    assert ds[0].date == "2026-07-22"
    assert ds[0].source == "write-test 測試9（ch0046）"
    assert ds[0].target == "設定/角色/少年/核心.md"
    assert ds[0].scope == "全書" and ds[0].status == STATUS_ACTIVE


def test_statuses_parsed():
    ds = parse_decisions(STREAM)
    assert [d.status for d in ds] == [
        STATUS_ACTIVE,
        STATUS_EXPIRED,
        STATUS_PROMOTED,
        STATUS_ACTIVE,
    ]
    assert ds[0].active and not ds[1].active


def test_header_must_match_column_order():
    with pytest.raises(ParseError, match="表頭欄位不符"):
        parse_decisions("| 日期 | 標的 | 裁決 |\n|--|--|--|\n")


def test_wrong_column_count_raises():
    bad = STREAM + "| 2026-07-26 | character | 設定/角色/少年/核心.md | 只有四欄 |\n"
    with pytest.raises(ParseError, match="欄數"):
        parse_decisions(bad)


def test_bad_date_raises():
    bad = STREAM + "| 7月26日 | character | 全書 | x | y | 全書 | 生效中 |\n"
    with pytest.raises(ParseError, match="日期格式"):
        parse_decisions(bad)


def test_unknown_status_raises():
    bad = STREAM + "| 2026-07-26 | character | 全書 | x | y | 全書 | 待辦 |\n"
    with pytest.raises(ParseError, match="未知狀態"):
        parse_decisions(bad)


# ---------------------------------------------------------------- 標的過濾

def test_target_directory_matches_its_facets():
    """給目錄，命中其下所有切面。"""
    ds = select(parse_decisions(STREAM), target="設定/角色/少年/")
    targets = {d.target for d in ds}
    assert "設定/角色/少年/核心.md" in targets and "設定/角色/少年/水下.md" in targets


def test_target_facet_matches_decisions_on_the_whole_character():
    """給某個切面，也要命中管整個角色（目錄層）的裁決。"""
    ds = parse_decisions(
        "| 日期 | 來源 | 標的 | 裁決 | 理由 | 射程 | 狀態 |\n"
        "|--|--|--|--|--|--|--|\n"
        "| 2026-07-25 | character | 設定/角色/少年/ | 升目錄形態 | 源檔過大 | 全書 | 生效中 |\n"
    )
    assert select(ds, target="設定/角色/少年/核心.md")


def test_target_all_always_matches():
    ds = select(parse_decisions(STREAM), target="設定/角色/別人.md")
    assert [d.target for d in ds] == ["全書"]


def test_unrelated_target_not_matched():
    assert not matches_target(parse_decisions(STREAM)[0], "設定/世界觀/魔法.md")


def test_active_only_filters_expired_and_promoted():
    ds = select(parse_decisions(STREAM), active_only=True)
    assert {d.status for d in ds} == {STATUS_ACTIVE}


def test_since_filters_by_date():
    ds = select(parse_decisions(STREAM), since="2026-07-24")
    assert [d.date for d in ds] == ["2026-07-24", "2026-07-25"]


def test_bad_since_raises():
    with pytest.raises(ParseError, match="--since"):
        select(parse_decisions(STREAM), since="2026/07/24")
