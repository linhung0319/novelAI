import pytest
from state_projection.cli import format_projection, main
from state_projection.fold import parse_events, project


def _slots(target):
    events = parse_events(
        "- 幕006（arcF）· 哈利 · 持有：得隱形斗篷\n"
        "- 幕009（arcF）· 哈利 · 持有：斗篷遭麥教授沒收（此後無）\n"
        "- 幕009（arcF）· 哈利↔榮恩 · 關係：摯友 → 鬧翻冷戰\n"
    )
    return project(events, {"arcF": 0}, target, "arcF")


def test_format_groups_by_entity_with_source():
    out = format_projection(_slots(10), 10, "arcF")
    assert "### 哈利" in out and "### 哈利↔榮恩" in out
    assert "沒收" in out and "←來源 幕009" in out


def test_format_entity_filter():
    out = format_projection(_slots(10), 10, "arcF", entities=["哈利↔榮恩"])
    assert "### 哈利↔榮恩" in out and "### 哈利\n" not in out


def _make_book(tmp_path):
    book = tmp_path / "book"
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "參照" / "狀態事件流.md").write_text(
        "# 狀態事件流\n- 幕009（arcF）· 哈利 · 持有：斗篷遭沒收（此後無）\n",
        encoding="utf-8",
    )
    (book / "story" / "幕綱" / "_index.md").write_text(
        "- 全書順序：arcF（幕001–幕012）\n", encoding="utf-8"
    )
    return book


def test_main_reads_book_and_prints(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）"])
    out = capsys.readouterr().out
    assert rc == 0 and "沒收" in out and "as-of 幕011（arcF）" in out


def test_main_bad_asof_format_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--as-of", "ch11"])
    assert rc == 1
    assert "幕NNN" in capsys.readouterr().err


def test_main_unknown_dimension_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path)
    (book / "story" / "參照" / "狀態事件流.md").write_text(
        "- 幕001（arcF）· 哈利 · 心情：開心\n", encoding="utf-8"
    )
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）"])
    assert rc == 1 and "未知變化維度" in capsys.readouterr().err
