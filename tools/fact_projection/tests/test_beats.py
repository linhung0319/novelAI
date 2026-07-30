"""--for-beat：由程式從幕綱導出 context，而不是讓 LLM 自己填 --entities。"""

import pytest
from fact_projection.beats import BeatLookupError, find_beat
from fact_projection.cli import main

SPINE = "- 全書順序：arc01（幕001–幕030）→ arc02（幕031–幕060）\n"

ARC01 = """\
# arc01

## 承諾區
- 本 arc 承諾：略（這一節不是幕，不得被併進任何一幕）

## 幕002 · 信物現身
- 角色：少年、同伴（法號真某）
- 行動：略
- 伏筆：埋[[伏筆:信物用途]]

## 幕003 · 走了
- 角色：少年
- 伏筆：—

## 本 arc 伏筆狀態
| 伏筆 | 狀態 |
| 信物用途 | 開著 |
| 主宰目的 | 開著 |
"""


def _ch(facts: str) -> str:
    return (
        "---\n對應幕: [幕001, 幕030]\n所屬arc: arc01\n---\n## 本章事實\n" + facts
    )


def _book(tmp_path, chapters: dict[str, str] | None = None, entities=("少年", "同伴")):
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "設定" / "角色").mkdir(parents=True)
    (book / "story" / "幕綱" / "_順序.md").write_text(SPINE, encoding="utf-8")
    (book / "story" / "幕綱" / "arc01.md").write_text(ARC01, encoding="utf-8")
    for name in entities:
        (book / "story" / "設定" / "角色" / f"{name}.md").write_text("略\n", encoding="utf-8")
    # 「主宰目的」由**物件檔**登記（2026-07-27 起揭示層級只住這裡；原本住設定層
    # `.ai.md` 的 🧊 標記，那是「不可重生的裁決住在會被重生的檔裡」）。它尚未落到
    # 任何一幕的伏筆欄——arc02 還沒拆，那是合法狀態（共同約定.md 六）。
    (book / "story" / "物件").mkdir(parents=True)
    (book / "story" / "物件" / "主宰目的.md").write_text(
        "---\n型別: 伏筆\n揭示層級: 水下｜揭示於 收[[伏筆:主宰目的]]\n---\n"
        "## 是什麼\n那個東西要什麼。\n\n"
        "## 為什麼存在\n作者拍板：這條線撐到全書收束才揭。\n",
        encoding="utf-8",
    )
    for name, body in (chapters or {}).items():
        (book / "chapters" / name).write_text(body, encoding="utf-8")
        if name.endswith(".ai.md"):
            (book / "chapters" / f"{name[:-6]}.md").write_text("（正文）\n", encoding="utf-8")
    return book


# ------------------------------------------------------------ 定位

def test_object_files_are_authoritative_entity_names_too(tmp_path):
    """一個**只以物件檔存在**的實體，它的約束不得被 `--for-beat` 靜默篩掉。

    實測過這個洞：作者替某配角立了排除線（住 `story/物件/<名>.md`）但還沒替他寫
    `設定/角色/<名>.md`，於是詞彙表沒有他 → `--for-beat` 把整條排除線篩掉 →
    `write` 理直氣壯地違反它，而沒有任何東西會報。**漏一條排除線比多給 context 嚴重。**
    """
    book = _book(tmp_path, entities=("少年",))  # 同伴刻意沒有設定源檔
    (book / "story" / "物件" / "同伴.md").write_text(
        "---\n型別: 角色\n---\n## 不得寫成什麼\n"
        "| 約束名 | 不得寫成 | 生效自 | 解除於 |\n|---|---|---|---|\n"
        "| 不得先於少年識破信物 | 只當是尋常舊物 | 全書 | — |\n",
        encoding="utf-8",
    )
    ctx = find_beat(book, 2)
    assert ctx.entities == ["少年", "同伴"]  # 依角色欄出現序


def test_finds_beat_and_derives_entities(tmp_path):
    ctx = find_beat(_book(tmp_path), 2)
    assert ctx.arc == "arc01" and ctx.beat == 2
    assert ctx.entities == ["少年", "同伴"]
    assert ctx.foreshadows == ["信物用途"]


def test_role_field_grammar_is_not_parsed_only_matched(tmp_path):
    """角色欄有括號註解與法號別名——靠設定層詞彙表比對，對標點風格免疫。"""
    ctx = find_beat(_book(tmp_path), 2)
    assert "同伴" in ctx.entities  # 欄位裡寫的是「同伴（法號真某）」


def test_non_beat_sections_do_not_leak_into_a_beat(tmp_path):
    """檔尾「本 arc 伏筆狀態」表提到大量伏筆，不得被併進最後一幕。"""
    ctx = find_beat(_book(tmp_path), 3)
    assert ctx.foreshadows == []


def test_missing_beat_raises(tmp_path):
    with pytest.raises(BeatLookupError, match="幕099"):
        find_beat(_book(tmp_path), 99)


# ------------------------------------------------------------ CLI

def test_for_beat_replaces_entities_and_asof(tmp_path, capsys):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch(
                "- 幕002（arc01）· 少年 · 位置：市集\n"
                "- 幕002（arc01）· 路人 · 位置：不該出現在本幕的 context\n"
            )
        },
    )
    assert main(["--book", str(book), "--for-beat", "幕002"]) == 0
    out = capsys.readouterr()
    assert "### 少年" in out.out and "路人" not in out.out
    # `（資訊）` 走 **stdout**（2026-07-28 功能 14 的輸出契約）
    assert "由該幕「角色」欄導出實體" in out.out


def test_explicit_entities_still_win(tmp_path, capsys):
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：市集\n")},
    )
    main(["--book", str(book), "--for-beat", "幕002", "--entities", "同伴"])
    assert "### 少年" not in capsys.readouterr().out


def test_relevant_propositions_narrow_and_report_the_hidden_count(tmp_path, capsys):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch(
                "- 幕001（arc01）· 少年 · 知識前沿："
                "＋尚不知〔信物用途〕、＋尚不知〔主宰目的〕\n"
            )
        },
    )
    assert main(["--book", str(book), "--for-beat", "幕002", "--propositions", "relevant"]) == 0
    out = capsys.readouterr()
    assert "信物用途" in out.out and "主宰目的" not in out.out
    assert "另 1 條休眠中" in out.out  # 縮減 context 不能是靜默的


def test_relevant_requires_for_beat(tmp_path, capsys):
    book = _book(tmp_path, chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲\n")})
    rc = main(["--book", str(book), "--as-of", "幕011（arc01）", "--propositions", "relevant"])
    assert rc == 1 and "需要 --for-beat" in capsys.readouterr().err


def test_default_gives_all_propositions(tmp_path, capsys):
    """預設不縮減——漏一條「尚不知」可能讓 write 洩漏知識邊界。"""
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch(
                "- 幕001（arc01）· 少年 · 知識前沿："
                "＋尚不知〔信物用途〕、＋尚不知〔主宰目的〕\n"
            )
        },
    )
    main(["--book", str(book), "--for-beat", "幕002"])
    assert "主宰目的" in capsys.readouterr().out


def test_relationship_slots_survive_entity_filtering(tmp_path, capsys):
    """關係型 slot 是 `A↔B`，而幕綱角色欄寫的是單個名字。

    用完全相等比對會讓 `關係` 這一整維在 --for-beat 這條路上靜默消失——
    而那正是 write 動筆前唯一會走的查詢。
    """
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年↔同伴 · 關係：萍水相逢 → 結伴同行\n")
        },
    )
    assert main(["--book", str(book), "--for-beat", "幕002"]) == 0
    assert "### 少年↔同伴" in capsys.readouterr().out


def test_unrelated_relationship_slot_is_still_filtered_out(tmp_path, capsys):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 路人甲↔路人乙 · 關係：陌生\n")
        },
    )
    main(["--book", str(book), "--for-beat", "幕002"])
    assert "路人" not in capsys.readouterr().out
