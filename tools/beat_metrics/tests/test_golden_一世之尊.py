"""回歸黃金檔：`beat-lint --book 一世之尊` 的完整輸出。

**為什麼要釘死一本書的壞產出。** 一世之尊是刻意保留的病例書（不遷移新格式）。
2026-07-27 之前，幕綱是全系統唯一「被四支工具逐行解析、卻零檢查器」的強格式產物：
`幕綱.schema.md` 宣稱了幕號唯一、固定八項、`[[幕NNN]]` 指向前因、分區是硬規定，
**一條都沒人守**。`beat-test/SKILL.md` 甚至明文說懸空前因「是最高優先級的機械事實，
不需 LLM 判斷」——而 repo 裡沒有任何一支工具解析過 `[[幕NNN]]`。

閘門上線後它報 15 個問題（承諾區 10 ＋ 近似伏筆名 4 ＋ 設計註目的地 1）。
**任何偏離都視為工具改壞了**，而不是「順手把病例書修乾淨」。

同時釘死的還有那條**乾淨的**基準：157 條前因 0 懸空、108 幕 0 重複。那是人手維持
出來的，本輪把它變成系統保證的——所以它也要有回歸，否則哪天解析器悄悄少抽一半，
問題數仍然是 15。

要重生黃金檔（只有在**刻意**改了門檻或訊息時才做，且要在 commit 訊息裡說清楚為什麼）：

    uv run --project tools/beat_metrics python -m pytest \\
        tools/beat_metrics/tests/test_golden_一世之尊.py --regenerate-golden
"""

from pathlib import Path

import pytest
from beat_metrics.lint import lint_report

# tests → beat_metrics → tools → repo 根
REPO = Path(__file__).resolve().parents[3]
BOOK = REPO / "一世之尊"
GOLDEN = Path(__file__).parent / "golden" / "一世之尊-beat-lint.txt"


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


def test_beat_lint_output_matches_golden(request):
    problems, stats = lint_report(BOOK)
    actual = _render(problems, stats)

    if request.config.getoption("--regenerate-golden", default=False):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(actual, encoding="utf-8")
        pytest.skip(f"已重生黃金檔 {GOLDEN}")

    assert GOLDEN.is_file(), f"黃金檔不在 {GOLDEN}（用 --regenerate-golden 產生）"
    expected = GOLDEN.read_text(encoding="utf-8")
    assert actual == expected, (
        "一世之尊的 beat-lint 輸出變了。它是刻意不遷移的病例書，所以：\n"
        "  - 如果你是在改工具 → 你改壞了（或改對了但沒更新黃金檔，請說明為什麼）\n"
        "  - 如果你是在「順手把它修乾淨」→ 別修，那些紅字就是它的價值"
    )


def test_the_case_book_is_still_red():
    """病例書必須是紅的。它變乾淨＝有人遷移了它，或有人又把檢查關掉了。"""
    problems, _ = lint_report(BOOK)
    assert len(problems) == 15, f"預期 15 個問題，得到 {len(problems)}"
    assert sum("缺「## 本 arc 承諾」分區" in p for p in problems) == 10
    assert sum("疑似同一條伏筆的兩個名字" in p for p in problems) == 4
    assert sum("裁決流.md` 不存在" in p for p in problems) == 1


def test_the_clean_baseline_is_also_pinned():
    """**乾淨的那半也要有回歸。**

    157 條前因 0 懸空、108 幕 0 重複——這兩個 0 正是這本書作為基準的價值。若哪天
    解析器悄悄少抽一半，問題數仍然是 15，只有覆蓋率行會變。
    """
    problems, stats = lint_report(BOOK)
    assert (stats.arcs, stats.beats, stats.refs) == (11, 108, 157)
    assert (stats.marks, stats.mark_names) == (18, 15)
    assert stats.status_rows == 53
    assert not [p for p in problems if "指向不存在的幕" in p or "重複——幕號" in p]


def test_coverage_line_admits_what_the_machine_cannot_see():
    """守衛要能回答「我在這本書上檢查了幾筆」，不能只回答「我發現幾個問題」。

    這裡特別釘住兩個數字：`0 支物件檔`（C3 的另一半還沒接上）與「其中 N 列的
    伏筆名全書無標記」（抉擇 2 B 之後，G5 兩軌 diff 只覆蓋有標記的那半——那要說出來）。
    """
    _, stats = lint_report(BOOK)
    line = stats.render()
    assert "11 支 arc／108 幕／157 條前因" in line
    assert "53 列狀態表（其中 4 列的伏筆名全書無標記·不入機械 diff）" in line
    assert "1 個承諾區／14 條排除線／0 支物件檔" in line
    assert "跳過 0 支骨架" in line
