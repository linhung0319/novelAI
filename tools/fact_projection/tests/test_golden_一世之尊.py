"""回歸黃金檔：`fact-lint --book 一世之尊` 的完整輸出。

**為什麼要釘死一本書的壞產出。** 一世之尊是刻意保留的病例書（不遷移新格式）。
2026-07-27 前 `fact-lint` 對它印「事實信封行格式乾淨」、exit 0，而同一份檔的成長哨兵
報 119 行肥大＋110 行括號超標——**閘門與哨兵對同一份資料給出 0 與 229 兩個答案**，
因為舊格式豁免是一個整本書的靜音開關。

拿掉那個開關之後它報 206 個問題（長度 52 ＋ 括號 110 ＋ 夾帶 44）。作者拍板把這 206
筆存成黃金檔（抉擇 5 A）：**任何偏離都是工具改壞了**，而不是「順手把病例書修乾淨」。

要重生黃金檔（只有在**刻意**改了門檻或訊息時才做，且要在 commit 訊息裡說清楚為什麼）：

    uv run --project tools/fact_projection python -m pytest \\
        tools/fact_projection/tests/test_golden_一世之尊.py --regenerate-golden
"""

from pathlib import Path

import pytest
from fact_projection.sources import lint_report

# tests → fact_projection → tools → repo 根
REPO = Path(__file__).resolve().parents[3]
BOOK = REPO / "一世之尊"
GOLDEN = Path(__file__).parent / "golden" / "一世之尊-fact-lint.txt"


def _render(problems: list[str], stats) -> str:
    lines = [stats.render()]
    lines += [f"（資訊）{n}" for n in stats.notes]
    lines += [f"（提示）{h}" for h in stats.hints]
    lines.append(f"發現 {len(problems)} 個問題：")
    lines += [f"  [x] {p}" for p in problems]
    return "\n".join(lines) + "\n"


def test_the_case_book_exists():
    """**找不到書就 fail，不 skip。**

    一個會自己 skip 掉的測試，就是本輪要修掉的那一類守衛：它跑了、它報平安、
    而它什麼都沒檢查（`設計原則.md` E2 第五格）。
    """
    assert BOOK.is_dir(), f"病例書不在 {BOOK}——它是這支測試的全部語料"


def test_fact_lint_output_matches_golden(request):
    problems, stats = lint_report(BOOK)
    actual = _render(problems, stats)

    if request.config.getoption("--regenerate-golden", default=False):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(actual, encoding="utf-8")
        pytest.skip(f"已重生黃金檔 {GOLDEN}")

    assert GOLDEN.is_file(), f"黃金檔不在 {GOLDEN}（用 --regenerate-golden 產生）"
    expected = GOLDEN.read_text(encoding="utf-8")
    assert actual == expected, (
        "一世之尊的 fact-lint 輸出變了。它是刻意不遷移的病例書，所以：\n"
        "  - 如果你是在改工具 → 你改壞了（或改對了但沒更新黃金檔，請說明為什麼）\n"
        "  - 如果你是在「順手把它修乾淨」→ 別修，那些紅字就是它的價值"
    )


def test_the_case_book_is_still_red():
    """病例書必須是紅的。它變乾淨＝有人遷移了它，或有人又把檢查關掉了。"""
    problems, stats = lint_report(BOOK)
    assert len(problems) == 206, f"預期 206 個問題，得到 {len(problems)}"
    assert stats.fact_lines_legacy == 259
    assert stats.fact_lines_new == 0  # 新格式覆蓋率 0——這正是它是病例書的原因


def test_coverage_line_admits_it_checked_no_new_format_lines():
    """守衛要能回答「我在這本書上檢查了幾筆」，不能只回答「我發現幾個問題」。"""
    _, stats = lint_report(BOOK)
    line = stats.render()
    assert "新格式 0" in line and "舊格式 259" in line
    assert "0 支物件檔" in line and "0 條約束" in line
