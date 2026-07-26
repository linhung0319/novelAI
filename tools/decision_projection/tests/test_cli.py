import pytest
from decision_projection.cli import main, resolve_stream

STREAM = """\
# 裁決流

| 日期 | 來源 | 標的 | 裁決 | 理由 | 射程 | 狀態 |
|------|------|------|------|------|------|------|
| 2026-07-22 | write-test 測試9 | 設定/角色/少年/核心.md | 年齡收窄成定點 | 數字登記防分裂 | 全書 | 生效中 |
| 2026-07-23 | beat-sheet arc07 | 幕綱/arc07.md | 本 arc 母題＝付現 | 論證略 | 至arc07 | 已過射程 |
"""


def _make_book(tmp_path, body=STREAM):
    book = tmp_path / "book"
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "參照" / "裁決流.md").write_text(body, encoding="utf-8")
    return book


def test_main_prints_all(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book)])
    out = capsys.readouterr().out
    assert rc == 0 and "年齡收窄成定點" in out and "本 arc 母題" in out


def test_main_target_filter(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--target", "設定/角色/少年/"])
    out = capsys.readouterr().out
    assert rc == 0 and "年齡收窄成定點" in out and "本 arc 母題" not in out


def test_main_active_only(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--active-only"])
    out = capsys.readouterr().out
    assert rc == 0 and "年齡收窄成定點" in out and "已過射程" not in out


def test_main_no_match_says_so(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--target", "設定/世界觀/魔法.md"])
    assert rc == 0 and "無符合的裁決" in capsys.readouterr().out


def test_main_parse_error_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path, body="| 日期 | 標的 |\n|--|--|\n")
    rc = main(["--book", str(book)])
    assert rc == 1 and "表頭欄位不符" in capsys.readouterr().err


def test_main_missing_file_returns_1(tmp_path, capsys):
    book = tmp_path / "empty"
    (book / "story" / "參照").mkdir(parents=True)
    rc = main(["--book", str(book)])
    assert rc == 1 and "找不到" in capsys.readouterr().err


def test_resolve_stream_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_stream(tmp_path / "nope")
