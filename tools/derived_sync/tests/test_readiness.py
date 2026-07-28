"""`readiness-lint` 與 `readiness` 的測試（2026-07-28 功能 10 重構輪新增）。

每一項都有「乾淨的書不報」與「壞的書會報」兩面——**一個只在壞資料上測過的
檢查器，不知道自己會不會對乾淨的書亂叫**（`test_world_lint.py` 立的紀律）。

投影那一半另有三組守**假陰性**的測試，那才是本輪的標的：

- `test_projection_prints_zero_sections`：`就緒.md` 不存在時三節照印、20 格照數
  ——一支「找不到源檔就安靜」的投影，會讓「還沒建檔」與「一切正常」長得一樣。
- `test_projection_separates_unwired_from_no_source`：**「未接」（跨套件，有來源）
  與「無機械來源」（這一格本來就是作者判斷）是兩件事**，混在一起就是新的假陰性。
- `test_projection_reports_mismatch`：作者判斷＝就緒而 lint 報問題時要印一行。
  那是本輪唯一新增的跨源比對邊，**它自己就是守衛**。
"""

from pathlib import Path

from derived_sync.readiness import lint_book, project_book

CLEAN = """# 就緒（作者判斷·源檔）

## 產物軸 × 深度成熟度

| 產物軸 | 粗 | 大綱 | 幕綱 | 正文 |
|--------|----|------|------|------|
| 設定層·世界觀 | 空白 | — | — | — |
| 設定層·角色 | 空白 | 空白 | 空白 | 空白 |
| 設定層·風格 | 空白 | — | — | — |
| 主線＋題旨＋基調 | 空白 | 空白 | 空白 | 空白 |
| 結構 | — | 空白 | 空白 | 空白 |

## 就緒清單

- [ ] 能用一句話說清主線
- [ ] 題旨可寫成「因為 X 導致 Y」
- [ ] 結局方向已拍板
- [ ] 主角／視角已定，且主角「需要」明確
- [ ] 世界觀無擋路的硬矛盾
- [ ] 基調已定（一句話），風格檔已承接展開
"""


def _book(
    tmp_path: Path,
    readiness: str | None = CLEAN,
    legacy: str | None = None,
    decision_log: bool = True,
) -> Path:
    book = tmp_path / "書"
    ref = book / "story" / "參照"
    ref.mkdir(parents=True)
    if readiness is not None:
        (ref / "就緒.md").write_text(readiness, encoding="utf-8")
    if legacy is not None:
        (ref / legacy).write_text("# 就緒儀表\n舊的\n", encoding="utf-8")
    if decision_log:
        (ref / "裁決流.md").write_text("# 裁決流\n", encoding="utf-8")
    return book


def _details(book: Path) -> str:
    problems, _ = lint_book(book)
    return "\n".join(p.detail for p in problems)


# ---------------------------------------------------------------- 乾淨那一面


def test_clean_book_is_silent(tmp_path: Path) -> None:
    problems, stats = lint_book(_book(tmp_path))
    assert problems == []
    assert (stats.cells, stats.bad_cells) == (20, 0)
    assert (stats.items, stats.checked) == (6, 0)


def test_row_labels_may_carry_parenthetical(tmp_path: Path) -> None:
    """`設定層·角色（需要／弧線）` 是合法列名——**標籤的寫法不該決定它比不比得上**。"""
    text = CLEAN.replace("| 設定層·角色 |", "| 設定層·角色（需要／弧線） |")
    assert _details(_book(tmp_path, text)) == ""


def test_checked_boxes_counted(tmp_path: Path) -> None:
    text = CLEAN.replace("- [ ] 能用一句話說清主線", "- [x] 能用一句話說清主線")
    problems, stats = lint_book(_book(tmp_path, text))
    assert problems == []
    assert stats.checked == 1


# ---------------------------------------------------------------- 七項各一反面


def test_missing_source_is_reported(tmp_path: Path) -> None:
    """第 1 項：從**源側**掃——`check` 從 `rglob("*.ai.md")` 出發，看不到這一格。"""
    problems, stats = lint_book(_book(tmp_path, readiness=None))
    assert "不存在" in problems[0].detail
    assert stats.source_exists is False


def test_third_section_is_reported(tmp_path: Path) -> None:
    """第 2 項：**第三節就是日誌回來的入口**。"""
    text = CLEAN + "\n## 局部下沉紀錄\n- 2026-07-28 arc09 已拆幕，本輪動檔 12 支…\n"
    assert "枚舉外的節" in _details(_book(tmp_path, text))


def test_note_column_is_reported(tmp_path: Path) -> None:
    """第 3 項：**沒有備註欄**（實測舊儀表的備註欄佔狀態格＋備註的 72.0%）。"""
    text = CLEAN.replace(
        "| 產物軸 | 粗 | 大綱 | 幕綱 | 正文 |", "| 產物軸 | 粗 | 大綱 | 幕綱 | 正文 | 備註 |"
    )
    detail = _details(_book(tmp_path, text))
    assert "表頭是 6 欄" in detail and "備註" in detail


def test_missing_axis_row_is_reported(tmp_path: Path) -> None:
    """第 4 項：五個產物軸是封閉的——還沒開始就填 `空白`，不是刪列。"""
    text = "\n".join(ln for ln in CLEAN.splitlines() if not ln.startswith("| 設定層·風格"))
    assert "缺 1 個產物軸" in _details(_book(tmp_path, text))


def test_overflowing_cell_is_reported(tmp_path: Path) -> None:
    """第 5 項：**結構判準不是長度門檻**——格值不是五 token 之一就報。

    實測分佈 1 → 3,647 字元連續無空隙，任何長度門檻都是任意值（06 抉擇 5 A）。
    """
    text = CLEAN.replace(
        "| 設定層·世界觀 | 空白 |",
        "| 設定層·世界觀 | 就緒（2026-07-22 第八輪 worldbuild 已收兩筆，見裁決流） |",
    )
    problems, stats = lint_book(_book(tmp_path, text))
    assert stats.bad_cells == 1
    assert "不是五 token 之一" in "\n".join(p.detail for p in problems)


def test_short_prose_cell_is_reported_too(tmp_path: Path) -> None:
    """溢位不必很長：`就緒（卷一）` 也是在寫沿革，而沿革的家是裁決流。"""
    text = CLEAN.replace("| 主線＋題旨＋基調 | 空白 |", "| 主線＋題旨＋基調 | 就緒（卷一） |")
    assert "不是五 token 之一" in _details(_book(tmp_path, text))


def test_dash_variants_pass(tmp_path: Path) -> None:
    """三種破折號是字形差異不是語意差異——正規化，不報。"""
    text = CLEAN.replace("| 設定層·世界觀 | 空白 | — | — | — |", "| 設定層·世界觀 | 空白 | - | – | — |")
    assert _details(_book(tmp_path, text)) == ""


def test_checklist_text_drift_is_reported(tmp_path: Path) -> None:
    """第 6 項：六條的文字與順序固定——`readiness` 逐條印前哨時靠序號對位。"""
    text = CLEAN.replace("- [ ] 結局方向已拍板", "- [ ] 結局大概想好了")
    assert "就緒清單第 3 條" in _details(_book(tmp_path, text))


def test_extra_checklist_item_is_reported(tmp_path: Path) -> None:
    text = CLEAN + "- [ ] 順便記一下這輪要做什麼\n"
    assert "7 條" in _details(_book(tmp_path, text))


def test_legacy_dashboard_is_reported(tmp_path: Path) -> None:
    """第 7 項（A5）：**撤銷要從檔案系統看得出來**。"""
    detail = _details(_book(tmp_path, legacy="就緒儀表.md"))
    assert "仍在" in detail


def test_legacy_dashboard_without_decision_log_reports_destination(tmp_path: Path) -> None:
    """舊檔還在、而日誌沒有家＝那 53.8% 無處可搬（E1 目的地推論）。"""
    problems, stats = lint_book(
        _book(tmp_path, legacy="就緒儀表.ai.md", decision_log=False)
    )
    detail = "\n".join(p.detail for p in problems)
    assert "裁決流.md` 不存在" in detail
    assert stats.decision_log is False


def test_legacy_ai_naming_is_caught_too(tmp_path: Path) -> None:
    """兩種命名都認——**沒有任何一種命名能讓那支檔被驗**，這是它被廢除的理由。"""
    assert "就緒儀表.ai.md" in _details(_book(tmp_path, legacy="就緒儀表.ai.md"))


# ---------------------------------------------------------------- 投影


def _text(book: Path) -> tuple[str, object]:
    lines, stats = project_book(book)
    return "\n".join(lines), stats


def test_projection_prints_three_sections(tmp_path: Path) -> None:
    out, stats = _text(_book(tmp_path))
    assert "### 1 · 產物軸 × 深度成熟度" in out
    assert "### 2 · 就緒清單" in out
    assert "### 3 · 局部下沉" in out
    assert stats.cells == 20


def test_projection_prints_zero_sections(tmp_path: Path) -> None:
    """`就緒.md` 不存在時三節照印、20 格照數，並明說作者判斷讀不到。

    一支「找不到源檔就安靜」的投影，會讓「還沒建檔」與「一切正常」長得一樣。
    """
    out, stats = _text(_book(tmp_path, readiness=None))
    assert "### 3 · 局部下沉" in out
    assert "0 個 arc" in out
    assert stats.cells == 20 and stats.source_exists is False
    assert "`就緒.md` 不存在" in out


def test_projection_separates_unwired_from_no_source(tmp_path: Path) -> None:
    """**「未接」與「無機械來源」是兩件事**（D3 2026-07-28 補的推論）。

    未接 ＝ 有來源、只是這一輪不跨套件接（4 格）；無機械來源 ＝ 這一格根本沒有
    任何產物在記它，它是真正的源。混在一起就是新的假陰性。
    """
    out, stats = _text(_book(tmp_path))
    assert stats.unwired == 4 and stats.no_source > 0
    assert "**未接** outline-lint" in out
    assert "（無機械來源）" in out
    assert "decision-project" in out  # ⚠️N 筆待裁決那一行也要印


def test_projection_prints_partial_coverage_honestly(tmp_path: Path) -> None:
    """#1／#5 只有部分覆蓋，**不得印成通過**（E2 最後一格）。"""
    out, stats = _text(_book(tmp_path))
    assert "**部分**（驗欄非空，**不驗「一句話」**）" in out
    assert "**不驗矛盾消掉沒有**" in out
    assert (stats.full, stats.partial, stats.item_unwired) == (2, 2, 2)


def test_projection_reports_mismatch(tmp_path: Path) -> None:
    """作者判斷＝就緒，而該格的機械前哨報問題 → 印一行。

    實測舊儀表寫「設定層·世界觀＝就緒」而同一天 `world-lint` 報 5 筆——**證據就在
    隔壁的輸出裡，而沒有任何東西把兩邊接起來**。
    """
    book = _book(tmp_path, CLEAN.replace("| 設定層·世界觀 | 空白 |", "| 設定層·世界觀 | 就緒 |"))
    # `<主題>.md` 有源而沒有 `<主題>.ai.md` → world-lint 會報。
    topics = book / "story" / "設定" / "世界觀"
    topics.mkdir(parents=True)
    (topics / "修煉體系.md").write_text("# 修煉體系\n", encoding="utf-8")
    (topics / "修煉體系.ai.md").write_text(
        "---\ngenerated-from: x\ngenerated-at: 2026-07-28\n主題: 別的名字\n---\n",
        encoding="utf-8",
    )
    out, stats = _text(book)
    assert stats.mismatches >= 1
    assert "**不一致**：作者判斷＝就緒" in out


def test_projection_counts_chapters_per_arc(tmp_path: Path) -> None:
    """局部下沉 100% 可重算——手抄那一節的下場是它與 `outline-lint` 直接矛盾。"""
    book = _book(tmp_path)
    (book / "story" / "大綱").mkdir(parents=True)
    (book / "story" / "大綱" / "arc01.md").write_text("# arc01\n", encoding="utf-8")
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "幕綱" / "arc01.md").write_text(
        "# arc01\nbeat-test: 2026-07-28·0高3中3低\n\n## 幕001 · x\n", encoding="utf-8"
    )
    ch = book / "chapters"
    ch.mkdir()
    for i in (1, 2):
        (ch / f"ch000{i}.ai.md").write_text(
            f"---\ngenerated-from: x\ngenerated-at: 2026-07-28\n所屬arc: arc01\n---\n# ch000{i}\n",
            encoding="utf-8",
        )
    out, stats = _text(book)
    assert "| arc01 | ✓ | ✓ | 2 章 | 2026-07-28·0高3中3低 |" in out
    assert stats.arcs == 1


def test_projection_marks_merged_outline(tmp_path: Path) -> None:
    """退役源住 `_已併入/`（A5），投影印「已併入」而不是「—」。"""
    book = _book(tmp_path)
    merged = book / "story" / "大綱" / "_已併入"
    merged.mkdir(parents=True)
    (merged / "arc01.md").write_text("# arc01\n", encoding="utf-8")
    out, _ = _text(book)
    assert "| arc01 | 已併入 |" in out
