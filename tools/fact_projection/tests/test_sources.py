"""章 delta ＋ 物件檔的收集、落點檢查與 lint。

**這裡的 fixture 全是自造的。** 新格式（章 delta ＋ 物件檔）在真實語料上覆蓋率是 0
（一世之尊 93 章有 `## 本章事實` 的 0 支、錨 0 筆、約束 0 列），所以那本書只能當
**反**例（見 `test_golden_一世之尊.py`），正例一律在這裡造。
"""

import pytest
from fact_projection.cli import lint_main, main
from fact_projection.fold import parse_spine, project
from fact_projection.ops import SET_DIMENSIONS
from fact_projection.sources import (
    check_kind_placement,
    collect_constraints,
    collect_events,
    lint,
    lint_report,
    section_lines,
)

SPINE = "- 全書順序：arc01（幕001–幕030）→ arc02（幕031–幕060）\n"

TABLE_HEAD = "| 約束名 | 不得寫成 | 生效自 | 解除於 |\n|---|---|---|---|\n"


def _obj(
    *rows: str,
    kind: str = "角色",
    reveal: str = "",
    why: str = "作者拍板：這條線要撐到收束。",
) -> str:
    """一支物件檔。給了 rows 就帶約束表，沒給就靠 `為什麼存在` 過內容測試。"""
    fm = f"---\n型別: {kind}\n"
    if reveal:
        fm += f"揭示層級: {reveal}\n"
    fm += "---\n"
    body = f"## 是什麼\n（一句話。）\n\n## 為什麼存在\n{why}\n"
    if rows:
        body += "\n## 不得寫成什麼\n" + TABLE_HEAD + "".join(r + "\n" for r in rows)
    return fm + body


def _book(
    tmp_path,
    chapters: dict[str, str] | None = None,
    objects: dict[str, str] | None = None,
    legacy_stream: str = "",
    retired_constraints: str = "",
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
    if objects:
        d = book / "story" / "物件"
        d.mkdir(parents=True)
        for name, body in objects.items():
            (d / name).write_text(body, encoding="utf-8")
    if legacy_stream:
        (book / "story" / "參照" / "狀態事件流.md").write_text(
            legacy_stream, encoding="utf-8"
        )
    if retired_constraints:
        (book / "story" / "參照" / "約束.co.md").write_text(
            retired_constraints, encoding="utf-8"
        )
    return book


def _ch(front_facts: str, extra: str = "", beats: str = "[幕001, 幕099]") -> str:
    return (
        "---\ngenerated-from: abc\ngenerated-at: 2026-07-26\n"
        f"對應幕: {beats}\n所屬arc: arc01\n---\n"
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
        objects={"同伴.md": _obj("| 不得識破 | 只當是舊物 | 全書 | — |")},
    )
    events, mode = collect_events(book)
    assert mode == "chapters"
    # 約束不再是事件——它走規則表，不進 fold
    assert [e.origin for e in events] == ["ch0001", "ch0002"]
    assert [e.order for e in events] == [0, 1]  # 跨檔遞增，as-of tiebreak 才穩定
    (c,) = collect_constraints(book)
    assert c.name == "不得識破" and c.entity == "同伴"  # 實體＝檔名
    assert c.origin == "物件/同伴.md"


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
        objects={"同伴.md": _obj("| 甲 | 乙 | 全書 | — |")},
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
    (problem,) = check_kind_placement(events, book)
    assert "重生就沒了" in problem and "不得寫成什麼" in problem


def test_retired_constraint_location_is_reported(tmp_path):
    """`約束.co.md` 這個落點已廢除。**留著它比刪掉它危險**——沒有工具會讀，
    而作者以為那些排除線還在生效。"""
    book = _book(
        tmp_path,
        retired_constraints=(
            "| 約束名 | 實體 | 不得寫成 | 生效自 | 解除於 |\n|---|---|---|---|---|\n"
            "| 甲 | 同伴 | 乙 | 全書 | — |\n"
        ),
    )
    (problem,) = check_kind_placement([], book)
    assert "落點已廢除" in problem and "物件/<該列的實體>.md" in problem
    assert any("落點已廢除" in p for p in lint(book))


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
        objects={"同伴.md": _obj("| 甲 | 乙 | 全書 | — |")},
    )
    assert lint(book) == []


def test_lint_main_exit_codes(tmp_path, capsys):
    clean = _book(tmp_path / "a", chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕")})
    assert lint_main(["--book", str(clean)]) == 0

    dirty = _book(
        tmp_path / "b", chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 心情：開心")}
    )
    assert lint_main(["--book", str(dirty)]) == 1
    # 問題清單走 **stdout**（2026-07-28 功能 14 的輸出契約）
    assert "未知類型 token" in capsys.readouterr().out


# ------------------------------------------------- 覆蓋率輸出（設計原則 E2）

def test_lint_always_reports_what_it_checked_even_when_clean(tmp_path, capsys):
    """只回答「發現幾個問題」的檢查器，在自己被關掉時會印「乾淨」。

    實測就是這樣讓 206 個問題報 0 的（`sources.py` 的整本書豁免開關）。
    """
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕")},
        objects={"同伴.md": _obj("| 甲 | 乙 | 全書 | — |")},
    )
    assert lint_main(["--book", str(book)]) == 0
    out = capsys.readouterr().out
    assert "1 支章 delta" in out
    assert "1 筆事實行（新格式 1·舊格式 0）" in out
    assert "1 支物件檔" in out and "1 條約束" in out


def test_stats_count_both_generations_separately(tmp_path):
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕")},
        legacy_stream="- 幕003（arc01）· 少年 · 位置：舊格式那筆\n",
    )
    _, stats = lint_report(book)
    assert (stats.fact_lines_new, stats.fact_lines_legacy) == (1, 1)


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
    assert any("排除線" in p and "不得寫成什麼" in p for p in lint(book))


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


def test_object_filename_also_registers_a_name(tmp_path):
    """物件檔名同樣算登記——命題名的命名空間＝幕綱伏筆名 ∪ 物件檔名。

    2026-07-27 前第二個來源是設定層 `.ai.md` 的 🧊 標記，那個落點已廢除
    （不可重生的裁決住在會被重生的檔裡）。
    """
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 知識前沿：＋尚不知〔母愛護盾〕")
        },
        objects={"母愛護盾.md": _obj(kind="設定規則")},
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
    book = _book(
        tmp_path,
        legacy_stream="- 幕002（arc01）· 少年 · 知識前沿：得知信物存在，尚不知其真正用途\n",
    )
    assert lint(book) == []


# --------------------------------------- 世代是逐行的，不是整本書一個開關（V6）

def test_generation_is_per_line_not_per_book(tmp_path):
    """混格式的書：舊那行的集合維度豁免，**同一本書裡新章那行照檢**。

    2026-07-27 前 `collect_events` 遇到舊單檔就 early-return，於是新章的 delta
    連讀都沒讀到——一支檔的存在與否決定整本書要不要跑檢查（實測 206 → 0）。
    """
    book = _book(
        tmp_path,
        chapters={
            "ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 知識前沿：這是自由散文，不是操作串")
        },
        legacy_stream="- 幕003（arc01）· 少年 · 知識前沿：舊格式的自由 prose\n",
    )
    events, mode = collect_events(book)
    assert mode == "legacy"
    assert len(events) == 2  # 兩個來源合流，不是二選一
    problems = lint(book)
    assert len(problems) == 1
    assert "ch0001 第" in problems[0] and "集合運算" in problems[0]


def test_purity_applies_to_legacy_lines_too(tmp_path):
    """純化三條是**行本身**的紀律，跟它出生在哪一代無關。

    那 206 筆全部出自舊格式那支檔——豁免它就等於豁免掉唯一的實測病例。
    """
    book = _book(
        tmp_path,
        legacy_stream="- 幕002（arc01）· 少年 · 位置：" + "字" * 250 + "\n",
    )
    (problem,) = lint(book)
    assert "250 字" in problem and "狀態事件流.md" in problem


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
        objects={"同伴.md": _obj("| 甲 | 乙 | 幕005(arc01) | — |")},
    )
    assert main(["--book", str(book), "--as-of", "幕011（arc01）"]) == 1
    # 閘門擋下的問題走 **stdout**（2026-07-28 功能 14 的輸出契約）
    out = capsys.readouterr().out
    assert "格式閘門擋下" in out and "全形／半形" in out


def test_projection_is_gated_by_object_lint_too(tmp_path, capsys):
    """物件檔壞了也擋——投影會把約束合流進來，壞物件檔＝漏一條排除線。"""
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲")},
        objects={"同伴.md": "---\n型別: 不存在的型\n---\n## 為什麼存在\n因為。\n"},
    )
    assert main(["--book", str(book), "--as-of", "幕011（arc01）"]) == 1
    assert "封閉枚舉" in capsys.readouterr().out


def test_ignore_lint_lets_it_through(tmp_path, capsys):
    book = _book(
        tmp_path,
        chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 位置：甲")},
        objects={"同伴.md": _obj("| 甲 | 乙 | 全書 | — |")},
    )
    assert main(["--book", str(book), "--as-of", "幕011（arc01）", "--ignore-lint"]) == 0


def test_projection_still_raises_on_bad_line(tmp_path, capsys):
    """投影是嚴格的——吐出不完整的事實比報錯危險。"""
    book = _book(
        tmp_path, chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 心情：開心")}
    )
    assert main(["--book", str(book), "--as-of", "幕011（arc01）"]) == 1
    assert "未知類型 token" in capsys.readouterr().out


def test_bom_prefixed_files_still_parse(tmp_path):
    """Windows 編輯器寫出的 UTF-8 BOM 不得讓第一筆事實靜默消失。"""
    book = _book(tmp_path)
    (book / "chapters" / "ch0001.ai.md").write_text(
        _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕"), encoding="utf-8-sig"
    )
    (book / "chapters" / "ch0001.md").write_text("（正文）\n", encoding="utf-8")
    d = book / "story" / "物件"
    d.mkdir(parents=True)
    (d / "同伴.md").write_text(
        _obj("| 甲 | 乙 | 全書 | — |"), encoding="utf-8-sig"
    )
    events, _ = collect_events(book)
    assert len(events) == 1
    assert len(collect_constraints(book)) == 1


@pytest.mark.parametrize("mode_file", ["事實流.md", "狀態事件流.md"])
def test_both_legacy_stream_names_are_read(tmp_path, mode_file):
    """舊單檔的兩種命名都吃，而且**不再蓋掉章 delta**——兩邊合流。"""
    book = _book(
        tmp_path, chapters={"ch0001.ai.md": _ch("- 幕002（arc01）· 少年 · 持有：＋〔舊劍〕")}
    )
    (book / "story" / "參照" / mode_file).write_text(
        "- 幕003（arc01）· 少年 · 位置：舊格式那筆\n", encoding="utf-8"
    )
    events, mode = collect_events(book)
    assert mode == "legacy"
    assert [(e.origin, e.generation) for e in events] == [
        (mode_file, "legacy"),
        ("ch0001", "new"),
    ]
