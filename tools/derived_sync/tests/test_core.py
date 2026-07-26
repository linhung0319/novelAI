from __future__ import annotations

from pathlib import Path

from derived_sync.core import (
    canonical_text,
    check_book,
    content_hash,
    read_generated_from,
    stamp,
)


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_hash_ignores_newline_and_trailing_ws() -> None:
    assert content_hash("凱\n怕水\n") == content_hash("凱\r\n怕水  \r\n\r\n")
    assert canonical_text("a\r\nb  \n\n").endswith("b\n")


def test_stamp_makes_fresh_then_edit_makes_stale(tmp_path: Path) -> None:
    book = tmp_path / "書"
    src = _write(book / "story" / "設定" / "角色" / "凱.md", "凱是個怕水的鐵匠。\n")
    ai = _write(
        book / "story" / "設定" / "角色" / "凱.ai.md",
        "---\n角色: 凱\n---\n## 需求四象限\n期盼：…\n",
    )

    digest = stamp(ai)
    assert read_generated_from(ai) == digest
    assert content_hash(src.read_text(encoding="utf-8")) == digest

    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["凱.ai.md"] == "fresh"

    src.write_text("凱是個怕水又欠債的鐵匠。\n", encoding="utf-8")
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["凱.ai.md"] == "stale"


def test_unstamped_and_orphan(tmp_path: Path) -> None:
    book = tmp_path / "書"
    _write(book / "story" / "設定" / "角色" / "艾拉.md", "艾拉。\n")
    _write(  # 有源、未封章
        book / "story" / "設定" / "角色" / "艾拉.ai.md", "## 分析\n無 front-matter\n"
    )
    _write(  # 無源 → orphan
        book / "story" / "設定" / "角色" / "幽靈.ai.md", "---\ngenerated-from: x\n---\n本體\n"
    )
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["艾拉.ai.md"] == "unstamped"
    assert statuses["幽靈.ai.md"] == "orphan"


def test_rollup_stale_when_sibling_added(tmp_path: Path) -> None:
    book = tmp_path / "書"
    d = book / "story" / "設定" / "角色"
    _write(d / "凱.md", "凱。\n")
    _write(d / "艾拉.md", "艾拉。\n")
    idx = _write(d / "_index.ai.md", "---\n---\n## 角色清單\n- 凱\n- 艾拉\n")

    stamp(idx)
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["_index.ai.md"] == "fresh"

    _write(d / "新角色.md", "新角色。\n")  # 同層新增源 → rollup 應 stale
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["_index.ai.md"] == "stale"


def test_stamp_preserves_body_and_other_frontmatter(tmp_path: Path) -> None:
    book = tmp_path / "書"
    _write(book / "a.md", "來源內容\n")
    ai = _write(
        book / "a.ai.md",
        "---\n角色: 甲\n所屬arc: [arc01]\n---\n## 分析\n第一段\n第二段\n",
    )
    stamp(ai, on="2026-07-19")
    text = ai.read_text(encoding="utf-8")
    assert "角色: 甲" in text
    assert "所屬arc: [arc01]" in text
    assert "generated-at: 2026-07-19" in text
    assert "## 分析" in text and "第二段" in text


# ---------------------------------------------------------------- 宣告式綜合檔

def _decl_book(tmp_path, name="就緒儀表.ai.md"):
    book = tmp_path / "book"
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "參照" / name).write_text("# 就緒儀表\n（無 front-matter）\n", encoding="utf-8")
    return book


def test_declarative_is_not_reported_orphan(tmp_path):
    """就緒儀表／結構無單一上游源；過去為了避開 orphan 誤報而不敢叫 .ai.md，
    那讓工具的實作細節決定了給作者看的命名訊號。"""
    book = _decl_book(tmp_path)
    statuses = {r.derived.name: r.status for r in check_book(book)}
    assert statuses == {"就緒儀表.ai.md": "declarative"}


def test_declarative_not_counted_as_problem(tmp_path):
    book = _decl_book(tmp_path, "結構.ai.md")
    assert all(r.status not in ("orphan", "stale", "unstamped") for r in check_book(book))


def test_stamping_declarative_raises_with_reason(tmp_path):
    import pytest

    book = _decl_book(tmp_path)
    with pytest.raises(ValueError, match="不必也不能封章"):
        stamp(book / "story" / "參照" / "就緒儀表.ai.md")


def test_declarative_only_applies_inside_參照(tmp_path):
    """同名檔若出現在別處，仍走一般的源→衍生規則（不該被特例吃掉）。"""
    book = tmp_path / "book"
    d = book / "story" / "設定" / "角色"
    d.mkdir(parents=True)
    (d / "結構.ai.md").write_text("x\n", encoding="utf-8")
    assert [r.status for r in check_book(book)] == ["orphan"]
