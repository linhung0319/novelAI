"""大綱層格式閘門（`outline-lint`）。

**為什麼這支工具存在。** 大綱是全系統唯一一個「**被 `共同約定.md` 明文列進「強格式源·
一支 lint」那一格、而那支 lint 不存在**」的產物——`共同約定.md:24` 的表格把它排在
「大綱、幕綱（`beat-lint`）、物件檔（`object-lint`）、裁決流（`decision-lint`）」的
第一位，**只有它後面沒有掛工具名**，同表另一處還寫著「嚴格（**有 lint**）」。
`CLAUDE.md` 的分類公理逐字複製了同一句。

這與功能 04 抓到的病**完全同形**：同一張表曾同時宣稱 `.co.md` 是「嚴格（有檢查器）」，
04 的報告把那句話當作「口頭承諾」的證物——**同一張表上的同一個假宣稱，換了一個主詞，
活到今天**（`設計原則.md` E1）。

**取值者確實存在，只是是 LLM**（A4 2026-07-27 功能 07 改寫後的判準，指得出行號）：
`beat-sheet/SKILL.md`「讀取（含選用結構公式、結局、題旨）」＝逐節取值；
`outline-test/SKILL.md` 測試 1／2 自稱「檢查欄位非空（機械）」「**正則檢查句型**
是否含『因為…導致』（機械）」——**宣稱是機械的，而沒有那支程式**；
`expand`／`organize` 各指名「本段全文」「本段收束與鉤子」。
`大綱.schema.md` 的 7 條檢查點 **0 條有實作**。

實測代價是一條乾淨的曲線（一世之尊 11 支 arc 檔、5 天）：
`本段全文` 佔全檔 **54.0% → 11.1%**，同期 **schema 枚舉外的節 0% → 64%**，
最大的一塊是 `## 本 arc 伏筆狀態`（6 支檔、28,941 字元），而它逐字就是
`foreshadow-project` 的輸出——三份同源資料，一份有工具、一份有 `beat-lint`、
一份什麼都沒有，兩側 8-gram 重疊從 arc06 的 55.8% 掉到 arc11 的 **8.4%**。
全程零警報：四支成長哨兵目標集 **0/4** 含 `story/大綱/`。

**為什麼住在 `beat_metrics` 而不是自己開一個套件**（作者拍板抉擇 1 B）：第 4 項要的
**幕號 registry** 就是同套件的 `structure.parse_book()`，第 5 項要的伏筆 regex
`beat-lint` 已經在用。另開套件＝新增第 7 份幕號集合實作。`beat-lint` 驗幕綱、
`ch-lint` 驗正文、`outline-lint` 驗大綱——**三個指令、一份解析層**。

**守的是「人破結構」那一側**（`設計原則.md` B1）：節、狀態標記、`[[伏筆:x]]`、
`幕NNN`／`chNNNN`／`arcNN` 引用全是人手打的結構與識別符。**內容好壞不歸它**：
結局定不定得了、立場一不一致、結構公式覆蓋得夠不夠，交 `outline-test`（LLM 審稿）。

**判準一律是結構或位置判準，不得用詞表**（`prose-metrics` 關鍵詞分類／世界觀主題
別名表／幕綱集合名對照表三次被駁回的形狀）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .scan import ScanError, read_text
from .structure import SKELETON_MARK, parse_book

# ------------------------------------------------------------------ 常數

OUTLINE_DIR = ("story", "大綱")
FULL_NAME = "01-大綱.md"
INDEX_NAME = "_index.md"
# 退役源的家（`設計原則.md` A5，2026-07-28 功能 09 新增）。**併入不是刪除，也不是
# 在檔頭寫一句話就算數**——身分只能被另一支檔的存在撤銷，而撤銷要從檔案系統看得出來。
RETIRED_DIR = "_已併入"

_ARC_FILE_RE = re.compile(r"^arc(\d+)$")
_ARC_TOKEN_RE = re.compile(r"arc(\d+)")
# `arc01–arc04`／`arc01—arc04`／`arc01-arc04`：`01-大綱.md` 實際在用的範圍寫法。
_ARC_RANGE_RE = re.compile(r"arc(\d+)\s*[–—-]\s*arc(\d+)")
_BEAT_TOKEN_RE = re.compile(r"幕(\d+)")
_CH_TOKEN_RE = re.compile(r"ch(\d{4})")
# 唯一真相在 `foreshadow_project/scan.py:_MARK_RE`；工具間零相依，故複製最小片段
# （同 `structure.py` 檔頭的理由）。大綱層**不分埋／收**——那是幕綱的事，這裡只問
# 「這個名字在不在 registry 裡」。
_FORESHADOW_RE = re.compile(r"\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]")
_H2_RE = re.compile(r"^##\s+(.*?)\s*$")
_INDEX_ROW_RE = re.compile(r"^-\s*arc(\d+)\s*[：:]")
_BULLET_RE = re.compile(r"^-\s*(.+?)\s*[：:]")
_SEP_ROW_RE = re.compile(r"^\|[\s:|-]+\|$")

# 節枚舉（`大綱.schema.md`「節枚舉」）。比對前先正規化標題（見 `_label`）。
# `卷級方向` 兩種變體都收：scoped 檔一支一卷；`01-大綱.md` 併入後可同時帶好幾卷，
# 所以卷 token 寫在括號裡（見 `_volume_token`）。
FULL_SECTIONS = frozenset({"選用結構公式", "故事全文", "結局與題旨", "卷級方向"})
SCOPED_SECTIONS = frozenset(
    {"選用結構公式", "本段全文", "本段收束與鉤子", "本 arc 伏筆狀態", "卷級方向"}
)
PROSE_SECTION_FULL = "故事全文"
PROSE_SECTION_SCOPED = "本段全文"
STATUS_SECTION = "本 arc 伏筆狀態"
VOLUME_SECTION = "卷級方向"
ENDING_SECTION = "結局與題旨"
CLOSING_SECTION = "本段收束與鉤子"

# 檔頭狀態的兩個標記（`大綱.schema.md`「檔頭狀態」）。**判定規則寫死：`已併入` 優先**
# ——實測 arc01–08 兩者並存（併入時在原註之上再加一行），而那是合法的沿革寫法。
MERGED_MARK = "已併入"
TENTATIVE_MARK = "暫定"

# 結局欄不得出現的模糊詞（`outline-test` 測試 1 自稱「機械」的那一半）。
# **這是字面比對，不是詞表分類**——它問的是「有沒有寫著『還沒定』」，不是
# 「這段文字算不算已定」。後者是 `outline-test` 的 LLM 判斷。
UNDECIDED_WORDS = ("待定", "未定", "大概")
# 題旨的可檢查句型（`主題題旨.md`「因為 X 導致 Y」）。
THESIS_PATTERN = re.compile(r"因為.*(導致|所以)")

CLOSING_LABELS = ("本段收束", "鉤子", "對全書結局")

# 第 9 項：只認**書內相對路徑**。schema 檔、知識庫、佔位寫法（`arcNN.md`）、
# 範圍寫法（`arc01–arc04.md`）都不是「指名一個檔」，逐一排除——不排除的話，
# 一支合法的大綱會因為引用了自己的 schema 而被報成「目的地不存在」。
_MD_REF_RE = re.compile(r"`([^`\n]+?\.md)`")
BOOK_PREFIXES = ("story/", "chapters/", "參照/", "幕綱/", "大綱/", "設定/", "物件/")
_PLACEHOLDER_RE = re.compile(r"(arcNN|chNNNN|<[^>]+>|＜[^＞]+＞|NNNN|NNN)")


# ------------------------------------------------------------------ 資料結構


@dataclass
class OutlineFile:
    """一支大綱檔。`kind` ∈ {全書, scoped, 已併入}。"""

    path: Path
    kind: str
    arc: str | None
    text: str
    skeleton: bool = False
    sections: list[tuple[int, str, str]] = field(default_factory=list)  # (行號, 正規化名, 原標題)
    header: str = ""  # 第一個 `##` 之前的內容

    @property
    def where(self) -> str:
        if self.kind == "已併入":
            return f"大綱/{RETIRED_DIR}/{self.path.name}"
        if self.kind == "全書":
            return self.path.name
        return f"大綱/{self.path.name}"

    def body(self, name: str) -> str | None:
        """取某一節的內容（不含標題行）。同名多節取第一個。"""
        for i, (lineno, label, _raw) in enumerate(self.sections):
            if label != name:
                continue
            end = (
                self.sections[i + 1][0] - 1
                if i + 1 < len(self.sections)
                else len(self.text.splitlines())
            )
            return "\n".join(self.text.splitlines()[lineno:end])
        return None

    @property
    def status(self) -> str | None:
        if MERGED_MARK in self.header:
            return MERGED_MARK
        if TENTATIVE_MARK in self.header:
            return TENTATIVE_MARK
        return None


@dataclass
class OutlineStats:
    """**我在這本書上檢查了幾筆。**（`設計原則.md` E2 的可執行推論，0 也印。）

    最需要這一行的是 `prose_share`：**「本段全文佔全檔多少」是「這一軸還在不在做
    它該做的事」的單一數字**。實測一世之尊那條曲線是 54.0%（arc01）→ 11.1%（arc11），
    而它在 11 個 arc、5 天裡沒有被任何東西看見過——問題數再多也講不出這件事，
    因為每一支檔單獨看都「只是多了幾個節」。

    次要的是 `beat_refs`／`ch_refs`：它們現在懸空 0，是人手維持的乾淨，不是系統
    保證的乾淨；哪天印 0 條引用，那不是乾淨，是解析器沒讀到檔。
    """

    files: int = 0
    full: int = 0
    scoped: int = 0
    retired: int = 0
    skeletons: int = 0
    total_chars: int = 0
    prose_chars: int = 0
    prose_min: tuple[str, float] | None = None
    stray_sections: int = 0
    stray_worst: tuple[str, str, int] | None = None  # (檔, 節名, 字元數)
    beat_refs: int = 0
    beat_dangling: int = 0
    ch_refs: int = 0
    ch_dangling: int = 0
    arc_refs: int = 0
    arc_resolved: int = 0
    foreshadow_hits: int = 0
    foreshadow_names: int = 0
    foreshadow_unknown: int = 0
    index_rows: int = 0
    index_mismatch: int = 0
    index_unordered: int = 0
    path_refs: int = 0
    path_missing: int = 0
    volume_sections: int = 0
    volume_tokens: int = 0
    covered_arcs: int = 0
    unmerged_scoped: int = 0
    both_homed: int = 0
    ending_copy: str = "未比對"
    merged_in_place: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    @property
    def prose_share(self) -> float:
        return self.prose_chars / self.total_chars if self.total_chars else 0.0

    def render(self) -> str:
        worst = (
            f"（最大 {self.stray_worst[2]} 字元＝{self.stray_worst[0]} 的 "
            f"`## {self.stray_worst[1]}`）"
            if self.stray_worst
            else ""
        )
        low = (
            f"（最低 {self.prose_min[0]}＝{self.prose_min[1]:.1%}）" if self.prose_min else ""
        )
        return "\n".join(
            [
                f"檢查範圍：{self.files} 支大綱檔"
                f"（{self.full} 支全書版／{self.scoped} 支 scoped／"
                f"{self.retired} 支在 `{RETIRED_DIR}/`）；跳過 {self.skeletons} 支骨架",
                f"          連續敘述佔全檔 {self.prose_share:.1%}{low}"
                f"／枚舉外節 {self.stray_sections} 個{worst}",
                f"          幕引用 {self.beat_refs} 筆（懸空 {self.beat_dangling}）／"
                f"章引用 {self.ch_refs} 筆（懸空 {self.ch_dangling}）／"
                f"arc 引用 {self.arc_refs} 筆"
                f"（{self.arc_resolved} 筆指得到既有 arc 檔·**裸 token 無守衛**）",
                f"          伏筆標記 {self.foreshadow_hits} 處（{self.foreshadow_names} 名，"
                f"registry 查無 {self.foreshadow_unknown}）／"
                f"卷級方向 {self.volume_sections} 節（{self.volume_tokens} 個卷 token）",
                f"          `{INDEX_NAME}` {self.index_rows} 列 vs 資料夾 "
                f"{self.scoped + self.retired} 支（不一致 {self.index_mismatch}／"
                f"列序非遞增 {self.index_unordered} 處）／"
                f"檔內路徑引用 {self.path_refs} 個（{self.path_missing} 個不存在）",
                f"          `{FULL_NAME}` 涵蓋 {self.covered_arcs} 個 arc／"
                f"未併入的 scoped {self.unmerged_scoped} 支（兩邊都有內容 {self.both_homed} 支）"
                f"／`{FULL_NAME}` 是否仍帶結局複本：{self.ending_copy}",
            ]
        )


@dataclass(frozen=True)
class Problem:
    where: str
    detail: str
    hint: str = ""

    def __str__(self) -> str:  # 問題字串一律以位置起頭（同 `beat-lint`）
        return f"{self.where}：{self.detail}" + (f"——{self.hint}" if self.hint else "")


# ------------------------------------------------------------------ 解析


def _label(raw: str) -> str:
    """`## 選用結構公式（本 arc 適用）` → `選用結構公式`。

    剝粗體與 `⚠️`、切到第一個全／半形左括號為止。**形狀照抄 `structure._label`**
    ——標籤怎麼裝飾不該決定它算不算 schema 定義的節（實測作者兩種寫法都在用）。
    """
    s = raw.replace("*", "").replace("⚠️", "").replace("⚠", "").strip()
    return re.split(r"[（(]", s, maxsplit=1)[0].strip()


def _volume_token(raw: str) -> str | None:
    """`## 卷級方向（卷三·本卷權威）` → `卷三`。

    **為什麼卷 token 要寫在標題裡**（2026-07-28 作者拍板）：抉擇 6 要驗「同一卷
    至多一支檔有這一節」，而「哪些 arc 屬同一卷」在系統裡**沒有任何機讀宣告**
    （`_index.md` 的卷分組是散文、arc 編號也不隱含卷界）。依 E1，驗不到就不該宣稱
    ——所以把卷寫進節名，讓「同一卷」變成一個可比對的字串。順帶解掉併入之後
    `01-大綱.md` 同時帶好幾卷會撞節名的問題。
    """
    m = re.search(r"[（(]\s*(卷[^·・\s（()）]+)", raw)
    return m.group(1) if m else None


def _sections(text: str) -> tuple[list[tuple[int, str, str]], str]:
    lines = text.splitlines()
    out: list[tuple[int, str, str]] = []
    for i, raw in enumerate(lines, start=1):
        m = _H2_RE.match(raw)
        if m:
            out.append((i, _label(m.group(1)), m.group(1)))
    head_end = out[0][0] - 1 if out else len(lines)
    return out, "\n".join(lines[:head_end])


def _index_file(book: Path) -> OutlineFile | None:
    """索引也算大綱層的一支檔——**只進文字層的檢查**（引用／伏筆／路徑），
    不進節枚舉與狀態那幾項（它沒有那些節）。

    漏掉它會讓覆蓋率行少算 18 筆幕引用與 22 筆章引用（實測一世之尊 146→164、
    84→106）——而索引正是最會抄下游 ID 的那一支。
    """
    p = book.joinpath(*OUTLINE_DIR, INDEX_NAME)
    if not p.is_file():
        return None
    text = read_text(p)
    sections, header = _sections(text)
    return OutlineFile(p, "索引", None, text, SKELETON_MARK in text, sections, header)


def load_files(book: Path) -> list[OutlineFile]:
    """收齊三種大綱檔。`01-大綱.md` 與 `大綱/` 都不存在時硬報錯，不靜默回空集合。"""
    out: list[OutlineFile] = []
    full = book.joinpath(*OUTLINE_DIR[:1], FULL_NAME)
    if full.is_file():
        text = read_text(full)
        sections, header = _sections(text)
        out.append(
            OutlineFile(full, "全書", None, text, SKELETON_MARK in text, sections, header)
        )
    d = book.joinpath(*OUTLINE_DIR)
    for sub, kind in ((d, "scoped"), (d / RETIRED_DIR, "已併入")):
        if not sub.is_dir():
            continue
        for p in sorted(sub.glob("*.md")):
            if not _ARC_FILE_RE.match(p.stem):
                continue
            text = read_text(p)
            sections, header = _sections(text)
            out.append(
                OutlineFile(
                    p, kind, p.stem, text, SKELETON_MARK in text, sections, header
                )
            )
    if not out:
        raise ScanError(
            f"找不到任何大綱檔：{full} 不存在，{d} 底下也沒有 arcNN.md"
        )
    return out


# ------------------------------------------------------------------ 各項檢查


def _check_sections(f: OutlineFile, stats: OutlineStats) -> list[Problem]:
    """第 1 項：節枚舉。

    **一支檔一行**（03 拍板的聚合判準）：同一支檔裡的枚舉外節病因與修法完全相同
    （內容找不到家而寄生在大綱檔裡），逐節一行只會把真正該看的別項淹掉。
    """
    allowed = FULL_SECTIONS if f.kind == "全書" else SCOPED_SECTIONS
    stray = [(ln, label) for ln, label, _ in f.sections if label not in allowed]
    if not stray:
        return []
    lines = f.text.splitlines()
    for i, (lineno, label, _raw) in enumerate(f.sections):
        if label in allowed:
            continue
        end = f.sections[i + 1][0] - 1 if i + 1 < len(f.sections) else len(lines)
        size = len("\n".join(lines[lineno:end]))
        if stats.stray_worst is None or size > stats.stray_worst[2]:
            stats.stray_worst = (f.where, label, size)
    stats.stray_sections += len(stray)
    listed = "、".join(f"第 {ln} 行「{label}」" for ln, label in stray[:5])
    if len(stray) > 5:
        listed += "…"
    return [
        Problem(
            f.where,
            f"{len(stray)} 個枚舉外的 `##` 節：{listed}",
            "大綱的節是封閉枚舉（`大綱.schema.md`「節枚舉」）。"
            "逐題發落紀錄／拍板來歷／護欄推導屬 story/參照/裁決流.md；"
            "本 arc 不引爆哪條線＝承諾，屬幕綱的 `## 本 arc 承諾`；"
            "既成的伏筆埋收由 foreshadow-project 回答；"
            "卷級方向要寫成 `## 卷級方向（卷X·本卷權威）`",
        )
    ]


def _check_header_status(f: OutlineFile, stats: OutlineStats) -> list[Problem]:
    """第 2 項：檔頭狀態二選一，且與它住的目錄一致（A5）。"""
    if f.kind == "全書":
        return []
    st = f.status
    if st is None:
        return [
            Problem(
                f.where,
                "檔頭沒有狀態標記",
                f"scoped 大綱恰要一個：`⚠️ 暫定，待粗層鎖定`（還沒併入）"
                f"或 `⚠️ 已併入 {FULL_NAME}（日期）`（已退役，且該搬進 "
                f"`大綱/{RETIRED_DIR}/`）",
            )
        ]
    if f.kind == "已併入" and st != MERGED_MARK:
        return [
            Problem(
                f.where,
                f"住在 `{RETIRED_DIR}/` 卻標「{st}」",
                f"`{RETIRED_DIR}/` 底下一律是已併入的退役源（`設計原則.md` A5）",
            )
        ]
    if f.kind == "scoped" and st == MERGED_MARK:
        # **不是格式錯，是還沒遷移。** 一世之尊是刻意不遷移的病例書，把 8 支報成
        # 問題只會製造警報疲勞；但它必須可見——那正是 A5 要解的那一格
        # （身分被自己檔內的一句話撤銷，而檔案系統看不出來）。
        # 聚合成一行（03 拍板的判準：同型且修法相同）。
        stats.merged_in_place.append(f.arc or f.path.name)
    return []


def _check_status_table(f: OutlineFile) -> list[Problem]:
    """第 10 項：`## 本 arc 伏筆狀態` ＝三欄意圖表（抉擇 2 B）。

    **收窄的理由**：舊的四欄裡 `埋設` 欄逐字就是 `foreshadow-project` 的輸出
    （`arc09 幕808（幕級首次埋設點）`／`arc04 幕307（正文 ch0028）`），而那是
    **既成事實**——大綱層抄它只會漂（實測兩側 8-gram 重疊 arc06 55.8% → arc11 8.4%，
    而 `foreshadow-project` 印「0 條為可疑點」exit 0，因為大綱那 28,941 字元根本
    不在它的射程裡）。留下來的是**意圖**：這一 arc 我打算怎麼動這條線、為什麼。
    意圖沒有重算規則，是 A1 乾淨的源。
    """
    body = f.body(STATUS_SECTION)
    if body is None:
        return []
    out: list[Problem] = []
    widths: set[int] = set()
    for raw in body.splitlines():
        line = raw.strip()
        if not line.startswith("|") or _SEP_ROW_RE.match(line):
            continue
        widths.add(len([c for c in line.strip().strip("|").split("|")]))
    bad = sorted(w for w in widths if w != 3)
    if bad:
        out.append(
            Problem(
                f.where,
                f"`## {STATUS_SECTION}` 有 {'／'.join(str(w) for w in bad)} 欄的列"
                f"（schema 定三欄）",
                "三欄＝`伏筆｜本 arc 打算怎麼動（埋/推/收/不碰）｜為什麼`。"
                "既成的埋設點與回收點跑 "
                "`foreshadow-project --book <書> --arc arcNN`，別在這裡抄第三份",
            )
        )
    facts = sorted(
        {m.group(0) for m in _BEAT_TOKEN_RE.finditer(body)}
        | {m.group(0) for m in _CH_TOKEN_RE.finditer(body)}
    )
    if facts:
        shown = "、".join(facts[:6]) + ("…" if len(facts) > 6 else "")
        out.append(
            Problem(
                f.where,
                f"`## {STATUS_SECTION}` 出現 {len(facts)} 個既成事實 token：{shown}",
                "本節只寫**意圖**（打算怎麼動、為什麼）。幕號與章號是幕綱與正文的"
                "既成事實，由 `foreshadow-project --arc arcNN` 回答——"
                "抄進來就是第三份會漂的複本",
            )
        )
    return out


def _check_volume(files: list[OutlineFile], stats: OutlineStats) -> list[Problem]:
    """第 11 項：卷級方向（抉擇 6 B ＋ `設計原則.md` F2 第五格）。

    射程＝一整卷的裁決，四格（單一實體／單一源檔／單一 arc／全書）**全落不進去**，
    於是實測那 5,079 字元寄生在 arc09 的檔頭 blockquote 裡、自稱「權威長版」，
    並自己複製了兩份出去（`參照/結構.md` 321 個共同 8-gram、`_index.md` 239 個），
    三份之間零比對。F2 因此補上第五格，這一項是它的閘門。
    """
    out: list[Problem] = []
    by_token: dict[str, list[OutlineFile]] = {}
    for f in files:
        for lineno, label, raw in f.sections:
            if label != VOLUME_SECTION:
                continue
            stats.volume_sections += 1
            token = _volume_token(raw)
            if token is None:
                out.append(
                    Problem(
                        f.where,
                        f"第 {lineno} 行 `## {raw}` 沒有卷 token",
                        "節名要寫成 `## 卷級方向（卷X·本卷權威）`——"
                        "卷界在系統裡沒有別的機讀宣告，"
                        "沒有 token 就驗不出「同一卷至多一支」（E1）",
                    )
                )
                continue
            by_token.setdefault(token, []).append(f)
            if f.kind == "已併入":
                out.append(
                    Problem(
                        f.where,
                        f"`{RETIRED_DIR}/` 底下有 `## 卷級方向（{token}…）`",
                        f"卷級方向是**仍在生效的方向宣告**，不是沿革——併入時要"
                        f"一併升進 `{FULL_NAME}`，不能跟著退役源一起被降級",
                    )
                )
    stats.volume_tokens = len(by_token)
    for token, owners in sorted(by_token.items()):
        if len(owners) > 1:
            out.append(
                Problem(
                    "大綱/",
                    f"卷 token「{token}」的 `## 卷級方向` 出現在 "
                    f"{len(owners)} 支檔：{'、'.join(o.where for o in owners)}",
                    "一卷只有一份權威（F2 第五格：落點＝該卷第一個 arc 的大綱檔）。"
                    "其餘檔只准指路",
                )
            )
        authority = {o.path for o in owners}
        for f in files:
            if f.path in authority:
                continue
            for i, raw in enumerate(f.text.splitlines(), start=1):
                if VOLUME_SECTION not in raw:
                    continue
                if "大綱/arc" in raw or FULL_NAME in raw:
                    continue
                out.append(
                    Problem(
                        f.where,
                        f"第 {i} 行提到「{VOLUME_SECTION}」卻沒有帶指標",
                        f"同卷其餘檔**只准指路、不准複述**（形狀照抄 "
                        f"`幕綱/arc10.md` 的「不複述、只指路」）："
                        f"那一行要帶 `大綱/arcNN.md` 或 `{FULL_NAME}` 的路徑",
                    )
                )
                break
    return out


def _check_ending(f: OutlineFile, stats: OutlineStats) -> list[Problem]:
    """第 6 項：`結局與題旨` 的形狀。

    **這正是 `outline-test` 測試 1／2 宣稱「機械」而零實作的那兩條**
    （`:22`「檢查欄位非空（機械）」、`:23`「正則檢查句型是否含『因為…導致』（機械）」）
    ——四處「機械」欄全部由 LLM 在腦內執行了整段開發期。
    """
    body = f.body(ENDING_SECTION)
    if body is None:
        return [
            Problem(
                f.where,
                f"缺 `## {ENDING_SECTION}` 節",
                "全書版的定稿門檻就是它（`大綱.schema.md`「規則」：沒有結局，"
                "大綱不算定稿）",
            )
        ]
    out: list[Problem] = []
    bullets: dict[str, str] = {}
    for raw in body.splitlines():
        m = _BULLET_RE.match(raw.strip())
        if m:
            label = m.group(1).replace("*", "").strip()
            bullets.setdefault(_label(label), raw.split("：", 1)[-1].strip())
    ending = bullets.get("結局")
    if ending is None:
        out.append(Problem(f.where, f"`## {ENDING_SECTION}` 缺 `結局：` 這一格"))
    else:
        if not ending:
            out.append(Problem(f.where, "`結局：` 是空的"))
        hits = [w for w in UNDECIDED_WORDS if w in ending]
        if hits:
            out.append(
                Problem(
                    f.where,
                    f"`結局：` 帶模糊字樣 {'、'.join(hits)}",
                    "結局已定是全書版的定稿門檻（結局是回頭修正前文的樞紐）。"
                    "還沒定就走 scoped 大綱，別讓全書版假裝定稿了",
                )
            )
        stats.ending_copy = (
            "否（已是指標）"
            if "00-摘要" in ending
            else "**是**（該切乾淨：「結局是什麼」回指 `00-摘要.md`「結局方向」，"
            "本節只寫通向它的情節路徑）"
        )
    thesis = bullets.get("題旨")
    if thesis is None:
        out.append(Problem(f.where, f"`## {ENDING_SECTION}` 缺 `題旨：` 這一格"))
    elif not THESIS_PATTERN.search(thesis):
        out.append(
            Problem(
                f.where,
                "`題旨：` 不是可檢查的因果句",
                "要寫成「因為（X），導致（Y）」（`主題題旨.md`）——"
                "不是因果句就沒有東西可以拿去對照大綱內容",
            )
        )
    return out


def _check_closing(f: OutlineFile) -> list[Problem]:
    """第 7 項：`本段收束與鉤子` 三欄齊全。"""
    body = f.body(CLOSING_SECTION)
    if body is None:
        return [
            Problem(
                f.where,
                f"缺 `## {CLOSING_SECTION}` 節",
                "scoped 大綱的定稿門檻是「本段收束已定」，而不是全書結局已定",
            )
        ]
    missing = [lab for lab in CLOSING_LABELS if lab not in body]
    if missing:
        return [
            Problem(
                f.where,
                f"`## {CLOSING_SECTION}` 缺 {'、'.join(missing)}",
                "三格缺一不可：本段收束（這一段的階段性結果）／鉤子（刻意留給後續的）"
                "／對全書結局・題旨的關係（誠實標未定，不得讓本段收束偽裝成全書結局）",
            )
        ]
    return []


def _check_refs(
    texts: list[OutlineFile],
    files: list[OutlineFile],
    book: Path,
    stats: OutlineStats,
) -> list[Problem]:
    """第 4 項：`幕NNN`／`chNNNN`／`arcNN` 引用不懸空。

    實測一世之尊 164 筆幕引用 ＋ 106 筆章引用**懸空 0**——那是人手維持的乾淨，
    不是系統保證的乾淨：大綱是上游、不會 stale，`beat-lint`／`ch-lint` 只掃自己
    那一層，所以幕號重編或重新分章時，**大綱的錯誤指向會靜靜地活著**，而下游拆幕
    正是照它做的。

    **`arcNN` 這一半刻意不報成問題，只進覆蓋率行**（2026-07-28 實作時改，與報告
    §三 第 4 項的字面「`arcNN` 對資料夾」有出入）：診斷輪提的是「對資料夾比對」，
    而實作時發現**裸 arc token 沒有可靠訊號**——`arc12` 是尚未下沉的未來 arc（合法，
    實測被引用 70 次）、`arc03` 可能是規劃中還沒下沉的中間段（也合法）、
    `01-大綱.md` 涵蓋的卷一四段可能從來沒有 scoped 檔（全書模式直接寫，仍然合法）。
    三種合法狀態與「打錯字」在檔案系統上**長得一模一樣**。依 E1，驗不到就不宣稱：
    報了只會是這一輪自己新增的警報疲勞來源。

    **指標那一半仍然有守衛**：寫成 `story/大綱/arcNN.md` 的路徑引用由第 9 項
    （目的地存在性）逐一驗——「指名一支檔」是可判定的，「提到一個 arc 編號」不是。
    """
    beats = {b.number for a in parse_book(book) for b in a.beats} if _has_beats(book) else set()
    chapters = {
        p.stem
        for p in (book / "chapters").glob("ch*.md")
        if not p.name.endswith(".ai.md")
    }
    present = {f.arc for f in files if f.arc}
    beats_dir = book / "story" / "幕綱"
    if beats_dir.is_dir():
        present |= {p.stem for p in beats_dir.glob("*.md") if _ARC_FILE_RE.match(p.stem)}

    out: list[Problem] = []
    for f in texts:
        dangling_beats: list[str] = []
        dangling_chs: list[str] = []
        for m in _BEAT_TOKEN_RE.finditer(f.text):
            stats.beat_refs += 1
            if beats and int(m.group(1)) not in beats:
                dangling_beats.append(m.group(0))
        for m in _CH_TOKEN_RE.finditer(f.text):
            stats.ch_refs += 1
            if chapters and f"ch{m.group(1)}" not in chapters:
                dangling_chs.append(m.group(0))
        for m in _ARC_TOKEN_RE.finditer(f.text):
            stats.arc_refs += 1
            if f"arc{m.group(1)}" in present:
                stats.arc_resolved += 1
        for kind, hits, why in (
            ("幕", dangling_beats, "全書幕綱找不到這幾幕"),
            ("章", dangling_chs, "chapters/ 底下沒有這幾章"),
        ):
            if not hits:
                continue
            uniq = sorted(set(hits))
            stats.beat_dangling += len(uniq) if kind == "幕" else 0
            stats.ch_dangling += len(uniq) if kind == "章" else 0
            shown = "、".join(uniq[:6]) + ("…" if len(uniq) > 6 else "")
            out.append(
                Problem(
                    f.where,
                    f"{len(uniq)} 個懸空的 {kind} 引用：{shown}",
                    f"{why}。大綱是上游、不會 stale，所以錯誤指向不會有別的守衛撞到"
                    f"——而下游拆幕正是照它做的",
                )
            )
    return out


def _has_beats(book: Path) -> bool:
    return (book / "story" / "幕綱").is_dir()


def _check_foreshadow(
    texts: list[OutlineFile], book: Path, stats: OutlineStats
) -> list[Problem]:
    """第 5 項：`[[伏筆:x]]` 命中既有 registry。形狀照抄 `world-lint` 第 3 項。"""
    registry: set[str] = set()
    beats_dir = book / "story" / "幕綱"
    if beats_dir.is_dir():
        for p in sorted(beats_dir.glob("*.md")):
            registry |= {n.strip() for n in _FORESHADOW_RE.findall(read_text(p))}
    objects = book / "story" / "物件"
    if objects.is_dir():
        registry |= {
            p.stem for p in objects.glob("*.md") if not p.stem.startswith(("_", "."))
        }
    names: dict[str, str] = {}
    for f in texts:
        for m in _FORESHADOW_RE.finditer(f.text):
            stats.foreshadow_hits += 1
            names.setdefault(m.group(1).strip(), f.where)
    stats.foreshadow_names = len(names)
    unknown = sorted(n for n in names if n not in registry)
    if not unknown:
        return []
    stats.foreshadow_unknown = len(unknown)
    shown = "、".join(f"〔{n}〕（{names[n]}）" for n in unknown[:5]) + (
        "…" if len(unknown) > 5 else ""
    )
    return [
        Problem(
            "大綱/",
            f"{len(unknown)}/{len(names)} 個伏筆名在 registry 查無：{shown}",
            "**提示不是門檻**——沒有物件檔的 ID 是合法的（`物件.schema.md` G4）；"
            "但這裡的名字既沒有幕綱標記也沒有物件檔，等於第三份自由造字的名冊（C3）。"
            "正解是改成幕綱既用的那個名字，或開一支 story/物件/<名>.md",
        )
    ]


def _check_index(
    files: list[OutlineFile], book: Path, stats: OutlineStats
) -> list[Problem]:
    """第 3 項：`_index.md` 視圖 ≡ 資料夾（雙向）＋ 列序遞增。

    第 6 份「rollup 視圖 ≡ 資料夾」比對（前五：`ch-lint` 第 6 項／`world-lint` 第 4 項
    ／`char-lint` 第 5 項／`style-lint` 第 6 項／`summary-lint` 第 5 項），而**這一份
    的兩邊是新組合**：Markdown 清單列 ↔ 資料夾（不是表格列、不是 front-matter）
    → 收斂交功能 14。
    """
    index = book.joinpath(*OUTLINE_DIR, INDEX_NAME)
    where = f"大綱/{INDEX_NAME}"
    folder = {f.arc for f in files if f.arc}
    if not index.is_file():
        if folder:
            return [
                Problem(
                    where,
                    f"不存在，而 `大綱/` 底下有 {len(folder)} 支 arc 檔",
                    "索引是那個資料夾的視圖（`大綱.schema.md`「索引檔」）",
                )
            ]
        return []
    text = read_text(index)
    if SKELETON_MARK in text:
        stats.notes.append(f"{where}：骨架（`{SKELETON_MARK}`），視圖比對跳過")
        return []
    rows: list[str] = []
    for raw in text.splitlines():
        m = _INDEX_ROW_RE.match(raw.strip())
        if m:
            rows.append(f"arc{m.group(1)}")
    stats.index_rows = len(rows)
    out: list[Problem] = []
    missing = sorted(folder - set(rows))
    extra = sorted(set(rows) - folder)
    stats.index_mismatch = len(missing) + len(extra)
    if missing:
        out.append(
            Problem(
                where,
                f"{len(missing)} 支 arc 檔沒有列：{'、'.join(missing)}",
                "視圖 ≡ 資料夾（雙向）",
            )
        )
    if extra:
        out.append(
            Problem(
                where,
                f"{len(extra)} 列指向不存在的 arc 檔：{'、'.join(extra)}",
                f"檔已搬進 `{RETIRED_DIR}/` 的話，列留著、狀態改成「已併入」即可；"
                f"檔真的不存在就刪列",
            )
        )
    unordered = [
        (rows[i - 1], rows[i]) for i in range(1, len(rows)) if rows[i] <= rows[i - 1]
    ]
    stats.index_unordered = len(unordered)
    if unordered:
        a, b = unordered[0]
        out.append(
            Problem(
                where,
                f"列序非遞增 {len(unordered)} 處（第一處：{a} 之後是 {b}）",
                "索引是視圖，序就是 arc 序——逆序的索引讓人以為那是「最近改過的」排序",
            )
        )
    return out


def _check_destinations(
    texts: list[OutlineFile], book: Path, stats: OutlineStats
) -> list[Problem]:
    """第 9 項：檔內指名的書內路徑存在（`設計原則.md` E1「目的地承諾」推論）。

    第 6 個實例（前五：幕綱設計註→裁決流／`derived-sync` 的 `missing_destinations`
    ／`decision-lint` 兩處／`ch-lint` 的 `風格` 欄／`summary-lint` 的幕號·arc 引用）。

    **射程刻意窄**：只認反引號裡、以書內資料夾開頭的 `.md`。schema 檔、`技巧知識庫/`、
    佔位寫法（`arcNN.md`）、範圍寫法（`arc01–arc04.md`）都不是「指名一個檔」——
    不排除的話，一支完全合法的大綱會因為引用了自己的 schema 而被報成目的地不存在。
    """
    missing: dict[str, set[str]] = {}
    for f in texts:
        for m in _MD_REF_RE.finditer(f.text):
            ref = m.group(1).strip()
            if not ref.startswith(BOOK_PREFIXES):
                continue
            if ".schema." in ref or _PLACEHOLDER_RE.search(ref):
                continue
            if _ARC_RANGE_RE.search(ref) or "–" in ref or "—" in ref:
                continue
            stats.path_refs += 1
            rel = ref[len("story/") :] if ref.startswith("story/") else ref
            if (book / "story" / rel).is_file() or (book / ref).is_file():
                continue
            missing.setdefault(ref, set()).add(f.where)
    if not missing:
        return []
    stats.path_missing = len(missing)
    shown = "、".join(
        f"`{r}`（{'、'.join(sorted(w))}）" for r, w in sorted(missing.items())[:4]
    ) + ("…" if len(missing) > 4 else "")
    return [
        Problem(
            "大綱/",
            f"{len(missing)} 個檔內指名的路徑不存在：{shown}",
            "箭頭指向空氣，而箭頭本身格式完全合法（E1）。改成實際的路徑，"
            "或照 `書本模板/` 的骨架先建那支檔",
        )
    ]


def _check_coexistence(files: list[OutlineFile], stats: OutlineStats) -> list[Problem]:
    """第 8 項：並存（抉擇 4 A：**合法化**，只有「同一個 arc 兩邊都有內容」才報）。

    **這是規格錯了不是書錯了的清楚案例**：`organize/SKILL.md:52` 明文寫「不會有
    全書已有 `01-大綱.md`、還繼續新增局部 `大綱/arcNN.md` 的狀況」，而實測有 3 支
    （arc09／10／11，全在 `01-大綱.md` 定稿之後產出、**由 `organize` 自己產的**），
    連續 3 個 arc、5 天、0 警報，而且每一輪都是作者逐題拍板、沒有出過錯。
    規格改成符合實務之後，這一項報的就只剩真正的病：**同一個 arc 兩個家**。
    """
    full = next((f for f in files if f.kind == "全書"), None)
    unmerged = [f for f in files if f.kind == "scoped" and f.status != MERGED_MARK]
    stats.unmerged_scoped = len(unmerged)
    if full is None:
        return []
    # **先剝掉反引號裡的路徑再抽 arc token**：`story/大綱/arc09.md` 是一個**指標**
    # （「形狀記於某某檔」），不是「本檔已經涵蓋 arc09」。不剝的話這一項會把
    # 「守留白紀律、只指路」誤判成「兩個家」——那正好與它要抓的病相反。
    prose = re.sub(r"`[^`\n]*`", "", full.body(PROSE_SECTION_FULL) or "")
    covered: set[int] = set()
    for m in _ARC_RANGE_RE.finditer(prose):
        covered |= set(range(int(m.group(1)), int(m.group(2)) + 1))
    covered |= {int(m.group(1)) for m in _ARC_TOKEN_RE.finditer(prose)}
    stats.covered_arcs = len(covered)
    both = [f for f in unmerged if int(_ARC_FILE_RE.match(f.arc).group(1)) in covered]
    stats.both_homed = len(both)
    if not both:
        return []
    return [
        Problem(
            "大綱/",
            f"{len(both)} 支 arc 兩邊都有內容："
            f"{'、'.join(f.arc for f in both)}",
            f"`{FULL_NAME}` 與 scoped 大綱**按卷分工**（`{FULL_NAME}` 涵蓋已收斂的卷、"
            f"未收斂的卷走 scoped）。同一個 arc 兩個家＝下游拆幕會讀到哪一份取決於"
            f"路由，而兩份會漂——把它併入並 `git mv` 進 `{RETIRED_DIR}/`",
        )
    ]


# ------------------------------------------------------------------ 主流程


def lint_report(book: Path) -> tuple[list[str], OutlineStats]:
    """驗一本書的大綱層。回 (問題清單, 覆蓋率統計)。"""
    stats = OutlineStats()
    everything = load_files(book)
    files = [f for f in everything if not f.skeleton]
    stats.skeletons = len(everything) - len(files)
    stats.files = len(files)
    stats.full = sum(1 for f in files if f.kind == "全書")
    stats.scoped = sum(1 for f in files if f.kind == "scoped")
    stats.retired = sum(1 for f in files if f.kind == "已併入")

    problems: list[Problem] = []
    for f in files:
        problems += _check_sections(f, stats)
        problems += _check_header_status(f, stats)
        problems += _check_status_table(f)
        if f.kind == "全書":
            problems += _check_ending(f, stats)
        else:
            problems += _check_closing(f)
        # 連續敘述佔比（覆蓋率行的頭號訊號）
        prose = f.body(PROSE_SECTION_FULL if f.kind == "全書" else PROSE_SECTION_SCOPED)
        total = len(f.text)
        stats.total_chars += total
        share = len(prose) / total if (prose and total) else 0.0
        stats.prose_chars += len(prose or "")
        if total and (stats.prose_min is None or share < stats.prose_min[1]):
            stats.prose_min = (f.where, share)

    # 文字層的三項要連索引一起掃（見 `_index_file`），節與狀態那幾項不掃它。
    index = _index_file(book)
    texts = files + ([index] if index is not None and not index.skeleton else [])

    problems += _check_volume(files, stats)
    problems += _check_refs(texts, files, book, stats)
    problems += _check_foreshadow(texts, book, stats)
    problems += _check_index(files, book, stats)
    problems += _check_destinations(texts, book, stats)
    problems += _check_coexistence(files, stats)

    if stats.merged_in_place:
        stats.notes.append(
            f"{len(stats.merged_in_place)} 支標了「已併入」卻仍住在 `大綱/`："
            f"{'、'.join(stats.merged_in_place)}"
            f"——併入的最後一步是 `git mv` 進 `大綱/{RETIRED_DIR}/`"
            f"（`設計原則.md` A5：源檔的身分不能被自己檔內的一句話撤銷，"
            f"撤銷要從檔案系統看得出來）"
        )

    return [str(p) for p in problems], stats


def lint(book: Path) -> list[str]:
    return lint_report(book)[0]
