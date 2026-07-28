"""`char-lint` 的測試（2026-07-27 功能 06 重構輪新增）。

每一項都要有「乾淨的書不報」與「壞的書會報」兩面——一個只在壞資料上測過的
檢查器，不知道自己會不會對乾淨的書亂叫（`設計原則.md` E2 的警報疲勞那一格）。
這一輪特別要測的是**假陽性**：實測第一版把 15 支合法的空伏筆宣告
（`伏筆: { 埋: [], 收: [] }`）全報成問題，那正是本輪在抓的假陰性的鏡像。
"""

from pathlib import Path

from derived_sync.char_lint import lint_book

CLEAN_DERIVED = (
    "---\n"
    "generated-from: abc123\n"
    "generated-at: 2026-07-27\n"
    "定位: 主角\n"
    "所屬arc: [arc01]\n"
    "暫定: false\n"
    "伏筆: { 埋: [怕水], 收: [] }\n"
    "---\n"
    "## 需求四象限\n"
    "- 期盼（動力）：還清債\n"
    "- 想要（誤導／假目標）：贖回鐵砧\n"
    "- 落差（阻礙）：他不肯開口求人\n"
    "- 需要（圓滿）：承認自己需要別人\n"
    "## 預期弧線\n盲目 → 挫折 → 醒悟 → 滿足\n"
    "## 馬斯洛層次\n安全 → 歸屬\n"
    "## 對衝關係\n與艾拉在「誰欠誰」上零和對撞\n"
)


def _rollup(rows: str = "| 凱 | 主角 | 還清債、贖回鐵砧 | arc01 | 否 |") -> str:
    return (
        "---\ngenerated-from: rollupdigest\ngenerated-at: 2026-07-27\n---\n"
        "## 角色清單\n"
        "| 角色 | 定位 | 一行需求（期盼／反派正當需求） | 所屬arc | 暫定 |\n"
        "|------|------|------------------------------|---------|------|\n"
        + rows
        + "\n"
    )


def _book(
    tmp_path,
    derived: str | None = CLEAN_DERIVED,
    rollup: str | None = None,
    role_field: str = "凱",
) -> Path:
    book = tmp_path / "book"
    d = book / "story" / "設定" / "角色"
    d.mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (d / "凱.md").write_text("# 凱\n一個怕水的鐵匠。\n", encoding="utf-8")
    if derived is not None:
        (d / "凱.ai.md").write_text(derived, encoding="utf-8")
    (d / "_index.ai.md").write_text(
        rollup if rollup is not None else _rollup(), encoding="utf-8"
    )
    (book / "story" / "幕綱" / "arc01.md").write_text(
        f"## 幕001 · 開場\n- 角色：{role_field}\n"
        "- 行動：他躲開水邊 埋[[伏筆:怕水]]\n",
        encoding="utf-8",
    )
    return book


# ---------------------------------------------------------------- 乾淨的一面


def test_clean_book_reports_nothing_but_still_prints_counts(tmp_path):
    problems, stats = lint_book(_book(tmp_path))
    assert problems == []
    # **0 也印**：這一行本身就是「它真的讀到我的檔了」的證據
    assert stats.sources == 1
    assert stats.derived == 1
    assert stats.sources_without_derived == 0
    assert stats.placeholder_slots == 0
    assert stats.req_slots == 5  # 四象限 4 個 bullet ＋ 預期弧線 1 行
    assert stats.foreshadow_names == 1
    assert stats.foreshadow_unknown == 0
    assert stats.rollup_rows == 1
    assert "0 支源沒有衍生檔" in stats.render()


def test_empty_foreshadow_declaration_is_legal(tmp_path):
    """`{ 埋: [], 收: [] }` ＝這個角色不牽伏筆，**不是解析失敗**。

    第一版把結構在、名字空的宣告全報成問題（實測一世之尊 15 支全中）。
    """
    derived = CLEAN_DERIVED.replace("伏筆: { 埋: [怕水], 收: [] }", "伏筆: { 埋: [], 收: [] }")
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    assert problems == []
    assert stats.foreshadow_names == 0


def test_broken_foreshadow_structure_is_reported(tmp_path):
    derived = CLEAN_DERIVED.replace("伏筆: { 埋: [怕水], 收: [] }", "伏筆: 怕水、欠債")
    problems, _ = lint_book(_book(tmp_path, derived=derived))
    assert any("解析不到" in p.detail for p in problems)


# ---------------------------------------------------------------- 第 1 項


def test_placeholder_required_section_is_reported(tmp_path):
    """佔位的判準是**形狀**（整段括號註記），不是詞表。"""
    derived = CLEAN_DERIVED.replace(
        "## 預期弧線\n盲目 → 挫折 → 醒悟 → 滿足\n",
        "## 預期弧線\n（源檔未載，待跑 `character` 補）\n",
    )
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    assert any("必填節有佔位" in p.detail for p in problems)
    assert stats.req_placeholder_slots == 1
    assert stats.hollow_sections == 1
    assert stats.hollow_files == 1


def test_partially_placeholder_quadrant_counts_slots_not_whole_section(tmp_path):
    derived = CLEAN_DERIVED.replace(
        "- 想要（誤導／假目標）：贖回鐵砧",
        "- 想要（誤導／假目標）：（源檔未載，待跑 `character` 補）",
    )
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    assert any("必填節有佔位" in p.detail for p in problems)
    assert stats.req_placeholder_slots == 1
    assert stats.hollow_sections == 0  # 整節沒有全空——四象限還有三格是真的


def test_missing_required_section_is_reported(tmp_path):
    derived = CLEAN_DERIVED.replace("## 預期弧線\n盲目 → 挫折 → 醒悟 → 滿足\n", "")
    problems, _ = lint_book(_book(tmp_path, derived=derived))
    assert any("缺必填節" in p.detail for p in problems)


# ---------------------------------------------------------------- 第 2／7 項


def test_source_without_derived_is_reported_from_the_source_side(tmp_path):
    """E1 新推論：從 Y 出發掃描的守衛，對「Y 不存在」永遠回報乾淨。"""
    problems, stats = lint_book(_book(tmp_path, derived=None))
    assert any("沒有對應的衍生檔" in p.detail for p in problems)
    assert stats.sources == 1
    assert stats.sources_without_derived == 1
    assert stats.derived == 0


def test_dir_form_counts_as_a_source(tmp_path):
    book = _book(tmp_path)
    d = book / "story" / "設定" / "角色"
    (d / "艾拉").mkdir()
    (d / "艾拉" / "核心.md").write_text("# 艾拉\n舊識。\n", encoding="utf-8")
    (d / "艾拉" / "水下.md").write_text("她才是那個放火的人。\n", encoding="utf-8")
    problems, stats = lint_book(book)
    assert stats.sources == 2
    assert stats.dir_form == 1
    # 目錄形態也要有衍生檔——這正是「從源側掃」才看得到的那一格
    assert stats.sources_without_derived == 1
    assert any("艾拉" in p.detail for p in problems)


def test_single_and_dir_form_must_not_coexist(tmp_path):
    book = _book(tmp_path)
    d = book / "story" / "設定" / "角色"
    (d / "凱").mkdir()
    (d / "凱" / "水下.md").write_text("秘密。\n", encoding="utf-8")
    problems, stats = lint_book(book)
    assert stats.coexist == 1
    assert any("並存" in p.detail for p in problems)


# ---------------------------------------------------------------- 第 3 項


def test_retired_keys_are_aggregated_into_one_line(tmp_path):
    derived = CLEAN_DERIVED.replace(
        "定位: 主角\n", "角色: 凱\n定位: 主角\n弧線類型: 正弧線\n影響力: 高\n🧊水下: []\n"
    )
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    hits = [p for p in problems if "已廢除" in p.detail]
    assert len(hits) == 1  # 聚合成一行（03 拍板的判準）
    assert stats.retired_keys == 4
    assert stats.files_with_retired == 1
    assert "角色×1" in hits[0].detail


def test_position_and_tentative_enums_are_read(tmp_path):
    """留下的四欄若沒有真的被讀，就不准留（抉擇 1 B 的成立條件）。"""
    derived = CLEAN_DERIVED.replace("定位: 主角", "定位: 配角（**已死**）").replace(
        "暫定: false", "暫定: 否（收徒動機已落定＝…2026-07-20 beat-sheet arc03·幕202）"
    ).replace("所屬arc: [arc01]", "所屬arc: arc01")
    problems, _ = lint_book(_book(tmp_path, derived=derived))
    details = " ".join(p.detail for p in problems)
    assert "不是枚舉值" in details
    assert "不是布林值" in details
    assert "不是方括號清單" in details


def test_unknown_foreshadow_name_is_reported(tmp_path):
    derived = CLEAN_DERIVED.replace("埋: [怕水]", "埋: [武道為何被毀]")
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    assert any("registry 查無" in p.detail for p in problems)
    assert stats.foreshadow_unknown == 1
    assert stats.registry_beats == 1  # registry ＝幕綱標記 ∪ 物件檔，兩側都要印


# ---------------------------------------------------------------- 第 5／6 項


def test_rollup_row_name_must_be_the_filename(tmp_path):
    problems, _ = lint_book(
        _book(tmp_path, rollup=_rollup("| 凱（鐵砧） | 主角 | 還清債 | arc01 | 否 |"))
    )
    hits = [p for p in problems if "與資料夾不一致" in p.detail]
    assert len(hits) == 1
    assert "1 支源檔沒進清單：凱" in hits[0].detail
    assert "1 列的列名不是檔名：凱（鐵砧）" in hits[0].detail


def test_rollup_columns_must_match_front_matter(tmp_path):
    problems, _ = lint_book(
        _book(tmp_path, rollup=_rollup("| 凱 | 配角 | 還清債 | arc02 | 是 |"))
    )
    details = " ".join(p.detail for p in problems)
    assert "`定位` 寫" in details
    assert "`所屬arc` 寫" in details
    assert "`暫定` 寫" in details


def test_need_column_content_rules_are_aggregated(tmp_path):
    problems, _ = lint_book(
        _book(
            tmp_path,
            rollup=_rollup("| 凱 | 主角 | 還清債（🧊 水下·見 ch0031）【表面】裝粗豪 | arc01 | 否 |"),
        )
    )
    hits = [p for p in problems if "一行需求" in p.detail]
    assert len(hits) == 1  # 三種病徵聚合成一行
    assert "1 列" in hits[0].detail


def test_missing_rollup_is_the_new_normal(tmp_path):
    """**缺 `_index.ai.md` 不再是問題**（2026-07-28 功能 12 抉擇 1 A）：那支檔廢除了，
    全書角色清單改跑 `char-lint --emit`。第 5 項降級成**殘留偵測**（舊檔還在才比對）。"""
    book = _book(tmp_path)
    (book / "story" / "設定" / "角色" / "_index.ai.md").unlink()
    problems, stats = lint_book(book)
    assert stats.rollup_found is False
    assert not any("沒有 _index.ai.md" in p.detail for p in problems)


def test_unstamped_rollup_skeleton_is_skipped(tmp_path):
    """尚未封章的骨架由 `check` 報 unstamped，這裡重複報是雜訊。"""
    skeleton = "# 角色清單\n\n## 角色清單\n| 角色 | 定位 |\n|---|---|\n| （尚無角色） |  |\n"
    problems, _ = lint_book(_book(tmp_path, rollup=skeleton))
    assert not any("與資料夾不一致" in p.detail for p in problems)


# ---------------------------------------------------------------- 第 8 項


def test_role_field_tokens_only_reported_at_three_or_more(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc01.md").write_text(
        "## 幕001 · 開場\n- 角色：凱、同伴組\n- 行動：埋[[伏筆:怕水]]\n"
        "## 幕002 · 追擊\n- 角色：凱、同伴組\n- 行動：跑\n"
        "## 幕003 · 收束\n- 角色：凱、同伴組、路過的老頭\n- 行動：談\n",
        encoding="utf-8",
    )
    problems, stats = lint_book(book)
    hits = [p for p in problems if "角色欄 token" in p.detail]
    assert len(hits) == 1
    assert "同伴組×3" in hits[0].detail
    assert "路過的老頭" not in hits[0].detail  # 只出現 1 次，不報
    assert stats.role_fields == 3
    assert stats.role_tokens_unknown == 4  # 同伴組×3 ＋ 路過的老頭×1
    assert stats.role_tokens_frequent == 1


def test_role_field_tokens_ignore_parenthetical_annotations(tmp_path):
    """位置判準：括號外的才是這一幕的正式宣告，括號內是註記。"""
    book = _book(tmp_path, role_field="凱（真定·心裡不在場）、**凱**")
    problems, stats = lint_book(book)
    assert stats.role_tokens == 2  # 兩個「凱」，括號內的註記不算
    assert stats.role_tokens_unknown == 0
    assert not any("角色欄 token" in p.detail for p in problems)


# ---------------------------------------------------------------- 邊界


def test_book_without_character_folder_does_not_crash(tmp_path):
    book = tmp_path / "empty"
    book.mkdir()
    problems, stats = lint_book(book)
    assert problems == []
    assert stats.sources == 0
    assert "0 支源" in stats.render()
