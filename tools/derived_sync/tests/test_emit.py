"""兩支設定層 `--emit` 投影的正反例（功能 12 抉擇 4 C）。

`char-lint` 第 5 項／`world-lint` 第 4·5 項為了比對「視圖 ≡ 資料夾」，早就必須先算
出正確的那一份——這裡驗的是「把比對改成輸出」之後印得對不對，以及三件紀律：
覆蓋率 0 也印／空的那幾列要被算出來／殘留偵測不在時也印一行。
"""

from __future__ import annotations

from pathlib import Path

from derived_sync.emit import emit_characters, emit_world, entity_lede, lede

CHAR_AI = (
    "---\ngenerated-from: x\ngenerated-at: 2026-07-28\n"
    "定位: 主角\n所屬arc: [arc01, arc03]\n暫定: false\n---\n"
    "## 需求四象限\n- 期盼：…\n## 預期弧線\n盲目 → 挫折\n"
    "## 馬斯洛層次\n安全\n## 對衝關係\n與反派對撞\n"
)


def _book(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    (book / "story" / "設定" / "角色").mkdir(parents=True)
    (book / "story" / "設定" / "世界觀").mkdir(parents=True)
    return book


def _char(book: Path, name: str, source: str) -> None:
    d = book / "story" / "設定" / "角色"
    (d / f"{name}.md").write_text(source, encoding="utf-8")
    (d / f"{name}.ai.md").write_text(CHAR_AI, encoding="utf-8")


# ------------------------------------------------------------------ lede 取值

def test_lede_takes_the_first_line_after_the_h1(tmp_path: Path):
    """**不印 H1**：實測角色 24/24、世界觀 4/4 的 H1 就是檔名（`# 修煉體系`），
    印它等於把 ID 欄抄第二遍。第一段才是舊 `一行需求` 要裝的那句話。"""
    p = tmp_path / "凱.md"
    p.write_text("# 凱\n\n- 還清債、贖回鐵砧的鐵匠。\n\n## 來歷\n…\n", encoding="utf-8")
    assert lede(p) == "還清債、贖回鐵砧的鐵匠。"


def test_lede_missing_is_empty(tmp_path: Path):
    p = tmp_path / "空.md"
    p.write_text("# 空\n", encoding="utf-8")
    assert lede(p) == ""
    assert lede(tmp_path / "不存在.md") == ""


def test_lede_reads_the_directory_form(tmp_path: Path):
    """目錄形態要一起吃——升級成目錄不該讓這一欄靜默變空（同 06 的空殼檔教訓）。"""
    d = tmp_path / "角色"
    (d / "凱").mkdir(parents=True)
    (d / "凱" / "核心.md").write_text("# 凱\n\n鐵匠。\n", encoding="utf-8")
    assert entity_lede(d, "凱") == "鐵匠。"


# ------------------------------------------------------------------ 角色清單

def test_emit_characters_projects_the_view(tmp_path: Path):
    book = _book(tmp_path)
    _char(book, "凱", "# 凱\n\n還清債、贖回鐵砧的鐵匠。\n")
    report, stats = emit_characters(book)
    assert "| 凱 | 主角 | [arc01, arc03] | false | 還清債、贖回鐵砧的鐵匠。 |" in report
    assert (stats.rows, stats.blank_ledes) == (1, 0)


def test_emit_characters_counts_blank_ledes(tmp_path: Path):
    """「命中 N 列」與「N 列裡有 M 列是空的」是兩個數字（E2，06 補的推論）。"""
    book = _book(tmp_path)
    _char(book, "凱", "# 凱\n")
    _, stats = emit_characters(book)
    assert stats.blank_ledes == 1
    assert "**其中 1 列的源檔第一段是空的**" in stats.render()


def test_emit_characters_zero_is_still_printed(tmp_path: Path):
    report, stats = emit_characters(_book(tmp_path))
    assert stats.rows == 0
    assert "| （0 個角色） |" in report


def test_emit_characters_legacy_detection(tmp_path: Path):
    book = _book(tmp_path)
    _char(book, "凱", "# 凱\n\n鐵匠。\n")
    report, stats = emit_characters(book)
    assert stats.legacy == [] and "舊檔：**不在**" in report

    (book / "story" / "設定" / "角色" / "_index.ai.md").write_text(
        "# 角色清單\n" + "舊" * 100, encoding="utf-8"
    )
    report, stats = emit_characters(book)
    assert len(stats.legacy) == 1
    assert "舊檔：**在**" in report
    # 那筆作者裁決要被指名（8,145 字元＝該檔 52.7%，2026-07-23 拍板）
    assert "**無機械來源＝它是源**" in report and "裁決流.md" in report


# ------------------------------------------------------------------ 世界觀

def test_emit_world_projects_topics(tmp_path: Path):
    book = _book(tmp_path)
    d = book / "story" / "設定" / "世界觀"
    (d / "修煉體系.md").write_text("# 修煉體系\n\n這個世界的武功是真的。\n", encoding="utf-8")
    report, stats = emit_world(book)
    assert "| 修煉體系 | `修煉體系.ai.md` | 這個世界的武功是真的。 |" in report
    assert (stats.rows, stats.blank_ledes) == (1, 0)


def test_emit_world_does_not_fake_the_dimension_table(tmp_path: Path):
    """舊 rollup 的維度 `內容`／`狀態` 兩欄**零機械來源**（schema 自己就寫了）。

    投影只回答「封閉枚舉是哪七個」，**不造一張每列都一樣的假表**——那正是這一輪
    要消滅的東西。它是 D3 第 ② 格（無機械來源、但刪掉重跑會回來），家在各
    `<主題>.ai.md`，不是投影也不是新開一支源檔。
    """
    report, _ = emit_world(_book(tmp_path))
    assert "### 背景七維（封閉枚舉）：時間／空間／活動／地點／組織／社會／自身" in report
    assert "| 時間 |" not in report
    assert "D3 第 ② 格" in report


def test_emit_world_zero_is_still_printed(tmp_path: Path):
    report, stats = emit_world(_book(tmp_path))
    assert stats.rows == 0
    assert "| （0 個主題） |" in report
    assert "投影 0 個主題" in stats.render("個主題")


# ------------------------------------------------- 源檔第一段的守衛（E1）
#
# 抉擇 3 B 宣稱了一個格式（「這個實體是什麼」＝源檔 H1 之後第一段），依 E1 就要
# 交出守它的檢查器——不然空的那幾支會**靜默印空白**，而挑實體的人拿到一份看起來
# 完整的清單（E2 最後一格）。


def test_char_lint_reports_blank_ledes(tmp_path: Path):
    from derived_sync.char_lint import lint_book

    book = _book(tmp_path)
    _char(book, "凱", "# 凱\n\n鐵匠。\n")
    _char(book, "空", "# 空\n")
    problems, stats = lint_book(book)
    assert stats.blank_ledes == 1
    hits = [p for p in problems if "沒有非空行" in p.detail]
    assert len(hits) == 1 and "空" in hits[0].detail
    assert "源檔第一段：**1/2 支是空的**" in stats.render()


def test_char_lint_lede_clean_book(tmp_path: Path):
    from derived_sync.char_lint import lint_book

    book = _book(tmp_path)
    _char(book, "凱", "# 凱\n\n鐵匠。\n")
    _, stats = lint_book(book)
    assert stats.blank_ledes == 0
    assert "源檔第一段：**0/1 支是空的**" in stats.render()


def test_world_lint_reports_blank_ledes(tmp_path: Path):
    from derived_sync.world_lint import lint_book

    book = _book(tmp_path)
    d = book / "story" / "設定" / "世界觀"
    (d / "修煉體系.md").write_text("# 修煉體系\n\n武功是真的。\n", encoding="utf-8")
    (d / "空主題.md").write_text("# 空主題\n", encoding="utf-8")
    problems, stats = lint_book(book)
    assert stats.blank_ledes == 1
    assert [p for p in problems if "沒有非空行" in p.detail]
    assert "源檔第一段：**1/2 支是空的**" in stats.render()
