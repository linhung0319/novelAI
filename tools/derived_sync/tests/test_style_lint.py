"""`style-lint` 的測試（2026-07-27 功能 07 重構輪新增）。

每一項都要有「乾淨的書不報」與「壞的書會報」兩面——**一個只在壞資料上測過的
檢查器，不知道自己會不會對乾淨的書亂叫**（`設計原則.md` E2 的警報疲勞那一格，
同 `test_world_lint.py` 立的紀律）。

第 4 項另外多測一組**假陰性**（`test_granularity_rejects_readfeel_adjectives`）：
第一版判準寫成「值裡有沒有 `分句|句|段` 這個字」，而 `短句快節奏…`／`短促碎句
動詞驅動` 都含「句」字，於是 4 個讀感形容詞裡有 2 個被判成「已宣告句層」——
**閘門對著它誕生要抓的那一格報乾淨**。那組測試是為了不讓它退回去。
"""

from pathlib import Path

from derived_sync.style_lint import granularity_of, lint_book

CLEAN_STYLE = (
    "---\n"
    "generated-from: abc123\n"
    "generated-at: 2026-07-27\n"
    "基調參照: 哥特恐怖＋黑色幽默\n"
    "禁用詞表: [OK, 搞定, 給力]\n"
    "稱謂系統: { 敬稱: [先生, 小姐, 閣下], 禁: [老X, 兄弟] }\n"
    "可用句式: { 常態: 碎在分句（8字上下、串 4–5 個）, 恐怖高潮: 碎在句（句號前 0–2 個逗號） }\n"
    "語域: 書面·古典\n"
    "---\n"
)

CLEAN_SUMMARY = (
    "---\n"
    "generated-from: sum123\n"
    "generated-at: 2026-07-27\n"
    "基調: 哥特恐怖＋黑色幽默\n"
    "---\n"
    "## 高概念\n一句話。\n"
)


def _book(tmp_path: Path, style: str = CLEAN_STYLE, summary: str | None = CLEAN_SUMMARY) -> Path:
    book = tmp_path / "書"
    d = book / "story" / "設定" / "風格"
    d.mkdir(parents=True)
    (d / "風格.ai.md").write_text(style, encoding="utf-8")
    (d / "風格.md").write_text("# 風格\n哥特恐怖打底。\n", encoding="utf-8")
    if summary is not None:
        (book / "story" / "00-摘要.ai.md").write_text(summary, encoding="utf-8")
    return book


def _details(book: Path) -> str:
    problems, _ = lint_book(book)
    return "\n".join(p.detail for p in problems)


# ---------------------------------------------------------------- 乾淨那一面


def test_clean_book_reports_nothing(tmp_path: Path) -> None:
    problems, stats = lint_book(_book(tmp_path))
    assert problems == []
    assert stats.files == 1
    assert stats.keys == 5
    assert stats.empty_keys == 0
    assert stats.slots == 2
    assert stats.slots_no_granularity == 0
    assert stats.slots_no_digit == 0
    assert stats.banned_entries == 3
    assert stats.banned_descriptive == 0
    assert stats.tone_state == "相符"


def test_no_style_dir_is_silent(tmp_path: Path) -> None:
    """沒有風格軸的書（只有 raw/ 的書真的存在）不該報任何東西。"""
    book = tmp_path / "書"
    (book / "raw").mkdir(parents=True)
    problems, stats = lint_book(book)
    assert problems == []
    assert stats.files == 0


def test_skeleton_is_skipped(tmp_path: Path) -> None:
    """尚未封章的骨架跳過——那個狀態 `check` 已經報成 unstamped，重複報是雜訊。"""
    problems, stats = lint_book(_book(tmp_path, style="# 風格（衍生）\n\n> ⚠️ 尚未產出\n"))
    assert problems == []
    assert stats.skeleton == 1


def test_rollup_is_skipped(tmp_path: Path) -> None:
    """`_` 開頭的 rollup 不套本閘門（多檔形態才有，格式比照世界觀 _總覽）。"""
    book = _book(tmp_path)
    (book / "story" / "設定" / "風格" / "_總覽.ai.md").write_text(
        "---\ngenerated-from: x\ngenerated-at: 2026-07-27\n---\n## 一句話定位\n兩個世界。\n",
        encoding="utf-8",
    )
    problems, stats = lint_book(book)
    assert problems == []
    assert stats.files == 1


# ---------------------------------------------------------------- 第 1 項


def test_missing_key_reported(tmp_path: Path) -> None:
    style = CLEAN_STYLE.replace("語域: 書面·古典\n", "")
    assert "缺（或空）語域" in _details(_book(tmp_path, style))


def test_empty_key_counts_as_missing(tmp_path: Path) -> None:
    """空值也算缺——**一個空的「機讀核對基準」比沒有更糟**（讀的人以為有）。"""
    book = _book(tmp_path, CLEAN_STYLE.replace("語域: 書面·古典", "語域:"))
    problems, stats = lint_book(book)
    assert "缺（或空）語域" in "\n".join(p.detail for p in problems)
    assert stats.empty_keys == 1


# ---------------------------------------------------------------- 第 2 項


def test_descriptive_banned_entry_reported(tmp_path: Path) -> None:
    style = CLEAN_STYLE.replace(
        "禁用詞表: [OK, 搞定, 給力]",
        "禁用詞表: [OK, 老周式暱稱(老X), 兄弟(現代語氣)]",
    )
    book = _book(tmp_path, style)
    problems, stats = lint_book(book)
    detail = "\n".join(p.detail for p in problems)
    assert "2/3 個 entry 含括號" in detail
    assert stats.banned_descriptive == 2


def test_fullwidth_paren_entry_also_reported(tmp_path: Path) -> None:
    """全形括號一樣不可字面掃——判準是「有沒有括號」，不是「是不是半形」。"""
    style = CLEAN_STYLE.replace("禁用詞表: [OK, 搞定, 給力]", "禁用詞表: [OK, 兄弟（現代語氣）]")
    assert "含括號" in _details(_book(tmp_path, style))


# ---------------------------------------------------------------- 第 3 項


def test_address_shape_reported(tmp_path: Path) -> None:
    style = CLEAN_STYLE.replace(
        "稱謂系統: { 敬稱: [先生, 小姐, 閣下], 禁: [老X, 兄弟] }",
        "稱謂系統: { 敬稱: 先生小姐閣下 }",
    )
    assert "不是 `分組: [詞…]` 的形狀" in _details(_book(tmp_path, style))


def test_address_forbidden_group_takes_same_rule(tmp_path: Path) -> None:
    style = CLEAN_STYLE.replace("禁: [老X, 兄弟]", "禁: [老X, 兄弟(現代語氣)]")
    assert "的 `禁` 組有 1 個 entry 含括號" in _details(_book(tmp_path, style))


def test_free_group_names_are_allowed(tmp_path: Path) -> None:
    """**分組名自由**：實測某本書用 `佛門`／`江湖`，schema 範例用 `敬稱`——
    那本來就不是封閉枚舉，驗不到的就不要宣稱（E1）。"""
    style = CLEAN_STYLE.replace(
        "稱謂系統: { 敬稱: [先生, 小姐, 閣下], 禁: [老X, 兄弟] }",
        "稱謂系統: { 佛門: [師父, 師兄], 江湖: [師兄, 大小姐], 禁: [老X] }",
    )
    problems, stats = lint_book(_book(tmp_path, style))
    assert problems == []
    assert stats.address_groups == 3
    assert stats.address_words == 5


# ---------------------------------------------------------------- 第 4 項


def test_granularity_accepts_canonical_forms() -> None:
    assert granularity_of("碎在分句（8字上下、串 4–5 個），句子不斷開") == "分句"
    assert granularity_of("碎在句（句號前 0–2 個逗號）") == "句"
    # 值裡後面又提到別級時，**位置決定宣告的是哪一級**（`碎在` 那一個才算）
    assert granularity_of("碎在句（一句一分句）") == "句"
    assert granularity_of("碎在分句（8字上下、串 4–5 個），句子不斷開") == "分句"
    assert granularity_of("碎在段（換行）") == "段"
    assert granularity_of("分句（串 4–5 個）") == "分句"  # 裸寫在開頭也吃


def test_granularity_rejects_readfeel_adjectives() -> None:
    """**這組測試守的是一個實測過的假陰性。**

    第一版判準是「值裡有沒有 `分句|句|段` 這個字」，而下面這兩個值都含「句」——
    於是一世之尊 4/4 讀感形容詞裡有 2 個被判成「已宣告句層」，閘門對著本輪要抓
    的那一格報乾淨。**別把判準放寬回去。**
    """
    assert granularity_of("短句快節奏＋破折號省略號承接跳躍念頭") is None
    assert granularity_of("短促碎句動詞驅動") is None
    assert granularity_of("沉緩留白＋單一準確意象") is None
    assert granularity_of("乾淨放慢收掉吐槽") is None


def test_missing_granularity_and_digit_reported(tmp_path: Path) -> None:
    style = CLEAN_STYLE.replace(
        "可用句式: { 常態: 碎在分句（8字上下、串 4–5 個）, 恐怖高潮: 碎在句（句號前 0–2 個逗號） }",
        "可用句式: { 常態: 短句為主節奏快, 恐怖高潮: 短促碎句動詞驅動 }",
    )
    book = _book(tmp_path, style)
    problems, stats = lint_book(book)
    detail = "\n".join(p.detail for p in problems)
    assert "2/2 個檔位沒有顆粒度 token" in detail
    assert "2/2 個檔位沒有可數的數字" in detail
    assert stats.slots_no_granularity == 2
    assert stats.slots_no_digit == 2


def test_all_slots_at_coarsest_reported(tmp_path: Path) -> None:
    style = CLEAN_STYLE.replace(
        "可用句式: { 常態: 碎在分句（8字上下、串 4–5 個）, 恐怖高潮: 碎在句（句號前 0–2 個逗號） }",
        "可用句式: { 常態: 碎在段（換行，2–3 句一段）, 恐怖高潮: 碎在段（換行，1 句一段） }",
    )
    assert "全落在最粗的一級" in _details(_book(tmp_path, style))


def test_undeclared_slots_count_as_coarsest(tmp_path: Path) -> None:
    """**未宣告＝最粗的一級**（`風格.schema.md` 的實測判準：不指定顆粒度時，
    LLM 一律在最粗的一級實現讀感）。所以 0/N 宣告的書會被第 4c 項報。"""
    style = CLEAN_STYLE.replace(
        "可用句式: { 常態: 碎在分句（8字上下、串 4–5 個）, 恐怖高潮: 碎在句（句號前 0–2 個逗號） }",
        "可用句式: { 常態: 短句為主（4 字）, 恐怖高潮: 更碎（2 字） }",
    )
    detail = _details(_book(tmp_path, style))
    assert "全落在最粗的一級" in detail
    assert "其中 2 個未宣告" in detail


def test_one_fine_slot_is_enough(tmp_path: Path) -> None:
    """至少一檔碎在分句層就不報——`write` 的「不全篇一種句長勻平」有執行路徑了。"""
    style = CLEAN_STYLE.replace(
        "可用句式: { 常態: 碎在分句（8字上下、串 4–5 個）, 恐怖高潮: 碎在句（句號前 0–2 個逗號） }",
        "可用句式: { 常態: 碎在分句（串 4–5 個）, 高潮: 碎在段（1 句一段） }",
    )
    assert _details(_book(tmp_path, style)) == ""


def test_unparsable_sentence_column_reported(tmp_path: Path) -> None:
    style = CLEAN_STYLE.replace(
        "可用句式: { 常態: 碎在分句（8字上下、串 4–5 個）, 恐怖高潮: 碎在句（句號前 0–2 個逗號） }",
        "可用句式: 短句為主",
    )
    detail = _details(_book(tmp_path, style))
    # 沒有冒號 → 解析成單一無名檔位，仍要被 4a／4b 抓到（不得靜默通過）
    assert "沒有顆粒度 token" in detail


# ---------------------------------------------------------------- 第 5 項


def test_halfwidth_paren_in_register_reported(tmp_path: Path) -> None:
    style = CLEAN_STYLE.replace("語域: 書面·古典", "語域: 敘述層可現代(刻意喜劇裝置)／對白層書面古樸")
    assert "有半形括號" in _details(_book(tmp_path, style))


def test_fullwidth_paren_in_register_is_fine(tmp_path: Path) -> None:
    style = CLEAN_STYLE.replace("語域: 書面·古典", "語域: 敘述層可現代（刻意喜劇裝置）／對白層書面古樸")
    assert _details(_book(tmp_path, style)) == ""


# ---------------------------------------------------------------- 第 6 項


def test_tone_mismatch_reported(tmp_path: Path) -> None:
    """`00-摘要.md` 改了基調，`風格.ai.md` 的 hash 不會 stale——**這條跨檔相依
    沒有 hash 邊，漂移只有本項看得見**。"""
    book = _book(tmp_path, summary=CLEAN_SUMMARY.replace("基調: 哥特恐怖＋黑色幽默", "基調: 溫暖日常"))
    problems, stats = lint_book(book)
    assert "不一致" in "\n".join(p.detail for p in problems)
    assert stats.tone_state == "**不符**"


def test_tone_missing_summary_reported(tmp_path: Path) -> None:
    book = _book(tmp_path, summary=None)
    problems, stats = lint_book(book)
    assert "不存在" in "\n".join(p.detail for p in problems)
    assert "未比對" in stats.tone_state


def test_tone_summary_skeleton_is_silent(tmp_path: Path) -> None:
    """摘要衍生檔還是骨架時不報（`check` 已經報成 unstamped），但覆蓋率行說出未比對。"""
    book = _book(tmp_path, summary="# 摘要（衍生）\n\n> ⚠️ 尚未產出\n")
    problems, stats = lint_book(book)
    assert problems == []
    assert "未比對" in stats.tone_state


def test_tone_comment_is_stripped(tmp_path: Path) -> None:
    """schema 的範例本身就在值後面寫 `# 引 00-摘要.md「基調」`——不剝註解會誤報。"""
    style = CLEAN_STYLE.replace(
        "基調參照: 哥特恐怖＋黑色幽默",
        "基調參照: 哥特恐怖＋黑色幽默         # 引 00-摘要.md「基調」",
    )
    assert _details(_book(tmp_path, style)) == ""


# ---------------------------------------------------------------- 正文掃描


def test_chapter_scan_counts_zero_hits(tmp_path: Path) -> None:
    """**0 也印**：「掃了 2 章／3 個字面 entry／命中 0 次」與「禁用詞 0」是兩份
    完全不同的訊息（`設計原則.md` E2）。"""
    book = _book(tmp_path)
    ch = book / "chapters"
    ch.mkdir()
    (ch / "ch0001.md").write_text("他合十行禮，一言不發。\n", encoding="utf-8")
    (ch / "ch0002.md").write_text("夜裡下起雨來。\n", encoding="utf-8")
    problems, stats = lint_book(book)
    assert problems == []
    assert stats.chapters == 2
    assert stats.literal_entries == 3
    assert stats.scan_hits == 0
    assert stats.notes == []


def test_chapter_scan_reports_candidates_without_failing(tmp_path: Path) -> None:
    """命中**不計入問題數**——「掃到即候選命中」，候選不是判定（複判交 write-test）。"""
    book = _book(tmp_path)
    ch = book / "chapters"
    ch.mkdir()
    (ch / "ch0001.md").write_text("「OK。」他說。搞定了。\n", encoding="utf-8")
    problems, stats = lint_book(book)
    assert problems == []
    assert stats.scan_hits == 2
    assert any("`OK` 命中 1 次" in n for n in stats.notes)
    assert any("`搞定` 命中 1 次" in n for n in stats.notes)


def test_descriptive_entries_are_not_scanned(tmp_path: Path) -> None:
    """含括號的 entry 不進掃描——它不是詞。覆蓋率行把兩個數字分開印，
    這樣「11 個 entry 掃到 0 次」不會被誤讀成「11 個詞都乾淨」。"""
    style = CLEAN_STYLE.replace("禁用詞表: [OK, 搞定, 給力]", "禁用詞表: [OK, 兄弟(現代語氣)]")
    book = _book(tmp_path, style)
    ch = book / "chapters"
    ch.mkdir()
    (ch / "ch0001.md").write_text("師兄弟三人同行。\n", encoding="utf-8")
    _, stats = lint_book(book)
    assert stats.banned_entries == 2
    assert stats.banned_descriptive == 1
    assert stats.literal_entries == 1
    assert stats.scan_hits == 0  # 「師兄弟」不該因為 `兄弟(現代語氣)` 而命中


def test_chapter_ai_files_are_not_scanned(tmp_path: Path) -> None:
    book = _book(tmp_path)
    ch = book / "chapters"
    ch.mkdir()
    (ch / "ch0001.md").write_text("乾淨的正文。\n", encoding="utf-8")
    (ch / "ch0001.ai.md").write_text("---\n對應幕: [幕001]\n---\n## 本章事實\nOK\n", encoding="utf-8")
    _, stats = lint_book(book)
    assert stats.chapters == 1
    assert stats.scan_hits == 0


def test_coverage_line_always_renders(tmp_path: Path) -> None:
    """覆蓋率行**乾淨的時候也印**（E2）。"""
    _, stats = lint_book(_book(tmp_path))
    line = stats.render()
    assert "檢查範圍：1 支 風格.ai.md" in line
    assert "禁用詞命中 0 次" in line
    assert "相符" in line
