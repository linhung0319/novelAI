"""輸出與 exit 契約（2026-07-28 功能 14，抉擇 6 A ＋ V10）。

**唯一真相在 `結構定義/共同約定.md`「輸出與 exit 契約」**；跨工具的守衛是
`meta-lint` 第 6 項（對 fixture 書實跑、比對 stdout／stderr／exit）。本檔守的是
**本套件五個指令**的那一份，因為 V6 的三個實測案例全在這裡。

在功能 14 之前：

- `beat-lint --book gothic_witch` 印**一行**「掃描錯誤：找不到幕綱目錄」、
  **連覆蓋率行都不印**、exit 1——與一支格式真的壞掉的書**完全不可分辨**，
  而 6 本書裡有 **3 本**長期處在這個狀態（只有 `raw/`）；
- 問題清單走 stderr，於是 `> report.txt` 會得到一份看起來乾淨的報告。
"""

from pathlib import Path

import pytest
from beat_metrics.cli import (
    EXIT_CLEAN,
    EXIT_LAYER_MISSING,
    EXIT_PROBLEMS,
    ch_lint_main,
    lint_main,
    main,
    outline_lint_main,
    structure_project_main,
)

ALL_COMMANDS = (
    ("beat-lint", lint_main),
    ("ch-lint", ch_lint_main),
    ("outline-lint", outline_lint_main),
    ("structure-project", structure_project_main),
    ("beat-metrics", main),
)


@pytest.fixture
def raw_only_book(tmp_path: Path) -> Path:
    """一本只有 `raw/` 的書——6 本裡有 3 本長期是這個狀態。"""
    book = tmp_path / "書"
    (book / "raw").mkdir(parents=True)
    (book / "raw" / "靈感.md").write_text("還沒想清楚。\n", encoding="utf-8")
    return book


@pytest.mark.parametrize("name,fn", ALL_COMMANDS, ids=[n for n, _ in ALL_COMMANDS])
def test_layer_missing_is_exit_2_with_a_coverage_line(name, fn, raw_only_book, capsys):
    """**exit 2 ＝跑不動，而且照樣印覆蓋率行**（「掃了 0 支」）。

    覆蓋率行必須在 **stdout**——`meta-lint` 第 6 項就是靠它把「跑不動」與
    argparse 的用法錯誤（同樣是 exit 2，但只印 usage 到 stderr）分開。
    """
    assert fn(["--book", str(raw_only_book)]) == EXIT_LAYER_MISSING
    cap = capsys.readouterr()
    assert "檢查範圍：掃了 0 支" in cap.out, f"{name} 的 exit 2 沒有印覆蓋率行"
    assert "還沒有這一層" in cap.out
    assert cap.err == "", f"{name} 把跑不動印進了 stderr"


@pytest.mark.parametrize(
    "name,fn",
    [c for c in ALL_COMMANDS if c[0].endswith("lint")],
    ids=[c[0] for c in ALL_COMMANDS if c[0].endswith("lint")],
)
def test_problems_go_to_stdout(name, fn, tmp_path, capsys):
    """**問題清單走 stdout**（V10）。

    實測 `fact-lint --book 一世之尊 > report.txt` 只得到 2 行（412 B），而 206 個
    問題（47,547 B）全部落進 stderr——在一個由 LLM 驅動、routinely 重導輸出的
    系統裡，那是一個會安靜地讀成「乾淨」的介面。
    """
    book = tmp_path / "書"
    d = book / "story" / "幕綱"
    d.mkdir(parents=True)
    # 缺 `## 本 arc 承諾`、缺八欄 → 至少一個問題
    (d / "arc01.md").write_text("# arc01\n\n## 幕001\n- 角色：少年\n", encoding="utf-8")
    (book / "story" / "01-大綱.md").write_text("# 大綱\n\n## 本段全文\n略。\n", encoding="utf-8")
    (book / "chapters").mkdir()

    rc = fn(["--book", str(book)])
    cap = capsys.readouterr()
    assert rc in (EXIT_CLEAN, EXIT_PROBLEMS)
    assert "檢查範圍：" in cap.out
    if rc == EXIT_PROBLEMS:
        assert "發現" in cap.out and "個問題" in cap.out
    assert "個問題" not in cap.err, f"{name} 還在把問題印進 stderr"


def test_exit_codes_are_the_three_documented_ones():
    """三個碼、三個語意——別再長出第四個。"""
    assert (EXIT_CLEAN, EXIT_PROBLEMS, EXIT_LAYER_MISSING) == (0, 1, 2)
