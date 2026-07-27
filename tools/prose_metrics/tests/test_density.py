"""章密度對照（抉擇 3 B）的正反例。

這一節與本套件其餘部分的合約**不同**，所以要有測試釘住那個不同：它印一個數字、
**不產生可疑點、不影響 exit code**。`章節.schema.md` 的「約 3000 字」是參考體例，
不是達標線——一條有門檻的章長檢查會在「高潮幕該厚、過場幕該薄」的書上狂報。
"""

from __future__ import annotations

from pathlib import Path

from prose_metrics.cli import main
from prose_metrics.density import WEB_NOVEL_CHARS, measure, read_stance, render
from prose_metrics.metrics import Metrics

STANCE = (
    "---\n"
    "generated-from: abc\n"
    "取向定位: { 整體: 網文爽感為底, 節奏速度: 偏快爽, 揭露速度: 長線, 連載鉤子: 強 }\n"
    "---\n"
)


def _rows(*chars: int) -> list[Metrics]:
    return [
        Metrics(label=f"ch{i:04d}", group="arc01", chars=c, quotes=0, paragraphs=1, cast=1)
        for i, c in enumerate(chars, start=1)
    ]


def _book(tmp_path: Path, summary: str | None = STANCE) -> Path:
    (tmp_path / "story").mkdir(parents=True)
    if summary is not None:
        (tmp_path / "story" / "00-摘要.ai.md").write_text(summary, encoding="utf-8")
    return tmp_path


def test_declared_stance_is_quoted_verbatim(tmp_path):
    """**刻意不判「這本書偏不偏網文」**——照抄宣告，讓作者自己對。

    判它就要拿詞表分類中文形容詞，那正是「幫基調加機讀欄」被駁回的形狀。
    """
    d = measure(_rows(3500, 2000, 1000), _book(tmp_path))
    assert d.declared and d.stance["節奏速度"] == "偏快爽"
    text = "\n".join(render(d))
    assert "取向定位.節奏速度：偏快爽" in text
    assert f"1/3 章 ≥{WEB_NOVEL_CHARS} 字" in text


def test_undeclared_stance_still_prints_the_number(tmp_path):
    """0 也要印（E2）。靜默跳過的對照節，與「這本書沒問題」在輸出上分不出來。"""
    d = measure(_rows(3500, 900), _book(tmp_path, summary=None))
    assert not d.declared
    text = "\n".join(render(d))
    assert "未宣告取向定位" in text
    assert "1/2 章" in text


def test_stance_present_but_unparsable_subkeys(tmp_path):
    d = measure(_rows(1000), _book(tmp_path, summary="---\n取向定位: { 隨便: x }\n---\n"))
    assert d.declared and d.stance == {}
    assert "讀不出 節奏速度／整體 子欄" in "\n".join(render(d))


def test_no_chapters_says_so(tmp_path):
    d = measure([], _book(tmp_path))
    assert "0 章正文，無從計數。" in "\n".join(render(d))


def test_the_wording_is_pinned_as_a_number_not_a_verdict(tmp_path):
    """這句措辭是拍板的一部分，不是文案——它擋的是「作者把印出的比例當門檻」。"""
    text = "\n".join(render(measure(_rows(1000), _book(tmp_path))))
    assert "**這是一個數字，不是一個判定。**" in text
    assert "不設達標線" in text


def _mini_book(tmp_path: Path, chars: int) -> Path:
    book = _book(tmp_path)
    (book / "story" / "設定" / "角色").mkdir(parents=True)
    (book / "story" / "設定" / "角色" / "少年.md").write_text("人", encoding="utf-8")
    d = book / "chapters"
    d.mkdir()
    for i in (1, 2, 3):
        (d / f"ch{i:04d}.md").write_text(
            f"# ch{i:04d}\n\n<!-- 幕{i:03d} -->\n少年" + "字" * chars + "\n",
            encoding="utf-8",
        )
        (d / f"ch{i:04d}.ai.md").write_text(
            f"---\n所屬arc: arc01\n對應幕: [幕{i:03d}]\n---\n", encoding="utf-8"
        )
    return book


def test_short_chapters_do_not_change_exit_code(tmp_path, capsys):
    """**不進 findings、不影響 exit code。** 分段數不足 3 段時本來就不談漂移，
    所以這裡的 exit 0 只可能來自章密度——確認它沒有偷偷變成門檻。"""
    book = _mini_book(tmp_path, chars=100)
    code = main(["--book", str(book)])
    out = capsys.readouterr().out
    assert "0/3 章 ≥3000 字" in out
    assert code == 0


def test_density_section_is_absent_for_plain_corpus(tmp_path, capsys):
    """對照語料沒有 `00-摘要.ai.md`，也沒有「這本書宣告了什麼」可對。"""
    d = tmp_path / "語料" / "卷一"
    d.mkdir(parents=True)
    (d / "001.txt").write_text("字" * 500, encoding="utf-8")
    main(["--plain-dir", str(tmp_path / "語料")])
    assert "### 章密度" not in capsys.readouterr().out
