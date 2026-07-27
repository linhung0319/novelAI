"""章 front-matter：`對應幕` 區間與 `所屬arc`，以及事實行掛對章沒有。

`章節.schema.md:106` 明文承諾這件事，但 2026-07-27 前**沒有任何檢查器**——它掉在
`fact-lint`（讀行不讀 front-matter）與 `derived-sync validate`（讀 front-matter
不讀行）的分工縫裡。
"""

import pytest
from fact_projection.chapters import (
    covering_chapter,
    load_chapter_meta,
    parse_chapter_meta,
)
from fact_projection.sources import lint, lint_report

SPINE = "- 全書順序：arc01（幕001–幕030）→ arc02（幕031–幕060）\n"


def _book(tmp_path, chapters: dict[str, str]):
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "_index.md").write_text(SPINE, encoding="utf-8")
    for name, body in chapters.items():
        (book / "chapters" / name).write_text(body, encoding="utf-8")
        if name.endswith(".ai.md"):
            (book / "chapters" / f"{name[:-6]}.md").write_text("（正文）\n", encoding="utf-8")
    return book


def _ch(facts: str, beats: str = "[幕001, 幕004]", arc: str = "arc01") -> str:
    fm = "---\ngenerated-from: abc\n"
    if beats:
        fm += f"對應幕: {beats}\n"
    if arc:
        fm += f"所屬arc: {arc}\n"
    return fm + "---\n## 本章事實\n" + facts


# ------------------------------------------------------------ front-matter 解析

def test_parses_schema_form():
    m = parse_chapter_meta("ch0001", _ch("", "[幕001, 幕004]"))
    assert (m.first_beat, m.last_beat, m.arc) == (1, 4, "arc01")


@pytest.mark.parametrize(
    "raw", ["幕001–幕004", "[幕001,幕004]", "幕001-幕004", "幕001 至 幕004"]
)
def test_tolerates_human_spellings_of_the_range(raw):
    """這一欄是機讀的，但人偶爾會手改——破折號的形狀不該決定成敗。"""
    m = parse_chapter_meta("ch0001", _ch("", raw))
    assert (m.first_beat, m.last_beat) == (1, 4)


def test_single_beat_chapter():
    m = parse_chapter_meta("ch0001", _ch("", "[幕007, 幕007]"))
    assert m.covers(7) and not m.covers(8)


def test_unparseable_range_is_a_problem():
    m = parse_chapter_meta("ch0001", _ch("", "大概前面那幾幕"))
    assert m.first_beat is None
    assert any("解析不了" in p for p in m.problems)


def test_reversed_range_is_reported_and_normalised():
    m = parse_chapter_meta("ch0001", _ch("", "[幕009, 幕002]"))
    assert any("起訖顛倒" in p for p in m.problems)
    assert (m.first_beat, m.last_beat) == (2, 9)  # 仍然可用，別讓報錯連鎖


def test_no_frontmatter_at_all():
    m = parse_chapter_meta("ch0001", "## 本章事實\n- 甲\n")
    assert not m.has_frontmatter


# ------------------------------------------------------------ 幕號落錯章（V5）

def test_beat_outside_the_range_is_reported(tmp_path):
    book = _book(
        tmp_path,
        {"ch0001.ai.md": _ch("- 幕009（arc01）· 少年 · 位置：甲", "[幕001, 幕004]")},
    )
    (problem,) = lint(book)
    assert "幕009 不在本章 `對應幕` 區間" in problem and "幕001–幕004" in problem


def test_beat_inside_the_range_passes(tmp_path):
    book = _book(
        tmp_path,
        {"ch0001.ai.md": _ch("- 幕003（arc01）· 少年 · 位置：甲", "[幕001, 幕004]")},
    )
    assert lint(book) == []


def test_arc_mismatch_is_reported(tmp_path):
    book = _book(
        tmp_path,
        {"ch0001.ai.md": _ch("- 幕003（arc02）· 少年 · 位置：甲", arc="arc01")},
    )
    (problem,) = lint(book)
    assert "arc 寫 arc02" in problem and "arc01" in problem


def test_facts_without_a_beat_range_are_reported(tmp_path):
    """有事實行卻沒有 `對應幕`＝沒有任何東西能核對這些事實掛對了章沒有。"""
    book = _book(
        tmp_path, {"ch0001.ai.md": _ch("- 幕003（arc01）· 少年 · 位置：甲", beats="")}
    )
    assert any("沒有可解析的 `對應幕`" in p for p in lint(book))


def test_unstamped_chapter_is_not_reported_here(tmp_path):
    """完全沒有 front-matter＝還沒封章，`derived-sync check` 已報 unstamped。

    分工：`check` 問「產出了沒」，本支問「形狀對不對」。重複報是雜訊。
    """
    book = _book(tmp_path, {"ch0001.ai.md": "## 本章事實\n- 幕003（arc01）· 少年 · 位置：甲\n"})
    assert lint(book) == []


def test_scope_check_reports_how_many_chapters_it_checked(tmp_path):
    """守衛要能回答「我檢查了幾筆」（設計原則 E2）。"""
    book = _book(
        tmp_path,
        {
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲"),
            "ch0002.ai.md": _ch("- 幕003（arc01）· 少年 · 位置：乙"),
        },
    )
    _, stats = lint_report(book)
    assert stats.chapter_scope_checked == 2


# ------------------------------------------------------------ 已寫成的幕

def test_covering_chapter_finds_the_written_chapter(tmp_path):
    book = _book(
        tmp_path,
        {
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲", "[幕001, 幕004]"),
            "ch0002.ai.md": _ch("- 幕006（arc01）· 少年 · 位置：乙", "[幕005, 幕009]"),
        },
    )
    metas = load_chapter_meta(book)
    assert covering_chapter(metas, "arc01", 6) == "ch0002"
    assert covering_chapter(metas, "arc01", 20) is None  # 還沒寫到
    assert covering_chapter(metas, "arc02", 2) is None  # 別的 arc
