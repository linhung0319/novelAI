"""`.ai.md` 格式閘門。"""

import pytest
from derived_sync.cli import main
from derived_sync.validate import (
    ValidateStats,
    classify,
    enum_for,
    validate_book,
    validate_file,
    validate_report,
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


@pytest.mark.parametrize("name", ["結構.ai.md", "就緒儀表.ai.md"])
def test_retired_reference_files_are_no_longer_exempt(tmp_path, name):
    """**2026-07-28（功能 11）：「宣告式」那個豁免整個刪掉。**

    在此之前這兩支是「**沒有任何命名能讓它被驗**」的：舊名 `.md` 讓 `check_book` 的
    `rglob("*.ai.md")` 掃不到，新名 `.ai.md` 讓 `validate_file` 早退**三次**
    （front-matter 必填鍵／裁決 blockquote／節枚舉）——而後兩項與那個豁免的理由
    （無單一源可 hash）**完全無關**（`設計原則.md` E2 第七種形態）。

    連理由本身都是假的：`結構` 的對應表實測 108/108 幕可從幕綱 `結構階段` 欄重算。
    """
    book = _book(tmp_path, {f"story/參照/{name}": "---\n更新: 2026-07-26\n---\n"})
    (p,) = validate_file(book, book / "story" / "參照" / name)
    assert "generated-from" in p.detail


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


# --------------------------------- schema 外的 front-matter 鍵（2026-07-28 功能 14，V13）
#
# `REQUIRED_KEYS` **只驗缺、不驗多**，所以一個沒有人定義過的鍵可以長出來並活很久
# ——實測 `00-摘要.ai.md` 的 `終局` 是某一輪重生自己長出來的 534 字元單行，
# schema 從沒定義過它，零消費者，活過至少 4 個版本。


def _char_book(tmp_path, fm: str):
    book = tmp_path / "書"
    d = book / "story" / "設定" / "角色"
    d.mkdir(parents=True)
    (d / "少年.md").write_text("# 少年\n\n怕水。\n", encoding="utf-8")
    (d / "少年.ai.md").write_text(
        f"---\n{fm}---\n"
        "## 需求四象限\n- 期盼：變強\n## 預期弧線\n盲目\n"
        "## 馬斯洛層次\n安全\n## 對衝關係\n對撞\n",
        encoding="utf-8",
    )
    return book


def test_schema_keys_pass(tmp_path):
    book = _char_book(
        tmp_path,
        "generated-from: abc\ngenerated-at: 2026-07-28\n定位: 主角\n"
        "所屬arc: [arc01]\n暫定: false\n伏筆: { 埋: [], 收: [] }\n",
    )
    assert validate_book(book) == []


def test_unknown_key_is_reported(tmp_path):
    """`弧線類型` 是 06 刪掉的欄；`占卜結果` 是誰都沒定義過的——兩種都要抓。"""
    book = _char_book(
        tmp_path,
        "generated-from: abc\ngenerated-at: 2026-07-28\n定位: 主角\n"
        "弧線類型: 正弧線\n占卜結果: 大吉\n",
    )
    problems = validate_book(book)
    assert len(problems) == 1
    assert "schema 外的 front-matter 鍵" in problems[0].detail
    assert "`占卜結果`" in problems[0].detail and "`弧線類型`" in problems[0].detail


def test_unknown_keys_aggregate_into_one_line(tmp_path):
    """**聚合**（03 拍板的判準）：實測一世之尊 29 支檔命中，逐支報就是 29 行同型雜訊。"""
    book = tmp_path / "書"
    d = book / "story" / "設定" / "角色"
    d.mkdir(parents=True)
    for name in ("甲", "乙", "丙"):
        (d / f"{name}.md").write_text(f"# {name}\n\n介紹。\n", encoding="utf-8")
        (d / f"{name}.ai.md").write_text(
            "---\ngenerated-from: a\ngenerated-at: 2026-07-28\n角色: X\n---\n"
            "## 需求四象限\n甲\n## 預期弧線\n乙\n## 馬斯洛層次\n丙\n## 對衝關係\n丁\n",
            encoding="utf-8",
        )
    problems = [p for p in validate_book(book) if "schema 外" in p.detail]
    assert len(problems) == 1
    assert "3 支 .ai.md" in problems[0].detail


def test_chinese_keys_are_visible_to_the_parser(tmp_path):
    """舊的 `^([A-Za-z0-9_-]+):` **連中文鍵都看不到**，所以「缺某鍵」在摘要軸上
    一直是空頭承諾——那支檔的鍵全是中文（`主線`／`題旨`／`基調`…）。"""
    book = tmp_path / "書"
    (book / "story").mkdir(parents=True)
    (book / "story" / "00-摘要.md").write_text("# 摘要\n\n主線。\n", encoding="utf-8")
    (book / "story" / "00-摘要.ai.md").write_text(
        "---\ngenerated-from: a\ngenerated-at: 2026-07-28\n"
        "主線: 少年復仇\n題旨: { X: 恨, Y: 放下 }\n終局: 他回頭了\n---\n"
        "## 壓縮\n略\n## 高概念\n略\n## 取向定位分析\n略\n",
        encoding="utf-8",
    )
    problems = [p for p in validate_book(book) if "schema 外" in p.detail]
    assert len(problems) == 1
    # 中文鍵讀得到 → `終局` 被抓到；`主線`／`題旨` 是合法鍵，不得誤報
    assert "`終局`" in problems[0].detail
    assert "`主線`" not in problems[0].detail and "`題旨`" not in problems[0].detail


def test_coverage_line_prints_both_key_numbers(tmp_path):
    """**兩個數字必須成對**：只印「檢查了幾個鍵」＝用命中率冒充可用率（E2）。"""
    book = _char_book(
        tmp_path, "generated-from: a\ngenerated-at: 2026-07-28\n弧線類型: 正弧線\n"
    )
    _, stats = validate_report(book)
    line = stats.render()
    assert "front-matter 鍵：1 支檔套鍵枚舉" in line
    assert "**1 個是 schema 外的**" in line


def test_rollups_have_no_key_enumeration(tmp_path):
    """rollup 三支 2026-07-28（功能 12）已廢除——殘留偵測是 `--emit` 末節的事，
    在這裡再報一次只是同一件事的第二個警報（E2 第七形態：豁免要寫出豁免哪一項）。"""
    book = tmp_path / "書"
    d = book / "story" / "設定" / "角色"
    d.mkdir(parents=True)
    (d / "_index.ai.md").write_text(
        "---\ngenerated-from: a\ngenerated-at: 2026-07-28\n誰都沒定義過: X\n---\n"
        "## 角色清單\n- 甲\n",
        encoding="utf-8",
    )
    _, stats = validate_report(book)
    assert stats.keys_unenumerated == 1 and stats.keys_unknown == 0
