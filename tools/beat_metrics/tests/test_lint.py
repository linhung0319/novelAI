"""`beat-lint` 的正反例。

每一項檢查都要有**反例會報、正例不報**兩個方向——只測「壞的會報」的檢查器，
無法分辨「它在守」與「它把全部東西都報成壞的」。

fixture 一律自造：一世之尊只有 15 個問題、涵蓋不到多數檢查（它的幕號 0 重複、
前因 0 懸空——那正是它作為乾淨基準的價值）。真實語料的回歸走 `test_golden_一世之尊.py`。
"""

from __future__ import annotations

import pytest

from beat_metrics.lint import lint_report
from beat_metrics.scan import ScanError

INDEX = "# 幕綱索引\n\n- 全書順序：arc01 → arc02\n"

ARC01 = """# arc01 · 起

## 本 arc 承諾

- 節奏檔位：開頭段
- 不得發生：
  - 反派不登場
  - 不跨階

## 幕001 · 開場
- 角色：林小凡
- 時空：老宅／清晨
- 行動：翻遍藥典找解毒法
- 衝突：藥石罔效
- 結果：確認無解
- 前因：—
- 伏筆：埋[[伏筆:血玉墜]]
- 結構階段：平凡失衡

## 幕002 · 立誓
- 角色：林小凡、母親
- 時空：老宅／夜
- 行動：向母親發誓親自去取寒髓
- 衝突：取者無人生還
- 結果：立誓獨力奪髓
- 前因：[[幕001]]（醫術無解逼出這條路）
- 伏筆：—
- 結構階段：召喚衝突
"""

ARC02 = """# arc02 · 承

## 本 arc 承諾

- 節奏檔位：常態段

## 幕101 · 奪髓
- 角色：林小凡、血衣老者
- 時空：北域冰原／第三夜
- 行動：闖禁地取寒髓
- 衝突：老者出手阻攔
- 結果：奪得寒髓，左臂遭封脈
- 前因：[[幕002]]（立誓獨力奪髓）
- 伏筆：收[[伏筆:血玉墜]]
- 結構階段：磨練成長
"""


def _book(tmp_path, index=INDEX, **arcs):
    d = tmp_path / "story" / "幕綱"
    d.mkdir(parents=True)
    (d / "_index.md").write_text(index, encoding="utf-8")
    for name, text in arcs.items():
        (d / f"{name}.md").write_text(text, encoding="utf-8")
    return tmp_path


def _only(problems, needle):
    return [p for p in problems if needle in p]


# --------------------------------------------------------------- 正例

def test_clean_book_reports_nothing(tmp_path):
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert problems == []
    assert (stats.arcs, stats.beats, stats.refs) == (2, 3, 2)
    assert (stats.marks, stats.mark_names) == (2, 1)
    assert stats.promise_sections == 2
    assert stats.exclusions == 2


def test_coverage_line_prints_zeroes(tmp_path):
    """**0 也要印。** 「我檢查了 0 筆」本身就是最有用的那一筆訊息。"""
    _, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    line = stats.render()
    assert "2 支 arc／3 幕／2 條前因" in line
    assert "0 列狀態表" in line and "0 支物件檔" in line and "跳過 0 支骨架" in line


# --------------------------------------------------------------- 反例

def test_duplicate_beat_number(tmp_path):
    dup = ARC02.replace("## 幕101 ·", "## 幕001 ·").replace(
        "- 前因：[[幕002]]（立誓獨力奪髓）", "- 前因：[[幕002]]"
    )
    dup = dup.replace("- 全書順序", "- 全書順序")
    problems, _ = lint_report(
        _book(tmp_path, arc01=ARC01, arc02=dup.replace("幕001", "幕002"))
    )
    assert _only(problems, "重複"), problems


def test_beat_number_outside_allocated_block(tmp_path):
    """arc02 的幕號該落在 幕101–幕200；寫成 幕999 要報。"""
    off = ARC02.replace("## 幕101 ·", "## 幕999 ·")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=off))
    assert _only(problems, "預配號段"), problems


def test_dangling_beat_reference(tmp_path):
    """V3：schema 與 beat-test 都稱它是「機械事實」，2026-07-27 前卻無工具在做。"""
    bad = ARC02.replace("[[幕002]]", "[[幕777]]")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=bad))
    hits = _only(problems, "指向不存在的幕")
    assert len(hits) == 1 and "幕777" in hits[0], problems


def test_missing_field(tmp_path):
    bad = ARC02.replace("- 結果：奪得寒髓，左臂遭封脈\n", "")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=bad))
    assert _only(problems, "缺欄位 結果"), problems


def test_blank_field(tmp_path):
    bad = ARC02.replace("- 衝突：老者出手阻攔", "- 衝突：—")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=bad))
    assert _only(problems, "「衝突」欄留白"), problems


def test_blank_antecedent_and_foreshadow_are_legal(tmp_path):
    """`前因：—`＝首幕；`伏筆：—`＝本幕無伏筆。**都不是格式問題。**

    非首幕卻沒有前因是「孤兒幕」，屬因果連續性（`beat-test` 測試1 的語意判斷），
    不歸本閘門——實測 `驗證範例` 幕005 正是刻意留著的那個缺陷樣本。
    """
    loose = ARC02.replace("- 前因：[[幕002]]（立誓獨力奪髓）", "- 前因：—")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=loose))
    assert _only(problems, "留白") == []


def test_missing_promise_section(tmp_path):
    bad = ARC02.replace("## 本 arc 承諾\n\n- 節奏檔位：常態段\n", "")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=bad))
    assert _only(problems, "缺「## 本 arc 承諾」分區"), problems


# --------------------------------------------------------------- spine

def test_spine_missing_arc(tmp_path):
    problems, _ = lint_report(
        _book(tmp_path, index="- 全書順序：arc01\n", arc01=ARC01, arc02=ARC02)
    )
    assert _only(problems, "未涵蓋 arc02"), problems


def test_spine_lists_nonexistent_arc(tmp_path):
    problems, _ = lint_report(
        _book(tmp_path, index="- 全書順序：arc01 → arc02 → arc03\n", arc01=ARC01, arc02=ARC02)
    )
    assert _only(problems, "沒有對應的 arc03.md"), problems


def test_spine_duplicate_entry(tmp_path):
    problems, _ = lint_report(
        _book(tmp_path, index="- 全書順序：arc01 → arc02 → arc01\n", arc01=ARC01, arc02=ARC02)
    )
    assert _only(problems, "重複列出 arc01"), problems


def test_spine_unparseable(tmp_path):
    problems, _ = lint_report(
        _book(tmp_path, index="# 幕綱索引\n\n- 選用結構公式：編劇九階段\n", arc01=ARC01, arc02=ARC02)
    )
    assert _only(problems, "全書順序"), problems


def test_spine_failure_is_loud_not_silent():
    """V4：`parse_spine` 讀不到就 raise，與其餘三支工具一致。

    舊版回 `{}` 退檔名排序、印 exit 0——同一個壞法，看你先跑哪支工具決定你會不會發現。
    """
    from beat_metrics.scan import parse_spine

    with pytest.raises(ScanError):
        parse_spine("# 幕綱索引\n- 選用結構公式：編劇九階段\n")
    assert parse_spine("- 全書順序：arc03 → arc01\n") == {"arc03": 0, "arc01": 1}


# --------------------------------------------------------------- 近似名／目的地

def test_near_duplicate_foreshadow_name(tmp_path):
    """V10：狀態表造出 `X（Y）`，而標記寫的是 `X`——兩個名字、一條伏筆。"""
    arc = ARC02 + (
        "\n## 本 arc 伏筆狀態\n"
        "| 伏筆 | 埋設幕 | 收回 | 備註 |\n"
        "|------|--------|------|------|\n"
        "| 血玉墜（母親給的） | 幕001 | 幕101 | 括號變體 |\n"
    )
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert _only(problems, "疑似同一條伏筆的兩個名字"), problems
    assert stats.status_rows == 1


def test_prose_continuation_rows_are_counted_not_reported(tmp_path):
    """抉擇 2 B：續行刻意不立 token，**不報成問題**，但要在覆蓋率行誠實計數。"""
    arc = ARC02 + (
        "\n## 本 arc 伏筆狀態\n"
        "| 伏筆 | 埋設幕 | 收回 | 備註 |\n"
        "|------|--------|------|------|\n"
        "| 母愛護盾 | arc01（未拆） | 未收 | 全書無標記的散文續行 |\n"
    )
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert problems == []
    assert (stats.status_rows, stats.status_prose_rows) == (1, 1)
    assert "其中 1 列的伏筆名全書無標記" in stats.render()


def test_design_note_without_destination(tmp_path):
    """E1 新推論：遷移承諾的終點要有守衛。箭頭指向空氣，而箭頭本身格式合法。"""
    arc = ARC02 + "\n## 設計註（下游不抄）\n\n母題論證：這一段的骨是對帳。\n"
    book = _book(tmp_path, arc01=ARC01, arc02=arc)
    problems, _ = lint_report(book)
    assert _only(problems, "裁決流.md` 不存在"), problems

    ref = book / "story" / "參照"
    ref.mkdir(parents=True)
    (ref / "裁決流.co.md").write_text("# 裁決流\n", encoding="utf-8")
    assert _only(lint_report(book)[0], "裁決流") == []


def test_legacy_decision_log_name_also_counts(tmp_path):
    """`裁決流.schema.md:6`：2026-07-27 前的書可能仍是舊名 `裁決流.md`。"""
    arc = ARC02 + "\n## 設計註\n\n理由。\n"
    book = _book(tmp_path, arc01=ARC01, arc02=arc)
    ref = book / "story" / "參照"
    ref.mkdir(parents=True)
    (ref / "裁決流.md").write_text("# 裁決流\n", encoding="utf-8")
    assert _only(lint_report(book)[0], "裁決流") == []


# --------------------------------------------------------------- 骨架／提示

def test_skeleton_is_skipped_but_counted(tmp_path):
    """跳過幾支要印出來，否則就是另一個「守衛報平安」。"""
    skeleton = "# arc02\n\n> ⚠️ **尚未產出**——本檔是空骨架。\n\n## 幕101 · （幕名）\n- 角色：\n"
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=skeleton))
    assert problems == []
    assert (stats.arcs, stats.skeletons) == (1, 1)
    assert "跳過 1 支骨架" in stats.render()


def test_tail_hook_is_a_hint_not_a_problem(tmp_path):
    """`幕尾鉤` 是 schema 未定義的第九欄（實測 79/108 幕）。本輪只提示、不裁歸屬。"""
    arc = ARC02.replace(
        "- 結構階段：磨練成長", "- 結構階段：磨練成長\n- 幕尾鉤：斷在老者抬眼那一下"
    )
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert problems == []
    assert any("幕尾鉤" in h for h in stats.hints)


def test_unregistered_foreshadow_names_are_hints(tmp_path):
    """`物件.schema.md`：沒有物件檔的 ID 是合法的，所以是提示不是問題。"""
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert problems == []
    assert any("沒有 `story/物件/" in h for h in stats.hints)


def test_registered_names_drop_out_of_the_hint(tmp_path):
    book = _book(tmp_path, arc01=ARC01, arc02=ARC02)
    objects = book / "story" / "物件"
    objects.mkdir(parents=True)
    (objects / "血玉墜.md").write_text("---\n型別: 伏筆\n---\n", encoding="utf-8")
    _, stats = lint_report(book)
    assert stats.object_files == 1
    assert not any("沒有 `story/物件/" in h for h in stats.hints)


def test_unknown_section_is_a_hint(tmp_path):
    arc = ARC02 + "\n## ⚠️ 措辭硬約束（全域）\n\n某某一律不以「手」字指稱。\n"
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert problems == []
    assert any("未定義的 `##` 分區" in h for h in stats.hints)
