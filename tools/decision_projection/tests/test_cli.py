import pytest
from decision_projection.cli import main, resolve_stream

STREAM = """\
# 裁決流

| 日期 | 來源 | 標的 | 裁決 | 理由 | 射程 | 狀態 |
|------|------|------|------|------|------|------|
| 2026-07-22 | write-test 測試9 | 設定/角色/少年/核心.md | 年齡收窄成定點 | 數字登記防分裂 | 全書 | 生效中 |
| 2026-07-23 | beat-sheet arc07 | 幕綱/arc07.md | 本 arc 母題＝付現 | 論證略 | 至arc07 | 已過射程 |
"""


def _make_book(tmp_path, body=STREAM, name="裁決流.md"):
    book = tmp_path / "book"
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "參照" / name).write_text(body, encoding="utf-8")
    return book


def test_legacy_name_still_resolves(tmp_path):
    """`.co.md` 這個檔類 2026-07-27 廢除（功能 04，依 `設計原則.md` A4），
    但既有書不必為改名動書內檔（比照 就緒儀表.md / .ai.md 雙吃）。"""
    book = _make_book(tmp_path, name="裁決流.co.md")
    assert resolve_stream(book).name == "裁決流.co.md"
    assert main(["--book", str(book)]) == 0


def test_new_name_wins_when_both_exist(tmp_path):
    """新舊並存時取新名。**2026-07-27 前這個優先序是相反的**（`.co.md` 贏）。"""
    book = _make_book(tmp_path)
    (book / "story" / "參照" / "裁決流.co.md").write_text("# 舊檔\n", encoding="utf-8")
    assert resolve_stream(book).name == "裁決流.md"


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


def test_main_missing_stream_is_exit_2_with_a_coverage_line(tmp_path, capsys):
    """**「這本書還沒有裁決軸」與「裁決流格式壞了」是兩件事**（2026-07-28 功能 14，
    抉擇 6 A）：exit 2，而且照樣印覆蓋率行——6 本書裡有 3 本長期是前者，
    不分開的話 CI 會被那 3 本永遠釘在紅色。"""
    book = tmp_path / "empty"
    (book / "story" / "參照").mkdir(parents=True)
    rc = main(["--book", str(book)])
    out = capsys.readouterr()
    assert rc == 2
    assert "掃了 0 列裁決" in out.out and "還沒有這一層" in out.out
    assert out.err == ""


def test_resolve_stream_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_stream(tmp_path / "nope")


# ------------------------------------------------ 標的分段比對（2026-07-27）

def test_directory_form_upgrade_no_longer_loses_old_decisions(tmp_path, capsys):
    """角色源檔升級成目錄形態是 schema 明文建議的路徑；升級不該讓舊裁決靜默失聯。"""
    body = STREAM.replace("設定/角色/少年/核心.md", "設定/角色/少年.md")
    book = _make_book(tmp_path, body=body)
    main(["--book", str(book), "--target", "設定/角色/少年/核心.md"])
    assert "年齡收窄成定點" in capsys.readouterr().out


def test_prefix_of_a_name_is_not_a_match(tmp_path, capsys):
    """假陽性：字串前綴會讓「設定/角色/真」命中 真觀／真慧／真應。"""
    body = STREAM.replace("設定/角色/少年/核心.md", "設定/角色/真觀.md")
    book = _make_book(tmp_path, body=body)
    main(["--book", str(book), "--target", "設定/角色/真"])
    assert "年齡收窄成定點" not in capsys.readouterr().out


# ------------------------------------------------ 射程自動判定（2026-07-27）

SPINE = "- 全書順序：arc07（幕701–幕799）→ arc11（幕1001–幕1099）\n"


def _with_spine(book):
    (book / "story" / "幕綱").mkdir(parents=True, exist_ok=True)
    (book / "story" / "幕綱" / "_index.md").write_text(SPINE, encoding="utf-8")
    return book


def test_scope_expiry_is_computed_not_hand_maintained(tmp_path, capsys):
    """射程欄 2026-07-27 前程式從未讀過——「至arc07」在 arc11 仍回「生效中」。"""
    body = STREAM.replace("| 至arc07 | 已過射程 |", "| 至arc07 | 生效中 |")
    book = _with_spine(_make_book(tmp_path, body=body))
    main(["--book", str(book), "--active-only", "--as-of", "arc11"])
    out = capsys.readouterr().out
    assert "本 arc 母題" not in out  # 射程已過，程式自己算出來的
    assert "年齡收窄成定點" in out  # 射程＝全書，仍在


def test_scope_still_active_within_range(tmp_path, capsys):
    body = STREAM.replace("| 至arc07 | 已過射程 |", "| 至arc07 | 生效中 |")
    book = _with_spine(_make_book(tmp_path, body=body))
    main(["--book", str(book), "--active-only", "--as-of", "arc07"])
    assert "本 arc 母題" in capsys.readouterr().out


def test_as_of_unknown_arc_returns_1(tmp_path, capsys):
    book = _with_spine(_make_book(tmp_path))
    assert main(["--book", str(book), "--active-only", "--as-of", "arc99"]) == 1
    assert "不在 spine" in capsys.readouterr().err


def test_missing_target_path_is_reported_as_info(tmp_path, capsys):
    book = _make_book(tmp_path)
    main(["--book", str(book)])
    # `（資訊）` 走 **stdout**（2026-07-28 功能 14 的輸出契約）
    assert "在書內找不到" in capsys.readouterr().out


# ------------------------------------------------- 待裁決那一節（2026-07-27 功能 04）
#
# 兩軸共用 `標的` 選擇器，所以查一次就同時看到「還沒裁決的」與「已經裁決過的」。
# 抉擇 2 A 把回饋集中成一支檔之後，「消化前先看回饋」本來會變成一個新的
# 「有人記得跑」的步驟——合流進既有查詢，它就不是新步驟，是既有步驟多吐一節。

PENDING = (
    "| 日期 | 來源 | 標的 | 發現 |\n"
    "|------|------|------|------|\n"
    "| 2026-07-25 | write-test 測試9 | 設定/角色/少年/核心.md | 其「需要」中段就被滿足 |\n"
    "| 2026-07-26 | beat-test 測試4 | 設定/世界觀/魔法.md | 規則不夠用 |\n"
)


def test_pending_section_printed_even_when_empty(tmp_path, capsys):
    """**0 列也印。**「這個標的沒有待裁決」與「沒有人去讀待裁決」是兩件事。"""
    book = _make_book(tmp_path)
    main(["--book", str(book)])
    out = capsys.readouterr().out
    assert "## 待裁決" in out and "沒有待裁決的回饋" in out


def test_pending_rows_are_listed(tmp_path, capsys):
    book = _make_book(tmp_path)
    (book / "story" / "參照" / "待裁決.md").write_text(PENDING, encoding="utf-8")
    main(["--book", str(book)])
    out = capsys.readouterr().out
    assert "其「需要」中段就被滿足" in out and "規則不夠用" in out


def test_pending_shares_the_target_selector(tmp_path, capsys):
    """給切面也命中管整個角色的列（路徑分段雙向前綴），與裁決流同一套。"""
    book = _make_book(tmp_path)
    (book / "story" / "參照" / "待裁決.md").write_text(PENDING, encoding="utf-8")
    main(["--book", str(book), "--target", "設定/角色/少年/"])
    out = capsys.readouterr().out
    assert "其「需要」中段就被滿足" in out and "規則不夠用" not in out


def test_coverage_line_separates_scanned_from_matched(tmp_path, capsys):
    """修掉 V2：空表／被註解吞掉的表，與「真的沒有相關裁決」曾經**逐字相同**。"""
    book = _make_book(tmp_path)
    (book / "story" / "參照" / "待裁決.md").write_text(PENDING, encoding="utf-8")
    main(["--book", str(book), "--target", "設定/角色/少年/"])
    out = capsys.readouterr().out
    assert "掃描了 2 列裁決／命中 1 列" in out
    assert "待裁決 2 列／命中 1 列" in out


def test_coverage_line_on_an_empty_stream(tmp_path, capsys):
    book = _make_book(tmp_path, body="# 裁決流\n\n（還沒有任何裁決）\n")
    main(["--book", str(book)])
    out = capsys.readouterr().out
    assert "掃描了 0 列裁決／命中 0 列" in out
