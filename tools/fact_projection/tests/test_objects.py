"""物件軸：檔名即 ID、型別枚舉、節枚舉、內容測試、揭示層級、近似名。

**全部是自造 fixture。** 物件軸 2026-07-27 才建，真實語料上一支都沒有——所以這裡
既是規格也是唯一的正例來源（一世之尊只能當反例，見 `test_golden_一世之尊.py`）。
"""

import pytest
from fact_projection.cli import object_lint_main
from fact_projection.objects import (
    KINDS,
    POLICY_KIND,
    POLICY_NAME,
    check_near_miss,
    check_objects,
    check_reveal_targets,
    load_objects,
    suggest_objects,
    unbuilt_arcs,
)
from fact_projection.sources import collect_constraints, lint, lint_report

SPINE = "- 全書順序：arc01（幕001–幕030）→ arc02（幕031–幕060）\n"

ARC01 = """\
# arc01

## 幕002 · 信物現身
- 角色：少年
- 伏筆：埋[[伏筆:小玉佛來歷]]

## 幕009 · 揭底
- 角色：少年
- 伏筆：收[[伏筆:小玉佛來歷]]
"""


def _book(tmp_path, objects: dict[str, str], arcs: dict[str, str] | None = None):
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    beats = book / "story" / "幕綱"
    beats.mkdir(parents=True)
    (beats / "_index.md").write_text(SPINE, encoding="utf-8")
    for name, body in (arcs or {"arc01.md": ARC01}).items():
        (beats / name).write_text(body, encoding="utf-8")
    d = book / "story" / "物件"
    d.mkdir(parents=True)
    for name, body in objects.items():
        (d / name).write_text(body, encoding="utf-8")
    return book


def _obj(front: str = "型別: 伏筆", body: str = "## 為什麼存在\n作者拍板。\n") -> str:
    return f"---\n{front}\n---\n{body}"


# ------------------------------------------------------------ 型別

def test_kinds_are_the_closed_eight():
    """七型是 2026-07-27 功能 01 拍板的；第八型 `方針` 同日功能 04 新增——
    那是「要第八型＝停下來問作者」這條規則**第一次被執行**（作者拍板）。
    這個 assert 是枚舉的閘門：要第九型也一樣，停下來問。"""
    assert KINDS == (
        "伏筆",
        "道具",
        "角色",
        "關係",
        "組織",
        "地點",
        "設定規則",
        "方針",
    )


def test_multiple_kinds_first_is_primary(tmp_path):
    """小玉佛既是伏筆又是道具——抉擇 2 選扁平＋型別欄，就是為了不必選邊站。"""
    book = _book(tmp_path, {"小玉佛來歷.md": _obj("型別: 伏筆、道具")})
    (o,) = load_objects(book)
    assert o.kinds == ("伏筆", "道具")
    assert check_objects([o]) == []


def test_unknown_kind_is_blocked(tmp_path):
    book = _book(tmp_path, {"甲.md": _obj("型別: 法寶")})
    (problem,) = check_objects(load_objects(book))
    assert "不在封閉枚舉內" in problem and "停下來問作者" in problem


def test_missing_kind_is_blocked(tmp_path):
    book = _book(tmp_path, {"甲.md": "---\n揭示層級: 公開\n---\n## 為什麼存在\n略。\n"})
    (problem,) = check_objects(load_objects(book))
    assert "缺 `型別`" in problem


# ------------------------------------------------------------ 檔名即 ID

def test_bad_filename_chars_are_blocked(tmp_path):
    book = _book(tmp_path, {"甲〔乙〕.md": _obj()})
    (problem,) = check_objects(load_objects(book))
    assert "檔名含" in problem


def test_underscore_prefixed_files_are_not_objects(tmp_path):
    """保留給日後的說明檔／rollup。"""
    book = _book(tmp_path, {"_說明.md": "隨便寫\n", "甲.md": _obj()})
    assert [o.name for o in load_objects(book)] == ["甲"]


# ------------------------------------------------------------ 節枚舉與內容測試

def test_stray_section_is_blocked(tmp_path):
    book = _book(
        tmp_path, {"甲.md": _obj(body="## 為什麼存在\n略。\n\n## 逐幕狀態\n- 幕001：略\n")}
    )
    (problem,) = check_objects(load_objects(book))
    assert "枚舉外的節" in problem and "逐幕狀態" in problem


def test_object_with_neither_why_nor_constraints_should_not_exist(tmp_path):
    """G4 的內容測試，可執行化：兩節都寫不出來的物件不必開檔。"""
    book = _book(tmp_path, {"路人甲.md": _obj(body="## 是什麼\n一個路人。\n")})
    (problem,) = check_objects(load_objects(book))
    assert "兩節都空" in problem and "不必開檔" in problem


def test_constraints_alone_satisfy_the_content_test(tmp_path):
    book = _book(
        tmp_path,
        {
            "真觀.md": _obj(
                "型別: 角色",
                "## 不得寫成什麼\n| 約束名 | 不得寫成 | 生效自 | 解除於 |\n"
                "|---|---|---|---|\n| 不得升為隱藏高手 | 就是看起來那樣 | 全書 | — |\n",
            )
        },
    )
    assert check_objects(load_objects(book)) == []
    (c,) = collect_constraints(book)
    assert c.entity == "真觀" and c.origin == "物件/真觀.md"


# ------------------------------------------------------------ 揭示層級（V1／V2）

def test_reveal_pointing_at_a_paid_beat_is_info(tmp_path):
    book = _book(
        tmp_path,
        {
            "小玉佛來歷.md": _obj(
                "型別: 伏筆\n揭示層級: 水下｜揭示於 收[[伏筆:小玉佛來歷]]"
            )
        },
    )
    notes: list[str] = []
    assert check_reveal_targets(book, load_objects(book), notes=notes) == []
    assert len(notes) == 1 and "幕綱有收點" in notes[0]


def test_cross_book_reveal_is_accepted(tmp_path):
    book = _book(tmp_path, {"甲.md": _obj("型別: 設定規則\n揭示層級: 水下｜跨集留白")})
    (o,) = load_objects(book)
    assert o.cross_book and o.reveal_target is None
    assert check_reveal_targets(book, [o]) == []


def test_public_is_the_default(tmp_path):
    book = _book(tmp_path, {"甲.md": _obj()})
    (o,) = load_objects(book)
    assert not o.underwater and o.reveal_raw == "公開"


@pytest.mark.parametrize(
    "bad",
    [
        "揭示層級: 🧊水下",  # 舊的 front-matter 鍵寫法
        "揭示層級: 後段才揭",  # 散文
        "揭示層級: 水下",  # 沒二選一
        "揭示層級: 水下｜大概結局吧",  # 既沒指向收點也沒明標跨集留白
    ],
)
def test_only_one_reveal_syntax_survives(tmp_path, bad):
    """2026-07-27 前有三種 schema 授權的寫法而工具只認一種，92 次出現 91 次隱形。"""
    book = _book(tmp_path, {"甲.md": _obj(f"型別: 伏筆\n{bad}")})
    errors: list[str] = []
    load_objects(book, errors=errors)
    assert len(errors) == 1 and "揭示層級" in errors[0]


def test_reveal_pointing_nowhere_is_a_suspect(tmp_path):
    book = _book(
        tmp_path,
        {"甲.md": _obj("型別: 伏筆\n揭示層級: 水下｜揭示於 收[[伏筆:打錯的名字]]")},
        arcs={"arc01.md": ARC01, "arc02.md": "# arc02\n\n## 幕031 · 略\n- 角色：少年\n"},
    )
    (problem,) = check_reveal_targets(book, load_objects(book))
    assert "既無這條伏筆的埋也無收" in problem


def test_reveal_pending_when_an_arc_is_unbuilt(tmp_path):
    """揭示點還不存在是合法狀態（共同約定.md 六）——arc02 還沒拆就別報。"""
    book = _book(
        tmp_path, {"甲.md": _obj("型別: 伏筆\n揭示層級: 水下｜揭示於 收[[伏筆:還沒排的線]]")}
    )
    assert unbuilt_arcs(book) == ["arc02"]
    notes: list[str] = []
    assert check_reveal_targets(book, load_objects(book), notes=notes) == []
    assert "揭示點待落幕" in notes[0]


# ------------------------------------------------------------ 近似名（V7）

def test_bracketed_variant_of_an_object_name_is_reported(tmp_path):
    """實測病徵：`呆底下另有東西` 與 `呆底下另有東西（真慧）` 在同一本書並存。

    `知識前沿` 的命題名比對就掛在這個命名空間上，一個括號註解就能讓比對失準。
    """
    objs = load_objects(_book(tmp_path, {"呆底下另有東西.md": _obj()}))
    (problem,) = check_near_miss(objs, {"呆底下另有東西（真慧）": ["幕綱/arc01.md"]})
    assert "疑似同一件事的兩個名字" in problem


def test_exact_match_is_not_reported(tmp_path):
    objs = load_objects(_book(tmp_path, {"呆底下另有東西.md": _obj()}))
    assert check_near_miss(objs, {"呆底下另有東西": ["幕綱/arc01.md"]}) == []


def test_unrelated_name_without_a_file_is_fine(tmp_path):
    """沒有物件檔的 ID 是合法的（G4）——不是每個名字都得開檔。"""
    objs = load_objects(_book(tmp_path, {"甲.md": _obj()}))
    assert check_near_miss(objs, {"完全無關的東西": ["幕綱/arc01.md"]}) == []


# ------------------------------------------------------------ 開檔提示（抉擇 3）

def test_frequently_referenced_name_gets_a_hint_not_a_block(tmp_path):
    objs = load_objects(_book(tmp_path, {"甲.md": _obj()}))
    refs = {"某條線": ["a", "b", "c"]}
    (hint,) = suggest_objects(objs, refs)
    assert "要不要開一支" in hint
    assert check_near_miss(objs, refs) == []  # 提示不是問題


def test_two_references_are_below_the_hint_threshold(tmp_path):
    objs = load_objects(_book(tmp_path, {"甲.md": _obj()}))
    assert suggest_objects(objs, {"某條線": ["a", "b"]}) == []


def test_hint_is_not_counted_as_a_problem(tmp_path, capsys):
    book = _book(tmp_path, {"甲.md": _obj()})
    problems, stats = lint_report(book)
    assert problems == []
    assert any("要不要開一支" not in h for h in stats.hints) or stats.hints == []


# ------------------------------------------------------------ object-lint 入口

def test_object_lint_reports_coverage_and_exits_clean(tmp_path, capsys):
    book = _book(tmp_path, {"甲.md": _obj()})
    assert object_lint_main(["--book", str(book)]) == 0
    out = capsys.readouterr().out
    assert "1 支物件檔" in out and "物件檔格式乾淨" in out


def test_object_lint_narrows_to_object_problems(tmp_path, capsys):
    """只動物件檔的 skill 要有一個對得上自己動作的閘門；要看全部跑 fact-lint。"""
    book = _book(tmp_path, {"甲.md": _obj("型別: 法寶")})
    (book / "chapters" / "ch0001.ai.md").write_text(
        "---\n對應幕: [幕001, 幕004]\n所屬arc: arc01\n---\n"
        "## 本章事實\n- 幕002（arc01）· 少年 · 心情：開心\n",
        encoding="utf-8",
    )
    (book / "chapters" / "ch0001.md").write_text("（正文）\n", encoding="utf-8")

    assert object_lint_main(["--book", str(book)]) == 1
    # 問題清單走 **stdout**（2026-07-28 功能 14 的輸出契約）
    out = capsys.readouterr().out
    assert "封閉枚舉" in out and "未知類型 token" not in out

    assert object_lint_main(["--book", str(book), "--all"]) == 1
    assert "未知類型 token" in capsys.readouterr().out


def test_object_lint_does_not_match_物件_inside_a_hint(tmp_path, capsys):
    """收斂要比對**開頭**，不是「有沒有出現」。

    純化違規的**修法提示**裡就寫著「排除線屬 story/物件/<實體>.md」——用 `in`
    比對會把它們全撈進 object-lint 的輸出（實測一世之尊：該印 0 個，印了 154 個）。
    """
    book = _book(tmp_path, {"甲.md": _obj()})
    (book / "chapters" / "ch0001.ai.md").write_text(
        "---\n對應幕: [幕001, 幕004]\n所屬arc: arc01\n---\n"
        "## 本章事實\n- 幕002（arc01）· 少年 · 位置：" + "字" * 250 + "\n",
        encoding="utf-8",
    )
    (book / "chapters" / "ch0001.md").write_text("（正文）\n", encoding="utf-8")

    assert object_lint_main(["--book", str(book)]) == 0  # 物件檔本身是乾淨的
    assert "不必重抄" not in capsys.readouterr().out
    assert object_lint_main(["--book", str(book), "--all"]) == 1
    assert "不必重抄" in capsys.readouterr().out


def test_object_lint_surfaces_the_retired_constraint_location(tmp_path, capsys):
    """約束的舊落點還在＝物件軸的遷移待辦，`object-lint` 要看得到。"""
    book = _book(tmp_path, {"甲.md": _obj()})
    ref = book / "story" / "參照"
    ref.mkdir(parents=True)
    (ref / "約束.co.md").write_text("| 約束名 |\n", encoding="utf-8")
    assert object_lint_main(["--book", str(book)]) == 1
    assert "落點已廢除" in capsys.readouterr().out


def test_object_lint_says_so_when_there_is_no_object_dir(tmp_path, capsys):
    """「我檢查了 0 支」要說出來，不能只印「乾淨」。"""
    book = tmp_path / "book"
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "_index.md").write_text(SPINE, encoding="utf-8")
    (book / "chapters").mkdir()
    object_lint_main(["--book", str(book)])
    out = capsys.readouterr().out
    assert "0 支物件檔" in out and "還沒有任何物件檔" in out


# ------------------------------------------------- 第八型 `方針`（2026-07-27 功能 04）
#
# 書級方針（「這本書不寫感情線」）射程＝全書、不綁任何實體，依改寫後的 F2
# 「跟著它的射程」需要一個**每次都會被無條件載入**的落點。它進物件軸是為了拿到
# 約束表與 `fact-project --for-beat` 的載入路徑。

POLICY_BODY = "## 為什麼存在\n作者拍板的全書通則。\n"


def test_policy_object_is_legal(tmp_path):
    book = _book(tmp_path, {f"{POLICY_NAME}.md": _obj(f"型別: {POLICY_KIND}", POLICY_BODY)})
    (o,) = load_objects(book)
    assert o.kinds == (POLICY_KIND,)
    assert check_objects([o]) == []


def test_policy_kind_is_bound_to_the_reserved_filename(tmp_path):
    """沒有這條，「方針」會退化成第二個約束軸：誰都能開一支方針檔，
    而 `--for-beat` 只無條件印 `全書` 那一支，其餘會**靜默不被載入**。"""
    book = _book(tmp_path, {"孟奇.md": _obj(f"型別: {POLICY_KIND}", POLICY_BODY)})
    (problem,) = check_objects(load_objects(book))
    assert "檔名不是" in problem and POLICY_NAME in problem


def test_reserved_filename_requires_the_policy_kind(tmp_path):
    book = _book(tmp_path, {f"{POLICY_NAME}.md": _obj("型別: 設定規則", POLICY_BODY)})
    (problem,) = check_objects(load_objects(book))
    assert POLICY_KIND in problem


def test_policy_must_not_carry_a_reveal_level(tmp_path):
    """方針不是「具名＋隨劇情推進會變狀態」的東西（G1），沒有「何時向讀者揭」
    可言——容忍它會讓 `foreshadow-project` 去解析一個永遠不會有收點的指標。"""
    book = _book(
        tmp_path,
        {
            f"{POLICY_NAME}.md": _obj(
                f"型別: {POLICY_KIND}\n揭示層級: 水下｜跨集留白", POLICY_BODY
            )
        },
    )
    assert any("不得有" in p for p in check_objects(load_objects(book)))

