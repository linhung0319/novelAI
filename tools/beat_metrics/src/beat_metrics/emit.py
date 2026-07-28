"""rollup 索引的**投影輸出**（`beat-lint`／`outline-lint`／`ch-lint` 的 `--emit`）。

**為什麼是 `--emit` 而不是新指令**（2026-07-28 功能 12 抉擇 4 C，作者拍板）。

五支 rollup 索引（`chapters/_index.ai.md`／`設定/角色/_index.ai.md`／
`設定/世界觀/_總覽.ai.md`／`幕綱/_index.md`／`大綱/_index.md`）在功能 12 之前是
**同一個結構性錯誤的五個實例**：rollup 是全系統唯一一支「關於全部東西」的檔，
所以任何找不到家的內容都落在它身上，而它的 hash（有的話）守的是**源檔集合**、
不是它自己的內容，於是沒有任何東西會反對。

而逐格套 `設計原則.md` D3 的推論之後，答案特別乾淨：**四支既有 lint 為了比對
「視圖 ≡ 資料夾」，早就必須先算出正確的那一份**——投影器的核心已經寫好了，
差的只是把「比對」改成「輸出」。所以：

- **不新開指令**（抉擇 4 A 的兩個 `index-project` 被駁回：使用者要記兩個指令）；
- **不做跨套件聚合器**（抉擇 4 B 已駁回：10 已經開過一次先例，再來一次就是零相依
  政策第二次被逼到牆角，而 14 還沒裁）；
- **誰重算誰印，同一行程式**——結構上不可能漂。

**`--emit` 是投影不是閘門**：只印，**一律 exit 0**（同 `structure-project`／
`readiness`）。它不印 problems——要驗格式就跑不帶 `--emit` 的同一支指令。

**每支的末節做殘留偵測**（形狀照抄 `structure_project._legacy`）：舊 rollup 檔在
不在 ＋ 逐格印「這一格的機械來源是哪一支檔的哪一欄」。**0 也印**——舊檔不在時印
「不在」那一行，才代表這本書已經遷完了；只在檔還在時才印，就是把「已遷移」與
「工具沒讀到」變成同一個綠燈。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .chapters import AI_SUFFIX, ChapterMeta, _POV_ROLE_RE, load_metas
from .lint import BLOCK, _ARC_NUM_RE
from .outline import (
    FULL_NAME,
    OUTLINE_DIR,
    RETIRED_DIR,
    load_files,
)
from .scan import SPINE_FILES, read_text
from .structure import SKELETON_MARK, parse_book

# H1 開頭的 ID 前綴（`# arc09 · 他留著那個名字…`／`# ch0001 · 一覺穿成小和尚`）。
# **投影把它剝掉**：ID 已經是自己那一欄，重複印一次是雜訊。
_H1_RE = re.compile(r"^#\s+(.*?)\s*$")
_H1_ID_PREFIX_RE = re.compile(r"^(?:arc[0-9A-Za-z]+|ch\d+)\s*[·・．.]\s*")


def h1(path: Path) -> str:
    """源檔的 H1（去掉 `# ` 與 ID 前綴）。取不到回空字串——**空要印出來**。

    **這是抉擇 3 B 的機械來源之一**：摘要欄（`備註`／arc 概覽／`名稱`）廢除之後，
    「這一段／這一章是什麼」改由源檔的 H1 回答。實測一世之尊 11/11 支 `arcNN.md`
    與 93/93 支 `chNNNN.md` 的 H1 都是有資訊的標題（`# arc09 · 他留著那個名字
    （卷三第一段・開卷：從暗處挖出一顆籌碼）`）——**H1 本來就是作者寫的一句話摘要**，
    而且它有作者維護、天生不會漂。
    """
    if not path.is_file():
        return ""
    for raw in read_text(path).splitlines():
        m = _H1_RE.match(raw)
        if m:
            return _H1_ID_PREFIX_RE.sub("", m.group(1)).strip()
    return ""


@dataclass
class EmitStats:
    """**我印了幾列、其中幾列是空的。**

    `設計原則.md` E2 的兩條推論合起來：印「我檢查／輸出了幾筆」（0 也印），
    再印「命中的筆數裡有幾筆是空的」（06 補）——只印前者＝用命中率冒充可用率。
    這裡的「空」＝該源檔取不到 H1，那一欄會是空白。
    """

    rows: int = 0
    blank_titles: int = 0
    legacy: list[tuple[str, int]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def render(self, unit: str = "列") -> str:
        legacy = (
            "、".join(f"`{n}`（{b:,} B）" for n, b in self.legacy)
            if self.legacy
            else "無"
        )
        return (
            f"投影 {self.rows} {unit}"
            f"（**其中 {self.blank_titles} {unit}取不到源檔 H1**）；"
            f"舊 rollup 檔殘留：{legacy}"
        )


def scan_legacy(book: Path, rels: tuple[str, ...], stats: EmitStats) -> None:
    """殘留偵測。**在渲染覆蓋率之前跑**——先渲染再掃，覆蓋率那一格會恆為 0，
    而末節同時印「在」：一支自己跟自己矛盾的報表，正是它要抓的那種病
    （形狀照抄 `structure_project._scan_legacy`）。"""
    for rel in rels:
        p = book.joinpath(*rel.split("/"))
        if p.is_file():
            stats.legacy.append((rel, len(read_text(p).encode("utf-8"))))


def legacy_section(
    stats: EmitStats, rels: tuple[str, ...], provenance: tuple[tuple[str, str], ...]
) -> list[str]:
    """末節：舊 rollup 在不在 ＋ 逐格「內容去哪了」（`設計原則.md` D3／A5 的驗收）。

    **0 也印。** 不在時印一行「不在」——那一行才代表「這本書已經遷完了」。
    """
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


# ---------------------------------------------------------------- 幕綱索引

BEAT_LEGACY = ("story/幕綱/_index.md",)
BEAT_PROVENANCE: tuple[tuple[str, str], ...] = (
    ("甲 `arcNN` 欄", "`story/幕綱/` 底下的 `arcNN.md`（檔名即 ID·C1）"),
    ("乙 幕號範圍", "該檔的 `## 幕NNN` 標題 min·max（`beat-lint` 早就在比對）"),
    ("丙 號段", "規則：arcNN ＝ 幕((NN-1)×100+1)…幕(NN×100)（`幕綱.schema.md`）"),
    ("丁 名稱", "該 `arcNN.md` 的 H1（抉擇 3 B：摘要欄廢除，改印源檔 H1）"),
    ("戊 arc 概覽散文", "**無獨立來源**——該 arc 檔本身的第三版改寫（實測 8-gram 保真率僅 4.2–35.8%）"),
    ("己 `選用結構公式：` 行", "大綱的 `## 選用結構公式`（功能 11 定的家，`outline-lint` 第 12 項守）"),
    ("庚 `全書順序：` 行", "**無機械來源＝它是源** → 同層的 `_順序.md`（A1，`beat-lint` 守）"),
    ("辛 檔頭沿革 blockquote", "拍板理由→`story/參照/裁決流.md`｜進度→`readiness` 投影"),
)


def emit_beats(book: Path) -> tuple[str, EmitStats]:
    """幕綱索引投影：`arcNN｜幕號範圍｜號段｜名稱`。

    **`結構階段` 那一欄刻意不進來**：`structure-project` 第二節已經在印階段 ↔ 幕，
    複述就是同一個病的第 12 次。檔頭改印一行指路（09 立的「不複述、只指路」判準）。
    """
    stats = EmitStats()
    scan_legacy(book, BEAT_LEGACY, stats)
    arcs = parse_book(book)

    lines = [
        f"## 幕綱索引投影 {book.name}（{len(arcs)} 支 arc；零 LLM、可覆算）",
        "",
        f"> 取代舊 `story/幕綱/_index.md` 的 arc 列（功能 12 抉擇 1 A）。"
        f"`全書順序：` 不在這裡——它是源，住 `story/幕綱/{SPINE_FILES[0]}`；"
        f"**階段 ↔ 幕跑 `structure-project`**；選用公式的權威是大綱的 "
        f"`## 選用結構公式`。",
        "",
        "| arc | 幕號範圍 | 號段 | 名稱（源檔 H1） |",
        "|-----|---------|------|----------------|",
    ]
    for a in arcs:
        stats.rows += 1
        span = (
            f"幕{min(b.number for b in a.beats):03d}–幕{max(b.number for b in a.beats):03d}"
            if a.beats
            else "（尚未拆幕）"
        )
        m = _ARC_NUM_RE.match(a.arc)
        block = (
            f"{(int(m.group(1)) - 1) * BLOCK + 1:03d}–{int(m.group(1)) * BLOCK:03d}"
            if m
            else "—"
        )
        title = h1(a.path)
        if not title:
            stats.blank_titles += 1
        if a.skeleton:
            title = f"{title}（骨架·`{SKELETON_MARK}`）" if title else f"（骨架·`{SKELETON_MARK}`）"
        lines.append(f"| {a.arc} | {span} | {block} | {title or '（源檔無 H1）'} |")
    if not arcs:
        lines.append("| （0 支 arc） | — | — | — |")

    lines += ["", stats.render(), ""]
    lines += legacy_section(stats, BEAT_LEGACY, BEAT_PROVENANCE)
    return "\n".join(lines).rstrip() + "\n", stats


# ---------------------------------------------------------------- 大綱索引

OUTLINE_LEGACY = ("story/大綱/_index.md",)
OUTLINE_PROVENANCE: tuple[tuple[str, str], ...] = (
    ("甲 `arcNN` 欄", f"`story/大綱/` 與 `story/大綱/{RETIRED_DIR}/` 底下的 `arcNN.md`"),
    ("乙 名稱", "該檔的 H1（實測 11/11 一字不差；抉擇 3 B）"),
    ("丙 狀態", "該檔的檔頭狀態行（`outline-lint` 第 2 項早就在解析它）"),
    ("丁 逐題發落紀錄／回填條件的歷史", "**無獨立來源** → `story/參照/裁決流.md`（`標的`＝該大綱檔）"),
    ("戊 `## 卷一整體結構` 節", "大綱的 `## 選用結構公式`（功能 11 定的家）——**索引不得有任何 `##` 節**"),
    ("己 檔頭沿革 blockquote", "拍板理由→`story/參照/裁決流.md`｜進度→`readiness` 投影"),
)


def emit_outline(book: Path) -> tuple[str, EmitStats]:
    """大綱索引投影：`arcNN｜名稱｜狀態`。**schema 規定的一列形狀 100% 可投影。**"""
    stats = EmitStats()
    scan_legacy(book, OUTLINE_LEGACY, stats)
    files = [f for f in load_files(book) if f.arc]

    lines = [
        f"## 大綱索引投影 {book.name}（{len(files)} 支 scoped 大綱；零 LLM、可覆算）",
        "",
        f"> 取代舊 `story/大綱/_index.md`（功能 12 抉擇 1 A）。`{FULL_NAME}` 是全書版，"
        f"不進本表；`{RETIRED_DIR}/` 底下的退役源**進表**（A5：視圖要涵蓋退役源，"
        f"否則「已併入」與「不存在」看起來一樣）。",
        "",
        "| arc | 名稱（源檔 H1） | 狀態 | 住哪 |",
        "|-----|----------------|------|------|",
    ]
    for f in sorted(files, key=lambda x: (x.arc or "", x.kind)):
        stats.rows += 1
        title = h1(f.path)
        if not title:
            stats.blank_titles += 1
        where = f"`大綱/{RETIRED_DIR}/`" if f.kind == "已併入" else "`大綱/`"
        lines.append(
            f"| {f.arc} | {title or '（源檔無 H1）'} | {f.status or '（無狀態標記）'} | {where} |"
        )
    if not files:
        lines.append("| （0 支 scoped 大綱） | — | — | — |")

    lines += ["", stats.render(), ""]
    lines += legacy_section(stats, OUTLINE_LEGACY, OUTLINE_PROVENANCE)
    return "\n".join(lines).rstrip() + "\n", stats


# ---------------------------------------------------------------- 章序

CH_LEGACY = ("chapters/_index.ai.md",)
CH_PROVENANCE: tuple[tuple[str, str], ...] = (
    ("甲 `章` 欄", "`chapters/` 底下的 `chNNNN.md`（檔名即 ID·C1）"),
    ("乙 `對應幕`", "`chNNNN.ai.md` 的 front-matter ＋正文 `<!-- 幕NNN -->` 錨點（`ch-lint` 早就在比對）"),
    ("丙 `所屬arc`／`POV`／`風格`／`狀態`", "`chNNNN.ai.md` 的 front-matter（同上）"),
    ("丁 章名", "`chNNNN.md` 的 H1（抉擇 3 B：`備註` 欄廢除，改印源檔 H1）"),
    ("戊 `備註` 欄的章摘要", "**無獨立來源**——LLM 每次重生重寫的一句話（實測 13,874 字元＝該檔 77.6% 獨有）"),
    ("己 `章末狀態快照` 殘骸", "跑 `fact-project --as-of <該章末幕>`，**不落檔**（`章節.schema.md` 早已廢除該節）"),
)


def emit_chapters(book: Path) -> tuple[str, EmitStats]:
    """章序投影：`章｜對應幕｜所屬arc｜POV｜風格｜狀態｜章名`。

    **它是章序的權威**（不是檔名）：亂序下沉時 `對應幕` 才是章 ↔ 幕的權威對映。
    `ch-lint` 第 8 項為了比對，早就必須先算出這 93 列六欄（實測 0 不一致）。
    """
    stats = EmitStats()
    scan_legacy(book, CH_LEGACY, stats)
    metas: list[ChapterMeta] = load_metas(book)
    d = book / "chapters"

    lines = [
        f"## 章序投影 {book.name}（{len(metas)} 章；零 LLM、可覆算）",
        "",
        "> 取代舊 `chapters/_index.ai.md`（功能 12 抉擇 1 A）。**這是章序的權威**"
        "——亂序下沉時 `對應幕` 才是章 ↔ 幕的權威對映，章號只是檔名。"
        "反查「某個 arc 有哪幾章」就篩 `所屬arc` 那一欄。",
        "",
        "| 章 | 對應幕 | 所屬arc | POV | 風格 | 狀態 | 章名（源檔 H1） |",
        "|----|--------|---------|-----|------|------|----------------|",
    ]
    for m in metas:
        stats.rows += 1
        if m.first is None:
            span = "—"
        elif m.last is None or m.first == m.last:
            span = f"幕{m.first:03d}"
        else:
            span = f"幕{m.first:03d}–幕{m.last:03d}"
        pov = _POV_ROLE_RE.search(m.keys.get("POV", ""))
        title = h1(d / f"{m.stem}.md")
        if not title:
            stats.blank_titles += 1
        lines.append(
            f"| {m.stem} | {span} | {m.keys.get('所屬arc', '—')} | "
            f"{pov.group(1).strip() if pov else '—'} | {m.keys.get('風格', '—')} | "
            f"{m.keys.get('狀態', '—')} | {title or '（源檔無 H1）'} |"
        )
    if not metas:
        lines.append("| （0 章） | — | — | — | — | — | — |")

    lines += ["", stats.render("章"), ""]
    lines += legacy_section(stats, CH_LEGACY, CH_PROVENANCE)
    return "\n".join(lines).rstrip() + "\n", stats


__all__ = [
    "AI_SUFFIX",
    "OUTLINE_DIR",
    "EmitStats",
    "emit_beats",
    "emit_chapters",
    "emit_outline",
    "h1",
]
