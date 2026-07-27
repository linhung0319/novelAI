"""`world-lint` 的測試（2026-07-27 功能 05 重構輪新增）。

每一項都要有「乾淨的書不報」與「壞的書會報」兩面——一個只在壞資料上測過的
檢查器，不知道自己會不會對乾淨的書亂叫（`設計原則.md` E2 的警報疲勞那一格）。
"""

from pathlib import Path

from derived_sync.world_lint import DIMENSIONS, lint_book

CLEAN_TOPIC = (
    "---\n"
    "generated-from: abc123\n"
    "generated-at: 2026-07-27\n"
    "主題: 修煉體系\n"
    "伏筆: { 埋: [原身已筑基], 收: [] }\n"
    "---\n"
    "## 限制與代價（Sanderson）\n- 上限＝…\n"
    "## 影響力\n抽掉會怎樣。主打·抽掉就垮。\n"
    "## 自洽\n無矛盾。\n"
)


def _rollup(topics: tuple[str, ...] = ("修煉體系",), dims: tuple[str, ...] = DIMENSIONS) -> str:
    rows = "\n".join(f"| {t} | 主打 | 高 | 否 | {t}.ai.md |" for t in topics)
    dim_rows = "\n".join(f"| {d} | 見源檔「## X」 | 已定 |" for d in dims)
    return (
        "---\ngenerated-from: rollupdigest\ngenerated-at: 2026-07-27\n---\n"
        "## 一句話定位\n一個世界。\n\n"
        "## 核心規則索引\n"
        "| 主題 | 主從 | 影響力 | 帶升格哨兵 | 檔 |\n"
        "|------|------|--------|-----------|-----|\n" + rows + "\n\n"
        "## 背景維度盤點\n"
        "| 維度 | 內容（指向源檔節名） | 狀態 |\n"
        "|------|----------------------|------|\n" + dim_rows + "\n\n"
        "## 待確認／潛在矛盾\n- 0 筆·見 story/參照/待裁決.md\n\n"
        "## 升格哨兵彙總\n- 0 條硬約束·見 story/物件/\n\n"
        "## 素材出處\n- raw/世界設定碎片.md\n"
    )


def _book(tmp_path, topic: str = CLEAN_TOPIC, rollup: str | None = None) -> Path:
    book = tmp_path / "book"
    d = book / "story" / "設定" / "世界觀"
    d.mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (d / "修煉體系.md").write_text("# 修煉體系\n作者手寫。\n", encoding="utf-8")
    (d / "修煉體系.ai.md").write_text(topic, encoding="utf-8")
    (d / "_總覽.ai.md").write_text(rollup if rollup is not None else _rollup(), encoding="utf-8")
    (book / "story" / "幕綱" / "arc01.md").write_text(
        "## 幕001 · 開場\n- 角色：少年\n- 行動：他練功 埋[[伏筆:原身已筑基]]\n",
        encoding="utf-8",
    )
    return book


def test_clean_book_reports_nothing_but_still_prints_counts(tmp_path):
    problems, stats = lint_book(_book(tmp_path))
    assert problems == []
    # **0 也印**：這一行本身就是「它真的讀到我的檔了」的證據
    assert stats.topics == 1
    assert stats.foreshadow_names == 1 and stats.foreshadow_unknown == 0
    assert stats.index_rows == 1 and stats.folder_topics == 1
    assert stats.dim_rows == 7
    assert stats.registry_beats == 1
    assert "0 個懸空" in stats.render()


# ---------------------------------------------------------------- 第 1／2 項

def test_missing_required_key_fires(tmp_path):
    book = _book(tmp_path, topic=CLEAN_TOPIC.replace("主題: 修煉體系\n", ""))
    problems, _ = lint_book(book)
    assert any("front-matter 缺 主題" in p.detail for p in problems)


def test_topic_key_must_match_filename(tmp_path):
    book = _book(tmp_path, topic=CLEAN_TOPIC.replace("主題: 修煉體系", "主題: 修練體系"))
    problems, _ = lint_book(book)
    assert any("與檔名" in p.detail for p in problems)


def test_retired_keys_fire(tmp_path):
    """抉擇 1 C 的閘門：沒有這一項，「四欄已刪」就只是口頭承諾。"""
    book = _book(
        tmp_path,
        topic=CLEAN_TOPIC.replace("主題: 修煉體系\n", "主題: 修煉體系\n影響力: 高\n升格哨兵: true\n"),
    )
    problems, stats = lint_book(book)
    hit = [p for p in problems if "已廢除" in p.detail]
    assert len(hit) == 1 and "影響力" in hit[0].detail and "升格哨兵" in hit[0].detail
    assert stats.topics_with_retired == 1 and stats.retired_keys == 2


def test_skeleton_without_frontmatter_is_skipped(tmp_path):
    """尚未封章的骨架由 `check` 報成 unstamped，這裡重複報是雜訊（同 validate）。"""
    book = _book(tmp_path, topic="## 限制與代價\n（尚未產出）\n")
    problems, stats = lint_book(book)
    assert stats.topics == 1
    assert not [p for p in problems if "front-matter" in p.detail]


# ---------------------------------------------------------------- 第 3 項

def test_foreshadow_name_not_in_registry_fires(tmp_path):
    book = _book(
        tmp_path,
        topic=CLEAN_TOPIC.replace("埋: [原身已筑基]", "埋: [如來神掌第三式密藏]"),
    )
    problems, stats = lint_book(book)
    assert stats.foreshadow_unknown == 1
    assert any("registry 查無" in p.detail for p in problems)


def test_object_file_alone_satisfies_registry(tmp_path):
    """沒有幕綱標記但有物件檔＝合法（物件.schema.md：ID 不必有幕綱標記）。"""
    book = _book(tmp_path, topic=CLEAN_TOPIC.replace("埋: [原身已筑基]", "埋: [母愛護盾]"))
    obj = book / "story" / "物件"
    obj.mkdir(parents=True)
    (obj / "母愛護盾.md").write_text("# 母愛護盾\n", encoding="utf-8")
    problems, stats = lint_book(book)
    assert stats.registry_objects == 1 and stats.foreshadow_unknown == 0
    assert problems == []


def test_unparseable_foreshadow_value_fires(tmp_path):
    book = _book(
        tmp_path, topic=CLEAN_TOPIC.replace("{ 埋: [原身已筑基], 收: [] }", "原身已筑基")
    )
    problems, _ = lint_book(book)
    assert any("解析不到任何名字" in p.detail for p in problems)


# ---------------------------------------------------------------- 第 4／5 項

def test_index_missing_a_source_file_fires(tmp_path):
    book = _book(tmp_path)
    d = book / "story" / "設定" / "世界觀"
    (d / "少林.md").write_text("# 少林\n", encoding="utf-8")
    problems, stats = lint_book(book)
    assert stats.folder_topics == 2 and stats.index_rows == 1
    assert any("沒進索引" in p.detail and "少林" in p.detail for p in problems)


def test_index_ghost_row_fires(tmp_path):
    book = _book(tmp_path, rollup=_rollup(topics=("修煉體系", "已刪掉的主題")))
    problems, _ = lint_book(book)
    assert any("指向不存在的主題" in p.detail for p in problems)


def test_index_header_row_is_not_data(tmp_path):
    """表頭「主題」曾被當成一筆資料而報成幽靈列（實作時的第一版 bug）。"""
    _, stats = lint_book(_book(tmp_path))
    assert stats.index_rows == 1


def test_dimension_table_must_be_the_closed_seven(tmp_path):
    book = _book(tmp_path, rollup=_rollup(dims=DIMENSIONS[:6]))
    problems, stats = lint_book(book)
    assert stats.dim_rows == 6
    assert any("不是封閉七維" in p.detail and "缺 自身" in p.detail for p in problems)


def test_missing_rollup_fires_when_sources_exist(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "設定" / "世界觀" / "_總覽.ai.md").unlink()
    problems, stats = lint_book(book)
    assert not stats.rollup_found
    assert any("沒有 _總覽" in p.detail for p in problems)


# ---------------------------------------------------------------- 第 6 項

def test_dangling_filename_reference_fires(tmp_path):
    """抉擇 3 拆檔程序步驟 4 的守衛：拆檔改了檔名而幕綱引用沒改。"""
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc02.md").write_text(
        "## 幕002 · x\n- 行動：見 `江湖勢力.ai.md` 的門派功法\n", encoding="utf-8"
    )
    problems, stats = lint_book(book)
    assert stats.ai_refs == 1 and stats.ai_refs_dangling == 1
    assert any("指向不存在的檔" in p.detail for p in problems)


def test_existing_filename_reference_is_clean(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc02.md").write_text(
        "## 幕002 · x\n- 行動：見 `設定/世界觀/修煉體系.ai.md` 的境界階梯\n", encoding="utf-8"
    )
    problems, stats = lint_book(book)
    assert stats.ai_refs == 1 and stats.ai_refs_dangling == 0
    assert problems == []


def test_unstamped_rollup_skeleton_is_skipped(tmp_path):
    """`書本模板` 那份骨架的表裡是佔位列，逐項比對只會報一堆幽靈列。
    那個狀態 `check` 已經報成 unstamped——同 validate 的骨架處置。"""
    book = _book(tmp_path, rollup="## 核心規則索引\n| 主題 | 檔 |\n|---|---|\n| （尚無主題） | |\n")
    problems, stats = lint_book(book)
    assert stats.rollup_found
    assert not [p for p in problems if "核心規則索引" in p.detail]
