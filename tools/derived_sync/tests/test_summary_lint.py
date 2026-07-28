"""`summary-lint` 的測試（2026-07-27 功能 08 重構輪新增）。

每一項都要有「乾淨的書不報」與「壞的書會報」兩面——**一個只在壞資料上測過的
檢查器，不知道自己會不會對乾淨的書亂叫**（`設計原則.md` E2 的警報疲勞那一格，
`test_world_lint.py` 立的紀律、`test_style_lint.py` 沿用）。

另有三組守**假陰性**的測試（那才是這一輪的標的）：

- `test_tone_ignores_master_subordinate_annotations`：源檔那句寫成
  `**貼身喜劇（主）＋宏大縹緲（從），偶爾安靜扎心。**` 而衍生欄是
  `貼身喜劇＋宏大縹緲，偶爾安靜扎心`——**正規化不對就會把一本一致的書報成不符**，
  而那種假陽性會讓人直接關掉這一項。
- `test_person_gate_rejects_first_person`：`第一人稱貼身` 必須被擋下來。這是本輪
  唯一「schema 寫對了、閘門沒接上」的實測案例（93 章成書全程沒問過）。
- `test_threshold_needs_unit_and_digit_on_the_same_line`：單位與數字**要落在同一
  行**。整檔比對會讓每本書無條件通過（任何散文檔裡都有日期與 arc 編號）。
"""

from pathlib import Path

from derived_sync.summary_lint import lint_book, normalize_tone

CLEAN_SOURCE = (
    "# 摘要\n\n"
    "## 一句話（主線）\n少年下山。\n\n"
    "## 基調（氛圍／筆調）\n"
    "**哥特恐怖（主）＋黑色幽默（從）。**\n"
    "達標線：每章至少 1 次讓讀者鼻子出一口氣。\n\n"
    "## 敘事視角結構\n單線、第三人稱有限。\n"
)

CLEAN_DERIVED = (
    "---\n"
    "generated-from: abc123\n"
    "generated-at: 2026-07-27\n"
    "主線: 少年下山。\n"
    "題旨: { X: 驕傲, Y: 自取滅亡 }\n"
    "基調: 哥特恐怖＋黑色幽默\n"
    "視角結構: { 線: 單線, POV: 小女巫, 人稱: 第三人稱有限·DeepPOV }\n"
    "取向定位: { 整體: 偏文學 }\n"
    "貫穿大懸念: 主角真身之謎\n"
    "---\n"
    "## 壓縮\n### 50 字\n少年下山。\n"
    "## 高概念\n- Look：畫面\n"
    "## 取向定位分析\n偏文學。\n"
)


def _book(
    tmp_path: Path,
    source: str | None = CLEAN_SOURCE,
    derived: str | None = CLEAN_DERIVED,
    style: str | None = None,
    beats: dict[str, str] | None = None,
) -> Path:
    book = tmp_path / "書"
    (book / "story").mkdir(parents=True)
    if source is not None:
        (book / "story" / "00-摘要.md").write_text(source, encoding="utf-8")
    if derived is not None:
        (book / "story" / "00-摘要.ai.md").write_text(derived, encoding="utf-8")
    if style is not None:
        d = book / "story" / "設定" / "風格"
        d.mkdir(parents=True)
        (d / "風格.md").write_text(style, encoding="utf-8")
    for name, text in (beats or {}).items():
        d = book / "story" / "幕綱"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text, encoding="utf-8")
    return book


def _details(book: Path) -> str:
    problems, _ = lint_book(book)
    return "\n".join(p.detail for p in problems)


# ---------------------------------------------------------------- 乾淨那一面


def test_clean_book_reports_nothing(tmp_path: Path) -> None:
    problems, stats = lint_book(_book(tmp_path))
    assert problems == []
    assert stats.source == 1 and stats.derived == 1
    assert stats.keys == 6 and stats.empty_keys == 0
    assert stats.retired == 0
    assert stats.person_state == "合法"
    assert stats.tone_state == "相符"
    assert stats.threshold_where == "摘要"


def test_book_without_summary_is_silent(tmp_path: Path) -> None:
    """只有 raw/ 的書真的存在——沒有摘要軸就不該報任何東西。"""
    book = tmp_path / "書"
    (book / "raw").mkdir(parents=True)
    problems, stats = lint_book(book)
    assert problems == []
    assert stats.source == 0 and stats.derived == 0


def test_skeleton_derived_is_skipped(tmp_path: Path) -> None:
    """尚未封章的骨架跳過——那個狀態 `check` 已經報成 unstamped，重複報是雜訊。"""
    problems, stats = lint_book(
        _book(tmp_path, derived="# 摘要（衍生）\n\n> ⚠️ 尚未產出\n")
    )
    assert problems == []
    assert stats.skeleton == 1


def test_placeholder_source_tone_is_not_compared(tmp_path: Path) -> None:
    """`書本模板` 的基調節整句就是一段括號註記——**形狀判準**（同
    `char_lint._is_placeholder`），骨架不該被亂叫。"""
    source = "# 摘要\n\n## 基調（氛圍／筆調）\n（一句話定調，如「哥特恐怖＋黑色幽默」。）\n"
    problems, stats = lint_book(
        _book(tmp_path, source=source, derived="# 摘要（衍生）\n\n> ⚠️ 尚未產出\n")
    )
    assert problems == []
    assert stats.threshold_where == "未比對（源檔尚未落基調）"


def test_coverage_line_always_renders(tmp_path: Path) -> None:
    """覆蓋率行**乾淨的時候也印**（E2）。"""
    _, stats = lint_book(_book(tmp_path))
    line = stats.render()
    assert "1 支摘要源／1 支衍生" in line
    assert "0 個懸空" in line
    assert "0 處駁回語彙" in line


# ---------------------------------------------------------------- 第 0 項


def test_source_without_derived_is_reported(tmp_path: Path) -> None:
    """**從源側掃**（E1 的 06 推論）：`check` 從 `rglob("*.ai.md")` 出發，
    「源有衍生無」在定義上掃不到，而下游 10 支 skill 的機讀欄全在那支檔裡。"""
    problems, stats = lint_book(_book(tmp_path, derived=None))
    assert stats.source_without_derived == 1
    assert "沒有 `00-摘要.ai.md`" in "\n".join(p.detail for p in problems)
    assert "不要為了讓工具看得見而建空殼檔" in problems[0].hint


# ---------------------------------------------------------------- 第 1／2 項


def test_missing_key_reported(tmp_path: Path) -> None:
    derived = CLEAN_DERIVED.replace("貫穿大懸念: 主角真身之謎\n", "")
    assert "缺（或空）貫穿大懸念" in _details(_book(tmp_path, derived=derived))


def test_empty_key_counts_as_missing(tmp_path: Path) -> None:
    """空值也算缺——**一個空的機讀基準比沒有更糟**（讀的人以為有）。"""
    derived = CLEAN_DERIVED.replace("取向定位: { 整體: 偏文學 }", "取向定位:")
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    assert "缺（或空）取向定位" in "\n".join(p.detail for p in problems)
    assert stats.empty_keys == 1


def test_retired_keys_reported_and_aggregated(tmp_path: Path) -> None:
    """三個欄聚合成一行（單檔，形狀同 `world-lint` 第 2 項）。"""
    derived = CLEAN_DERIVED.replace(
        "貫穿大懸念: 主角真身之謎\n",
        "貫穿大懸念: 主角真身之謎\n"
        "基調主從: [哥特恐怖(主)]\n"
        "終局: { 狀態: 已定案 }\n"
        "節奏檔位: { 卷一: 開頭段 }\n",
    )
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    detail = "\n".join(p.detail for p in problems)
    assert "仍帶 3 個已廢除的欄：基調主從、終局、節奏檔位" in detail
    assert stats.retired == 3
    assert len([p for p in problems if "已廢除" in p.detail]) == 1


# ---------------------------------------------------------------- 第 3 項（人稱閘門）


def test_person_gate_accepts_both_supported_values(tmp_path: Path) -> None:
    """封閉二值表的兩個值都要過，而且**不同寫法都要過**——實測值寫成
    `第三人稱有限·DeepPOV`、`第三人稱有限視角（含 Deep POV）` 等多種形態。"""
    for value in (
        "第三人稱有限·DeepPOV",
        "第三人稱有限視角（含 Deep POV）",
        "第三人稱全知",
    ):
        derived = CLEAN_DERIVED.replace("第三人稱有限·DeepPOV", value)
        assert _details(_book(tmp_path / value, derived=derived)) == ""


def test_person_gate_rejects_first_person(tmp_path: Path) -> None:
    """**這一格是本模組存在的主要理由。** schema 明訂「填了非支援值，停下回問
    作者、不得直接封章」而零實作——唯一的書填 `第一人稱貼身`、順利封章、93 章
    成書，全程沒有一處問過。"""
    derived = CLEAN_DERIVED.replace("第三人稱有限·DeepPOV", "第一人稱貼身")
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    detail = "\n".join(p.detail for p in problems)
    assert "`人稱: 第一人稱貼身` 不是系統支援值" in detail
    assert stats.person_state == "**非支援值（第一人稱貼身）**"
    # 回問時要把理由講給作者聽，不要只說「不支援」
    assert "貼身喜感在第三人稱 Deep POV 一樣做得到" in problems[0].hint


def test_person_gate_rejects_third_person_without_a_kind(tmp_path: Path) -> None:
    """**不能放寬成「含第三人稱就好」**——那會放過「第三人稱與第一人稱交錯」。"""
    derived = CLEAN_DERIVED.replace("第三人稱有限·DeepPOV", "第三人稱與第一人稱交錯")
    assert "不是系統支援值" in _details(_book(tmp_path, derived=derived))


def test_missing_person_subkey_reported(tmp_path: Path) -> None:
    derived = CLEAN_DERIVED.replace(
        "視角結構: { 線: 單線, POV: 小女巫, 人稱: 第三人稱有限·DeepPOV }",
        "視角結構: { 線: 單線, POV: 小女巫 }",
    )
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    assert "解析不到 `人稱` 子欄" in "\n".join(p.detail for p in problems)
    assert "未比對" in stats.person_state


# ---------------------------------------------------------------- 第 4 項（POV 可解析）


def test_unparsable_pov_reported(tmp_path: Path) -> None:
    """`beat_metrics.load_pov` 抽不到 POV 時只印「讀不到——不猜」：很誠實，
    但**沒有人負責去修**，於是「純內在幕比例」會長期報「不適用」而報告正常。"""
    derived = CLEAN_DERIVED.replace(
        "視角結構: { 線: 單線, POV: 小女巫, 人稱: 第三人稱有限·DeepPOV }",
        "視角結構: { 線: 單線, 主角: 小女巫, 人稱: 第三人稱有限·DeepPOV }",
    )
    assert "的 `POV` 抽不出來" in _details(_book(tmp_path, derived=derived))


# ---------------------------------------------------------------- 第 5 項（基調比對）


def test_normalize_strips_bold_parens_and_trailing_punctuation() -> None:
    assert (
        normalize_tone("**哥特恐怖（主）＋黑色幽默（從），偶爾安靜扎心。**")
        == "哥特恐怖＋黑色幽默，偶爾安靜扎心"
    )
    assert normalize_tone("哥特恐怖＋黑色幽默") == "哥特恐怖＋黑色幽默"


def test_tone_ignores_master_subordinate_annotations(tmp_path: Path) -> None:
    """**這組守的是假陽性。** 源那句帶 `（主）`／`（從）` 與粗體、衍生欄不抄它們
    ——正規化不對就會把一本一致的書報成不符，而那種噪音會讓人直接關掉這一項。"""
    problems, stats = lint_book(_book(tmp_path))
    assert problems == []
    assert stats.tone_state == "相符"


def test_tone_drift_reported(tmp_path: Path) -> None:
    """源↔衍生這條邊在 2026-07-27 之前**零守衛**，而 `style-lint` 第 6 項只守
    `.ai.md` ↔ `.ai.md`——兩支衍生對得上、而它們一起對不上源時，三支守衛會同時
    報正常。"""
    derived = CLEAN_DERIVED.replace("基調: 哥特恐怖＋黑色幽默", "基調: 溫暖日常")
    problems, stats = lint_book(_book(tmp_path, derived=derived))
    assert "不一致" in "\n".join(p.detail for p in problems)
    assert stats.tone_state == "**不符**"


def test_tone_without_source_section_reported(tmp_path: Path) -> None:
    """抄本存在而正本不存在：`style-lint` 第 6 項與本項都在拿一個沒有來源的
    字串當基準。"""
    source = "# 摘要\n\n## 一句話（主線）\n少年下山。\n"
    problems, stats = lint_book(_book(tmp_path, source=source))
    assert "沒有「## 基調」" in "\n".join(p.detail for p in problems)
    assert "未比對" in stats.tone_state


def test_style_source_copy_is_visible(tmp_path: Path) -> None:
    """抉擇 4 A 把 `風格.md` 的複製句改成指標。**一世之尊不遷移，所以那句複本
    會留著**——覆蓋率行要能讓它可見（只印、不擋）。"""
    copy = "# 風格\n\n## 基調（承接 `00-摘要.md`）\n\n哥特恐怖（主）＋黑色幽默（從）。\n"
    pointer = "# 風格\n\n## 基調\n\n基調的定義在 `00-摘要.md`，本檔只寫它在句子層怎麼落。\n"
    problems, stats = lint_book(_book(tmp_path, style=copy))
    assert problems == []  # 只印、不擋
    assert stats.style_copy.startswith("**是**")
    _, stats2 = lint_book(_book(tmp_path / "b", style=pointer))
    assert stats2.style_copy == "否"


# ---------------------------------------------------------------- 第 6 項（引用）


def test_dangling_beat_reference_reported(tmp_path: Path) -> None:
    """實測 `貫穿大懸念` 寫著 `交棒點: arc05 幕411`，而**零檢查**——那個幕確實
    存在是運氣不是機制。幕綱改號之後摘要不會 stale（digest 只覆蓋源檔）。"""
    derived = CLEAN_DERIVED.replace(
        "貫穿大懸念: 主角真身之謎",
        "貫穿大懸念: { 卷一: 真身之謎, 交棒點: arc05 幕411 }",
    )
    book = _book(tmp_path, derived=derived, beats={"arc05.md": "# arc05\n## 幕410 · x\n"})
    problems, stats = lint_book(book)
    detail = "\n".join(p.detail for p in problems)
    assert "1 個幕號·arc 引用在幕綱查無：幕411" in detail
    assert stats.refs == 2 and stats.refs_dangling == 1
    assert stats.registry_beats == 1 and stats.registry_arcs == 1


def test_resolvable_references_are_clean(tmp_path: Path) -> None:
    derived = CLEAN_DERIVED.replace(
        "貫穿大懸念: 主角真身之謎",
        "貫穿大懸念: { 交棒點: arc05 幕411 }",
    )
    book = _book(tmp_path, derived=derived, beats={"arc05.md": "# arc05\n## 幕411 · x\n"})
    problems, stats = lint_book(book)
    assert problems == []
    assert stats.refs == 2 and stats.refs_dangling == 0


def test_stamp_keys_are_not_scanned_as_references(tmp_path: Path) -> None:
    """hash 與日期不是引用——把它們算進去會製造永遠修不掉的懸空。"""
    derived = CLEAN_DERIVED.replace("generated-from: abc123", "generated-from: a1c05f411b")
    _, stats = lint_book(_book(tmp_path, derived=derived))
    assert stats.refs == 0 and stats.refs_dangling == 0


# ---------------------------------------------------------------- 第 7 項（達標線）


def test_threshold_needs_unit_and_digit_on_the_same_line(tmp_path: Path) -> None:
    """**單位與數字要落在同一行。** 整檔比對沒有意義：任何散文檔裡都有日期與
    arc 編號，那會讓每本書都無條件通過（形狀照抄 `style-lint` 第 4 項）。"""
    source = CLEAN_SOURCE.replace(
        "達標線：每章至少 1 次讓讀者鼻子出一口氣。\n",
        "達標線：每章至少一次讓讀者鼻子出一口氣。\n2026-07-27 落定。\n",
    )
    problems, stats = lint_book(_book(tmp_path, source=source))
    assert "沒有寫出單位與達標線" in "\n".join(p.detail for p in problems)
    assert stats.threshold_where == "**兩邊都沒有**"


def test_threshold_may_live_in_the_style_source(tmp_path: Path) -> None:
    """**兩邊至少一邊有**（2026-07-28 作者拍板）：抉擇 4 A 把 `風格.md` 定義成
    「基調在句子層怎麼落」的執行細則，而達標線正是執行細則——不逼作者把一句
    執行細則複製回摘要（那正是本輪在砍的複本）。"""
    source = CLEAN_SOURCE.replace("達標線：每章至少 1 次讓讀者鼻子出一口氣。\n", "")
    style = "# 風格\n\n## 沉段的喜劇怎麼落\n達標線是「每章至少 1 次讓讀者鼻子出一口氣」。\n"
    problems, stats = lint_book(_book(tmp_path, source=source, style=style))
    assert problems == []
    assert stats.threshold_where == "風格"


def test_threshold_missing_on_both_sides_reported(tmp_path: Path) -> None:
    source = CLEAN_SOURCE.replace("達標線：每章至少 1 次讓讀者鼻子出一口氣。\n", "")
    style = "# 風格\n\n## 腔調\n端莊、句子偏長。\n"
    problems, stats = lint_book(_book(tmp_path, source=source, style=style))
    assert "沒有寫出單位與達標線" in "\n".join(p.detail for p in problems)
    assert stats.threshold_where == "**兩邊都沒有**"


# ---------------------------------------------------------------- 只印不擋的兩個提示


def test_rejection_vocabulary_is_a_note_not_a_problem(tmp_path: Path) -> None:
    """抉擇 1 C：切分線是語意判斷、lint 守不住，**只印、不擋**。"""
    source = CLEAN_SOURCE + "\n## 結局方向\n- a2 圓不回來，捨棄；排斥 (b) 接手。\n"
    problems, stats = lint_book(_book(tmp_path, source=source))
    assert problems == []  # 不計入問題數
    assert stats.rejection_hits == 3
    assert any("處駁回語彙" in n for n in stats.notes)


def test_rejection_scan_skips_blockquotes(tmp_path: Path) -> None:
    """**位置判準**：源檔的頭註與骨架指示寫在 `>` 裡，而那些指示本身就在講
    「被**捨棄**的方案要搬去哪」——不排除的話 `書本模板` 會因為自己的說明文字
    被報 2 處，**閘門對著一支空骨架亂叫**。"""
    source = CLEAN_SOURCE + "\n> **被捨棄的方案＋為什麼捨棄** → `story/參照/裁決流.md`。\n"
    _, stats = lint_book(_book(tmp_path, source=source))
    assert stats.rejection_hits == 0
    assert stats.notes == []


def test_settled_items_under_a_tentative_heading_are_flagged(tmp_path: Path) -> None:
    """抉擇 6：**標題在說謊**——下游讀到「非定版」會以為可以翻案。
    **條數看頂格、字樣看整段**：`2.` 的標題沒寫已定案，`已鎖定` 在它的續行裡。"""
    source = CLEAN_SOURCE + (
        "\n## 臨場拍板、非定版（待後續拍板，別鎖死）\n"
        "1. **全書終局方向＝已定案**（2026-07-21 收斂）。\n"
        "2. **玄悲收徒的時點與頂罪動機**：\n"
        "   - **收徒時點＝已鎖定**：arc03 前中段。\n"
        "3. 文字取捨仍暫定、可再議。\n"
    )
    problems, stats = lint_book(_book(tmp_path, source=source))
    assert problems == []  # 只印、不擋
    assert stats.adhoc_items == 3  # 續行不算一條
    assert stats.adhoc_settled == 2  # 而字樣要看整段，否則會漏掉第 2 條
    assert any("2 條帶" in n for n in stats.notes)
