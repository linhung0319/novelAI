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


def test_skeleton_unstamped_and_orphan(tmp_path: Path) -> None:
    """**`skeleton` 與 `unstamped` 是兩件事**（2026-07-28 功能 14）。

    front-matter 完全沒有 ＝這支檔從沒被產出過（`書本模板` 的骨架），**不可能
    stale**，所以它不計入「需處理」；有 front-matter 卻缺 `generated-from` ＝
    重生了忘記封章，那才是問題。在此之前兩者共用 `unstamped`，於是一支乾淨的
    模板永遠 exit 1——而抉擇 2 A 的 CI 閘門要拿它當「零成本的釘死」。
    """
    book = tmp_path / "書"
    _write(book / "story" / "設定" / "角色" / "艾拉.md", "艾拉。\n")
    _write(  # 有源、front-matter 完全沒有 → 尚未產出的骨架
        book / "story" / "設定" / "角色" / "艾拉.ai.md", "## 分析\n無 front-matter\n"
    )
    _write(book / "story" / "設定" / "角色" / "妙音.md", "妙音。\n")
    _write(  # 有源、有 front-matter 卻缺 generated-from → 重生了忘記封章
        book / "story" / "設定" / "角色" / "妙音.ai.md",
        "---\n定位: 配角\n---\n## 需求四象限\n期盼：…\n",
    )
    _write(  # 無源 → orphan
        book / "story" / "設定" / "角色" / "幽靈.ai.md", "---\ngenerated-from: x\n---\n本體\n"
    )
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["艾拉.ai.md"] == "skeleton"
    assert statuses["妙音.ai.md"] == "unstamped"
    assert statuses["幽靈.ai.md"] == "orphan"


def test_rollup_stale_when_sibling_added(tmp_path: Path) -> None:
    """多源 digest 機制本身仍在跑。

    **fixture 的檔名 2026-07-29（功能 15）從 `_index.ai.md` 換掉**：那個名字現在在
    `ABOLISHED_ROLLUPS` 裡，`check` 對它報 `abolished` 而不比新鮮度。**合法的 rollup
    目前零支**，所以這一支測的是機制、不是任何一支活著的檔——而機制要留著，因為
    `A6` 第 1 條路（「沒有源」是待驗證的宣稱）就是靠它成立的。
    """
    book = tmp_path / "書"
    d = book / "story" / "設定" / "角色"
    _write(d / "凱.md", "凱。\n")
    _write(d / "艾拉.md", "艾拉。\n")
    idx = _write(d / "_試作.ai.md", "---\n---\n## 角色清單\n- 凱\n- 艾拉\n")

    stamp(idx)
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["_試作.ai.md"] == "fresh"

    _write(d / "新角色.md", "新角色。\n")  # 同層新增源 → rollup 應 stale
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["_試作.ai.md"] == "stale"


# ------------------------------------------------- 已廢除的 rollup（2026-07-29 功能 15）
# **診斷輪用 scratchpad 復現過的那一格，重構輪把它變成測試**（抉擇 7 A 逐字要求）：
# 功能 12 廢除了五支 rollup，而 `_is_rollup` 是**檔名 pattern 級的通用機制**——只廢除了
# 實例、沒有廢除機制。復現的結果是三件事同時成立：`world-lint` 印「格式合規」exit 0、
# `validate` 印「所有 .ai.md 格式合規」、**`check` 主動報 `[STALE]` 要你去 `stamp` 它**。


@pytest.mark.parametrize(
    ("where", "name"),
    [
        (("chapters",), "_index.ai.md"),
        (("story", "設定", "角色"), "_index.ai.md"),
        (("story", "設定", "世界觀"), "_總覽.ai.md"),
    ],
)
def test_a_revived_abolished_rollup_is_reported_abolished_not_stale(tmp_path, where, name):
    """**回歸數字 ②**：復活一支已廢除的 rollup → 報 `abolished`，**不是 `stale`**。

    `stale` 是最糟的那一格：它把「這支檔不該存在」講成「這支檔需要維護」，而作者
    照著 `stamp` 就讓一支已廢除的檔**永久合法**了（`設計原則.md` A5：撤銷要從機制
    看得出來，不能只由一句散文完成）。
    """
    book = tmp_path / "書"
    d = book.joinpath(*where)
    _write(d / "凱.md", "凱。\n")
    rollup = _write(d / name, "---\n---\n## 清單\n- 凱\n")

    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses[name] == "abolished"

    # 連「填對格式再封章」這條路也要堵掉——那正是實測會讓它永久合法的動作
    with pytest.raises(ValueError, match="已於 .* 廢除，不必也不能封章"):
        stamp(rollup)

    # 而且**封章過的舊書一樣報**（不是只有沒封章的才報）：一世之尊那三支都是 fresh
    _write(d / name, "---\ngenerated-from: deadbeef\ngenerated-at: 2026-07-01\n---\n## 清單\n")
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses[name] == "abolished"


def test_a_rollup_name_not_on_the_closed_list_still_goes_through_hash(tmp_path):
    """**清單是封閉的**：不在上面的 `_*.ai.md` 照舊走 digest。

    沒有這一支，「封閉清單」與「所有 rollup 都廢除了」不可分辨——而後者是錯的
    （A6 第 1 條路要用多源 digest）。
    """
    book = tmp_path / "書"
    d = book / "story" / "設定" / "角色"
    _write(d / "凱.md", "凱。\n")
    rollup = _write(d / "_別的彙總.ai.md", "---\n---\n## 清單\n")
    stamp(rollup)
    assert {s.derived.name: s.status for s in check_book(book)} == {"_別的彙總.ai.md": "fresh"}


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
    # 那支 `.ai.md` 沒有 front-matter ＝尚未產出的骨架（功能 14 起與 `unstamped` 分開）
    assert [r.status for r in check_book(book)] == ["skeleton"]
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
        book / "story" / "設定" / "角色" / "_試作.ai.md",
        "---\n---\n## 角色清單\n| 角色 |\n|---|\n| 凱 |\n",
    )
    return book


def test_dir_form_source_can_be_stamped_and_is_not_orphan(tmp_path: Path) -> None:
    book = _dir_form_book(tmp_path)
    d = book / "story" / "設定" / "角色"
    for name in ("凱.ai.md", "艾拉.ai.md", "_試作.ai.md"):
        stamp(d / name)
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses == {"_試作.ai.md": "fresh", "凱.ai.md": "fresh", "艾拉.ai.md": "fresh"}


def test_editing_a_facet_makes_both_the_entity_and_the_rollup_stale(tmp_path: Path) -> None:
    book = _dir_form_book(tmp_path)
    d = book / "story" / "設定" / "角色"
    for name in ("凱.ai.md", "艾拉.ai.md", "_試作.ai.md"):
        stamp(d / name)
    (d / "凱" / "水下.md").write_text("其實不是他放的火。\n", encoding="utf-8")
    statuses = {s.derived.name: s.status for s in check_book(book)}
    assert statuses["凱.ai.md"] == "stale"
    assert statuses["_試作.ai.md"] == "stale"
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
