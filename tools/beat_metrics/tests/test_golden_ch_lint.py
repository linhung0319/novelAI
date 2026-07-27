"""回歸黃金檔：`ch-lint --book 一世之尊` 的完整輸出。

**為什麼要釘死一本書的產出。** 一世之尊是刻意保留的病例書（不遷移新格式）。
2026-07-27 之前，`<!-- 幕NNN -->` 是全 repo 唯一「有機讀標記、零解析器」的地方：
`章節.schema.md` 對它下了五條格式承諾，而唯一碰到它的程式（`prose_metrics`）作用是
**把它剝掉當雜訊**。

閘門上線後它報 3 個問題，**全部是格式收斂類**（`對應幕` 單幕寫法 52 支／備註欄的
伏筆標記 16 列／備註欄超長 52 列）——那三條是抉擇 5 B 與 §3.4 對「新書」立的規矩，
病例書不遷移所以它們會一直紅著。**任何偏離都視為工具改壞了**，不是「順手把病例書
修乾淨」。

同時釘死那條**乾淨的**基準：8 項結構檢查全清（108 個錨點 0 個對不到 registry、
0 非單調、0 跨章、0 人性寫法、93 章對應幕 0 不一致、94 列章序 0 不一致）。那是人手
維持出來的，本輪把它變成系統保證的——所以它也要有回歸，否則哪天解析器悄悄少抽一半，
問題數仍然是 3。

要重生黃金檔（只有在**刻意**改了門檻或訊息時才做，且要在 commit 訊息裡說清楚為什麼）：

    uv run --project tools/beat_metrics python -m pytest \\
        tools/beat_metrics/tests/test_golden_ch_lint.py --regenerate-golden
"""

from pathlib import Path

import pytest
from beat_metrics.chapters import lint_report

# tests → beat_metrics → tools → repo 根
REPO = Path(__file__).resolve().parents[3]
BOOK = REPO / "一世之尊"
GOLDEN = Path(__file__).parent / "golden" / "一世之尊-ch-lint.txt"


def _render(problems: list[str], stats) -> str:
    lines = [stats.render()]
    lines += [f"（資訊）{n}" for n in stats.notes]
    lines += [f"（提示）{h}" for h in stats.hints]
    lines.append(f"發現 {len(problems)} 個問題：")
    lines += [f"  [x] {p}" for p in problems]
    return "\n".join(lines) + "\n"


def test_the_case_book_exists():
    """**找不到書就 fail，不 skip。** 會自己 skip 掉的測試，就是它跑了、它報平安、
    而它什麼都沒檢查（`設計原則.md` E2 第五格）。"""
    assert BOOK.is_dir(), f"病例書不在 {BOOK}——它是這支測試的全部語料"


def test_ch_lint_output_matches_golden(request):
    problems, stats = lint_report(BOOK)
    actual = _render(problems, stats)

    if request.config.getoption("--regenerate-golden", default=False):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(actual, encoding="utf-8")
        pytest.skip(f"已重生黃金檔 {GOLDEN}")

    assert GOLDEN.is_file(), f"黃金檔不在 {GOLDEN}（用 --regenerate-golden 產生）"
    expected = GOLDEN.read_text(encoding="utf-8")
    assert actual == expected, (
        "一世之尊的 ch-lint 輸出變了。它是刻意不遷移的病例書，所以：\n"
        "  - 如果你是在改工具 → 你改壞了（或改對了但沒更新黃金檔，請說明為什麼）\n"
        "  - 如果你是在「順手把它修乾淨」→ 別修，那些紅字就是它的價值"
    )


def test_the_case_book_is_red_only_where_we_expect():
    """病例書紅的是**格式收斂**那三條，不是結構那八項。

    這條測試的價值在**反面**：如果哪天結構那八項也開始報，代表有人動了正文層
    （或工具的解析壞了）——那不是「病例書本來就髒」可以解釋的。
    """
    problems, _ = lint_report(BOOK)
    assert len(problems) == 3, f"預期 3 個問題，得到 {len(problems)}"
    assert sum("把單幕寫成" in p for p in problems) == 1
    assert sum("含 `埋|收[[伏筆:x]]` 標記" in p for p in problems) == 1
    assert sum("備註欄超過 100 字" in p for p in problems) == 1


def test_the_clean_baseline_is_also_pinned():
    """**乾淨的那半也要有回歸。**

    108 個錨點 0 懸空、0 非單調、0 跨章、93 章對應幕 0 不一致——這幾個 0 正是這本書
    作為基準的價值。若哪天解析器悄悄少抽一半，問題數仍然是 3，只有覆蓋率行會變。
    """
    problems, stats = lint_report(BOOK)
    assert (stats.sources, stats.metas, stats.index_rows) == (93, 93, 94)
    assert (stats.anchors, stats.transitions, stats.registry) == (108, 17, 108)
    assert (stats.beats_checked, stats.beats_mismatch) == (93, 0)
    assert (stats.rows_checked, stats.rows_mismatch) == (93, 0)
    assert (stats.unknown_beats, stats.normalize_candidates) == (0, 0)
    for needle in (
        "指向不存在的幕",
        "單調遞增",
        "一幕不可跨章切開",
        "是人性寫法",
        "正文找不到",
    ):
        assert not [p for p in problems if needle in p], needle


def test_coverage_line_says_how_many_it_looked_at():
    """守衛要能回答「我在這本書上檢查了幾筆」，不能只回答「我發現幾個問題」。

    這支工具最需要這一行的是 `108 個幕錨點`：在它之前那 108 個錨點被 **0 支工具**
    讀過，而 schema 對它們下了五條承諾。印 0 就代表解析器又沒在解析了。
    """
    _, stats = lint_report(BOOK)
    line = stats.render()
    assert "93 章正文源／108 個幕錨點／17 個過渡錨點／93 支章衍生／94 列章序" in line
    assert "比對了 93 章的對應幕（0 章不一致）" in line
    assert "125 個錨點幕號（0 個對不到 registry）" in line
    assert "非標準錨點寫法 0 筆" in line
