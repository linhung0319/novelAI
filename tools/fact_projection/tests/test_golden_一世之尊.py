"""回歸黃金檔：`fact-lint --book 一世之尊` 的完整輸出。

**為什麼要釘死一本書的壞產出。** 一世之尊是刻意保留的病例書（不遷移新格式）。
2026-07-27 前 `fact-lint` 對它印「事實信封行格式乾淨」、exit 0，而同一份檔的成長哨兵
報 119 行肥大＋110 行括號超標——**閘門與哨兵對同一份資料給出 0 與 229 兩個答案**，
因為舊格式豁免是一個整本書的靜音開關。

拿掉那個開關之後它報 206 個問題（長度 52 ＋ 括號 110 ＋ 夾帶 44）。作者拍板把這 206
筆存成黃金檔（抉擇 5 A）：**任何偏離都是工具改壞了**，而不是「順手把病例書修乾淨」。

---

**2026-07-30（驗證輪階段 1c）：那 206 筆變成 1 筆，而這是拍板過的代價。**

舊單檔事實流（`story/參照/狀態事件流.md`）的**讀取路徑移除**——實測活用戶只有這本
書，而已拍板的前提是「`一世之尊/` 留原地，接受它從此跑不動，黃金檔改成記錄
『不再支援』」。不讀那支檔，那 259 筆事實行就不進 `fact-lint`，206 個問題隨之消失。

**這一格是全流程最容易騙自己的地方**，所以說清楚：

- **消失的不是問題，是量測。** 那 206 筆的病灶（行長、括號佔比、夾帶設計註）
  一個字都沒改，`110,946 B` 的檔還在磁碟上。
- **換來的是一句更大聲的話。** 現在 `fact-lint` 對這本書報的那 1 筆是
  「這支檔裡的事實**目前沒有任何工具在讀**，而 `write` 會理直氣壯地違反」
  ——比 206 筆「這一行太長」更接近真相：那本書的事實層**整層失聯**。
- **哨兵沒有跟著關掉。** `derived-sync check` 的成長哨兵仍量它的行
  （`sentinel.APPEND_LOG_STEMS` 仍含 `狀態事件流`），所以行長那一半仍有人看。
  這正是 2026-07-27 那次「閘門與哨兵對同一份資料給出 0 與 229」的反面：
  **這次是閘門說「我看不到它」，而哨兵說「它在這裡、而且很肥」——兩句都是真的。**

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
    """病例書必須是紅的。它變乾淨＝有人遷移了它，或有人又把檢查關掉了。

    **2026-07-30：206 → 1。** 見檔頭。那 1 筆是墓碑，而墓碑說的話比 206 筆
    「這一行太長」更重：這本書的事實層整層沒有人在讀。
    """
    problems, stats = lint_report(BOOK)
    assert len(problems) == 1, f"預期 1 個問題（墓碑），得到 {len(problems)}"
    assert "狀態事件流.md" in problems[0]
    assert "2026-07-30 起不再讀" in problems[0]
    assert "沒有任何工具在讀" in problems[0]
    # **新格式覆蓋率仍是 0，而那正是它是病例書的原因**——93 支章 delta 一支都沒有
    # `## 本章事實`。這個 0 在拿掉舊路徑之後**更重要**：它是「這本書為什麼跑不動」
    # 的唯一答案。
    assert stats.fact_lines == 0
    assert stats.chapter_files == 93


def test_coverage_line_admits_it_checked_nothing():
    """守衛要能回答「我在這本書上檢查了幾筆」，不能只回答「我發現幾個問題」。

    **這一行現在是這本書最誠實的一句話**：93 支章 delta、0 筆事實行。
    「掃了 93 支檔卻抽出 0 筆」與「這本書沒有事實」長得完全不同——前者說的是
    「東西在別的地方，而那個地方沒有人讀」。
    """
    _, stats = lint_report(BOOK)
    line = stats.render()
    assert "93 支章 delta" in line and "0 筆事實行" in line
    assert "0 支物件檔" in line and "0 條約束" in line
    # 舊的「新格式 N·舊格式 M」拆分已移除——一個恆為 0 的計數欄看起來像還在量。
    assert "舊格式" not in line
