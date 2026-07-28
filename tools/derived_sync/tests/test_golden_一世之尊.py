"""回歸黃金檔：`derived_sync` 六支閘門 ＋ 兩支投影在 `一世之尊` 上的完整輸出。

**為什麼要釘死一本病例書的壞產出**（抉擇 5 C ＋ 8 B，2026-07-28 功能 14）。

在這一輪之前，19 個指令裡只有 **4 個**有真實語料黃金檔——其餘 15 個「解析器悄悄
少抽一半而問題數不變」**不會被任何東西擋**。而那正是 `test_golden_一世之尊.py`
自己的 docstring 早就寫出來的失效模式：

> 若哪天解析器悄悄少抽一半，問題數仍然是 15，只有覆蓋率行會變。

**擴到「有覆蓋率行的 12 支 lint ＋ 5 個 `--emit` 投影」而不是全部 19 支**：黃金檔
的價值來自「覆蓋率行的每一個數字都被釘住」，而 `beat-metrics`／`prose-metrics`
沒有覆蓋率行，**釘不出這個價值**（抉擇 5 C）。

**它同時是抉擇 8 B（黃金檔即基準線）的實作**：一世之尊那 531 筆 findings 依政策
永遠不會被修，所以它們視為**已登記**；黃金檔比的是完整輸出，於是任何**新增**的
筆數都會讓 diff 失敗。「病例書的紅字是資產」這句話從此是一個機制，不是一句話。

要重生（只有在**刻意**改了門檻或訊息時才做，且要在 commit 訊息裡說清楚為什麼）：

    uv run --project tools/derived_sync pytest \\
        tools/derived_sync/tests/test_golden_一世之尊.py --regenerate-golden
"""

from pathlib import Path

import pytest
from derived_sync.char_lint import lint_book as char_lint
from derived_sync.emit import emit_characters, emit_world
from derived_sync.readiness import lint_book as readiness_lint
from derived_sync.style_lint import lint_book as style_lint
from derived_sync.summary_lint import lint_book as summary_lint
from derived_sync.validate import validate_report
from derived_sync.world_lint import lint_book as world_lint

# tests → derived_sync → tools → repo 根
REPO = Path(__file__).resolve().parents[3]
BOOK = REPO / "一世之尊"
GOLDEN_DIR = Path(__file__).parent / "golden"

# 六支閘門：(指令名, 跑它的函式)
GATES = (
    ("validate", validate_report),
    ("world-lint", world_lint),
    ("char-lint", char_lint),
    ("style-lint", style_lint),
    ("summary-lint", summary_lint),
    ("readiness-lint", readiness_lint),
)
# 兩支投影（`beat_metrics` 那三支在它自己的套件裡）
EMITS = (
    ("char-lint--emit", emit_characters),
    ("world-lint--emit", emit_world),
)


def _render_gate(problems, stats) -> str:
    """**與 CLI 的輸出順序逐字相同**（覆蓋率行→提示→問題）。

    黃金檔比的是 `_render()` 不是 CLI，所以這裡要自己維持那個順序——不然一次
    CLI 改版會讓黃金檔看起來還好好的，而使用者看到的東西已經變了。
    """
    lines = [stats.render()]
    lines += [f"[?]    {n}" for n in getattr(stats, "notes", [])]
    lines.append(f"發現 {len(problems)} 個問題：")
    lines += [f"  [x] {p.path.name}  {p.detail}" for p in problems]
    return "\n".join(lines) + "\n"


def _check(name: str, got: str, request) -> None:
    golden = GOLDEN_DIR / f"一世之尊-{name}.txt"
    if request.config.getoption("--regenerate-golden"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(got, encoding="utf-8")
        pytest.skip(f"已重生黃金檔 {golden.name}")
    assert golden.is_file(), f"黃金檔不在 {golden}——用 --regenerate-golden 生一份"
    assert got == golden.read_text(encoding="utf-8"), (
        f"一世之尊的 {name} 輸出變了。它是刻意不遷移的病例書，所以：\n"
        "  - 如果你是在改工具 → 你改壞了（或改對了但沒更新黃金檔，請說明為什麼）\n"
        "  - 如果你是在「順手把它修乾淨」→ 別修，那些紅字就是它的價值"
    )


def test_the_case_book_exists():
    """**找不到書就 fail，不 skip。**

    一個會自己 skip 掉的測試，就是本輪要修掉的那一類守衛：它跑了、它報平安、
    而它什麼都沒檢查（`設計原則.md` E2 第五格）。
    """
    assert BOOK.is_dir(), f"病例書不在 {BOOK}——它是這 8 份黃金檔的全部語料"


@pytest.mark.parametrize("name,fn", GATES, ids=[n for n, _ in GATES])
def test_gate_output_matches_golden(name, fn, request):
    problems, stats = fn(BOOK)
    _check(name, _render_gate(problems, stats), request)


@pytest.mark.parametrize("name,fn", EMITS, ids=[n for n, _ in EMITS])
def test_emit_output_matches_golden(name, fn, request):
    report, _stats = fn(BOOK)
    _check(name, report, request)


def test_the_case_book_is_still_red():
    """**病例書必須是紅的。** 它變乾淨＝有人遷移了它，或有人又把檢查關掉了。

    這幾個數字是 2026-07-28 功能 14 之後的基準（`validate` 那一支比重構前多 1，
    來源是本輪新增的「不得有 schema 外的 front-matter 鍵」聚合成的那一行）。
    """
    counts = {name: len(fn(BOOK)[0]) for name, fn in GATES}
    assert counts == {
        "validate": 34,
        "world-lint": 5,
        "char-lint": 7,
        "style-lint": 5,
        "summary-lint": 3,
        "readiness-lint": 2,
    }, counts


def test_the_clean_baseline_is_also_pinned():
    """**乾淨的那半也要有回歸。**

    若哪天解析器悄悄少抽一半，問題數不會變，**只有覆蓋率行會變**——所以覆蓋率行
    的每一個數字都要被釘住，而不只是「發現幾個問題」。
    """
    _, v = validate_report(BOOK)
    assert (v.files, v.enumerated, v.fm_only, v.skeleton) == (126, 126, 0, 0)
    assert (v.keys_files, v.keys_unenumerated) == (123, 3)
    assert (v.blockquote_files, v.blockquote_lines) == (29, 190)

    _, c = char_lint(BOOK)
    assert (c.sources, c.derived, c.sources_without_derived) == (24, 24, 0)

    _, w = world_lint(BOOK)
    assert w.folder_topics == 4
