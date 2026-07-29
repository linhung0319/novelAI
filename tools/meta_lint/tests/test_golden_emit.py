"""回歸黃金檔：`meta-lint` 的兩個投影（2026-07-29 功能 15，第 18／19 份）。

**為什麼這兩支非釘不可**——它們與前 17 份的性質不同：那 17 份釘的是**對一本書的
檢查輸出**，這兩份釘的是**取代了手抄清單的那份輸出本身**。

- `--emit guards` 取代 `共同約定.md` 八 的 11,399 B 閘門說明（抉擇 1 A）；
- `--emit kb` 取代 `技巧知識庫/_index.md` 的「被哪些 skill 引用」欄（抉擇 4 A）。

**手抄的那兩份會漂、而漂了沒有人發現**（實測 `_index.md` 那一欄 15/27 列不一致）。
改成投影之後漂移在結構上不可能發生，但**投影自己壞掉**仍然可能——而它壞掉的樣子
正是 E2 最後一格：表格照印、欄位還在、只是少了幾列或某一欄變成「讀不到」。

**這兩份的語料是 repo 自己**（`meta-lint` 不吃 `--book`），所以它們同時是「這個
repo 現在有幾支指令、幾支技法檔、誰引用誰」的基準線——數字變了就是有人動了
entry point、SKILL.md 的依據節，或技法檔的集合。

要重生（只有在**刻意**改了投影格式時才做，且要在 commit 訊息裡說清楚為什麼）：

    uv run --project tools/meta_lint pytest \\
        tools/meta_lint/tests/test_golden_emit.py --regenerate-golden
"""

from pathlib import Path

import pytest
from meta_lint.checks import emit_guards, emit_kb
from meta_lint.repo import find_repo

REPO = find_repo(Path(__file__))
GOLDEN_DIR = Path(__file__).parent / "golden"

EMITS = (
    ("meta-lint--emit-guards", emit_guards),
    ("meta-lint--emit-kb", emit_kb),
)


def _check(name: str, got: str, request) -> None:
    golden = GOLDEN_DIR / f"{name}.txt"
    if request.config.getoption("--regenerate-golden"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(got, encoding="utf-8")
        pytest.skip(f"已重生黃金檔 {golden.name}")
    assert golden.is_file(), f"黃金檔不在 {golden}——用 --regenerate-golden 生一份"
    assert got == golden.read_text(encoding="utf-8"), (
        f"{name} 的輸出變了。這份投影**取代了一份手抄清單**，所以：\n"
        "  - 改了 entry point／SKILL.md 的依據節／技法檔集合 → 那是真的變動，"
        "更新黃金檔並在 commit 訊息說明；\n"
        "  - 沒改那些卻 diff 了 → 投影器壞了（少抽一欄的樣子就是「表格照印、"
        "只是短了幾列」）"
    )


@pytest.mark.parametrize("name,fn", EMITS, ids=[n for n, _ in EMITS])
def test_emit_output_matches_golden(name, fn, request):
    _check(name, "\n".join(fn(REPO)) + "\n", request)


def test_every_command_has_a_guarded_description():
    """**「守什麼」那一欄不得有洞。**

    它的機械來源是各 `cli.py` 的 argparse `description`；取不到值時投影印
    「讀不到 description」——而那在一份取代了手抄清單的投影上是一個真的洞，
    不是一個中性的佔位（E2：未接要說出來，而說出來之後就要處置）。
    """
    assert "讀不到 description" not in "\n".join(emit_guards(REPO))


def test_the_zero_reference_files_stay_visible():
    """**「0 支」是儀表，不是待修的洞**（同功能 10 對「未接」的處置）。

    投影印得出「0 支」，這一格才有下一輪可以看的東西。要不要讓某支 skill 引用
    那兩支技法檔是**內容決定**，重構輪刻意不動。
    """
    assert "**0 支**" in "\n".join(emit_kb(REPO))
