from derived_sync.sentinel import (
    beat_sheet_density,
    bloated_fact_lines,
    long_lines,
    oversized_sources,
    run,
    unsliceable_derived,
)

# 角色衍生檔的合法節（見 結構定義/角色.schema.md「節是封閉枚舉」）
LEGAL_CHAR_AI = (
    "---\n角色: 少年\n---\n"
    "## 需求四象限\n- 期盼：…\n"
    "## 預期弧線\n盲目 → 挫折\n"
    "## 馬斯洛層次\n安全\n"
    "## 對衝關係\n與反派對撞\n"
)


def _beats(n: int, filler: int) -> str:
    out = ["# arcNN\n"]
    for i in range(1, n + 1):
        out.append(f"## 幕{i:03d} · x\n- 角色：少年\n- 行動：{'字' * filler}\n")
    return "\n".join(out)


def _book(tmp_path):
    book = tmp_path / "book"
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "設定" / "角色").mkdir(parents=True)
    (book / "story" / "參照").mkdir(parents=True)
    return book


# ---------------------------------------------------------------- 幕綱

def test_lean_beat_sheet_is_clean(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc01.md").write_text(_beats(10, 100), encoding="utf-8")
    assert beat_sheet_density(book) == []


def test_bloated_beat_sheet_fires(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc09.md").write_text(_beats(10, 3000), encoding="utf-8")
    findings = beat_sheet_density(book)
    assert len(findings) == 1 and findings[0].kind == "幕綱肥大"
    assert "裁決流" in findings[0].hint


def test_non_arc_files_in_beat_dir_ignored(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "_index.md").write_text("巨" * 50000, encoding="utf-8")
    assert beat_sheet_density(book) == []


# ---------------------------------------------------------------- 源檔

def test_oversized_source_uses_absolute_not_median(tmp_path):
    """承重角色本來就該比路人厚——中位數比值會把主角每次都報出來，那是雜訊。"""
    book = _book(tmp_path)
    d = book / "story" / "設定" / "角色"
    for name in ("路人甲", "路人乙", "路人丙"):
        (d / f"{name}.md").write_text("短", encoding="utf-8")
    (d / "主角.md").write_text("字" * 5000, encoding="utf-8")  # 15KB，遠高於中位數但合理
    assert oversized_sources(book) == []
    (d / "超巨.md").write_text("字" * 10000, encoding="utf-8")  # 30KB，過絕對門檻
    assert [f.path.stem for f in oversized_sources(book)] == ["超巨"]


def test_derived_and_index_files_not_checked_as_sources(tmp_path):
    book = _book(tmp_path)
    d = book / "story" / "設定" / "角色"
    (d / "某角.ai.md").write_text("字" * 20000, encoding="utf-8")
    (d / "_index.ai.md").write_text("字" * 20000, encoding="utf-8")
    assert oversized_sources(book) == []


def test_directory_form_sums_its_facets(tmp_path):
    """目錄形態＝把源拆開，每支都小；只有總和過大才報。"""
    book = _book(tmp_path)
    d = book / "story" / "設定" / "角色" / "主角"
    d.mkdir()
    for facet in ("核心", "來歷", "能力", "關係", "水下"):
        (d / f"{facet}.md").write_text("字" * 1000, encoding="utf-8")  # 各 3KB，總 15KB
    assert oversized_sources(book) == []
    (d / "來歷.md").write_text("字" * 6000, encoding="utf-8")  # 總和逾 25KB
    findings = oversized_sources(book)
    assert len(findings) == 1 and findings[0].path.name == "主角"
    assert "已是目錄形態" in findings[0].hint


# ---------------------------------------------------------------- 衍生檔（新）

def test_legal_derived_is_clean(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "設定" / "角色" / "少年.ai.md").write_text(
        LEGAL_CHAR_AI, encoding="utf-8"
    )
    assert unsliceable_derived(book) == []


def test_stray_section_fires_regardless_of_size(tmp_path):
    """「硬事實」「反派備註」「下游硬約束」屬事實流，不該寄生在衍生檔——
    這是分類錯誤，不是體積問題，故小檔也報。"""
    book = _book(tmp_path)
    (book / "story" / "設定" / "角色" / "少年.ai.md").write_text(
        LEGAL_CHAR_AI + "## 硬事實\n年齡十五\n## 下游硬約束\n不得登場\n", encoding="utf-8"
    )
    findings = unsliceable_derived(book)
    assert len(findings) == 1 and findings[0].kind == "衍生檔不可切片"
    assert "硬事實" in findings[0].detail and "下游硬約束" in findings[0].detail
    assert "本章事實" in findings[0].hint and "story/物件/<名>.md" in findings[0].hint


def test_section_title_may_carry_a_suffix_note(tmp_path):
    """「## 對衝關係（2 筆）」不算枚舉外——比對的是開頭。"""
    book = _book(tmp_path)
    (book / "story" / "設定" / "角色" / "少年.ai.md").write_text(
        LEGAL_CHAR_AI.replace("## 對衝關係", "## 對衝關係（2 筆）"), encoding="utf-8"
    )
    assert unsliceable_derived(book) == []


def test_oversized_derived_fires_even_with_legal_sections(tmp_path):
    """衍生檔無切片工具、又該是源的壓縮，故比源檔門檻嚴。"""
    book = _book(tmp_path)
    (book / "story" / "設定" / "角色" / "少年.ai.md").write_text(
        LEGAL_CHAR_AI + "字" * 5000, encoding="utf-8"  # 15KB > 12000
    )
    findings = unsliceable_derived(book)
    assert len(findings) == 1 and "建議 ≤12000" in findings[0].detail


def test_rollup_uses_its_own_section_enum(tmp_path):
    book = _book(tmp_path)
    d = book / "story" / "設定" / "角色"
    (d / "_index.ai.md").write_text("## 角色清單\n| 少年 |\n", encoding="utf-8")
    assert unsliceable_derived(book) == []
    (d / "_index.ai.md").write_text(
        "## 角色清單\n| 少年 |\n## 乙批·character 觸發條件表\n（8k 字）\n", encoding="utf-8"
    )
    findings = unsliceable_derived(book)
    assert len(findings) == 1 and "觸發條件表" in findings[0].detail


def test_unknown_kind_derived_only_size_checked(tmp_path):
    """風格.ai.md 沒有登記的節枚舉——只查大小，不亂報節。"""
    book = _book(tmp_path)
    d = book / "story" / "設定" / "風格"
    d.mkdir(parents=True)
    (d / "風格.ai.md").write_text("## 隨便什麼節\n短\n", encoding="utf-8")
    assert unsliceable_derived(book) == []


# ------------------------------------------------- chapters/（2026-07-27 功能 03 補）
#
# 在此之前這三個目標集**恰好都不含 `chapters/`**，於是 50,782 B 的
# `chapters/_index.ai.md`（門檻的 4.2×）與 2,235 字元的單行完全靜音，
# 而 `derived-sync check` 印「0 個需處理」——`設計原則.md` E2 最後一格。
# 證據這不是刻意豁免：`bloated_fact_lines` 早就在掃 `chapters/ch*.ai.md`。

def test_chapter_index_size_is_measured(tmp_path):
    book = _book(tmp_path)
    d = book / "chapters"
    d.mkdir()
    (d / "_index.ai.md").write_text("## 章節索引\n" + "| 甲 |\n" * 3000, encoding="utf-8")
    findings = unsliceable_derived(book)
    assert len(findings) == 1 and findings[0].path.name == "_index.ai.md"
    assert findings[0].kind == "衍生檔不可切片"


def test_chapter_index_stray_section_fires(tmp_path):
    """`章末狀態快照` 是僵屍規格（schema 2026-07-27 刪掉、從來沒有產生器）。"""
    book = _book(tmp_path)
    d = book / "chapters"
    d.mkdir()
    (d / "_index.ai.md").write_text(
        "## 章節索引\n| ch0001 |\n## 章末狀態快照\n殘骸\n", encoding="utf-8"
    )
    findings = unsliceable_derived(book)
    assert len(findings) == 1 and "章末狀態快照" in findings[0].detail


def test_chapter_derived_uses_the_chapter_enum(tmp_path):
    book = _book(tmp_path)
    d = book / "chapters"
    d.mkdir()
    (d / "ch0001.ai.md").write_text("---\n對應幕: [幕001]\n---\n## 本章事實\n- x\n", encoding="utf-8")
    assert unsliceable_derived(book) == []
    (d / "ch0002.ai.md").write_text("---\n---\n## 反派備註\nx\n", encoding="utf-8")
    findings = unsliceable_derived(book)
    assert len(findings) == 1 and findings[0].path.name == "ch0002.ai.md"


def test_chapter_index_row_uses_the_rollup_line_limit(tmp_path):
    """備註欄與設定層 rollup 同一把尺（400），不是綜合檔的 2000。"""
    book = _book(tmp_path)
    d = book / "chapters"
    d.mkdir()
    (d / "_index.ai.md").write_text(
        "## 章節索引\n| ch0001 | 幕001 | arc01 | 甲 | 風格 | 草稿 | " + "註" * 800 + " |\n",
        encoding="utf-8",
    )
    findings = long_lines(book)
    assert len(findings) == 1 and findings[0].path.name == "_index.ai.md"
    assert findings[0].kind == "狀態格過長"


def test_chapter_prose_sources_are_not_line_limited(tmp_path):
    """正文源是人管·源，段落想多長就多長——只有 rollup 那支受行長管。"""
    book = _book(tmp_path)
    d = book / "chapters"
    d.mkdir()
    (d / "ch0001.md").write_text("他" * 3000 + "\n", encoding="utf-8")
    assert long_lines(book) == []


# ---------------------------------------------------------------- 長行

def test_long_line_fires_on_status_cell(tmp_path):
    book = _book(tmp_path)
    p = book / "story" / "參照" / "就緒儀表.md"
    p.write_text("| 主線 | " + "沿" * 3000 + " |\n短短一行\n", encoding="utf-8")
    findings = long_lines(book)
    assert len(findings) == 1 and findings[0].kind == "狀態格過長"


def test_rollup_row_has_tighter_limit(tmp_path):
    """rollup 那一欄是「一行需求」——800 字的整段補厚紀錄該被報，
    但它還沒到綜合檔的 2000 字門檻，故 rollup 需要自己的尺。"""
    book = _book(tmp_path)
    p = book / "story" / "設定" / "角色" / "_index.ai.md"
    p.write_text("## 角色清單\n| 少年 | 主角 | " + "補" * 800 + " |\n", encoding="utf-8")
    findings = long_lines(book)
    assert len(findings) == 1 and findings[0].path.name == "_index.ai.md"


def test_append_log_exempt_from_long_lines(tmp_path):
    """事實流／裁決流有投影工具，不受行長規範（新舊檔名都算）。"""
    book = _book(tmp_path)
    for name in ("事實流.md", "狀態事件流.md", "裁決流.md"):
        (book / "story" / "參照" / name).write_text("- " + "長" * 3000, encoding="utf-8")
    assert long_lines(book) == []


def test_append_log_with_short_lines_is_clean(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "參照" / "事實流.md").write_text(
        "\n".join(f"- 幕{i:03d}（arc01）· 少年 · 持有：東西{i}" for i in range(500)),
        encoding="utf-8",
    )
    assert long_lines(book) == []


# ---------------------------------------------------------------- 彙總

def test_run_aggregates_all_four(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc09.md").write_text(_beats(5, 3000), encoding="utf-8")
    (book / "story" / "設定" / "角色" / "超巨.md").write_text("字" * 10000, encoding="utf-8")
    (book / "story" / "設定" / "角色" / "少年.ai.md").write_text(
        LEGAL_CHAR_AI + "## 反派備註\nx\n", encoding="utf-8"
    )
    (book / "story" / "參照" / "結構.md").write_text("巨" * 5000 + "\n", encoding="utf-8")
    kinds = {f.kind for f in run(book)}
    # 這本 fixture 沒有裁決流，而上面四項的 hint 都叫人往那裡搬 → 第五類必然觸發。
    assert kinds == {
        "幕綱肥大",
        "源檔肥大",
        "衍生檔不可切片",
        "狀態格過長",
        "目的地不存在",
    }


def test_missing_dirs_do_not_crash(tmp_path):
    assert run(tmp_path / "nonexistent") == []


# ------------------------------------------------ 目的地存在性（E1 新推論）

def test_destination_reported_when_hints_point_at_a_missing_file(tmp_path):
    """**箭頭指向空氣**：實測一世之尊 229 行輸出裡有 37 行叫人搬進裁決流，
    而那本書沒有那支檔。它不是假陰性也不是單純的警報疲勞——是「報得沒錯但
    照做會失敗」。"""
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc09.md").write_text(_beats(5, 3000), encoding="utf-8")
    findings = [f for f in run(book) if f.kind == "目的地不存在"]
    assert len(findings) == 1
    assert "story/參照/裁決流.md" in findings[0].detail
    assert "幕綱肥大" in findings[0].detail


def test_destination_silent_when_it_exists(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc09.md").write_text(_beats(5, 3000), encoding="utf-8")
    (book / "story" / "參照" / "裁決流.md").write_text("# 裁決流\n", encoding="utf-8")
    assert [f for f in run(book) if f.kind == "目的地不存在"] == []


def test_legacy_destination_name_still_counts(tmp_path):
    """既有書仍是 `裁決流.co.md`（2026-07-27 前建的）——不該叫它再建一支。"""
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc09.md").write_text(_beats(5, 3000), encoding="utf-8")
    (book / "story" / "參照" / "裁決流.co.md").write_text("# 裁決流\n", encoding="utf-8")
    assert [f for f in run(book) if f.kind == "目的地不存在"] == []


def test_no_content_to_move_means_no_nagging(tmp_path):
    """**只在真的有內容要搬時才報。** 一支乾淨的書不該因為「你沒有裁決流」被念
    ——那就是製造下一個沒人看的警報。"""
    book = _book(tmp_path)
    assert [f for f in run(book) if f.kind == "目的地不存在"] == []


def test_declarative_files_scanned_under_both_namings(tmp_path):
    """就緒儀表／結構 2026-07-26 起改叫 .ai.md；既有書仍是舊名。兩種都要掃到。"""
    for name in ("就緒儀表.ai.md", "結構.md"):
        book = _book(tmp_path / name)
        (book / "story" / "參照" / name).write_text(
            "| 主線 | " + "沿" * 3000 + " |\n", encoding="utf-8"
        )
        findings = long_lines(book)
        assert len(findings) == 1 and findings[0].path.name == name


def test_append_log_exempt_under_both_namings(tmp_path):
    book = _book(tmp_path)
    for name in ("事實流.md", "狀態事件流.md", "裁決流.md"):
        (book / "story" / "參照" / name).write_text("- " + "長" * 3000, encoding="utf-8")
    assert long_lines(book) == []


# ---------------------------------------------------------------- 事實行（2026-07-27）

def _facts(*lines: str) -> str:
    return "---\nk: v\n---\n## 本章事實\n" + "".join(f"- {ln}\n" for ln in lines)


def _chapters(tmp_path, **files: str):
    book = _book(tmp_path)
    (book / "chapters").mkdir(parents=True)
    for name, body in files.items():
        (book / "chapters" / f"{name}.ai.md").write_text(body, encoding="utf-8")
    return book


def test_pure_delta_lines_are_clean(tmp_path):
    book = _chapters(
        tmp_path,
        ch0001=_facts(
            "幕002（arc01）· 少年 · 知識前沿：＋尚不知〔信物用途〕",
            "幕003（arc01）· 少年 · 位置：雜役院",
        ),
    )
    assert bloated_fact_lines(book) == []


def test_rewritten_recap_line_is_reported(tmp_path):
    """重抄：fold 覆蓋逼出的前情提要效應（實測病態期內容欄平均 194 字）。"""
    book = _chapters(
        tmp_path, ch0001=_facts("幕002（arc01）· 少年 · 位置：" + "字" * 200)
    )
    (finding,) = bloated_fact_lines(book)
    assert finding.kind == "事實行肥大" and "200 字" in finding.detail


def test_smuggled_design_notes_are_reported(tmp_path):
    """夾帶：伏筆狀態／裁決理由／排除線塞進唯一會被 write 讀到的欄位。"""
    body = "他到了那裡" + "（" + "本 arc 收·口子閉合·on-page 最後一次" * 4 + "）"
    book = _chapters(tmp_path, ch0001=_facts(f"幕002（arc01）· 少年 · 位置：{body}"))
    kinds = {f.kind for f in bloated_fact_lines(book)}
    assert "事實行夾帶" in kinds


def test_feedback_section_lines_are_not_facts(tmp_path):
    """`## 本章事實` 區塊**外**的 `- ` 開頭行不得被當成事實行誤報。
    （2026-07-27 前的實例是「## 待裁決回饋」，那個節已搬去 story/參照/待裁決.md；
    這條防禦仍然要在——任何枚舉外的節都可能有 `- ` 開頭的行。）"""
    book = _chapters(
        tmp_path,
        ch0001="---\nk: v\n---\n## 待裁決回饋\n- 幕002（arc01）· 少年 · 位置："
        + "字" * 300
        + "\n",
    )
    assert bloated_fact_lines(book) == []


def test_append_log_no_longer_exempt_from_line_length(tmp_path):
    """2026-07-27 前這裡整支檔豁免——但投影的粒度就是行，一行不可再切。"""
    book = _book(tmp_path)
    (book / "story" / "參照" / "裁決流.co.md").write_text(
        "- 幕002（arc01）· 少年 · 位置：" + "字" * 300 + "\n", encoding="utf-8"
    )
    assert [f.kind for f in bloated_fact_lines(book)] == ["事實行肥大"]


def test_file_size_exemption_for_append_logs_survives(tmp_path):
    """行長受管，但**檔案大小**仍不受管（有投影工具可切片）。"""
    book = _book(tmp_path)
    (book / "story" / "參照" / "裁決流.co.md").write_text(
        "".join(f"- 幕{i:03d}（arc01）· 少年 · 位置：走到某處\n" for i in range(400)),
        encoding="utf-8",
    )
    assert long_lines(book) == [] and bloated_fact_lines(book) == []
