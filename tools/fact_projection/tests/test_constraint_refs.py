"""`fact-refs --constraint` 與約束到期提醒。

補的是報告的 V4：`設計原則.md` E3 說約束**不會自癒**（只被讀、不被再寫，沒有東西會
撞到它），E4 說「以後會發現」要成立的前提是有反向索引——兩條原則同時指名約束，而
`fact-refs` 原本只有 `--entity` 與 `--anchor` 兩條路。
"""

from fact_projection.cli import main, refs_main

SPINE = "- 全書順序：arc01（幕001–幕030）→ arc02（幕031–幕060）\n"

TABLE = "| 約束名 | 不得寫成 | 生效自 | 解除於 |\n|---|---|---|---|\n"


def _book(tmp_path, rows: str = "| 口子開著 | 不得死、不得離位 | 幕002（arc01） | 幕009（arc01） |\n"):
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "_index.md").write_text(SPINE, encoding="utf-8")
    d = book / "story" / "物件"
    d.mkdir(parents=True)
    (d / "真觀.md").write_text(
        "---\n型別: 角色\n---\n## 不得寫成什麼\n" + TABLE + rows, encoding="utf-8"
    )
    return book


def _chapter(book, stem: str, beats: str, prose: str, facts: str = ""):
    (book / "chapters" / f"{stem}.md").write_text(prose, encoding="utf-8")
    (book / "chapters" / f"{stem}.ai.md").write_text(
        f"---\n對應幕: {beats}\n所屬arc: arc01\n---\n## 本章事實\n{facts}",
        encoding="utf-8",
    )


# ------------------------------------------------------------ 反向索引

def test_constraint_refs_list_chapters_written_under_it(tmp_path, capsys):
    book = _book(tmp_path)
    _chapter(
        book,
        "ch0001",
        "[幕001, 幕004]",
        "真觀站在門邊，沒有動。\n",
        "- 幕003（arc01）· 真觀 · 位置：門邊\n",
    )
    _chapter(book, "ch0009", "[幕020, 幕025]", "後來的事與真觀無關了。\n")

    assert refs_main(["--book", str(book), "--constraint", "口子開著"]) == 0
    out = capsys.readouterr().out
    assert "約束〔口子開著〕· 真觀" in out
    assert "幕002（arc01） → 幕009（arc01）" in out
    assert "ch0001" in out  # 射程內
    assert "ch0009" not in out  # 射程外（解除之後才寫的）
    assert "「真觀」×1" in out  # 正文字面命中
    assert "幕003（arc01）" in out  # 射程內的 delta


def test_constraint_refs_reject_unknown_name(tmp_path, capsys):
    book = _book(tmp_path)
    assert refs_main(["--book", str(book), "--constraint", "沒這條"]) == 1
    err = capsys.readouterr().err
    # 打錯名字時列出全書現有的，比只說「查無」有用
    assert "查無約束" in err and "口子開著" in err


def test_constraint_with_no_written_chapter_says_so(tmp_path, capsys):
    """約束天生領先幕綱——射程內還沒有正文是常態，不是錯誤。"""
    book = _book(tmp_path)
    assert refs_main(["--book", str(book), "--constraint", "口子開著"]) == 0
    assert "還沒有任何既成正文受它管" in capsys.readouterr().out


# ------------------------------------------------------------ 到期提醒

def test_release_point_already_written_prints_a_reminder(tmp_path, capsys):
    """一條該解除的約束沒被解除，原本沒有任何機制會撞到它（E2 第六個永久盲點）。"""
    book = _book(tmp_path)
    _chapter(book, "ch0003", "[幕008, 幕012]", "那扇門終於關上了。\n")
    assert main(["--book", str(book), "--as-of", "幕012（arc01）"]) == 0
    # `（資訊）` 走 **stdout**（2026-07-28 功能 14 的輸出契約）
    out = capsys.readouterr().out
    assert "「解除於」幕009（arc01） 已經寫成正文" in out and "ch0003" in out


def test_no_reminder_while_the_release_point_is_unwritten(tmp_path, capsys):
    book = _book(tmp_path)
    _chapter(book, "ch0001", "[幕001, 幕004]", "真觀站在門邊。\n")
    assert main(["--book", str(book), "--as-of", "幕004（arc01）"]) == 0
    assert "已經寫成正文" not in capsys.readouterr().out


def test_no_reminder_for_a_constraint_that_never_releases(tmp_path, capsys):
    book = _book(tmp_path, rows="| 不得升為隱藏高手 | 就是看起來那樣 | 全書 | — |\n")
    _chapter(book, "ch0001", "[幕001, 幕004]", "真觀站在門邊。\n")
    assert main(["--book", str(book), "--as-of", "幕004（arc01）"]) == 0
    assert "已經寫成正文" not in capsys.readouterr().err
