"""章 delta ＋ 約束 log 的收集、落點檢查與 lint。"""

import pytest
from fact_projection.cli import lint_main, main
from fact_projection.fold import parse_spine, project
from fact_projection.sources import (
    check_kind_placement,
    collect_events,
    lint,
    section_lines,
)

SPINE = "- 全書順序：arc01（幕001–幕030）→ arc02（幕031–幕060）\n"


def _book(tmp_path, chapters: dict[str, str] | None = None, constraints: str = ""):
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "_index.md").write_text(SPINE, encoding="utf-8")
    for name, body in (chapters or {}).items():
        (book / "chapters" / name).write_text(body, encoding="utf-8")
    if constraints:
        (book / "story" / "參照" / "約束.md").write_text(constraints, encoding="utf-8")
    return book


def _ch(front_facts: str, extra: str = "") -> str:
    return (
        "---\ngenerated-from: abc\ngenerated-at: 2026-07-26\n所屬arc: arc01\n---\n"
        f"## 本章事實\n{front_facts}\n{extra}"
    )


# ------------------------------------------------------------ 區塊抽取

def test_section_lines_keeps_line_numbers():
    text = "---\nk: v\n---\n## 本章事實\n- 甲\n## 待裁決回饋\n- 乙\n"
    got = section_lines(text, "本章事實").split("\n")
    assert got[4] == "- 甲"  # 第 5 行，行號對得上原檔
    assert got[6] == ""  # 「待裁決回饋」底下的內容不算事實


def test_section_lines_tolerates_annotated_title():
    text = "## 本章事實（3 筆）\n- 甲\n"
    assert "- 甲" in section_lines(text, "本章事實")


def test_section_absent_yields_nothing():
    assert section_lines("## 待裁決回饋\n- 乙\n", "本章事實").strip() == ""


# ------------------------------------------------------------ 收集與定序

def test_collects_across_chapters_and_constraint_log(tmp_path):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：得舊劍"),
            "ch0002.ai.md": _ch("- 幕009（arc01）· 少年 · 持有：舊劍遺失"),
        },
        constraints="- 幕005（arc01）· 同伴 · 約束〔不得識破〕：只當是舊物\n",
    )
    events, mode = collect_events(book)
    assert mode == "chapters"
    assert [e.origin for e in events] == ["ch0001", "ch0002", "約束.md"]
    assert [e.order for e in events] == [0, 1, 2]  # 跨檔遞增，as-of tiebreak 才穩定


def test_projection_folds_chapter_delta_with_constraints(tmp_path):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：得舊劍"),
            "ch0002.ai.md": _ch("- 幕009（arc01）· 少年 · 持有：舊劍遺失"),
        },
        constraints="- 幕005（arc01）· 同伴 · 約束〔不得識破〕：只當是舊物\n",
    )
    events, _ = collect_events(book)
    spine = parse_spine(SPINE)
    slots = {s.token: s for s in project(events, spine, 20, "arc01")}
    assert slots["持有"].content == "舊劍遺失"  # 序最新勝
    assert slots["持有"].origin == "ch0002"
    assert "約束〔不得識破〕" in slots


def test_asof_before_the_change_still_sees_old_value(tmp_path):
    """作者問『第 N 幕當時是什麼』——as-of 就是為此存在的。"""
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 信物 · 錨〔形制〕：青銅牌"),
            "ch0009.ai.md": _ch("- 幕025（arc01）· 信物 · 錨〔形制〕：銀牌"),
        },
    )
    events, _ = collect_events(book)
    spine = parse_spine(SPINE)
    early = {s.token: s.content for s in project(events, spine, 10, "arc01")}
    late = {s.token: s.content for s in project(events, spine, 30, "arc01")}
    assert early["錨〔形制〕"] == "青銅牌"
    assert late["錨〔形制〕"] == "銀牌"


def test_chapters_without_fact_section_are_skipped(tmp_path):
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": "---\nk: v\n---\n（本體留空）\n"},
        constraints="- 幕005（arc01）· 同伴 · 約束〔甲〕：乙\n",
    )
    events, _ = collect_events(book)
    assert len(events) == 1


# ------------------------------------------------------------ 落點檢查

def test_constraint_in_chapter_delta_is_reported(tmp_path):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 同伴 · 約束〔不得識破〕：只當舊物")
        },
    )
    events, _ = collect_events(book)
    (problem,) = check_kind_placement(events)
    assert "重生就沒了" in problem and "約束.md" in problem


def test_state_in_constraint_log_is_reported(tmp_path):
    book = _book(tmp_path, constraints="- 幕005（arc01）· 少年 · 持有：得舊劍\n")
    events, _ = collect_events(book)
    (problem,) = check_kind_placement(events)
    assert "只住" in problem and "本章事實" in problem


# ------------------------------------------------------------ lint

def test_lint_reports_every_bad_line_not_just_the_first(tmp_path):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch(
                "- 幕002（arc01）· 少年 · 心情：開心\n"
                "- 幕003（arc01）· 少年 缺點分隔：內容\n"
                "- 幕004（arc01）· 少年 · 持有：得舊劍"
            )
        },
    )
    problems = lint(book)
    assert len(problems) == 2
    assert any("未知類型 token" in p for p in problems)
    assert any("ch0001 第" in p for p in problems)


def test_lint_clean_book(tmp_path):
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：得舊劍")},
        constraints="- 幕005（arc01）· 同伴 · 約束〔甲〕：乙\n",
    )
    assert lint(book) == []


def test_lint_main_exit_codes(tmp_path, capsys):
    clean = _book(tmp_path / "a", chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：得劍")})
    assert lint_main(["--book", str(clean)]) == 0

    dirty = _book(
        tmp_path / "b", chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 心情：開心")}
    )
    assert lint_main(["--book", str(dirty)]) == 1
    assert "未知類型 token" in capsys.readouterr().err


def test_projection_still_raises_on_bad_line(tmp_path, capsys):
    """投影是嚴格的——吐出不完整的事實比報錯危險。"""
    book = _book(
        tmp_path, chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 心情：開心")}
    )
    assert main(["--book", str(book), "--as-of", "幕011（arc01）"]) == 1
    assert "未知類型 token" in capsys.readouterr().err


def test_bom_prefixed_files_still_parse(tmp_path):
    """Windows 編輯器寫出的 UTF-8 BOM 不得讓第一筆事實靜默消失。"""
    book = _book(tmp_path)
    (book / "chapters" / "ch0001.ai.md").write_text(
        _ch("- 幕002（arc01）· 少年 · 持有：得舊劍"), encoding="utf-8-sig"
    )
    (book / "story" / "參照" / "約束.md").write_text(
        "- 幕005（arc01）· 同伴 · 約束〔甲〕：乙\n", encoding="utf-8-sig"
    )
    events, _ = collect_events(book)
    assert len(events) == 2


@pytest.mark.parametrize("mode_file", ["事實流.md", "狀態事件流.md"])
def test_legacy_book_takes_precedence(tmp_path, mode_file):
    book = _book(
        tmp_path, chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：得劍")}
    )
    (book / "story" / "參照" / mode_file).write_text(
        "- 幕003（arc01）· 少年 · 持有：舊格式那筆\n", encoding="utf-8"
    )
    events, mode = collect_events(book)
    assert mode == "legacy" and len(events) == 1
    assert events[0].content == "舊格式那筆"
