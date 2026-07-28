"""`beat_metrics` 這個套件裡「引用」相關的**唯一一份**解析層。

**為什麼要有這支檔（2026-07-28 功能 14，抉擇 1 D）。** 這個套件裡有四個指令
（`beat-lint`／`ch-lint`／`outline-lint`／`structure-project`），而它們曾各自帶著
自己的一份：

| 形狀 | 功能 14 之前住哪 |
|---|---|
| `埋|收[[伏筆:x]]` | `chapters._MARK_RE`／`structure._MARK_RE`／`outline._FORESHADOW_RE`（**3 份**） |
| 檔內書內路徑的目的地存在性 | `lint._check_destinations`／`outline._check_destinations`（**2 份**，四個常數也各一份） |

**跨套件的複製有政策在支持它**（所有 `tools/*/pyproject.toml` 皆 `dependencies = []`
——`foreshadow_project/scan.py:_MARK_RE` 是這條 regex 的跨套件唯一真相，本檔仍然是
它的複本）。**同一個套件內的複製沒有**：它們在同一個 `import` 得得到的空間裡，而
`derived_sync` 那一側已經實測出這種複製會**語意分歧且分歧無人守**（V4）。

所以本檔只收「同套件內原本有兩份以上」的那幾個形狀；跨套件那 42 份本輪刻意不動，
由 `meta-lint` 第 8 項把份數印成一個逐輪可見的數字（抉擇 1：D 現在做、B 當方向）。
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------- 伏筆標記
#
# **跨套件唯一真相在 `tools/foreshadow_project/src/foreshadow_project/scan.py:_MARK_RE`**；
# 工具間零相依，故本套件複製最小片段——但**本套件只複製一次**。
# schema 用半形冒號，這裡連全形一起收，錯字不靜默漏掉。
MARK_RE = re.compile(r"(埋|收)\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]")
# 不分埋／收的版本（大綱層用：那一層只問「這個名字在不在 registry 裡」，
# 埋／收是幕綱的事）。
FORESHADOW_RE = re.compile(r"\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]")

# ---------------------------------------------------------------- 目的地存在性
#
# `設計原則.md` E1「目的地承諾」推論：凡 schema 指定「把某種內容搬去某支檔」的
# 遷移動作，那支目的地檔的存在性本身要有守衛——**箭頭指向空氣，而箭頭本身格式
# 完全合法**。
#
# **射程刻意窄**：只認反引號裡、以書內資料夾開頭的 `.md`。schema 檔、`技巧知識庫/`、
# 佔位寫法（`arcNN.md`）、範圍寫法（`arc01–arc04.md`）都不是「指名一個檔」——不排除
# 的話，一支完全合法的大綱／幕綱會因為引用了自己的 schema 而被報成目的地不存在。
MD_REF_RE = re.compile(r"`([^`\n]+?\.md)`")
BOOK_PREFIXES = ("story/", "chapters/", "參照/", "幕綱/", "大綱/", "設定/", "物件/")
PLACEHOLDER_RE = re.compile(r"(arcNN|chNNNN|<[^>]+>|＜[^＞]+＞|NNNN|NNN)")
ARC_RANGE_RE = re.compile(r"arc(\d+)\s*[–—-]\s*arc(\d+)")


def scan_md_refs(items: list[tuple[str, str]], book: Path) -> tuple[int, dict[str, set[str]]]:
    """掃 (來源標籤, 全文) 清單裡的書內路徑引用。

    回傳 (檢查了幾筆, {不存在的路徑: {在哪幾支檔}})。**兩個回傳值都要進覆蓋率行**
    ——只回報「幾個不存在」的守衛，在它自己被關掉時會印「乾淨」（E2）。
    """
    checked = 0
    missing: dict[str, set[str]] = {}
    for where, text in items:
        for m in MD_REF_RE.finditer(text):
            ref = m.group(1).strip()
            if not ref.startswith(BOOK_PREFIXES):
                continue
            if ".schema." in ref or PLACEHOLDER_RE.search(ref):
                continue
            if ARC_RANGE_RE.search(ref) or "–" in ref or "—" in ref:
                continue
            checked += 1
            rel = ref[len("story/") :] if ref.startswith("story/") else ref
            if (book / "story" / rel).is_file() or (book / ref).is_file():
                continue
            missing.setdefault(ref, set()).add(where)
    return checked, missing


def format_missing(missing: dict[str, set[str]], limit: int = 4) -> str:
    """不存在的路徑聚合成一行（03 拍板的判準：病因與修法相同時聚合）。"""
    shown = "、".join(
        f"`{r}`（{'、'.join(sorted(w))}）" for r, w in sorted(missing.items())[:limit]
    )
    return shown + ("…" if len(missing) > limit else "")


MISSING_HINT = (
    "箭頭指向空氣，而箭頭本身格式完全合法（E1）。改成實際的路徑，"
    "或照 `書本模板/` 的骨架先建那支檔"
)
