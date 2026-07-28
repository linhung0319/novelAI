from pathlib import Path

# 最小的 registry 語料（2026-07-28 功能 11）。**tmp_path 的書一定要種一個套件根**，
# 否則 `formula.package_root` 往上找不到 `技巧知識庫/`＋`結構定義/`，registry 回
# 「未接」，而所有跟 registry 有關的檢查會**靜靜地不跑、測試照樣全綠**——那正是本輪
# 刪掉的那五支 `_is_declarative` 測試的死法（**測試是綠的，射程是空的**）。
KNOWLEDGE = """# 結構公式

## 一、三幕劇
<!-- 結構公式: 三幕劇 | 必要階段: 觸發,衝突,解決 -->

## 二、起承轉合
<!-- 結構公式: 起承轉合 | 必要階段: 起,承,轉,合 -->

## 三、雪花法
<!-- 結構公式: 雪花法 | 必要階段: — -->
"""


def plant_package_root(root: Path, knowledge: str = KNOWLEDGE) -> Path:
    """在 `root` 底下種一個能被 `formula.package_root` 認出來的套件根。

    判準與 `共同約定.md` 一 相同：**同時**含 `技巧知識庫/` 與 `結構定義/`。
    """
    (root / "結構定義").mkdir(parents=True, exist_ok=True)
    d = root / "技巧知識庫"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "結構公式.md"
    p.write_text(knowledge, encoding="utf-8")
    return p


def pytest_addoption(parser):
    """`--regenerate-golden`：重寫回歸黃金檔而不是比對它。

    刻意做成明確的旗標而不是「檔不存在就自動生成」——自動生成會讓「黃金檔被誤刪」
    與「工具改壞了」變成同一個綠燈。
    """
    parser.addoption(
        "--regenerate-golden",
        action="store_true",
        default=False,
        help="重生 tests/golden/ 下的黃金檔（只在刻意改門檻或訊息時用）",
    )
