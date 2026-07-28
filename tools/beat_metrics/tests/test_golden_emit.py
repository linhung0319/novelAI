"""回歸黃金檔：`beat-lint`／`ch-lint`／`outline-lint` 的 **`--emit` 投影**。

**投影比閘門更需要黃金檔**（2026-07-28 功能 14，抉擇 5 C）。閘門壞了會少報問題，
而那還會被「問題數」這個數字反映；**投影壞了會少印幾列，而輸出看起來完全正常**
——它沒有「問題數」可以掉。

功能 12 廢除五支 rollup 時的依據是「四支既有 lint 為了比對『視圖 ≡ 資料夾』，早就
必須先算出正確的那一份」（抉擇 4 C：誰重算誰印，同一支程式，結構上不可能漂）。
**那個論證成立的前提是「算出來的那一份是對的」**，而在這三份黃金檔之前，沒有任何
東西驗過它。

要重生（只有在**刻意**改了門檻或訊息時才做，且要在 commit 訊息裡說清楚為什麼）：

    uv run --project tools/beat_metrics pytest \\
        tools/beat_metrics/tests/test_golden_emit.py --regenerate-golden
"""

from pathlib import Path

import pytest
from beat_metrics.emit import emit_beats, emit_chapters, emit_outline

REPO = Path(__file__).resolve().parents[3]
BOOK = REPO / "一世之尊"
GOLDEN_DIR = Path(__file__).parent / "golden"

EMITS = (
    ("beat-lint--emit", emit_beats),
    ("ch-lint--emit", emit_chapters),
    ("outline-lint--emit", emit_outline),
)


def test_the_case_book_exists():
    """**找不到書就 fail，不 skip。**"""
    assert BOOK.is_dir(), f"病例書不在 {BOOK}——它是這 3 份黃金檔的全部語料"


@pytest.mark.parametrize("name,fn", EMITS, ids=[n for n, _ in EMITS])
def test_emit_matches_golden(name, fn, request):
    report, _stats = fn(BOOK)
    golden = GOLDEN_DIR / f"一世之尊-{name}.txt"
    if request.config.getoption("--regenerate-golden"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(report, encoding="utf-8")
        pytest.skip(f"已重生黃金檔 {golden.name}")
    assert golden.is_file(), f"黃金檔不在 {golden}——用 --regenerate-golden 生一份"
    assert report == golden.read_text(encoding="utf-8"), (
        f"一世之尊的 {name} 投影變了。**投影沒有「問題數」可以掉**——"
        "少印幾列時輸出看起來完全正常，所以這裡逐字比對"
    )


@pytest.mark.parametrize("name,fn", EMITS, ids=[n for n, _ in EMITS])
def test_emit_is_not_empty(name, fn):
    """**空的投影與壞掉的投影不能長得一樣。** 一世之尊有 11 個 arc、93 章、
    12 支大綱檔——任何一支投影印出 0 列都代表它沒讀到檔。"""
    _report, stats = fn(BOOK)
    assert stats.rows > 0, f"{name} 印了 0 列——它沒讀到檔"
