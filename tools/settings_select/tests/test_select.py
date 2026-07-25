import pytest
from settings_select.select import (
    SelectError,
    load_entities,
    parse_beat_range,
    parse_beats,
    select,
)

ARC = """\
# arc09 · 測試用弧線

## 本 arc 承諾
- 節奏檔位：推進段
- 不得發生：少年的舊劍不得尋回

## 幕801 · 起
- 角色：少年、老僕
- 時空：山道／黃昏
- 行動：少年攔下老僕問路，老僕支吾
- 衝突：問不出來
- 結果：只得自己上山

## 幕802 · 承
- 角色：少年／（不出場·心裡：同伴）
- 時空：山門
- 行動：少年推開門，發現同伴留下的記號
- 衝突：記號指向他不想去的方向
- 結果：他還是去了

## 本 arc 伏筆狀態
| 伏筆 | 埋設幕 | 收回 | 備註 |
|------|--------|------|------|
| 舊劍 | 幕801 | 未收 | 這一列提到 老僕 與 同伴 與 反派，全都不該被選進來 |

## 設計註（下游不抄）
本輪拍板：反派 本 arc 不登場。
"""


def _book(tmp_path):
    book = tmp_path / "book"
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "設定" / "角色").mkdir(parents=True)
    (book / "story" / "設定" / "世界觀").mkdir(parents=True)
    (book / "story" / "幕綱" / "arc09.md").write_text(ARC, encoding="utf-8")
    for name in ("少年", "老僕", "同伴", "反派"):
        (book / "story" / "設定" / "角色" / f"{name}.md").write_text("源", encoding="utf-8")
        (book / "story" / "設定" / "角色" / f"{name}.ai.md").write_text("衍生", encoding="utf-8")
    (book / "story" / "設定" / "世界觀" / "山門.md").write_text("源", encoding="utf-8")
    (book / "story" / "設定" / "世界觀" / "海國.md").write_text("源", encoding="utf-8")
    return book


def test_parse_beats_ignores_non_beat_sections(tmp_path):
    beats = parse_beats(ARC)
    assert [b.number for b in beats] == [801, 802]
    # 檔尾伏筆表/設計註不得被併進最後一幕，否則選取會被污染回全讀
    assert "伏筆" not in beats[-1].text
    assert "設計註" not in beats[-1].text


def test_selects_only_entities_named_in_role_field(tmp_path):
    sel = select(_book(tmp_path), "arc09")
    names = {h.entity.name for h in sel.selected}
    assert names == {"少年", "老僕", "同伴", "山門"}
    # 反派 只出現在檔尾設計註 → 完全不該出現在任何一邊
    assert "反派" not in names
    assert "反派" not in {h.entity.name for h in sel.mentioned_only}
    # 海國 從未被提及
    assert "海國" not in names


def test_mentioned_only_is_reported_but_not_selected(tmp_path):
    book = _book(tmp_path)
    # 把「同伴」從角色欄拿掉，只留在行動欄 → 應降級為 mentioned_only
    p = book / "story" / "幕綱" / "arc09.md"
    p.write_text(ARC.replace("- 角色：少年／（不出場·心裡：同伴）", "- 角色：少年"), encoding="utf-8")
    sel = select(book, "arc09")
    assert "同伴" not in {h.entity.name for h in sel.selected}
    assert "同伴" in {h.entity.name for h in sel.mentioned_only}


def test_prefers_derived_falls_back_to_source(tmp_path):
    sel = select(_book(tmp_path), "arc09")
    by_name = {h.entity.name: h.entity for h in sel.selected}
    assert by_name["少年"].read_path.name == "少年.ai.md"
    assert by_name["山門"].read_path.name == "山門.md"  # 無 .ai.md → 退回源


def test_beat_range_filter(tmp_path):
    sel = select(_book(tmp_path), "arc09", "幕802")
    assert sel.beat_count == 1
    assert "老僕" not in {h.entity.name for h in sel.selected}


@pytest.mark.parametrize(
    "spec,expected",
    [("幕1001-1005", (1001, 1005)), ("1001-1005", (1001, 1005)), ("幕1001", (1001, 1001))],
)
def test_parse_beat_range(spec, expected):
    assert parse_beat_range(spec) == expected


def test_parse_beat_range_rejects_garbage():
    with pytest.raises(SelectError):
        parse_beat_range("arc11")
    with pytest.raises(SelectError):
        parse_beat_range("幕1005-1001")


def test_missing_arc_raises(tmp_path):
    with pytest.raises(SelectError):
        select(_book(tmp_path), "arc99")


def test_entities_skip_derived_and_index_files(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "設定" / "角色" / "_index.ai.md").write_text("x", encoding="utf-8")
    names = {e.name for e in load_entities(book)}
    assert names == {"少年", "老僕", "同伴", "反派", "山門", "海國"}
