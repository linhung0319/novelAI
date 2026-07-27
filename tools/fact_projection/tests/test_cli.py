import pytest
from fact_projection.cli import format_projection, main
from fact_projection.fold import parse_events, project
from fact_projection.sources import collect_events, resolve_legacy_stream


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


def test_format_orders_state_then_anchor_then_constraint():
    events = parse_events(
        "- 幕002（arcF）· 哈利 · 約束〔不得動用魔杖〕：校規期間\n"
        "- 幕003（arcF）· 哈利 · 錨〔年齡〕：十一\n"
        "- 幕004（arcF）· 哈利 · 持有：得斗篷\n"
    )
    out = format_projection(project(events, {"arcF": 0}, 9, "arcF"), 9, "arcF")
    body = [ln for ln in out.splitlines() if ln.startswith("- ")]
    assert body[0].startswith("- 持有") and body[1].startswith("- 錨〔") and body[2].startswith("- 約束〔")


def _make_book(tmp_path, stream_name="事實流.md", body=None):
    book = tmp_path / "book"
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "參照" / stream_name).write_text(
        body or "# 事實流\n- 幕009（arcF）· 哈利 · 持有：斗篷遭沒收（此後無）\n",
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


def test_main_unknown_token_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path, body="- 幕001（arcF）· 哈利 · 心情：開心\n")
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）"])
    assert rc == 1 and "未知類型 token" in capsys.readouterr().err


def test_main_bad_kinds_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）", "--kinds", "心情"])
    assert rc == 1 and "未知類型" in capsys.readouterr().err


# ------------------------------------------------ 舊格式相容（既有書不遷移）

def test_legacy_prefers_new_name(tmp_path):
    book = _make_book(tmp_path)
    (book / "story" / "參照" / "狀態事件流.md").write_text("# 舊檔\n", encoding="utf-8")
    assert resolve_legacy_stream(book).name == "事實流.md"


def test_legacy_falls_back_to_older_name(tmp_path):
    """一世之尊等既有書不遷移，仍須跑得動（見 事實流.schema.md 舊格式相容）。"""
    book = _make_book(tmp_path, stream_name="狀態事件流.md")
    assert resolve_legacy_stream(book).name == "狀態事件流.md"
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）"])
    assert rc == 0


def test_legacy_absent_returns_none(tmp_path):
    book = tmp_path / "empty"
    (book / "story" / "參照").mkdir(parents=True)
    assert resolve_legacy_stream(book) is None


def test_no_source_at_all_raises(tmp_path):
    book = tmp_path / "empty"
    (book / "story" / "參照").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="物件"):
        collect_events(book)


# ------------------------------------------------- 全書方針節（2026-07-27 功能 04）
#
# 抉擇 4 B 把書級方針放進 `story/物件/全書.md`，它的決定性優點是「方針會自動被
# 載入，不必有人記得查」。**實作時發現那句話照現況是假的**：方針的實體是 `全書`，
# 而 `--for-beat` 的實體集是從幕綱「角色」欄導出的——沒有任何一幕的角色欄會是
# 「全書」，所以方針會被實體過濾**靜默吃掉**。這一節不是加碼，是那個選項成立的
# 必要條件（同 arc 排除線：落點留在原處，載入靠查詢層合流）。


def _policy_slots():
    events = parse_events(
        "- 幕006（arcF）· 哈利 · 持有：得隱形斗篷\n"
        "- 幕001（arcF）· 全書 · 約束〔不寫感情線〕：任何角色的戀愛線\n"
    )
    return project(events, {"arcF": 0}, 10, "arcF")


def test_policy_section_survives_entity_filtering():
    """這是本節存在的**唯一理由**：把 `entities` 設成幕綱會給的樣子（單個角色名），
    方針仍要印出來。"""
    out = format_projection(_policy_slots(), 10, "arcF", entities=["哈利"])
    assert "### 全書方針" in out and "不寫感情線" in out


def test_policy_section_printed_even_when_absent():
    """**0 條也印。**「這本書沒有書級方針」與「沒有人去讀書級方針」是兩件事。"""
    out = format_projection(_slots(10), 10, "arcF")
    tail = out.split("### 全書方針")[1]
    assert "無" in tail


def test_policy_is_not_listed_as_an_entity_section():
    """方針不該同時出現在 `### 全書` 實體節裡——那會讓它看起來像某個角色的狀態。"""
    out = format_projection(_policy_slots(), 10, "arcF")
    assert "### 全書\n" not in out

