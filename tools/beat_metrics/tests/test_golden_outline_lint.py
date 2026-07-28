"""回歸黃金檔：`outline-lint --book 一世之尊` 的完整輸出。

**為什麼要釘死一本書的產出。** 一世之尊是刻意保留的病例書（不遷移新格式）。
在這支閘門上線之前，大綱是全系統唯一一個「被 `共同約定.md` 明文列進『強格式源·
一支 lint』那一格、而那支 lint 不存在」的產物——**0 支工具解析它**，而 4 支 SKILL.md
逐節取值、`大綱.schema.md` 的 7 條檢查點 0 條有實作。

閘門上線後它報 16 個問題，**全部是病例書自己的病**（6 支檔的四欄伏筆狀態表＋既成事實
token、2 支檔的枚舉外節、1 個 registry 查無的伏筆名、索引列序逆序）——那些數字正是
本輪要的：在此之前這一軸的 302,669 B 對整個工具鏈是不存在的。**任何偏離都視為工具
改壞了**，不是「順手把病例書修乾淨」。

同時釘死那條**乾淨的**基準：164 筆幕引用與 106 筆章引用**懸空 0**、83 個檔內路徑
引用 0 個不存在、索引 11 列 ≡ 資料夾 11 支。那是人手維持出來的，本輪把它變成系統
保證的——所以它也要有回歸，否則哪天解析器悄悄少抽一半，問題數仍然是 16。

**最該盯的一行是「連續敘述佔全檔 27.8%（最低 10.9%）」**：那是「這一軸還在不在做
它該做的事」的單一數字，而它在 11 個 arc、5 天裡沒有被任何東西看見過。

要重生黃金檔（只有在**刻意**改了門檻或訊息時才做，且要在 commit 訊息裡說清楚為什麼）：

    uv run --project tools/beat_metrics python -m pytest \\
        tools/beat_metrics/tests/test_golden_outline_lint.py --regenerate-golden
"""

from pathlib import Path

import pytest
from beat_metrics.outline import lint_report

# tests → beat_metrics → tools → repo 根
REPO = Path(__file__).resolve().parents[3]
BOOK = REPO / "一世之尊"
GOLDEN = Path(__file__).parent / "golden" / "一世之尊-outline-lint.txt"


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


def test_outline_lint_output_matches_golden(request):
    problems, stats = lint_report(BOOK)
    got = _render(problems, stats)
    if request.config.getoption("--regenerate-golden"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(got, encoding="utf-8")
        pytest.skip("已重生黃金檔")
    assert GOLDEN.is_file(), f"黃金檔不在 {GOLDEN}——用 --regenerate-golden 生一份"
    assert got == GOLDEN.read_text(encoding="utf-8")


def test_the_clean_half_is_really_clean():
    """把**乾淨的那一半**單獨釘死：它們是這支工具最容易悄悄失效的地方。

    `beat_refs` 若哪天印 0，那不是乾淨，是它沒讀到檔（同 `ch-lint` 的「幾個幕錨點」）。
    """
    _, stats = lint_report(BOOK)
    assert (stats.beat_refs, stats.beat_dangling) == (164, 0)
    assert (stats.ch_refs, stats.ch_dangling) == (106, 0)
    assert (stats.index_rows, stats.index_mismatch) == (11, 0)
    assert (stats.path_refs, stats.path_missing) == (83, 0)
