from __future__ import annotations

from pathlib import Path

import pytest
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


# ------------------------------------------------- 「宣告式綜合檔」廢除後的殘留
# **2026-07-28（功能 11）：`_is_declarative` 整個刪掉，這一組從「驗豁免生效」翻面
# 成「驗豁免真的沒了」。** 原本這裡有四支測試（＋`test_validate.py` 一支）在驗那個
# 特例，而它們在**真實語料上跑的是 0 支檔**——全部用 `tmp_path` 造 `結構.ai.md`，
# 而唯一的活書叫 `結構.md`（`rglob("*.ai.md")` 掃不到）。**測試是綠的，射程是空的**
# ——那是 `設計原則.md` E2 第七種形態（「豁免的射程比它的理由大」）的鏡像。


def _reference_book(tmp_path, name):
    """一支住在 `story/參照/` 底下、帶 `.ai.md` 而沒有同名源的檔。"""
    book = tmp_path / "book"
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "參照" / name).write_text("# X\n（無 front-matter）\n", encoding="utf-8")
    return book


@pytest.mark.parametrize("name", ["結構.ai.md", "就緒儀表.ai.md"])
def test_retired_reference_files_are_reported_orphan(tmp_path, name):
    """兩支已廢除的「宣告式綜合檔」現在都報 `orphan`——**那是對的**。

    依 `設計原則.md` A6，「不許人改 ＋ 沒有 inbound 重算規則」是一個要解掉的衝突，
    不是可以永遠豁免的第三種身分。真正說得出所以然的那一筆由各自的守衛給：
    `結構` → `structure-project` 第五節；`就緒儀表` → `readiness-lint` 第 7 項。
    """
    book = _reference_book(tmp_path, name)
    assert [r.status for r in check_book(book)] == ["orphan"]


def test_stamping_a_sourceless_reference_file_raises(tmp_path):
    """`stamp` 不再有「不必也不能封章」那條專屬 raise——它現在走一般的「算不出 digest」。

    差別是實質的：舊訊息說「**這種檔**不必封章」（一種身分），新訊息說「**這一支**
    找不到源」（一個要解掉的狀態）。
    """
    book = _reference_book(tmp_path, "結構.ai.md")
    with pytest.raises(ValueError, match="無法為 .* 計算源 digest"):
        stamp(book / "story" / "參照" / "結構.ai.md")


def test_reference_file_with_a_source_behaves_normally(tmp_path):
    """`story/參照/` 不再是特例資料夾：有同名源就照常走 hash。"""
    book = _reference_book(tmp_path, "就緒.ai.md")
    (book / "story" / "參照" / "就緒.md").write_text("成熟度\n", encoding="utf-8")
    assert [r.status for r in check_book(book)] == ["unstamped"]
    stamp(book / "story" / "參照" / "就緒.ai.md")
    assert [r.status for r in check_book(book)] == ["fresh"]


# ---------------------------------------------------------------- 目錄形態
# 2026-07-27（功能 06）。在此之前這一組**全部是紅的**：`角色.schema.md` 寫著
# 「rollup 的 digest 對目錄形態取其下所有切面檔的集合」，而實作對非 rollup 一律
# 找同層 `<名>.md`、rollup 只 `glob("*.md")`（不遞迴）——目錄形態的 `<名>.ai.md`
# 被報成 orphan、`stamp` 直接 raise、改切面不會讓 rollup stale。0/24 實測所以
# 從沒撞到；功能 06 把升級改成哨兵驅動之後，第一支升級的角色就會撞上。


def _dir_form_book(tmp_path: Path) -> Path:
    book = tmp_path / "書"
    _write(book / "story" / "設定" / "角色" / "凱" / "核心.md", "凱是個怕水的鐵匠。\n")
    _write(book / "story" / "設定" / "角色" / "凱" / "水下.md", "他才是放火的人。\n")
    _write(
        book / "story" / "設定" / "角色" / "凱.ai.md",
        "---\n定位: 主角\n---\n## 需求四象限\n期盼：…\n",
    )
    _write(book / "story" / "設定" / "角色" / "艾拉.md", "艾拉是舊識。\n")
    _write(
        book / "story" / "設定" / "角色" / "艾拉.ai.md",
        "---\n定位: 配角\n---\n## 需求四象限\n期盼：…\n",
    )
    _write(
        book / "story" / "設定" / "角色" / "_index.ai.md",
        "---\n---\n## 角色清單\n| 角色 |\n|---|\n| 凱 |\n",
    )
    return book


def test_dir_form_source_can_be_stamped_and_is_not_orphan(tmp_path: Path) -> None:
    book = _dir_form_book(tmp_path)
    d = book / "story" / "設定" / "角色"
    for name in ("凱.ai.md", "艾拉.ai.md", "_index.ai.md"):
        stamp(d / name)
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses == {"_index.ai.md": "fresh", "凱.ai.md": "fresh", "艾拉.ai.md": "fresh"}


def test_editing_a_facet_makes_both_the_entity_and_the_rollup_stale(tmp_path: Path) -> None:
    book = _dir_form_book(tmp_path)
    d = book / "story" / "設定" / "角色"
    for name in ("凱.ai.md", "艾拉.ai.md", "_index.ai.md"):
        stamp(d / name)
    (d / "凱" / "水下.md").write_text("其實不是他放的火。\n", encoding="utf-8")
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["凱.ai.md"] == "stale"
    assert statuses["_index.ai.md"] == "stale"
    assert statuses["艾拉.ai.md"] == "fresh"


def test_adding_a_facet_makes_the_entity_stale(tmp_path: Path) -> None:
    """digest 吃的是「檔名:hash」的集合，所以新增一個切面也算變動。"""
    book = _dir_form_book(tmp_path)
    d = book / "story" / "設定" / "角色"
    stamp(d / "凱.ai.md")
    _write(d / "凱" / "能力.md", "打鐵。\n")
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["凱.ai.md"] == "stale"


def test_empty_dir_form_still_reports_orphan(tmp_path: Path) -> None:
    """目錄在但一個切面都沒有 ＝ 沒有源，不該假裝算得出 digest。"""
    book = tmp_path / "書"
    (book / "story" / "設定" / "角色" / "凱").mkdir(parents=True)
    _write(book / "story" / "設定" / "角色" / "凱.ai.md", "---\n---\n## 需求四象限\n")
    assert [r.status for r in check_book(book)] == ["orphan"]


def test_single_form_digest_is_unchanged_by_the_dir_form_support(tmp_path: Path) -> None:
    """既有書的 digest 不能因為這次改動而變（那會讓全書一次變 stale）。"""
    book = tmp_path / "書"
    src = _write(book / "story" / "設定" / "角色" / "凱.md", "凱是個怕水的鐵匠。\n")
    _write(book / "story" / "設定" / "角色" / "凱.ai.md", "---\n---\n## 需求四象限\n")
    assert stamp(book / "story" / "設定" / "角色" / "凱.ai.md") == content_hash(
        src.read_text(encoding="utf-8")
    )
