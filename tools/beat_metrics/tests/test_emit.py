"""三支 `--emit` 投影的正反例（功能 12 抉擇 4 C）。

**投影是投影不是閘門**：一律 exit 0、不印 problems。這裡驗的是三件事——
① 印出來的那一份是對的（＝ lint 為了比對而算出來的那一份）；
② 覆蓋率行說得出「印了幾列、其中幾列是空的」（E2 ＋ 06 補的推論）；
③ 殘留偵測 **0 也印**（舊檔不在時印「不在」那一行，才代表這本書遷完了）。
"""

from __future__ import annotations

from pathlib import Path

from beat_metrics.emit import emit_beats, emit_chapters, emit_outline, h1
from conftest import plant_package_root
from test_lint import ARC01, ARC02, INDEX, SPINE, _book


# ------------------------------------------------------------------ H1 取值

def test_h1_strips_the_id_prefix(tmp_path: Path):
    """ID 已經是自己那一欄，H1 裡再印一次是雜訊。"""
    p = tmp_path / "arc09.md"
    p.write_text("# arc09 · 他留著那個名字（卷三第一段）\n\n內文\n", encoding="utf-8")
    assert h1(p) == "他留著那個名字（卷三第一段）"


def test_h1_missing_is_empty_not_a_crash(tmp_path: Path):
    """取不到就回空字串——**空要被算進覆蓋率**，不是靜默略過。"""
    p = tmp_path / "arc09.md"
    p.write_text("沒有標題的檔\n", encoding="utf-8")
    assert h1(p) == ""
    assert h1(tmp_path / "不存在.md") == ""


# ------------------------------------------------------------------ 幕綱索引

def test_emit_beats_projects_the_view(tmp_path: Path):
    report, stats = emit_beats(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert "| arc01 | 幕001–幕002 | 001–100 | 起 |" in report
    assert "| arc02 | 幕101–幕101 | 101–200 | 承 |" in report
    assert (stats.rows, stats.blank_titles) == (2, 0)


def test_emit_beats_does_not_restate_the_stage(tmp_path: Path):
    """`結構階段` 刻意不進來——`structure-project` 第二節已經在印階段 ↔ 幕，
    複述就是同一個病的第 12 次（09 立的「不複述、只指路」判準）。"""
    report, _ = emit_beats(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert "structure-project" in report
    assert "| 結構階段 |" not in report


def test_emit_beats_says_where_the_spine_lives(tmp_path: Path):
    """spine 不在投影裡——它是源，住 `_順序.md`（抉擇 2 A）。"""
    report, _ = emit_beats(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert "`story/幕綱/_順序.md`" in report
    assert "全書順序：arc01" not in report


def test_blank_h1_is_counted_not_hidden(tmp_path: Path):
    """「命中 N 列」與「N 列裡有 M 列是空的」是**兩個數字**（E2，06 補的推論）。"""
    naked = ARC02.replace("# arc02 · 承\n", "")
    report, stats = emit_beats(_book(tmp_path, arc01=ARC01, arc02=naked))
    assert stats.blank_titles == 1
    assert "（源檔無 H1）" in report
    assert "**其中 1 列取不到源檔 H1**" in stats.render()


# ------------------------------------------------------------------ 殘留偵測

def test_legacy_absent_still_prints_a_line(tmp_path: Path):
    """**0 也印。** 只在檔還在時才印，就是把「已遷移」與「工具沒讀到」變成同一個綠燈。"""
    report, stats = emit_beats(_book(tmp_path, index=None, arc01=ARC01, arc02=ARC02))
    assert stats.legacy == []
    assert "舊檔：**不在**" in report


def test_legacy_present_prints_size_and_provenance(tmp_path: Path):
    """舊檔還在時要逐格印「這一格的機械來源是哪一支檔的哪一欄」（D3／A5 的驗收）。"""
    report, stats = emit_beats(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert len(stats.legacy) == 1 and stats.legacy[0][0] == "story/幕綱/_index.md"
    assert "舊檔：**在**" in report
    # 答不出來的那幾格要印出來，印出來才看得見它是源
    assert "**無獨立來源**" in report and "**無機械來源＝它是源**" in report


# ------------------------------------------------------------------ 大綱索引

OUTLINE_SCOPED = (
    "# arc02 · 走出去\n\n"
    "> ⚠️ 暫定，待粗層鎖定\n\n"
    "## 選用結構公式\n\n- 起承轉合\n\n"
    "## 本段全文\n\n內文。\n"
)


def _outline_book(tmp_path: Path) -> Path:
    plant_package_root(tmp_path)
    book = tmp_path / "book"
    (book / "story" / "大綱").mkdir(parents=True)
    (book / "story" / "01-大綱.md").write_text(
        "# 大綱\n\n## 選用結構公式\n\n- 起承轉合\n", encoding="utf-8"
    )
    (book / "story" / "大綱" / "arc02.md").write_text(OUTLINE_SCOPED, encoding="utf-8")
    (book / "story" / "大綱" / "_index.md").write_text(
        "# 大綱索引\n\n- arc02：走出去 —— 狀態：暫定\n", encoding="utf-8"
    )
    return book


def test_emit_outline_projects_name_and_status(tmp_path: Path):
    """schema 規定的一列形狀（`arcNN：名稱 —— 狀態`）**100% 可投影**。"""
    report, stats = emit_outline(_outline_book(tmp_path))
    assert "| arc02 | 走出去 | 暫定 | `大綱/` |" in report
    assert (stats.rows, stats.blank_titles) == (1, 0)
    assert stats.legacy and stats.legacy[0][0] == "story/大綱/_index.md"


def test_emit_outline_excludes_the_full_outline(tmp_path: Path):
    """`01-大綱.md` 是全書版，不是 scoped——它不進這張表。"""
    report, _ = emit_outline(_outline_book(tmp_path))
    assert "01-大綱.md` 是全書版" in report
    assert "| 01-大綱" not in report


# ------------------------------------------------------------------ 章序

def _ch_book(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    d = book / "chapters"
    d.mkdir(parents=True)
    (d / "ch0001.md").write_text(
        "# ch0001 · 一覺穿成小和尚\n\n<!-- 幕001 -->\n正文。\n", encoding="utf-8"
    )
    (d / "ch0001.ai.md").write_text(
        "---\n對應幕: 幕001\n所屬arc: arc01\nPOV: {人稱: 第一人稱, 角色: 孟奇, 時態: 過去}\n"
        "風格: 風格.ai.md\n狀態: 草稿\n---\n## 本章事實\n",
        encoding="utf-8",
    )
    return book


def test_emit_chapters_projects_six_columns_plus_title(tmp_path: Path):
    """`ch-lint` 第 8 項為了比對，早就必須先算出這六欄——投影只是把它印出來。"""
    report, stats = emit_chapters(_ch_book(tmp_path))
    assert "| ch0001 | 幕001 | arc01 | 孟奇 | 風格.ai.md | 草稿 | 一覺穿成小和尚 |" in report
    assert (stats.rows, stats.blank_titles) == (1, 0)


def test_emit_chapters_legacy_absent_prints_the_line(tmp_path: Path):
    report, stats = emit_chapters(_ch_book(tmp_path))
    assert stats.legacy == []
    assert "舊檔：**不在**" in report


def test_emit_chapters_on_an_empty_book_prints_zero(tmp_path: Path):
    """**0 也印**：一張空表比「什麼都不印」有用得多。"""
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    report, stats = emit_chapters(book)
    assert stats.rows == 0
    assert "| （0 章） |" in report
    assert "投影 0 章" in stats.render("章")
