"""章 delta ＋ 約束表的收集、落點檢查與 lint。"""

import pytest
from fact_projection.cli import lint_main, main
from fact_projection.fold import parse_spine, project
from fact_projection.ops import SET_DIMENSIONS
from fact_projection.sources import (
    check_kind_placement,
    collect_constraints,
    collect_events,
    lint,
    section_lines,
)

SPINE = "- 全書順序：arc01（幕001–幕030）→ arc02（幕031–幕060）\n"

TABLE_HEAD = (
    "| 約束名 | 實體 | 不得寫成 | 生效自 | 解除於 |\n"
    "|---|---|---|---|---|\n"
)


def _table(*rows: str) -> str:
    return "# 約束\n\n" + TABLE_HEAD + "".join(r if r.endswith("\n") else r + "\n" for r in rows)


def _book(
    tmp_path,
    chapters: dict[str, str] | None = None,
    constraints: str = "",
    legacy_constraints: str = "",
):
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "_index.md").write_text(SPINE, encoding="utf-8")
    for name, body in (chapters or {}).items():
        (book / "chapters" / name).write_text(body, encoding="utf-8")
        # 每支衍生檔都要有正文源，否則會被（正確地）報成孤兒
        if name.endswith(".ai.md"):
            (book / "chapters" / f"{name[:-6]}.md").write_text("（正文）\n", encoding="utf-8")
    if constraints:
        (book / "story" / "參照" / "約束.co.md").write_text(constraints, encoding="utf-8")
    if legacy_constraints:
        (book / "story" / "參照" / "約束.md").write_text(
            legacy_constraints, encoding="utf-8"
        )
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

def test_collects_across_chapters(tmp_path):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕"),
            "ch0002.ai.md": _ch("- 幕009（arc01）· 少年 · 持有：−〔舊劍〕"),
        },
        constraints=_table("| 不得識破 | 同伴 | 只當是舊物 | 全書 | — |"),
    )
    events, mode = collect_events(book)
    assert mode == "chapters"
    # 約束不再是事件——它走規則表，不進 fold
    assert [e.origin for e in events] == ["ch0001", "ch0002"]
    assert [e.order for e in events] == [0, 1]  # 跨檔遞增，as-of tiebreak 才穩定
    assert [c.name for c in collect_constraints(book)] == ["不得識破"]


def test_legacy_constraint_log_still_flows_through_events(tmp_path):
    """2026-07-27 前的 4 欄信封 append log：既有書不遷移，仍須讀得動。"""
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕")},
        legacy_constraints="- 幕005（arc01）· 同伴 · 約束〔不得識破〕：只當是舊物\n",
    )
    events, _ = collect_events(book)
    assert [e.origin for e in events] == ["ch0001", "約束.md"]
    assert collect_constraints(book) == []  # 舊格式不走規則表


def test_projection_folds_chapter_delta(tmp_path):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕"),
            "ch0002.ai.md": _ch("- 幕009（arc01）· 少年 · 持有：−〔舊劍〕"),
        },
    )
    events, _ = collect_events(book)
    spine = parse_spine(SPINE)
    slots = {
        s.token: s
        for s in project(events, spine, 20, "arc01", set_dims=SET_DIMENSIONS)
    }
    assert slots["持有"].items == ()  # ch0001 加、ch0002 減，折完是空集合
    assert slots["持有"].origin == "ch0002"  # 來源標最後動它的那一章


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
        constraints=_table("| 甲 | 同伴 | 乙 | 全書 | — |"),
    )
    events, _ = collect_events(book)
    assert events == []


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
    assert "重生就沒了" in problem and "約束.co.md" in problem


def test_state_in_legacy_constraint_log_is_reported(tmp_path):
    book = _book(tmp_path, legacy_constraints="- 幕005（arc01）· 少年 · 持有：＋〔舊劍〕\n")
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
                "- 幕004（arc01）· 少年 · 持有：＋〔舊劍〕"
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
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕")},
        constraints=_table("| 甲 | 同伴 | 乙 | 全書 | — |"),
    )
    assert lint(book) == []


def test_lint_main_exit_codes(tmp_path, capsys):
    clean = _book(tmp_path / "a", chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕")})
    assert lint_main(["--book", str(clean)]) == 0

    dirty = _book(
        tmp_path / "b", chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 心情：開心")}
    )
    assert lint_main(["--book", str(dirty)]) == 1
    assert "未知類型 token" in capsys.readouterr().err


# ------------------------------------------------------------ delta 純化

def test_overlong_content_is_reported(tmp_path):
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：" + "字" * 250)},
    )
    (problem,) = lint(book)
    assert "250 字" in problem and "不必重抄" in problem


def test_paren_heavy_content_is_reported(tmp_path):
    """夾帶：實測病態期 51.9% 的字元在括號裡，裡面全是別條軸的東西。"""
    body = "他到了那裡" + "（" + "本 arc 收·口子閉合·真觀 on-page 最後一次" * 3 + "）"
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch(f"- 幕002（arc01）· 少年 · 位置：{body}")},
    )
    assert any("疑似夾帶設計註" in p for p in lint(book))


def test_constraint_vocabulary_in_delta_is_reported(tmp_path):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：到了藏經閣，下游不得寫成他離開")
        },
    )
    assert any("排除線" in p and "約束.co.md" in p for p in lint(book))


def test_short_pure_delta_passes_purity(tmp_path):
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：雜役院（與同伴同屋）")},
    )
    assert lint(book) == []


# ------------------------------------------------------------ 命題名共用伏筆命名空間

def _with_beatsheet(book, arc_body: str):
    (book / "story" / "幕綱" / "arc01.md").write_text(arc_body, encoding="utf-8")
    return book


def test_proposition_name_must_be_a_registered_foreshadow(tmp_path):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 知識前沿：＋尚不知〔沒登記過的東西〕")
        },
    )
    _with_beatsheet(book, "## 幕002 · 甲\n- 伏筆：埋[[伏筆:信物用途]]\n")
    (problem,) = lint(book)
    assert "未登記" in problem and "沒登記過的東西" in problem


def test_registered_foreshadow_name_passes(tmp_path):
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 知識前沿：＋尚不知〔信物用途〕")
        },
    )
    _with_beatsheet(book, "## 幕002 · 甲\n- 伏筆：埋[[伏筆:信物用途]]\n")
    assert lint(book) == []


def test_underwater_marker_also_registers_a_name(tmp_path):
    """🧊 水下標記指向的伏筆名同樣算登記（共同約定.md 六）。"""
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 知識前沿：＋尚不知〔母愛護盾〕")
        },
    )
    (book / "story" / "設定" / "角色").mkdir(parents=True)
    (book / "story" / "設定" / "角色" / "少年.ai.md").write_text(
        "## 水下\n- 母親留下的東西（🧊 水下｜揭示於 收[[伏筆:母愛護盾]]）\n",
        encoding="utf-8",
    )
    assert lint(book) == []


def test_plain_set_dimension_names_are_not_cross_checked(tmp_path):
    """持有／能力的名字是道具與招式，不共用伏筆命名空間。"""
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔沒登記過的劍〕")},
    )
    assert lint(book) == []


def test_legacy_book_prose_is_not_linted_for_ops(tmp_path):
    """一世之尊刻意不遷移——舊格式的自由 prose 不該被新語法報一整本。"""
    book = _book(tmp_path)
    (book / "story" / "參照" / "狀態事件流.md").write_text(
        "- 幕002（arc01）· 少年 · 知識前沿：得知信物存在，尚不知其真正用途\n",
        encoding="utf-8",
    )
    assert lint(book) == []


# ------------------------------------------------------------ 孤兒衍生檔（洞 b）

def test_orphan_ai_md_facts_are_marked_not_dropped(tmp_path):
    """作者合併兩章、只刪了正文源：那一章的事實仍會被餵進 write 的 context。

    `derived-sync check` 早就報 orphan 了，但兩支工具互不知會。不靜默排除——
    讓事實憑空消失比標記更危險。
    """
    book = _book(tmp_path, chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲")})
    (book / "chapters" / "ch0002.ai.md").write_text(
        _ch("- 幕009（arc01）· 少年 · 持有：＋〔舊劍〕"), encoding="utf-8"
    )
    orphans: list[str] = []
    events, _ = collect_events(book, orphans=orphans)
    assert len(orphans) == 1 and "ch0002" in orphans[0]
    assert any(e.origin == "ch0002〔孤兒〕" for e in events)


def test_orphan_is_a_lint_problem(tmp_path):
    book = _book(tmp_path)
    (book / "chapters" / "ch0002.ai.md").write_text(
        _ch("- 幕009（arc01）· 少年 · 位置：甲"), encoding="utf-8"
    )
    assert any("找不到正文源" in p for p in lint(book))


# ------------------------------------------------------------ 投影前自 lint（情境 2）

def test_projection_is_gated_by_lint(tmp_path, capsys):
    """作者手改約束表打成半形括號——訊息要直接說破，而不是投影中途才炸。"""
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲")},
        constraints=_table("| 甲 | 同伴 | 乙 | 幕005(arc01) | — |"),
    )
    assert main(["--book", str(book), "--as-of", "幕011（arc01）"]) == 1
    err = capsys.readouterr().err
    assert "格式閘門擋下" in err and "全形／半形" in err


def test_ignore_lint_lets_it_through(tmp_path, capsys):
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲")},
        constraints=_table("| 甲 | 同伴 | 乙 | 全書 | — |"),
    )
    assert main(["--book", str(book), "--as-of", "幕011（arc01）", "--ignore-lint"]) == 0


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
        _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕"), encoding="utf-8-sig"
    )
    (book / "story" / "參照" / "約束.co.md").write_text(
        _table("| 甲 | 同伴 | 乙 | 全書 | — |"), encoding="utf-8-sig"
    )
    events, _ = collect_events(book)
    assert len(events) == 1
    assert len(collect_constraints(book)) == 1


@pytest.mark.parametrize("mode_file", ["事實流.md", "狀態事件流.md"])
def test_legacy_book_takes_precedence(tmp_path, mode_file):
    book = _book(
        tmp_path, chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕")}
    )
    (book / "story" / "參照" / mode_file).write_text(
        "- 幕003（arc01）· 少年 · 持有：舊格式那筆\n", encoding="utf-8"
    )
    events, mode = collect_events(book)
    assert mode == "legacy" and len(events) == 1
    assert events[0].content == "舊格式那筆"
