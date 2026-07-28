"""回歸黃金檔：`decision-lint --book 一世之尊`。

**這一份釘住的是一個 0**：一世之尊**沒有 `story/參照/裁決流.md`**（那本書早於裁決軸），
所以覆蓋率行印「裁決流（**無**）0 列／待裁決（無）0 列」。

那個 0 是本輪最該有黃金檔的一格，理由與別支相反——**別支的黃金檔在防「問題數不變而
解析器少抽一半」，這一份在防「一支從來沒有語料的 lint 悄悄爛掉而沒有人知道」**：
它在真實語料上跑出來的東西幾乎是空的，於是任何回歸都只會表現成「輸出還是空的」。
把空的那一份逐字釘住，是唯一能分辨「掃出來是空的」與「根本沒掃」的辦法（E2）。

要重生（只有在**刻意**改了門檻或訊息時才做，且要在 commit 訊息裡說清楚為什麼）：

    uv run --project tools/decision_projection pytest \\
        tools/decision_projection/tests/test_golden_decision_lint.py --regenerate-golden
"""

from pathlib import Path

import pytest
from decision_projection.lint import lint_report

REPO = Path(__file__).resolve().parents[3]
BOOK = REPO / "一世之尊"
GOLDEN = Path(__file__).parent / "golden" / "一世之尊-decision-lint.txt"


def _render() -> str:
    problems, stats = lint_report(BOOK)
    lines = [stats.render()]
    lines += [f"（資訊）{n}" for n in getattr(stats, "notes", [])]
    lines.append(f"發現 {len(problems)} 個問題：")
    lines += [f"  [x] {p}" for p in problems]
    return "\n".join(lines) + "\n"


def test_the_case_book_exists():
    """**找不到書就 fail，不 skip。**"""
    assert BOOK.is_dir(), f"病例書不在 {BOOK}——它是這支測試的全部語料"


def test_decision_lint_output_matches_golden(request):
    got = _render()
    if request.config.getoption("--regenerate-golden"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(got, encoding="utf-8")
        pytest.skip("已重生黃金檔")
    assert GOLDEN.is_file(), f"黃金檔不在 {GOLDEN}——用 --regenerate-golden 生一份"
    assert got == GOLDEN.read_text(encoding="utf-8")


def test_the_zero_is_a_scanned_zero_not_an_unscanned_one():
    """**「掃出來是 0」與「根本沒掃」不能長得一樣。**

    這正是 `decision-project` 曾經的死法：它對空表與無命中印的東西**逐字相同**。
    """
    _, stats = lint_report(BOOK)
    line = stats.render()
    assert "裁決流" in line and "待裁決" in line
    assert "0 列" in line
