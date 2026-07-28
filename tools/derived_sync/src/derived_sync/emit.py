"""設定層 rollup 的**投影輸出**（`char-lint`／`world-lint` 的 `--emit`）。

**為什麼是 `--emit` 而不是新指令**（2026-07-28 功能 12 抉擇 4 C，作者拍板）：
`char-lint` 第 5 項與 `world-lint` 第 4·5 項為了比對「視圖 ≡ 資料夾」，**早就必須
先算出正確的那一份**——投影器的核心已經寫好了，差的只是把「比對」改成「輸出」。
所以誰重算誰印、同一支程式，結構上不可能漂。**已駁回跨套件聚合器**（抉擇 4 B：
功能 10 已經開過一次先例，再來一次就是零相依政策第二次被逼到牆角，而 14 還沒裁）。

`beat_metrics` 那一側（幕綱／大綱／章序三支投影）在 `beat_metrics/emit.py`。
**兩份 `EmitStats` 是刻意的最小複製**（工具間零相依，同 `parse_spine` 的先例）。

**`--emit` 是投影不是閘門**：只印，**一律 exit 0**（同 `readiness`）。

**「一句話」那一欄的機械來源是源檔 H1 之後第一個非空行**，不是 H1 本身
（2026-07-28 功能 12 實作時量出來的）：`大綱`／`幕綱`／`chapters` 三軸的 H1 是有
資訊的標題，而**角色 24/24 與世界觀 4/4 的 H1 就是檔名**（`# 修煉體系`），印它等於
把 ID 欄抄第二遍。實測那兩軸「H1 之後第一個非空行」100% 非空、中位 29／104 字元、
**0 支超過 rollup 的 400 行長**，而且內容正是舊 `一行需求`／`一句話定位` 要裝的東西
（`妙音 → 卷二 arc06 出場的江湖線第三方變數…`）。

**它仍是純機械來源**：位置固定、零 LLM。與 08 抉擇 4 C 被駁回的「從自由源抽基調
那一句」不同——那一格抽的是**一個具名語意欄**（位置假設承載語意宣稱），這一格抽的
是**檔的開頭**（位置不承載語意），而且投影只印、不取值：印錯了作者一眼看得出，
因為那句話就在源檔第一段。依 E1 配守衛：`char-lint`／`world-lint` 各加一項驗
「每支源檔 H1 之後要有非空行」，覆蓋率行印**其中幾支是空的**（06 補的 E2 推論）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .char_lint import (
    ARC_KEY,
    POSITION_KEY,
    TENTATIVE_KEY,
    char_dir,
    entity_lede,
    source_names,
)
from .core import AI_SUFFIX, lede
from .md import front_matter_of
from .world_lint import DIMENSIONS, topic_sources


@dataclass
class EmitStats:
    """**我印了幾列、其中幾列是空的。**（`設計原則.md` E2 ＋ 06 補的推論，0 也印。）"""

    rows: int = 0
    blank_ledes: int = 0
    legacy: list[tuple[str, int]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def render(self, unit: str = "列") -> str:
        legacy = (
            "、".join(f"`{n}`（{b:,} B）" for n, b in self.legacy) if self.legacy else "無"
        )
        return (
            f"投影 {self.rows} {unit}"
            f"（**其中 {self.blank_ledes} {unit}的源檔第一段是空的**）；"
            f"舊 rollup 檔殘留：{legacy}"
        )


def scan_legacy(book: Path, rels: tuple[str, ...], stats: EmitStats) -> None:
    """殘留偵測。**在渲染覆蓋率之前跑**（形狀照抄 `structure_project._scan_legacy`）。"""
    for rel in rels:
        p = book.joinpath(*rel.split("/"))
        if p.is_file():
            stats.legacy.append((rel, len(p.read_text(encoding="utf-8").encode("utf-8"))))


def legacy_section(
    stats: EmitStats, rels: tuple[str, ...], provenance: tuple[tuple[str, str], ...]
) -> list[str]:
    """末節：舊 rollup 在不在 ＋ 逐格「內容去哪了」。**0 也印**。"""
    shown = "／".join(f"`{r}`" for r in rels)
    lines = [f"### 舊 rollup {shown}（廢除於 2026-07-28·功能 12）", ""]
    if not stats.legacy:
        lines.append("舊檔：**不在**（已廢除，全書視圖由本投影回答）")
        return lines
    for rel, size in stats.legacy:
        lines.append(f"舊檔：**在** —— `{rel}`，{size:,} B")
    lines += [
        "",
        "逐格「這一格的機械來源是哪一支檔的哪一欄」（`設計原則.md` D3／A5 的驗收步驟）：",
        "",
    ]
    for cell, source in provenance:
        lines.append(f"- **{cell}** → {source}")
    lines += [
        "",
        "> 廢檔前要把「無機械來源」那幾格搬到它的落點，其餘直接刪。"
        "**病例書刻意不遷移**（抉擇 8 A），所以這一節會一直印；"
        "成長哨兵也會一直報它的體積與行長。",
    ]
    return lines


# ---------------------------------------------------------------- 角色清單

CHAR_LEGACY = ("story/設定/角色/_index.ai.md", "story/設定/角色/_index.md")
CHAR_PROVENANCE: tuple[tuple[str, str], ...] = (
    ("甲 `角色` 欄", "`story/設定/角色/` 底下的 `<名>.md` 與 `<名>/`（檔名即 ID·C1）"),
    ("乙 `定位`／`所屬arc`／`暫定`", "各 `<名>.ai.md` 的 front-matter（`char-lint` 第 5 項早就在比對）"),
    ("丙 一句話", "源 `<名>.md` H1 之後第一段（抉擇 3 B；**不印 H1**——實測 24/24 的 H1 就是檔名）"),
    ("丁 `一行需求` 欄", "**無獨立來源**——LLM 每次重生重寫的一句話（實測該檔 69.1% 獨有）"),
    ("戊〈乙批・`character` 觸發條件表〉", "**無機械來源＝它是源**（2026-07-23 作者裁決·8,145 字元＝52.7%）→ `story/參照/裁決流.md`"),
)


def emit_characters(book: Path) -> tuple[str, EmitStats]:
    """角色清單投影：`角色｜定位｜所屬arc｜暫定｜一句話`。"""
    stats = EmitStats()
    scan_legacy(book, CHAR_LEGACY, stats)
    d = char_dir(book)
    names, dirs, _ = source_names(book)

    lines = [
        f"## 角色清單投影 {book.name}（{len(names)} 支源檔；零 LLM、可覆算）",
        "",
        "> 取代舊 `story/設定/角色/_index.ai.md`（功能 12 抉擇 1 A）。"
        "**列 ≡ 資料夾、列名 ≡ 檔名**（C1／C3：檔名是 ID，不得加括號別名）。"
        "要展開就去讀該角色的 `.ai.md`；挑實體也可以走 "
        "`settings-select --arc arcNN`（那一支以幕綱的角色欄為準）。",
        "",
        "| 角色 | 定位 | 所屬arc | 暫定 | 一句話（源檔第一段） |",
        "|------|------|---------|------|--------------------|",
    ]
    for name in names:
        stats.rows += 1
        fm = front_matter_of(d / f"{name}{AI_SUFFIX}") or {}
        one = entity_lede(d, name)
        if not one:
            stats.blank_ledes += 1
        shape = "（目錄形態）" if name in dirs else ""
        lines.append(
            f"| {name}{shape} | {fm.get(POSITION_KEY, '—')} | "
            f"{fm.get(ARC_KEY, '—')} | {fm.get(TENTATIVE_KEY, '—')} | "
            f"{one or '（源檔第一段是空的）'} |"
        )
    if not names:
        lines.append("| （0 個角色） | — | — | — | — |")

    lines += ["", stats.render(), ""]
    lines += legacy_section(stats, CHAR_LEGACY, CHAR_PROVENANCE)
    return "\n".join(lines).rstrip() + "\n", stats


# ---------------------------------------------------------------- 世界觀總覽

WORLD_LEGACY = ("story/設定/世界觀/_總覽.ai.md", "story/設定/世界觀/_總覽.md")
WORLD_PROVENANCE: tuple[tuple[str, str], ...] = (
    ("甲 `主題`／`檔` 兩欄", "`story/設定/世界觀/` 底下的 `<主題>.md`（`world-lint` 第 4 項早就在比對）"),
    ("乙 七維列", "封閉枚舉 `DIMENSIONS`（`world-lint` 第 5 項早就在比對）"),
    ("丙 一句話", "源 `<主題>.md` H1 之後第一段（抉擇 3 B；**不印 H1**——實測 4/4 的 H1 就是檔名）"),
    ("丁 `待確認 N`", "`decision-project` 的覆蓋率行（0 也印）"),
    ("戊 `升格哨兵 M`", "`story/物件/` 的檔數"),
    # 己：**本投影刻意不印它**（2026-07-28 功能 13）。這一行在 12 寫的是「`raw/` 的
    # 檔名清單」，讀起來像一個承諾，而 `emit_world()` 從來沒有印過——依 E1，驗不到／
    # 產不出來就不該宣稱。而且 `ls raw/` 本來就答得了這件事，零成本、不會漂。
    # 「這個主題的素材從哪來」那一半的家是**源 `<主題>.md` 的散文**（`worldbuild` 步驟 9）。
    ("己 `素材出處`", "`ls raw/`（**本投影不印**）＋源 `<主題>.md` 的散文；裁決那一半走 `story/參照/裁決流.md`"),
    ("庚 `主從`／`影響力`／`帶升格哨兵`／各維 `內容`", "**無機械來源**——`世界觀.schema.md` 自己就寫「本 schema 不宣稱」；內容降級成各源檔的 `## 影響力` 散文"),
)


def emit_world(book: Path) -> tuple[str, EmitStats]:
    """世界觀總覽投影：`主題｜檔｜一句話` ＋ 封閉七維列。"""
    stats = EmitStats()
    scan_legacy(book, WORLD_LEGACY, stats)
    d = book / "story" / "設定" / "世界觀"
    topics = topic_sources(book)

    lines = [
        f"## 世界觀總覽投影 {book.name}（{len(topics)} 個主題；零 LLM、可覆算）",
        "",
        "> 取代舊 `story/設定/世界觀/_總覽.ai.md`（功能 12 抉擇 1 A）。"
        "**主題 ≡ 資料夾**；`主從`／`影響力` 那幾欄**不在這裡**——它們零機械來源，"
        "內容降級成各源檔的 `## 影響力` 散文（功能 05）。"
        "待確認矛盾跑 `decision-project`；硬約束看 `story/物件/`。",
        "",
        "| 主題 | 檔 | 一句話（源檔第一段） |",
        "|------|-----|--------------------|",
    ]
    for t in topics:
        stats.rows += 1
        one = lede(d / f"{t}.md")
        if not one:
            stats.blank_ledes += 1
        lines.append(f"| {t} | `{t}{AI_SUFFIX}` | {one or '（源檔第一段是空的）'} |")
    if not topics:
        lines.append("| （0 個主題） | — | — |")

    # ---- 背景七維：**只印枚舉本身，不造一張假表**
    #
    # 舊 rollup 的維度表有 `內容`／`狀態` 兩欄，而 `世界觀.schema.md:166,168` 自己就
    # 寫著「無機械核對者，本 schema 不宣稱」——**投影變不出來**。照著印一張每列都
    # 一樣的表，正是這一輪要消滅的東西（一個沒有來源的欄位，看起來像有人在維護）。
    #
    # 逐格套 D3 的三分法（本輪補的第三格）：它是 ②「無機械來源、但刪掉重跑會回來」
    # ——LLM 讀源檔重新盤點得出來。②需要的是**一個真的會被重生的容器**，而那個容器
    # 已經存在：各 `<主題>.ai.md`。所以投影只回答「枚舉是哪七個」，不回答「誰做了」。
    lines += [
        "",
        f"### 背景七維（封閉枚舉）：{'／'.join(DIMENSIONS)}",
        "",
        "> **哪一維被哪個主題做了，本投影不回答**——舊 rollup 的 `內容`／`狀態` 兩欄"
        "零機械來源（`世界觀.schema.md` 自己寫「無機械核對者，本 schema 不宣稱」）。"
        "它是「無機械來源、但刪掉重跑會回來」那一類（`設計原則.md` D3 第 ② 格），"
        "所以它的家是**一個真的會被重生的容器**＝各 `<主題>.ai.md` 的分析節，"
        "不是投影、也不是新開一支源檔。",
        "",
        stats.render("個主題"),
        "",
    ]
    lines += legacy_section(stats, WORLD_LEGACY, WORLD_PROVENANCE)
    return "\n".join(lines).rstrip() + "\n", stats


__all__ = [
    "EmitStats",
    "emit_characters",
    "emit_world",
    "entity_lede",
    "lede",
]
