import pytest
from foreshadow_project.project import (
    CLOSED,
    OPEN_DECLARED,
    OPEN_UNDECLARED,
    PAID_UNPLANTED,
    build,
    entering,
)
from foreshadow_project.scan import LayerMissing, ScanError, parse_spine, scan_arc

INDEX = """\
# 幕綱索引
- 全書順序：arc01 → arc02 → arc03
"""

ARC01 = """\
# arc01

## 幕001 · 起
- 角色：少年
- 行動：少年撿到一塊舊玉
- 伏筆：埋[[伏筆:舊玉來歷]]
- 結構階段：起

## 幕002 · 承
- 角色：少年
- 行動：少年被追
- 伏筆：埋[[伏筆:誰在追他]]／埋[[伏筆:母親的信]]
- 結構階段：承

## 本 arc 伏筆狀態
| 伏筆 | 埋設幕 | 收回 | 備註 |
|------|--------|------|------|
| 舊玉來歷 | 幕001 | 未收（刻意留白，全書懸念） | 貫穿全書 |
| 母親的信 | 幕002 | arc03（未拆） | 等 arc03 拆幕後回填 |
"""

ARC02 = """\
# arc02

## 幕101 · 轉
- 角色：少年
- 行動：追兵現身，少年認出他們的紋章
- 伏筆：收[[伏筆:誰在追他]]
- 結構階段：轉

## 幕102 · 合
- 角色：少年
- 行動：少年收下一封沒有署名的信
- 伏筆：收[[伏筆:從未埋過的東西]]
- 結構階段：合
"""


def _book(tmp_path, *, arc03: str | None = None):
    book = tmp_path / "book"
    (book / "story" / "幕綱").mkdir(parents=True, exist_ok=True)  # 同一 test 可重建
    (book / "story" / "幕綱" / "_index.md").write_text(INDEX, encoding="utf-8")
    (book / "story" / "幕綱" / "arc01.md").write_text(ARC01, encoding="utf-8")
    (book / "story" / "幕綱" / "arc02.md").write_text(ARC02, encoding="utf-8")
    if arc03 is not None:
        (book / "story" / "幕綱" / "arc03.md").write_text(arc03, encoding="utf-8")
    return book


def _by_name(rep):
    return {t.name: t for t in rep.threads}


def test_pairs_across_arcs(tmp_path):
    t = _by_name(build(_book(tmp_path)))
    assert t["誰在追他"].status == CLOSED
    assert t["誰在追他"].pays[0].arc == "arc02"


def test_declared_open_is_information_not_suspect(tmp_path):
    t = _by_name(build(_book(tmp_path)))
    assert t["舊玉來歷"].status == OPEN_DECLARED
    assert t["舊玉來歷"].suspect is False


def test_undeclared_open_is_suspect(tmp_path):
    """埋了沒收、也沒在狀態表列出＝可疑點。"""
    t = _by_name(build(_book(tmp_path)))
    assert t["母親的信"].status == OPEN_DECLARED  # 這條有列表
    # 把狀態表整段拿掉，同一條就該變成可疑點
    book = _book(tmp_path)
    p = book / "story" / "幕綱" / "arc01.md"
    p.write_text(ARC01.split("## 本 arc 伏筆狀態")[0], encoding="utf-8")
    t2 = _by_name(build(book))
    assert t2["母親的信"].status == OPEN_UNDECLARED
    assert t2["母親的信"].suspect is True


def test_paid_without_plant_is_suspect(tmp_path):
    t = _by_name(build(_book(tmp_path)))
    assert t["從未埋過的東西"].status == PAID_UNPLANTED
    assert t["從未埋過的東西"].suspect is True


def test_unbuilt_arc_reference_expires_when_arc_gets_built(tmp_path):
    rep = build(_book(tmp_path))
    assert rep.expired_unbuilt == []  # arc03 尚未拆 → 資訊
    arc03 = "# arc03\n\n## 幕201 · 收\n- 角色：少年\n- 伏筆：—\n"
    rep2 = build(_book(tmp_path, arc03=arc03))
    assert [arc for _row, arc in rep2.expired_unbuilt] == ["arc03"]


def test_marker_in_status_table_is_violation(tmp_path):
    book = _book(tmp_path)
    p = book / "story" / "幕綱" / "arc01.md"
    p.write_text(
        ARC01.replace("| 舊玉來歷 | 幕001 |", "| 舊玉來歷 埋[[伏筆:舊玉來歷]] | 幕001 |"),
        encoding="utf-8",
    )
    rep = build(book)
    assert any("狀態表" in v.kind for v in rep.violations)


def test_entering_drops_already_closed_threads(tmp_path):
    rep = build(_book(tmp_path))
    names = {t.name for t in entering(rep, "arc02")}
    assert "舊玉來歷" in names  # arc01 埋、未收 → 仍開著
    assert "誰在追他" in names  # 本 arc 收 → 本 arc 動到
    names3 = {t.name for t in entering(rep, "arc03")}
    assert "誰在追他" not in names3  # arc02 已收，進 arc03 時不再相關


def test_spine_ordering_not_beat_number(tmp_path):
    """幕號是穩定 ID、不代表全書順序——定序必須走 spine。"""
    spine = parse_spine("- 全書順序：arc03 → arc01 → arc02")
    assert spine == {"arc03": 0, "arc01": 1, "arc02": 2}


def test_missing_index_raises_layer_missing(tmp_path):
    """**找不到 spine ＝這本書還沒有這一層**，不是掃描錯誤（功能 14，抉擇 6 A）。

    `LayerMissing` 讓 CLI 分得出 exit 2；它與 `ScanError` 是兄弟不是父子，所以
    這裡明確斷言型別——寫成 `pytest.raises(Exception)` 就等於沒驗到分類。
    """
    book = tmp_path / "b"
    (book / "story" / "幕綱").mkdir(parents=True)
    with pytest.raises(LayerMissing):
        build(book)


def test_only_foreshadow_field_counts(tmp_path):
    """行動欄提到 埋[[伏筆:x]] 不算埋設點，但要報成 violation。"""
    arc = (
        "# arcX\n\n## 幕301 · x\n- 角色：少年\n"
        "- 行動：他想起 埋[[伏筆:不該在這裡]] 這件事\n- 伏筆：—\n"
    )
    s = scan_arc_from_text(tmp_path, arc)
    assert s.marks == []
    assert any("伏筆欄以外" in v.kind for v in s.violations)


def scan_arc_from_text(tmp_path, text):
    p = tmp_path / "arcX.md"
    p.write_text(text, encoding="utf-8")
    return scan_arc(p, "arcX")
