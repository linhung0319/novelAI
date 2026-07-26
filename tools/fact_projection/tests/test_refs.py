"""反向索引與 --history：整條軸原本只有正向，這兩支補的是「誰依賴了這條事實」。"""

from fact_projection.cli import main, refs_main
from fact_projection.refs import literal_terms

SPINE = "- 全書順序：arc01（幕001–幕030）→ arc02（幕031–幕060）\n"


def _ch(facts: str) -> str:
    return "---\nk: v\n---\n## 本章事實\n" + facts


def _book(tmp_path, chapters: dict[str, str], prose: dict[str, str] | None = None):
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "_index.md").write_text(SPINE, encoding="utf-8")
    for name, body in chapters.items():
        (book / "chapters" / name).write_text(body, encoding="utf-8")
        if name.endswith(".ai.md"):
            (book / "chapters" / f"{name[:-6]}.md").write_text("（正文）\n", encoding="utf-8")
    for name, body in (prose or {}).items():
        (book / "chapters" / name).write_text(body, encoding="utf-8")
    return book


# ------------------------------------------------------------ --history

def test_history_lists_every_event_for_one_slot(tmp_path, capsys):
    book = _book(
        tmp_path,
        {
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 知識前沿：＋尚不知〔信物用途〕\n"),
            "ch0002.ai.md": _ch("- 幕040（arc02）· 少年 · 知識前沿：〔信物用途〕→已知\n"),
        },
    )
    assert main(["--book", str(book), "--history", "少年/知識前沿"]) == 0
    out = capsys.readouterr().out
    assert "2 筆" in out and "＋尚不知〔信物用途〕" in out and "→已知" in out


def test_history_orders_by_spine_not_beat_number(tmp_path, capsys):
    """arc02 的幕031 排在 arc01 的幕030 之後——定序走全書順序，不比幕號大小。"""
    book = _book(
        tmp_path,
        {
            "ch0001.ai.md": _ch("- 幕031（arc02）· 少年 · 位置：後面那個\n"),
            "ch0002.ai.md": _ch("- 幕030（arc01）· 少年 · 位置：前面那個\n"),
        },
    )
    main(["--book", str(book), "--history", "少年/位置"])
    body = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("- ")]
    assert "前面那個" in body[0] and "後面那個" in body[1]


def test_history_bad_format_returns_1(tmp_path, capsys):
    book = _book(tmp_path, {"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲\n")})
    assert main(["--book", str(book), "--history", "少年知識前沿"]) == 1
    assert "實體/維度" in capsys.readouterr().err


def test_asof_is_optional_only_when_history_is_given(tmp_path, capsys):
    book = _book(tmp_path, {"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲\n")})
    assert main(["--book", str(book)]) == 1
    assert "--as-of" in capsys.readouterr().err


# ------------------------------------------------------------ fact-refs --entity

def test_entity_refs_use_the_structured_column(tmp_path, capsys):
    book = _book(
        tmp_path,
        {
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲\n"),
            "ch0040.ai.md": _ch("- 幕040（arc02）· 少年 · 位置：乙\n"),
            "ch0041.ai.md": _ch("- 幕041（arc02）· 同伴 · 位置：丙\n"),
        },
    )
    assert refs_main(["--book", str(book), "--entity", "少年"]) == 0
    out = capsys.readouterr().out
    assert "ch0001" in out and "ch0040" in out and "ch0041" not in out


def test_entity_refs_match_relationship_slots(tmp_path, capsys):
    book = _book(
        tmp_path,
        {"ch0001.ai.md": _ch("- 幕002（arc01）· 少年↔同伴 · 關係：結盟\n")},
    )
    refs_main(["--book", str(book), "--entity", "同伴"])
    assert "ch0001" in capsys.readouterr().out


def test_after_filters_to_downstream_only(tmp_path, capsys):
    """這正是主要用途：改了 幕002 的事實，問「之後有哪幾章依賴它」。"""
    book = _book(
        tmp_path,
        {
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲\n"),
            "ch0040.ai.md": _ch("- 幕040（arc02）· 少年 · 位置：乙\n"),
        },
    )
    refs_main(["--book", str(book), "--entity", "少年", "--after", "幕002（arc01）"])
    out = capsys.readouterr().out
    assert "ch0040" in out and "ch0001" not in out


# ------------------------------------------------------------ fact-refs --anchor

def test_literal_terms_drops_parenthetical_notes():
    assert literal_terms("巴掌大、缺一角的青銅牌（往後一律以此為準）") == [
        "巴掌大",
        "缺一角的青銅牌",
    ]


def test_anchor_finds_stale_prose_downstream(tmp_path, capsys):
    """本測試就是那個洞：ch0009 改成銀牌後，ch0040 的正文還寫著青銅牌。"""
    book = _book(
        tmp_path,
        chapters={
            "ch0009.ai.md": _ch("- 幕002（arc01）· 信物 · 錨〔形制〕：青銅牌\n"),
            "ch0040.ai.md": _ch("- 幕040（arc02）· 信物 · 錨〔形制〕：銀牌\n"),
        },
        prose={
            "ch0009.md": "他攤開手掌，那是一塊青銅牌。\n",
            "ch0040.md": "他把青銅牌收回懷裡，青銅牌還帶著體溫。\n",
            "ch0041.md": "什麼都沒提。\n",
        },
    )
    assert refs_main(["--book", str(book), "--anchor", "形制"]) == 0
    out = capsys.readouterr().out
    assert "青銅牌" in out and "ch0040×2" in out and "ch0041" not in out
    assert "銀牌" in out  # 新舊值都列出來，讓人看得出改了什麼


def test_anchor_accepts_name_with_or_without_brackets(tmp_path, capsys):
    book = _book(
        tmp_path,
        chapters={"ch0009.ai.md": _ch("- 幕002（arc01）· 信物 · 錨〔形制〕：青銅牌\n")},
        prose={"ch0009.md": "青銅牌\n"},
    )
    assert refs_main(["--book", str(book), "--anchor", "〔形制〕"]) == 0
    assert "青銅牌" in capsys.readouterr().out


def test_unknown_anchor_returns_1(tmp_path, capsys):
    book = _book(tmp_path, {"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲\n")})
    assert refs_main(["--book", str(book), "--anchor", "不存在"]) == 1
    assert "查無錨" in capsys.readouterr().err


def test_was_recovers_a_value_that_was_edited_in_place(tmp_path, capsys):
    """錨就地改版時舊值會從 ledger 消失——而要找的正是還寫著舊值的下游正文。"""
    book = _book(
        tmp_path,
        chapters={"ch0009.ai.md": _ch("- 幕002（arc01）· 信物 · 錨〔形制〕：銀牌\n")},
        prose={"ch0040.md": "他把青銅牌收回懷裡。\n"},
    )
    assert refs_main(
        ["--book", str(book), "--anchor", "形制", "--was", "巴掌大、缺一角的青銅牌"]
    ) == 0
    out = capsys.readouterr().out
    # 正文只寫「青銅牌」，錨的值卻是「缺一角的青銅牌」——回退到最長有命中的後綴
    assert "「青銅牌」" in out and "ch0040" in out


def test_multiple_registered_values_are_all_grepped(tmp_path, capsys):
    """改版時另發一行同名事件的話，新舊值都在 ledger，不必傳 --was。"""
    book = _book(
        tmp_path,
        chapters={
            "ch0009.ai.md": _ch("- 幕002（arc01）· 信物 · 錨〔形制〕：青銅牌\n"),
            "ch0040.ai.md": _ch("- 幕040（arc02）· 信物 · 錨〔形制〕：銀牌\n"),
        },
        prose={"ch0041.md": "青銅牌與銀牌都提了一次。\n"},
    )
    refs_main(["--book", str(book), "--anchor", "形制"])
    out = capsys.readouterr().out
    assert "「青銅牌」" in out and "「銀牌」" in out
