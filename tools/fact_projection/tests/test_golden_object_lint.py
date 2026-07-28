"""回歸黃金檔：`object-lint --book 一世之尊`。

`object-lint` 跑的是 `fact-lint` 的**同一組檢查**（同一份真相，不是第二套），只是把
輸出收斂到物件檔那幾類。所以它與 `fact-lint` 的黃金檔一起才完整——**收斂本身是一個
會壞的東西**：`_is_object_problem` 曾用 `in` 比對，把純化違規的**修法提示**裡那句
「排除線屬 story/物件/<實體>.md」全撈進來（實測該印 0 個、印了 154 個）。

一世之尊沒有任何物件檔，所以它現在印的是 0 個問題 ＋ 一行「這本書還沒有任何物件檔」。
**那個 0 正是要釘住的東西**：它哪天變成非 0，要嘛是有人建了物件檔（好事，更新黃金檔），
要嘛是收斂又壞了（`fact-lint` 那 206 筆漏進來）。

要重生（只有在**刻意**改了門檻或訊息時才做，且要在 commit 訊息裡說清楚為什麼）：

    uv run --project tools/fact_projection pytest \\
        tools/fact_projection/tests/test_golden_object_lint.py --regenerate-golden
"""

from pathlib import Path

import pytest
from fact_projection.cli import _is_object_problem
from fact_projection.sources import lint_report

REPO = Path(__file__).resolve().parents[3]
BOOK = REPO / "一世之尊"
GOLDEN = Path(__file__).parent / "golden" / "一世之尊-object-lint.txt"


def _render() -> str:
    problems, stats = lint_report(BOOK)
    picked = [p for p in problems if _is_object_problem(p)]
    lines = [stats.render()]
    lines += [f"（資訊）{n}" for n in stats.notes]
    lines += [f"（提示）{h}" for h in stats.hints]
    lines.append(f"發現 {len(picked)} 個問題：")
    lines += [f"  [x] {p}" for p in picked]
    return "\n".join(lines) + "\n"


def test_the_case_book_exists():
    """**找不到書就 fail，不 skip。**"""
    assert BOOK.is_dir(), f"病例書不在 {BOOK}——它是這支測試的全部語料"


def test_object_lint_output_matches_golden(request):
    got = _render()
    if request.config.getoption("--regenerate-golden"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(got, encoding="utf-8")
        pytest.skip("已重生黃金檔")
    assert GOLDEN.is_file(), f"黃金檔不在 {GOLDEN}——用 --regenerate-golden 生一份"
    assert got == GOLDEN.read_text(encoding="utf-8")


def test_the_convergence_still_holds():
    """**收斂是會壞的東西。** `fact-lint` 在這本書上報 206 筆，而 `object-lint`
    該印 0 筆——用 `in` 比對會讓那 206 筆的修法提示把它們全撈回來。"""
    problems, _ = lint_report(BOOK)
    assert len(problems) == 206
    assert [p for p in problems if _is_object_problem(p)] == []
