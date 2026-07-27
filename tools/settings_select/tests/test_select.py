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


def test_reads_both_derived_and_source(tmp_path):
    """衍生檔依 schema 只放四象限分析，人物描述在源——兩邊都要。"""
    sel = select(_book(tmp_path), "arc09")
    by_name = {h.entity.name: h.entity for h in sel.selected}
    assert [p.name for p in by_name["少年"].read_paths()] == ["少年.ai.md", "少年.md"]
    assert [p.name for p in by_name["山門"].read_paths()] == ["山門.md"]  # 無 .ai.md


# ---------------------------------------------------------------- 目錄形態＋切面

def _with_dir_form(tmp_path):
    book = _book(tmp_path)
    d = book / "story" / "設定" / "角色"
    (d / "少年.md").unlink()
    (d / "少年").mkdir()
    for facet in ("核心", "來歷", "能力", "關係", "水下"):
        (d / "少年" / f"{facet}.md").write_text(facet, encoding="utf-8")
    return book


def test_directory_form_entity_is_discovered_by_dir_name(tmp_path):
    ents = {e.name: e for e in load_entities(_with_dir_form(tmp_path))}
    assert ents["少年"].dir_form and ents["少年"].derived is not None
    assert not ents["老僕"].dir_form


def test_underwater_facet_withheld_by_default(tmp_path):
    """水下＝存取控制：揭底前的 write 拿不到它。"""
    ents = {e.name: e for e in load_entities(_with_dir_form(tmp_path))}
    names = [p.name for p in ents["少年"].read_paths()]
    assert "水下.md" not in names
    assert set(names) == {"少年.ai.md", "核心.md", "來歷.md", "能力.md", "關係.md"}


def test_underwater_facet_opt_in(tmp_path):
    ents = {e.name: e for e in load_entities(_with_dir_form(tmp_path))}
    names = [p.stem for p in ents["少年"].read_paths(include_underwater=True)]
    assert "水下" in names


def test_facet_filter_narrows(tmp_path):
    ents = {e.name: e for e in load_entities(_with_dir_form(tmp_path))}
    names = [p.name for p in ents["少年"].read_paths(facets=("核心", "能力"))]
    assert names == ["少年.ai.md", "核心.md", "能力.md"]  # 衍生在前


def test_facet_filter_cannot_smuggle_underwater(tmp_path):
    ents = {e.name: e for e in load_entities(_with_dir_form(tmp_path))}
    names = [p.stem for p in ents["少年"].read_paths(facets=("核心", "水下"))]
    assert "水下" not in names


def test_single_file_form_ignores_facets(tmp_path):
    """單檔形態切不動——不能改成「只讀一部分」。"""
    ents = {e.name: e for e in load_entities(_with_dir_form(tmp_path))}
    assert [p.name for p in ents["老僕"].read_paths(facets=("核心",))] == [
        "老僕.ai.md",
        "老僕.md",
    ]


def test_parse_facets_rejects_unknown():
    from settings_select.select import parse_facets

    assert parse_facets(None) is None
    assert parse_facets("核心, 能力") == ("核心", "能力")
    with pytest.raises(SelectError, match="未知切面"):
        parse_facets("核心,秘密")


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


# ---------------------------------------------------------------- 覆蓋率（功能 05 抉擇 2 D）

def test_coverage_counts_are_always_produced(tmp_path):
    """0 也要有——「命中 0 筆」本身就是最有用的那一筆訊息（E2）。"""
    sel = select(_book(tmp_path), "arc09")
    # 少年／老僕／同伴——三個都出現在幕的「角色」欄（同伴 是幕802 的括號註解）；
    # 反派 只在檔尾設計註，不屬任何幕
    assert sel.char_count == 3
    assert [b.name for b in sel.world_basis] == ["山門"]  # 海國 沒被提到 → 不在清單


def test_world_hit_by_bare_mention_is_not_filename_only(tmp_path):
    """`山門` 在幕802 的時空欄裸提及 → 這一筆是真的在講它。"""
    sel = select(_book(tmp_path), "arc09")
    b = sel.world_basis[0]
    assert b.bare >= 1 and b.by_filename == 0 and not b.filename_only


def test_world_hit_only_via_filename_reference_is_flagged(tmp_path):
    r"""實測一世之尊 4 個主題裡 3 個是這一格：命中的是註腳、不是內容。

    02 把 `見 \`X.ai.md\`` 從八欄清掉的那天，這一筆會靜默地消失——所以它必須
    在數字上先看得見（抉擇 2 D）。
    """
    book = _book(tmp_path)
    arc = (book / "story" / "幕綱" / "arc09.md").read_text(encoding="utf-8")
    arc = arc.replace(
        "- 結果：只得自己上山",
        "- 結果：只得自己上山（規則見 `海國.ai.md`）",
    )
    (book / "story" / "幕綱" / "arc09.md").write_text(arc, encoding="utf-8")
    sel = select(book, "arc09")
    hit = {b.name: b for b in sel.world_basis}
    assert hit["海國"].by_filename == 1 and hit["海國"].bare == 0
    assert hit["海國"].filename_only
    assert not hit["山門"].filename_only


def test_coverage_does_not_change_what_gets_selected(tmp_path):
    """抉擇 2 D 的字面：**只量，不改選取行為。**"""
    book = _book(tmp_path)
    sel = select(book, "arc09")
    world = [h.entity.name for h in sel.selected if h.entity.kind == "世界觀"]
    assert world == ["山門"]
    # 命中依據只是註解，不是過濾條件——僅因檔名的那一筆照樣要被選進來
    arc = (book / "story" / "幕綱" / "arc09.md").read_text(encoding="utf-8")
    (book / "story" / "幕綱" / "arc09.md").write_text(
        arc.replace("- 衝突：問不出來", "- 衝突：問不出來（見 `海國.ai.md`）"),
        encoding="utf-8",
    )
    sel2 = select(book, "arc09")
    assert {h.entity.name for h in sel2.selected if h.entity.kind == "世界觀"} == {"山門", "海國"}
