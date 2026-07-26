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
    "## 待裁決回饋\n| 日期 | 來源 |\n"
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
    assert "本章事實" in findings[0].hint and "約束.md" in findings[0].hint


def test_section_title_may_carry_a_suffix_note(tmp_path):
    """「## 待裁決回饋（2 筆）」不算枚舉外——比對的是開頭。"""
    book = _book(tmp_path)
    (book / "story" / "設定" / "角色" / "少年.ai.md").write_text(
        LEGAL_CHAR_AI.replace("## 待裁決回饋", "## 待裁決回饋（2 筆）"), encoding="utf-8"
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
    assert kinds == {"幕綱肥大", "源檔肥大", "衍生檔不可切片", "狀態格過長"}


def test_missing_dirs_do_not_crash(tmp_path):
    assert run(tmp_path / "nonexistent") == []


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
    """「## 待裁決回饋」底下也是 `- ` 開頭，不得被當成事實行誤報。"""
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
    (book / "story" / "參照" / "約束.co.md").write_text(
        "- 幕002（arc01）· 少年 · 位置：" + "字" * 300 + "\n", encoding="utf-8"
    )
    assert [f.kind for f in bloated_fact_lines(book)] == ["事實行肥大"]


def test_file_size_exemption_for_append_logs_survives(tmp_path):
    """行長受管，但**檔案大小**仍不受管（有投影工具可切片）。"""
    book = _book(tmp_path)
    (book / "story" / "參照" / "約束.co.md").write_text(
        "".join(f"- 幕{i:03d}（arc01）· 少年 · 位置：走到某處\n" for i in range(400)),
        encoding="utf-8",
    )
    assert long_lines(book) == [] and bloated_fact_lines(book) == []
