"""`derived_sync` 這個套件**唯一一份** Markdown 解析層。

**為什麼要有這支檔（2026-07-28 功能 14，抉擇 1 D）。** 在它之前，同一個套件裡有
**六份** front-matter 解析器（`core._split_frontmatter` ＋ `char_lint`／`style_lint`／
`summary_lint`／`world_lint` 各一個 `_front_matter` ＋ `emit._fm`），而且它們沿
**三個獨立軸**分歧：

| 軸 | 分歧 |
|---|---|
| 鍵的 regex | `^([A-Za-z0-9_-]+):`（`validate`，**中文鍵一個字都讀不到**）／`^([^\\s:：]+)\\s*[:：]`（四支 lint）／`partition(":")`（`emit`，只吃半形冒號） |
| `#` 註解剝不剝 | `style`／`summary`／`emit` 剝，**`char`／`world` 不剝** |
| front-matter 怎麼偵測 | `_split_frontmatter`（首行 `---` ＋ 要求封閉）／`emit` 的 `startswith("---")` ＋ 兩次 `partition` |

**分歧有實測後果，而且沒有任何守衛**：一支合法的
`主題: 修煉體系   # 檔名即 ID` 會讓 `world-lint` 報「`主題` 與檔名不一致」，
而 `style-lint`／`summary-lint` 的同名函式會正確處理——**`世界觀.schema.md:57` 的
範例自己就在 front-matter 值後面寫註解**。

**零相依政策（`dependencies = []`）解釋得了跨套件那 42 份，解釋不了這 14 份**——
它們在同一個 `import` 得得到的空間裡。這是功能 14 推翻的第一個既有結論：從 05 到 12，
每一輪都把新的複製記成「零相依的代價」。

**跨套件的複製本輪刻意不動**（抉擇 1：D 現在做、B 當方向）：`spine_path` 4 份、
`_force_utf8` 6 份、`所屬arc` 5 份留著，由 `meta-lint` 第 8 項把份數印成一個逐輪
可見的數字——**先讓成本可見，再決定要不要付**（同 D2「量出來再蓋」的紀律）。
"""

from __future__ import annotations

import re
from pathlib import Path

# 鍵：不含空白與兩種冒號的任何字元（**中文鍵要吃得到**——`00-摘要.ai.md` 的
# `主線`／`題旨`／`基調` 全是中文鍵，而 `validate` 在功能 14 之前用的是
# `^([A-Za-z0-9_-]+):`，對它們一個字都讀不到，於是「front-matter 缺某鍵」這條
# 檢查在摘要軸上是空頭承諾）。冒號兩種都吃（作者會打成全形）。
KEY_RE = re.compile(r"^([^\s:：]+)\s*[:：]\s*(.*)$")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_H1_RE = re.compile(r"^#\s+")
# `^## 幕NNN`（`sentinel` 數幕數、`summary_lint` 驗幕號引用，兩支同一把尺）
BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)")
# 幕綱的 `埋[[伏筆:x]]`／`收[[伏筆:x]]`（與 `beat-lint` 同一把尺）
FORESHADOW_RE = re.compile(r"\[\[伏筆[:：]([^\]]+)\]\]")


def split_frontmatter(text: str) -> tuple[list[str] | None, str]:
    """回傳 (front-matter 行清單, 本體)；無合法 front-matter 時 (None, 全文)。

    **未封閉的 front-matter 視為沒有 front-matter**——那個狀態由 `check` 報成
    `skeleton`／`unstamped`，這裡不猜。
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1 :])
    return None, text  # 未封閉 → 視為無 front-matter


def front_matter(text: str) -> dict[str, str] | None:
    """front-matter → 扁平 dict；沒有 front-matter 回 None。

    **值一律剝掉 `#` 之後的註解**：`世界觀.schema.md:57`／`風格.schema.md`／
    `摘要.schema.md` 三支的範例本身就在值後面寫註解
    （`基調參照: 哥特恐怖＋黑色幽默    # 引 00-摘要.md「基調」`），不剝的話跨檔
    比對會對著一段註解比。**「沒有 front-matter」與「front-matter 是空的」是兩件事**，
    所以回 `None` 而不是 `{}`。
    """
    fm, _ = split_frontmatter(text)
    if fm is None:
        return None
    out: dict[str, str] = {}
    for line in fm:
        m = KEY_RE.match(line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).split("#", 1)[0].strip()
    return out


def front_matter_of(path: Path) -> dict[str, str] | None:
    """`front_matter()` 的讀檔版（缺檔回 None，同「沒有 front-matter」）。"""
    if not path.is_file():
        return None
    return front_matter(path.read_text(encoding="utf-8"))


def section_body(text: str, title: str) -> list[str] | None:
    """某個 `##` 節的內容行；**節不存在回 None**（與「節在但空的」是兩件事）。

    節名以 `startswith` 比對——作者會在標題後加註記（`## 基調（氛圍／筆調）`、
    `## 臨場拍板、非定版（待後續拍板，別鎖死）`）。
    """
    out: list[str] = []
    found = inside = False
    for raw in text.replace("\r\n", "\n").split("\n"):
        m = _H2_RE.match(raw.strip())
        if m:
            inside = m.group(1).strip().startswith(title)
            found = found or inside
            continue
        if inside:
            out.append(raw)
    return out if found else None


def sections(text: str) -> list[str]:
    """全檔的 `##` 節標題（依出現順序）。"""
    return [m.group(1).strip() for ln in text.splitlines() if (m := _H2_RE.match(ln))]


def table_rows(lines: list[str]) -> list[list[str]]:
    """Markdown 表格的**資料列**（表頭與 `|---|` 分隔列都不算）。

    判準是位置：`|---|` 分隔列**之後**的才是資料。**不能只跳分隔列**——那會把表頭
    當成一筆資料，於是「主題」「維度」這兩個欄名被報成「指向不存在的主題」
    （`world_lint` 實作時實測到的第一版 bug）。表格缺分隔列時回 0 列，那個狀態會
    出現在覆蓋率行而不是靜默通過。
    """
    rows: list[list[str]] = []
    after_sep = False
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            if not s:
                after_sep = False  # 空行結束一張表
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and all(set(c) <= set("-: ") for c in cells):
            after_sep = True
            continue
        if after_sep:
            rows.append(cells)
    return rows


def lede_of(text: str) -> str:
    """H1 之後第一個非空行（去掉開頭的 bullet 記號）。取不到回空字串。"""
    seen_h1 = False
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if not seen_h1 and _H1_RE.match(s):
            seen_h1 = True
            continue
        return re.sub(r"^[-*]\s*", "", s)
    return ""
