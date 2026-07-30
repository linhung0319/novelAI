import pytest
from fact_projection.cli import format_projection, main
from fact_projection.fold import parse_events, project
from fact_projection.sources import collect_events


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


def _make_book(tmp_path, body=None):
    """事實住 `chapters/chNNNN.ai.md` 的「## 本章事實」——**唯一落點**。

    2026-07-30（驗證輪階段 1c）改：在此之前這份 fixture 把事實寫進
    `story/參照/事實流.md`，於是**整個 `test_cli.py` 測的都是那條舊格式讀取路徑**
    ——而那條路徑的活用戶只有 `一世之尊`（`設計原則.md` E2 第七形態的鏡像：
    測試是綠的，射程是空的）。
    """
    book = tmp_path / "book"
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "chapters").mkdir(parents=True)
    (book / "chapters" / "ch0001.md").write_text("正文\n", encoding="utf-8")
    (book / "chapters" / "ch0001.ai.md").write_text(
        "---\n對應幕: [幕001, 幕012]\n所屬arc: arcF\n---\n## 本章事實\n"
        + (body or "- 幕009（arcF）· 哈利 · 持有：＋〔隱形斗篷〕\n"),
        encoding="utf-8",
    )
    (book / "story" / "幕綱" / "_順序.md").write_text(
        "- 全書順序：arcF（幕001–幕012）\n", encoding="utf-8"
    )
    return book


def test_main_reads_book_and_prints(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）"])
    out = capsys.readouterr().out
    assert rc == 0 and "隱形斗篷" in out and "as-of 幕011（arcF）" in out


def test_main_bad_asof_format_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--as-of", "ch11"])
    assert rc == 1
    assert "幕NNN" in capsys.readouterr().err


def test_main_unknown_token_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path, body="- 幕001（arcF）· 哈利 · 心情：開心\n")
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）"])
    # 格式閘門擋下的問題走 **stdout**（2026-07-28 功能 14 的輸出契約）
    assert rc == 1 and "未知類型 token" in capsys.readouterr().out


def test_main_bad_kinds_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）", "--kinds", "心情"])
    assert rc == 1 and "未知類型" in capsys.readouterr().err


# --------------------------- 舊單檔事實流：讀取路徑 2026-07-30 移除（驗證輪階段 1c）
#
# **本輪代價最大的一筆刪除。** 那條路徑的活用戶只有 `一世之尊`，而那本書的事實層
# 覆蓋率是 **0**（93 章 0 章用 `## 本章事實`）——它的事實軸完全靠這條路徑活著。
# 已拍板的前提：「`一世之尊/` 留原地，接受它從此跑不動」。
# 代價要**被記錄**而不是被發現，所以刪除的另一半是墓碑。


def test_the_retired_single_file_stream_is_not_read(tmp_path):
    """舊檔裡的事實**不再進投影**。"""
    book = _make_book(tmp_path)
    (book / "story" / "參照" / "狀態事件流.md").write_text(
        "- 幕003（arcF）· 哈利 · 位置：舊格式那筆\n", encoding="utf-8"
    )
    events, mode = collect_events(book)
    assert mode == "retired"
    assert not [e for e in events if "舊格式那筆" in e.content]


def test_the_retired_stream_is_a_tombstone_not_silence(tmp_path, capsys):
    """**留著一支沒有工具讀的檔比刪掉它危險**——作者以為那些事實還在生效。

    形狀照抄 2026-07-27 對 `約束.co.md` 的處置（`RETIRED_CONSTRAINT_NAMES`）：
    報成落點錯，不靜默忽略。
    """
    book = _make_book(tmp_path)
    (book / "story" / "參照" / "狀態事件流.md").write_text(
        "- 幕003（arcF）· 哈利 · 位置：舊格式那筆\n", encoding="utf-8"
    )
    notes: list[str] = []
    collect_events(book, orphans=notes)
    (hit,) = [n for n in notes if "狀態事件流.md" in n]
    assert "2026-07-30 起不再讀" in hit
    assert "本章事實" in hit and "沒有任何工具在讀" in hit


def test_a_book_whose_only_facts_are_retired_is_not_called_layer_missing(tmp_path):
    """**「還沒有這一層」與「這一層住在已廢除的落點」是兩件事。**

    回 exit 2 說「還沒有這一層」會是假話——那本書有 93 章的事實，只是沒有人讀。
    """
    book = tmp_path / "old"
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "參照" / "狀態事件流.md").write_text(
        "- 幕003（arcF）· 哈利 · 位置：舊格式那筆\n", encoding="utf-8"
    )
    notes: list[str] = []
    events, mode = collect_events(book, orphans=notes)  # 不 raise LayerMissing
    assert events == [] and mode == "retired"
    assert [n for n in notes if "狀態事件流.md" in n]


def test_no_source_at_all_raises(tmp_path):
    """射程非空的鏡像：真的什麼都沒有時，還是要回「還沒到那一層」。"""
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

