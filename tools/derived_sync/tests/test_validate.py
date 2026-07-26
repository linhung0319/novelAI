"""`.ai.md` 格式閘門。"""

from derived_sync.cli import main
from derived_sync.validate import classify, enum_for, validate_book, validate_file

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


def test_enum_picks_rollup_variant():
    assert enum_for("章節", "ch0001") == ("本章事實", "待裁決回饋")
    assert enum_for("章節", "_index") == ("章節索引", "章末狀態快照")
    assert enum_for("風格", "風格") is None  # 未定義枚舉 → 只查 front-matter


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
    assert "硬事實" in p.detail and "約束.md" in p.hint


def test_annotated_section_title_is_allowed(tmp_path):
    book = _book(
        tmp_path, {"chapters/ch0001.ai.md": GOOD_FM + "## 待裁決回饋（2 筆）\n- 甲\n"}
    )
    assert validate_file(book, book / "chapters" / "ch0001.ai.md") == []


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


# ------------------------------------------------------------ CLI

def test_validate_book_and_cli_exit_codes(tmp_path, capsys):
    clean = _book(tmp_path / "a", {"chapters/ch0001.ai.md": GOOD_FM + "## 本章事實\n- 甲\n"})
    assert validate_book(clean) == []
    assert main(["validate", "--book", str(clean)]) == 0

    dirty = _book(tmp_path / "b", {"chapters/ch0001.ai.md": GOOD_FM + "## 硬事實\n- 乙\n"})
    assert main(["validate", "--book", str(dirty)]) == 1
    assert "硬事實" in capsys.readouterr().out
