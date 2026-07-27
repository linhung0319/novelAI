"""`decision-lint`：裁決軸與待裁決軸的格式閘門。

這支工具存在的理由：`裁決流.schema.md` 宣告了七欄、三種射程寫法、三種狀態值、
「一項裁決一列」——**2026-07-27 前一條都沒人守**，而 `共同約定.md` 同時宣稱
`.co.md` 是「嚴格（有檢查器）」。
"""

import pytest
from decision_projection.cli import lint_main
from decision_projection.lint import lint_report

HEAD = (
    "| 日期 | 來源 | 標的 | 裁決 | 理由 | 射程 | 狀態 |\n"
    "|------|------|------|------|------|------|------|\n"
)
ROW = "| 2026-07-22 | character | 設定/角色/少年.md | 年齡收窄 | 數字登記防分裂 | 全書 | 生效中 |\n"

PEND_HEAD = "| 日期 | 來源 | 標的 | 發現 |\n|------|------|------|------|\n"
PEND_ROW = "| 2026-07-25 | write-test 測試9 | 設定/角色/少年.md | 其「需要」中段就被滿足 |\n"


def _book(tmp_path, stream=None, pending=None, sources=("設定/角色/少年.md",)):
    book = tmp_path / "book"
    (book / "story" / "參照").mkdir(parents=True)
    for rel in sources:
        p = book / "story" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("源檔\n", encoding="utf-8")
    if stream is not None:
        (book / "story" / "參照" / "裁決流.md").write_text(stream, encoding="utf-8")
    if pending is not None:
        (book / "story" / "參照" / "待裁決.md").write_text(pending, encoding="utf-8")
    return book


# ------------------------------------------------------------ 覆蓋率行

def test_coverage_printed_even_with_no_files(tmp_path, capsys):
    """**0 也印。** 「這本書沒有裁決軸」與「有但沒問題」不能長得一樣。"""
    book = _book(tmp_path)
    assert lint_main(["--book", str(book)]) == 0
    out = capsys.readouterr().out
    assert "裁決流（**無**）0 列" in out and "待裁決（無）0 列" in out
    assert "還沒有裁決軸" in out


def test_coverage_counts_both_axes(tmp_path, capsys):
    book = _book(tmp_path, stream=HEAD + ROW, pending=PEND_HEAD + PEND_ROW)
    assert lint_main(["--book", str(book)]) == 0
    out = capsys.readouterr().out
    assert "裁決流（有）1 列" in out and "待裁決（有）1 列" in out
    assert "裁決軸格式乾淨。" in out


# ------------------------------------------------------------ 裁決流

def test_bad_scope_is_reported(tmp_path):
    """`decision-project` **從不驗射程欄**——寫錯只會在 --as-of 時靜默當成判不了，
    於是一條早該過期的裁決永遠回「生效中」。"""
    bad = ROW.replace("| 全書 | 生效中 |", "| 卷二為止 | 生效中 |")
    problems, _ = lint_report(_book(tmp_path, stream=HEAD + bad))
    assert len(problems) == 1 and "射程" in problems[0]


@pytest.mark.parametrize("scope", ["全書", "至arc07", "本輪", "至 arc11"])
def test_legal_scopes_pass(tmp_path, scope):
    row = ROW.replace("| 全書 | 生效中 |", f"| {scope} | 生效中 |")
    problems, _ = lint_report(_book(tmp_path, stream=HEAD + row))
    assert problems == []


def test_long_ruling_is_reported(tmp_path):
    """「一項裁決一列」的可執行形式——併成一列長文會讓 --target 過濾失效。"""
    row = ROW.replace("| 年齡收窄 |", "| " + "決" * 201 + " |")
    problems, _ = lint_report(_book(tmp_path, stream=HEAD + row))
    assert len(problems) == 1 and "`裁決` 欄 201 字" in problems[0]


def test_long_rationale_is_fine(tmp_path):
    """**只有 `理由` 欄不設上限。** 設了等於把人趕回去寫 blockquote。"""
    row = ROW.replace("| 數字登記防分裂 |", "| " + "理" * 3000 + " |")
    problems, _ = lint_report(_book(tmp_path, stream=HEAD + row))
    assert problems == []


def test_missing_target_is_reported(tmp_path):
    row = ROW.replace("設定/角色/少年.md", "設定/角色/不存在的人.md")
    problems, stats = lint_report(_book(tmp_path, stream=HEAD + row))
    assert len(problems) == 1 and "在書內找不到" in problems[0]
    assert stats.bad_targets == 1


def test_target_all_needs_no_file(tmp_path):
    row = ROW.replace("設定/角色/少年.md", "全書")
    problems, _ = lint_report(_book(tmp_path, stream=HEAD + row))
    assert problems == []


def test_directory_form_target_resolves(tmp_path):
    row = ROW.replace("設定/角色/少年.md", "設定/角色/少年/核心.md")
    book = _book(tmp_path, stream=HEAD + row, sources=("設定/角色/少年/核心.md",))
    problems, _ = lint_report(book)
    assert problems == []


def test_promoted_without_a_pointer_is_reported(tmp_path):
    """`已升為通則` 的理由欄要「改成一句指過去」，不留第二份。"""
    row = ROW.replace("| 全書 | 生效中 |", "| 全書 | 已升為通則 |")
    problems, stats = lint_report(_book(tmp_path, stream=HEAD + row))
    assert stats.promoted == 1
    assert len(problems) == 1 and "沒有指向" in problems[0]


def test_promoted_pointer_to_a_missing_file_is_reported(tmp_path):
    """E1 目的地存在性：箭頭指向空氣，而箭頭本身格式完全合法。"""
    root = tmp_path / "pkg"
    (root / "結構定義").mkdir(parents=True)
    (root / "技巧知識庫").mkdir(parents=True)
    (root / "結構定義" / "幕綱.schema.md").write_text("x\n", encoding="utf-8")
    row = ROW.replace(
        "| 數字登記防分裂 | 全書 | 生效中 |",
        "| 已升格為 `結構定義/不存在.schema.md` | 全書 | 已升為通則 |",
    )
    book = _book(root, stream=HEAD + row)
    problems, _ = lint_report(book)
    assert len(problems) == 1 and "不存在" in problems[0]

    ok = ROW.replace(
        "| 數字登記防分裂 | 全書 | 生效中 |",
        "| 已升格為 `結構定義/幕綱.schema.md` | 全書 | 已升為通則 |",
    )
    (book / "story" / "參照" / "裁決流.md").write_text(HEAD + ok, encoding="utf-8")
    assert lint_report(book)[0] == []


def test_broken_table_reports_instead_of_crashing(tmp_path):
    problems, _ = lint_report(_book(tmp_path, stream="| 日期 | 標的 |\n|--|--|\n"))
    assert len(problems) == 1 and "解析失敗" in problems[0]


# ------------------------------------------------------------ 待裁決

def test_status_column_is_rejected(tmp_path):
    """**T2 的持久形態。** 舊設計那個只允許一個值的 `狀態` 欄，實測 7 列平均
    171 字元、最長 440、佔整列 61%——人的裁決被塞進 AI 那一筆的最後一格。"""
    bad = (
        "| 日期 | 來源 | 標的 | 發現 | 狀態 |\n|--|--|--|--|--|\n"
        "| 2026-07-25 | write-test | 設定/角色/少年.md | 弧線塌陷 | 待裁決 |\n"
    )
    problems, _ = lint_report(_book(tmp_path, stream=HEAD, pending=bad))
    assert len(problems) == 1
    assert "解析失敗" in problems[0] and "不得有 `狀態` 欄" in problems[0]


def test_long_finding_is_reported(tmp_path):
    row = PEND_ROW.replace("| 其「需要」中段就被滿足 |", "| " + "發" * 201 + " |")
    problems, _ = lint_report(_book(tmp_path, stream=HEAD, pending=PEND_HEAD + row))
    assert len(problems) == 1 and "`發現` 欄 201 字" in problems[0]


def test_pending_target_must_exist(tmp_path):
    """舊設計那一欄是散文（「建議回寫（改哪個源檔）」），路徑寫錯**永遠不會發現**。"""
    row = PEND_ROW.replace("設定/角色/少年.md", "設定/角色/打錯了.md")
    problems, _ = lint_report(_book(tmp_path, stream=HEAD, pending=PEND_HEAD + row))
    assert len(problems) == 1 and "在書內找不到" in problems[0]


def test_pending_without_a_stream_is_reported(tmp_path):
    """E1 目的地存在性：結案時「理由」無處可去，下場是改落 `.ai.md` 的 blockquote。"""
    problems, _ = lint_report(_book(tmp_path, pending=PEND_HEAD + PEND_ROW))
    assert len(problems) == 1 and "`裁決流.md` 不存在" in problems[0]


def test_pending_with_zero_decisions_is_a_note_not_a_problem(tmp_path, capsys):
    """跨時間對帳守不住，但病徵要可見：「待裁決在漲而裁決恆為 0」。
    **不計入問題數**——它不是格式錯，是一個值得看一眼的形狀。"""
    book = _book(tmp_path, stream=HEAD, pending=PEND_HEAD + PEND_ROW)
    assert lint_main(["--book", str(book)]) == 0
    out = capsys.readouterr().out
    assert "1 列待裁決、0 列裁決" in out and "不計入問題數" in out


# ------------------------------------------------------------ CLI

def test_exit_code_1_on_problems(tmp_path, capsys):
    bad = ROW.replace("| 全書 | 生效中 |", "| 卷二為止 | 生效中 |")
    book = _book(tmp_path, stream=HEAD + bad)
    assert lint_main(["--book", str(book)]) == 1
    cap = capsys.readouterr()
    assert "檢查範圍：" in cap.out  # 覆蓋率行走 stdout
    assert "發現 1 個問題" in cap.err  # 問題走 stderr
