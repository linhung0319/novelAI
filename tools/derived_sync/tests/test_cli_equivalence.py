"""「與 `derived-sync X` 完全等價」——**那句話 2026-07-28 之前是假的**（功能 14，V5）。

`world_lint_main`／`char_lint_main` 的 docstring 逐字寫著「與 `derived-sync world-lint`
完全等價」，而 `--emit` **只掛在獨立入口上**：`derived-sync world-lint --emit` 回
`error: unrecognized arguments`。那是一句**沒有任何東西在驗的行為承諾**——依 E1，
宣稱了就要有守衛，所以這支檔存在。
"""

from pathlib import Path

import pytest
from derived_sync.cli import char_lint_main, main, world_lint_main


@pytest.fixture
def book(tmp_path: Path) -> Path:
    b = tmp_path / "書"
    (b / "story" / "設定" / "角色").mkdir(parents=True)
    (b / "story" / "設定" / "世界觀").mkdir(parents=True)
    (b / "story" / "設定" / "角色" / "少年.md").write_text(
        "# 少年\n\n卷一的主角，怕水。\n", encoding="utf-8"
    )
    (b / "story" / "設定" / "角色" / "少年.ai.md").write_text(
        "---\n定位: 主角\n---\n"
        "## 需求四象限\n- 期盼：變強\n## 預期弧線\n盲目 → 挫折\n"
        "## 馬斯洛層次\n安全\n## 對衝關係\n與反派對撞\n",
        encoding="utf-8",
    )
    (b / "story" / "設定" / "世界觀" / "修煉體系.md").write_text(
        "# 修煉體系\n\n以甘露為根。\n", encoding="utf-8"
    )
    (b / "story" / "設定" / "世界觀" / "修煉體系.ai.md").write_text(
        "---\n主題: 修煉體系   # 檔名即 ID\n---\n"
        "## 限制與代價\n甘露有限。\n## 影響力\n決定階級。\n## 自洽\n無衝突。\n",
        encoding="utf-8",
    )
    return b


SUBCOMMANDS = (
    ("world-lint", world_lint_main),
    ("char-lint", char_lint_main),
)


@pytest.mark.parametrize("name,standalone", SUBCOMMANDS, ids=[n for n, _ in SUBCOMMANDS])
def test_subcommand_and_standalone_agree(name, standalone, book, capsys):
    """閘門模式：兩個入口的 exit 與 stdout 必須逐字相同。"""
    rc_sub = main([name, "--book", str(book)])
    out_sub = capsys.readouterr().out
    rc_alone = standalone(["--book", str(book)])
    out_alone = capsys.readouterr().out
    assert (rc_sub, out_sub) == (rc_alone, out_alone)


@pytest.mark.parametrize("name,standalone", SUBCOMMANDS, ids=[n for n, _ in SUBCOMMANDS])
def test_emit_works_on_the_subcommand_too(name, standalone, book, capsys):
    """**這一格就是 V5。** 在功能 14 之前這一行是 `error: unrecognized arguments`。"""
    rc_sub = main([name, "--book", str(book), "--emit"])
    out_sub = capsys.readouterr().out
    rc_alone = standalone(["--book", str(book), "--emit"])
    out_alone = capsys.readouterr().out
    assert (rc_sub, out_sub) == (rc_alone, out_alone)
    assert rc_sub == 0  # 投影不是閘門
    assert "投影" in out_sub


def test_comment_in_a_front_matter_value_does_not_break_world_lint(book, capsys):
    """**V4 的復現案例。** `主題: 修煉體系   # 檔名即 ID` 是合法的——
    `世界觀.schema.md:57` 的範例自己就這樣寫——而在 `md.py` 之前 `world-lint`
    會報「`主題` 與檔名不一致」，`style-lint`／`summary-lint` 卻不會。
    """
    world_lint_main(["--book", str(book)])
    assert "與檔名不一致" not in capsys.readouterr().out
