"""`.ai.md` 格式閘門。"""

from derived_sync.cli import main
from derived_sync.validate import (
    ValidateStats,
    classify,
    enum_for,
    validate_book,
    validate_file,
)

GOOD_FM = "---\ngenerated-from: abc123\ngenerated-at: 2026-07-26\n---\n"


def _book(tmp_path, files: dict[str, str]):
    book = tmp_path / "book"
    for rel, body in files.items():
        p = book / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return book


# ------------------------------------------------------------ 分類

def test_classify_chapters_and_settings(tmp_path):
    book = _book(tmp_path, {"chapters/ch0001.ai.md": GOOD_FM})
    assert classify(book, book / "chapters" / "ch0001.ai.md") == "章節"
    assert classify(book, book / "story/設定/角色/凱.ai.md") == "角色"
    assert classify(book, book / "story/參照/裁決流.md") is None
    # 2026-07-27（功能 08）：摘要衍生檔住 `story/` 根目錄、不在任何 `<kind>`
    # 資料夾裡——**那正是它一直被 `classify()` 漏掉的原因**（第七次同根因）。
    assert classify(book, book / "story/00-摘要.ai.md") == "摘要"
    # 源檔不歸這裡管（`.ai.md` 才有節枚舉）
    assert classify(book, book / "story/00-摘要.md") is None


def test_enum_picks_rollup_variant():
    # 2026-07-27（功能 04）移除 `待裁決回饋`：它是源卻住在會被重生的容器裡（A1/A3），
    # 已搬去 story/參照/待裁決.md。
    assert enum_for("章節", "ch0001") == ("本章事實",)
    # 「章末狀態快照」2026-07-27 刪除：無產生器、無檢查器的僵屍規格，
    # 要人眼可讀的章末切片跑 `fact-project --as-of`，不落檔。
    assert enum_for("章節", "_index") == ("章節索引",)
    # 2026-07-27（功能 07）`風格` ＝**空 tuple，那是一個枚舉不是「沒有枚舉」**：
    # 衍生檔只留 front-matter 五欄，開任何 `##` 節就報。**判斷要用 `is not None`**
    # ——寫成 `if allowed:` 的話它會退回「只驗 front-matter」而輸出看起來完全正常。
    assert enum_for("風格", "風格") == ()
    assert enum_for("風格", "風格") is not None
    # 2026-07-27（功能 08）摘要補上三節枚舉。**`fm_only` 從此該恆為 0**——
    # 那一格現在是「有沒有新產物又沒登記枚舉」的哨兵，不是已知缺口的計數器。
    assert enum_for("摘要", "00-摘要") == ("壓縮", "高概念", "取向定位分析")


# ------------------------------------------------------------ front-matter

def test_skeleton_without_frontmatter_is_silent(tmp_path):
    """書本模板的「尚未產出」骨架——`check` 已報 unstamped，這裡不重複報。"""
    book = _book(tmp_path, {"chapters/_index.ai.md": "## 章節索引\n（尚未產出）\n"})
    assert validate_file(book, book / "chapters" / "_index.ai.md") == []


def test_section_enum_still_applies_without_frontmatter(tmp_path):
    """跳過的是 front-matter 檢查，不是整支檔——節枚舉照樣守。"""
    book = _book(tmp_path, {"chapters/ch0001.ai.md": "## 硬事實\n- 乙\n"})
    (p,) = validate_file(book, book / "chapters" / "ch0001.ai.md")
    assert "硬事實" in p.detail


def test_missing_required_keys(tmp_path):
    book = _book(tmp_path, {"chapters/ch0001.ai.md": "---\n對應幕: [幕001]\n---\n"})
    (p,) = validate_file(book, book / "chapters" / "ch0001.ai.md")
    assert "generated-from" in p.detail and "generated-at" in p.detail


def test_declarative_files_exempt_from_required_keys(tmp_path):
    """就緒儀表／結構無單一源、不走 hash，本來就不該有 generated-from。"""
    book = _book(tmp_path, {"story/參照/就緒儀表.ai.md": "---\n更新: 2026-07-26\n---\n"})
    assert validate_file(book, book / "story/參照/就緒儀表.ai.md") == []


# ------------------------------------------------------------ 節枚舉

def test_stray_section_in_chapter(tmp_path):
    book = _book(
        tmp_path,
        {"chapters/ch0001.ai.md": GOOD_FM + "## 本章事實\n- 甲\n## 硬事實\n- 乙\n"},
    )
    (p,) = validate_file(book, book / "chapters" / "ch0001.ai.md")
    assert "硬事實" in p.detail and "story/物件/<名>.md" in p.hint


def test_annotated_section_title_is_allowed(tmp_path):
    """節名取 `##` 標題的**開頭**比對，容許作者在標題後加註記。"""
    book = _book(
        tmp_path, {"chapters/ch0001.ai.md": GOOD_FM + "## 本章事實（2 筆）\n- 甲\n"}
    )
    assert validate_file(book, book / "chapters" / "ch0001.ai.md") == []


def test_retired_feedback_section_is_now_stray(tmp_path):
    """`## 待裁決回饋` 2026-07-27 移出枚舉（搬去 story/參照/待裁決.md）。
    既有書那些節現在會被報成枚舉外——**那是預期的**（同移除 `## 🧊 水下` 時）。"""
    book = _book(
        tmp_path, {"chapters/ch0001.ai.md": GOOD_FM + "## 本章事實\n- 甲\n## 待裁決回饋\n| 日期 |\n"}
    )
    (p,) = validate_file(book, book / "chapters" / "ch0001.ai.md")
    assert "待裁決回饋" in p.detail and "story/參照/待裁決.md" in p.hint


def test_stray_section_in_character(tmp_path):
    book = _book(
        tmp_path,
        {"story/設定/角色/凱.ai.md": GOOD_FM + "## 需求四象限\n- a\n## 反派備註\n- b\n"},
    )
    (p,) = validate_file(book, book / "story/設定/角色/凱.ai.md")
    assert "反派備註" in p.detail


def test_frontmatter_keys_not_mistaken_for_sections(tmp_path):
    """節枚舉只看本體；front-matter 裡的鍵不該被當成節。"""
    book = _book(
        tmp_path,
        {"chapters/ch0001.ai.md": "---\ngenerated-from: a\ngenerated-at: b\n## 不是節\n---\n"},
    )
    assert validate_file(book, book / "chapters" / "ch0001.ai.md") == []


# ------------------------------------------------- 裁決 blockquote 禁令（T1）

BQ = "> " + "理" * 60  # 遠超 BLOCKQUOTE_CHARS


def test_decision_blockquote_after_a_section_is_reported(tmp_path):
    """三支 schema 明文禁止、零守衛。實測 232 行／52,745 字元，28 個觀測點單調遞增。"""
    book = _book(
        tmp_path, {"chapters/ch0001.ai.md": GOOD_FM + f"## 本章事實\n- 甲\n\n{BQ}\n"}
    )
    problems = validate_book(book)
    assert len(problems) == 1
    assert "1 支 .ai.md 有裁決日誌 blockquote" in problems[0].detail
    assert "1 行" in problems[0].detail


def test_header_note_before_first_section_is_exempt(tmp_path):
    """**位置判準，不是分類判準。** 檔頭那句「⚠️ 本檔由 write 重生…」是合法頭註；
    要分辨「這段是不是裁決日誌」需要讀懂中文，那正是被駁回的形狀。"""
    book = _book(
        tmp_path, {"chapters/ch0001.ai.md": GOOD_FM + f"{BQ}\n\n## 本章事實\n- 甲\n"}
    )
    assert validate_book(book) == []


def test_short_blockquote_not_counted(tmp_path):
    book = _book(tmp_path, {"chapters/ch0001.ai.md": GOOD_FM + "## 本章事實\n- 甲\n\n> 短註\n"})
    assert validate_book(book) == []


def test_skeleton_blockquote_exempt(tmp_path):
    """書本模板的骨架檔沒有 front-matter，而它的「⚠️ 尚未產出」頭註本來就是長
    blockquote——那不是任何人的 append log。"""
    book = _book(tmp_path, {"chapters/_index.ai.md": f"# 章節索引\n\n{BQ}\n\n## 章節索引\n{BQ}\n"})
    assert validate_book(book) == []


def test_blockquotes_aggregate_into_one_line(tmp_path):
    """病因與修法完全相同 → 聚合（03 重構輪拍板的判準）。29 支檔逐支報就是
    29 行同型雜訊，會把真正該看的枚舉外節淹掉。"""
    files = {
        f"story/設定/角色/{n}.ai.md": GOOD_FM + f"## 需求四象限\n- a\n\n{BQ}\n{BQ}\n"
        for n in ("甲", "乙", "丙")
    }
    problems = validate_book(_book(tmp_path, files))
    assert len(problems) == 1
    assert "3 支 .ai.md" in problems[0].detail and "6 行" in problems[0].detail


# ------------------------------------------------------------ 覆蓋率行（T4）

def test_coverage_line_printed_even_when_clean(tmp_path, capsys):
    """**0 也印。** 只回答「發現幾個問題」的檢查器，在它自己被關掉時會印「乾淨」。"""
    book = _book(tmp_path, {"chapters/ch0001.ai.md": GOOD_FM + "## 本章事實\n- 甲\n"})
    assert main(["validate", "--book", str(book)]) == 0
    out = capsys.readouterr().out
    assert "檢查範圍：1 支 .ai.md" in out and "所有 .ai.md 格式合規" in out


def test_coverage_line_names_the_files_with_no_enum(tmp_path, capsys):
    """某些產物根本不在 `DERIVED_SECTIONS` 裡——節枚舉對它們是空頭承諾。
    不分開印，那個缺口永遠看不出來。

    **07 補上 `風格`、08 補上 `摘要` 之後 `fm_only` 該恆為 0**，所以這一格
    現在守的是**下一個**沒登記枚舉的產物（這裡拿一支假的 `story/大綱/arc01.ai.md`
    當代表）。這個測試不能因為現有缺口補完了就刪掉——刪掉等於把哨兵拆了。
    """
    book = _book(
        tmp_path,
        {
            "story/大綱/arc01.ai.md": GOOD_FM + "## 隨便一節\n- a\n",
            "chapters/ch0001.ai.md": GOOD_FM + "## 本章事實\n- 甲\n",
        },
    )
    main(["validate", "--book", str(book)])
    out = capsys.readouterr().out
    assert "1 支套節枚舉" in out and "1 支只驗 front-matter" in out


# ------------------------------------------------------------ 摘要（功能 08）

def test_summary_derived_stray_section_is_reported(tmp_path):
    """04 從五處枚舉移除的 `## 待裁決回饋` 在摘要衍生檔裡活了下來——因為
    `classify()` 認不得 `story/00-摘要.ai.md`，而 `validate` 把它算成
    `fm_only` 裡一個匿名的數字。**守衛的掃描起點決定了它能看見什麼**（E2）。"""
    book = _book(
        tmp_path,
        {
            "story/00-摘要.ai.md": GOOD_FM
            + "## 壓縮\n### 50 字\n一句話。\n## 待裁決回饋\n| 日期 | 來源 |\n"
        },
    )
    (p,) = validate_file(book, book / "story" / "00-摘要.ai.md")
    assert "1 個枚舉外的節：待裁決回饋" in p.detail
    assert "待裁決回饋屬 story/參照/待裁決.md" in p.hint


def test_summary_derived_with_schema_sections_is_clean(tmp_path):
    """乾淨那一面：三節都在枚舉內就不報，而且**算進 `enumerated`**。"""
    book = _book(
        tmp_path,
        {
            "story/00-摘要.ai.md": GOOD_FM
            + "## 壓縮\n### 50 字\n一句話。\n## 高概念\n- Look\n## 取向定位分析\n偏爽。\n"
        },
    )
    stats = ValidateStats()
    assert validate_file(book, book / "story" / "00-摘要.ai.md", stats) == []
    assert stats.enumerated == 1 and stats.fm_only == 0


# ------------------------------------------------------------ 空 tuple 枚舉（風格）

def test_style_derived_must_not_have_any_section(tmp_path):
    """`DERIVED_SECTIONS["風格"]` ＝空 tuple：**有任何 `##` 節就報**（功能 07 抉擇 5 B）。

    本體四節實測是源檔的同長度改寫（1.02×、8-gram 重疊 30%），腔調散文的唯一
    落點是源 `風格.md`。
    """
    book = _book(tmp_path, {"story/設定/風格/風格.ai.md": GOOD_FM + "## 腔調\n端莊。\n"})
    (p,) = validate_file(book, book / "story" / "設定" / "風格" / "風格.ai.md")
    assert "1 個枚舉外的節：腔調" in p.detail
    assert "不得有任何 `##` 節" in p.hint


def test_style_derived_with_only_frontmatter_is_clean(tmp_path):
    """乾淨那一面：只有 front-matter 的風格衍生檔不報，而且**算進 `enumerated`**
    ——空 tuple 是一個枚舉，不是「沒有枚舉」。"""
    book = _book(tmp_path, {"story/設定/風格/風格.ai.md": GOOD_FM})
    stats = ValidateStats()
    assert validate_file(book, book / "story" / "設定" / "風格" / "風格.ai.md", stats) == []
    assert stats.enumerated == 1 and stats.fm_only == 0


# ------------------------------------------------------------ CLI

def test_validate_book_and_cli_exit_codes(tmp_path, capsys):
    clean = _book(tmp_path / "a", {"chapters/ch0001.ai.md": GOOD_FM + "## 本章事實\n- 甲\n"})
    assert validate_book(clean) == []
    assert main(["validate", "--book", str(clean)]) == 0

    dirty = _book(tmp_path / "b", {"chapters/ch0001.ai.md": GOOD_FM + "## 硬事實\n- 乙\n"})
    assert main(["validate", "--book", str(dirty)]) == 1
    assert "硬事實" in capsys.readouterr().out
