"""正文層格式閘門（`ch-lint`）。

**為什麼這支工具存在。** `<!-- 幕NNN -->` 是全 repo 唯一「有機讀標記、零解析器」的
地方：`章節.schema.md` 對它下了五條格式承諾（幕號沿用幕綱編號／同一幕跨多段只標一次／
過渡錨點格式／人性寫法正規化／一幕不可跨章切開），而 2026-07-27 之前**沒有任何一支
程式讀它**——唯一碰到它的是 `prose_metrics/metrics.py:_HTML_COMMENT_RE`，那支正則的
作用是**把它剝掉當雜訊**。一世之尊 108 個錨點全清，是 AI 一路寫下來的紀律，不是工具
保證的乾淨（`設計原則.md` E1：填不出檢查器就不准在 schema 裡宣稱那個格式）。

`write-test/SKILL.md` 更把「`對應幕` vs 正文錨點的差集」明文寫成「**機械事實，不需
LLM 判斷**」——而執行者一直是 LLM。那是 E2 第四格（無人守）披著第一格的皮。

**為什麼住在 `beat_metrics` 而不是自己開一個套件**（作者拍板抉擇 1 B）：第 1／3／4 項
要的是**幕號 registry**，而那份真相就在同套件的 `structure.parse_book()`。另開套件等於
新增第 5 份 `parse_spine`／幕號集合實作。`beat-lint` 驗幕綱、`ch-lint` 驗正文，
**兩個指令、一份解析層**——同 `object-lint` 是 `fact-lint` 的聚焦入口的先例：
`write`／`revise` 落檔後只想驗正文層，不該同時吃到幕綱那邊與它無關的問題。

**守的是「人破結構」那一側**（`設計原則.md` B1）：錨點、幕號、front-matter 鍵都是人
手打的識別符與結構，與 `derived-sync validate`／`beat-lint` 同類。內容好壞不歸它
（那是 `write-test`），漂移統計不歸它（那是 `prose-metrics`）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .scan import ScanError, read_text
from .structure import parse_book

AI_SUFFIX = ".ai.md"

# **位數一律 `\d+`，不是 `\d{3}`。** `章節.schema.md` 2026-07-27 前寫「三位數」，而
# 幕號預配號段（每 arc 100 個）在 arc10 之後必然溢出——實測一世之尊 arc11 起是 `幕1001`。
# 照舊 schema 寫成 `幕(\d{3})` 的解析器會 **silently 前綴匹配**（`幕1001` 讀成 `幕100`），
# 不報錯、給出一整批假的不一致。本輪第一次量測就踩過這個坑，故 schema 那句已改掉。
_ANCHOR_RE = re.compile(r"<!--\s*幕(\d+)\s*(?:(?:→|->)\s*幕(\d+)\s*)?-->")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# 只有「註解裡出現幕號」才算疑似錨點——一般編輯註解（`<!-- 這段待改 -->`）不冤枉。
_LOOKS_LIKE_ANCHOR_RE = re.compile(r"幕\s*\d")
# 作者手寫的人性化分隔（`章節.schema.md`「作者可用人性化標記」）。**報，不代改**：
# 代改是編輯動作，閘門只回答「這份檔還是不是它宣稱的那個格式」。
_HUMAN_RE = re.compile(r"^\s*-{2,}\s*幕(\d+)\s*-{2,}\s*$")

_CH_STEM_RE = re.compile(r"^ch\d+$")
_FM_FENCE = "---"
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_SEP_ROW_RE = re.compile(r"^\|[\s:|-]+\|$")
_BEAT_NUM_RE = re.compile(r"幕(\d+)")
_MARK_RE = re.compile(r"(埋|收)\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]")
_POV_ROLE_RE = re.compile(r"角色\s*[:：]\s*([^,，}]+)")

# front-matter 必填六鍵（`章節.schema.md`「欄位說明」）。
# `風格` 2026-07-27 由選填改必填：舊 schema 說「單一風格檔時可省略，預設 風格.ai.md」，
# 而**沒有任何工具實作那個 fallback**（grep 全 tools/ 確認）——一條沒有讀者的預設值，
# 只會讓 `write-test` 測試5 拿不到本章該對照哪份風格檔。
REQUIRED_KEYS = ("對應幕", "所屬arc", "POV", "基調參照", "風格", "狀態")
POV_SUBKEYS = ("角色", "人稱", "距離")
STATUS_VALUES = ("草稿", "已定稿")

# 測試執行紀錄（2026-07-28 功能 10 抉擇 3 A 新增）。**選填——缺席合法、不計入問題數**：
# 沒測過是一種真實狀態，把它報成問題等於把一個明訂非門檻的東西變成門檻（`write`
# 的就緒提醒本來就是 non-blocking）。缺幾支由覆蓋率行說，**0 也印**。
#
# **判準是結構判準**：日期 ＋ `N高N中N低` 的阿拉伯數字。**不驗測試結果好不好**
# ——那是 `write-test` 的事，一個閘門不該對內容有意見。中文數字不認（同
# `style-lint` 第 4 項與 `summary-lint` 第 7 項的紀律）。
#
# **它在誕生當天就有消費者**（`設計原則.md` E1）：`write/SKILL.md` 步驟 2 的就緒
# 提醒讀它、`readiness` 第 3 節逐 arc 印它；寫它的是 `write-test` 的收尾。在此之前
# 這件事有**三份手抄、零比對、零格式**（就緒儀表狀態格／幕綱檔頭散文／測試報告
# 不落檔），而 `write:81` 明文同時吃前兩份。
TEST_RECORD_KEY = "write-test"
TEST_RECORD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*[·・]\s*(\d+)高(\d+)中(\d+)低$")

# `風格` 欄指向的檔住這裡（`風格.schema.md`「檔案佈局」）。
# 2026-07-27（功能 07 抉擇 6 A）新增**目的地存在性**檢查：在此之前 93/93 章都寫
# `風格.ai.md`，而**沒有任何一行驗那支檔在不在**——這一欄非空（上面 `REQUIRED_KEYS`）
# 與 `_index` 視圖一致（`_lint_index`）都驗過了，唯獨箭頭指向的東西沒人看。
# 它是 `設計原則.md` E1「目的地承諾」推論的第 4 個實例（前三：幕綱設計註→裁決流、
# `derived-sync` 的 `missing_destinations`、`decision-lint` 兩處）。
# **為什麼值得補**：schema 的多世界 forward-compat（`風格/主世界.md`）0 本書用過，
# 那條路徑一旦有人走，93 章的指標會同時落空而零報告——同一行的既有註解記著完全
# 同型的教訓（「沒有任何工具實作那個 fallback」）。成本 3 行。
STYLE_DIR = ("story", "設定", "風格")

INDEX_NAME = "_index.ai.md"
INDEX_SECTION = "章節索引"
INDEX_COLUMNS = ("章", "對應幕", "所屬 arc", "POV", "風格", "狀態", "備註")
UNWRITTEN = "（未寫）"

# 備註欄字數上限。**門檻取自實測分佈**（同 `derived_sync/sentinel.py` 各門檻的作法）：
# 一世之尊健康群 arc01–arc04 是 33／53／48／54 字/章、**最大 92**；漂移群 arc05 起
# 88 → 347（arc09），最長 561 字（ch0075 那格寫的是幕的排序理由）。100 落在兩群之間。
NOTE_CHARS = 100

# 空欄位的各種寫法（`_index` 的「（未寫）」列各欄填 `—`）。與 `structure.EMPTY_VALUES`
# 同義但**刻意不 import**：那份的擁有者是幕綱八欄，兩邊的空值語意日後可能分家。
BLANK = frozenset({"", "—", "–", "-", "－"})


# ------------------------------------------------------------------ 資料結構

@dataclass(frozen=True)
class Anchor:
    """一個幕錨點。`to_beat` 非 None 即過渡錨點 `<!-- 幕A→幕B -->`。"""

    beat: int
    to_beat: int | None
    lineno: int

    @property
    def transition(self) -> bool:
        return self.to_beat is not None


@dataclass
class ChapterSource:
    stem: str
    path: Path
    anchors: list[Anchor] = field(default_factory=list)
    human: list[tuple[int, int]] = field(default_factory=list)  # (行號, 幕號)
    malformed: list[tuple[int, str]] = field(default_factory=list)  # (行號, 原文)

    @property
    def scene_beats(self) -> list[int]:
        return [a.beat for a in self.anchors if not a.transition]


@dataclass
class ChapterMeta:
    stem: str
    path: Path
    keys: dict[str, str] = field(default_factory=dict)
    first: int | None = None
    last: int | None = None
    beats_raw: str = ""
    beats_form: str = ""  # canonical-single｜canonical-range｜same-pair｜loose｜unparsed


@dataclass(frozen=True)
class IndexRow:
    lineno: int
    cells: tuple[str, ...]

    def cell(self, i: int) -> str:
        return self.cells[i] if i < len(self.cells) else ""


@dataclass
class ChLintStats:
    """**我在這本書上檢查了幾筆。**

    `設計原則.md` E2 的可執行推論。本工具最需要這一行的兩格是 `anchors` 與
    `beats_checked`：前者若印 0，代表錨點解析器又沒在解析了（那正是它誕生的理由——
    在它之前 108 個錨點被 0 支工具讀過）；後者說出「對應幕 ≡ 錨點集合」這條
    `write-test` 宣稱為機械事實的檢查，實際核對了幾支章。**0 也要印。**
    """

    sources: int = 0
    anchors: int = 0
    transitions: int = 0
    metas: int = 0
    index_rows: int = 0
    registry: int = 0
    beats_checked: int = 0
    beats_mismatch: int = 0
    unknown_beats: int = 0
    rows_checked: int = 0
    rows_mismatch: int = 0
    normalize_candidates: int = 0
    style_refs: int = 0
    style_refs_dangling: int = 0
    test_records: int = 0
    test_records_bad: int = 0
    notes: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    def render(self) -> str:
        return (
            f"檢查範圍：{self.sources} 章正文源／{self.anchors} 個幕錨點／"
            f"{self.transitions} 個過渡錨點／{self.metas} 支章衍生／"
            f"{self.index_rows} 列章序（幕綱 registry {self.registry} 幕）；\n"
            f"          比對了 {self.beats_checked} 章的對應幕"
            f"（{self.beats_mismatch} 章不一致）、"
            f"{self.anchors + self.transitions} 個錨點幕號"
            f"（{self.unknown_beats} 個對不到 registry）、"
            f"{self.rows_checked} 列章序六欄（{self.rows_mismatch} 列不一致）、"
            f"{self.style_refs} 個 `風格` 欄指向的檔"
            f"（{self.style_refs_dangling} 個不存在）；\n"
            f"          非標準錨點寫法 {self.normalize_candidates} 筆；\n"
            f"          {self.test_records}/{self.metas} 支章衍生有 "
            f"`{TEST_RECORD_KEY}` 紀錄（**格式不合 {self.test_records_bad} 支**"
            f"·缺紀錄不計入問題數）。"
        )


# ------------------------------------------------------------------ 解析

def _frontmatter(text: str) -> dict[str, str]:
    """`.ai.md` 的 YAML front-matter → 扁平 dict。

    **自帶一份、不 import `fact_projection`**：所有 `tools/*/pyproject.toml` 皆
    `dependencies = []`，套件之間複製最小片段是本 repo 既有取捨（見 `scan.py` 檔頭）。
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != _FM_FENCE:
        return {}
    out: dict[str, str] = {}
    for raw in lines[1:]:
        if raw.strip() == _FM_FENCE:
            break
        key, sep, value = raw.partition(":")
        if sep and key.strip() and not key.startswith(" "):
            out[key.strip()] = value.split("#", 1)[0].strip()
    return out


def _classify_beats(raw: str) -> tuple[int | None, int | None, str]:
    """`對應幕` 的值 → (起, 訖, 寫法)。

    收斂結果由作者拍板（抉擇 5 B）：**單幕 `[幕N]`、多幕 `[起, 訖]`**。
    ✗ 已駁回「一律 `[起, 訖]`」——78/93 章要帶一個冗餘的同值寫法，而下游解析器
    （`fact_projection/chapters.py`）本來就刻意吃兩種，寬鬆是為了「人會手改」。

    **解析仍然寬鬆、只是寫法會被報**：讀得懂就讀，形狀不對另外報一筆。閘門的職責是
    指出格式漂了，不是讓下游讀不到資料。
    """
    s = raw.strip()
    nums = [int(n) for n in _BEAT_NUM_RE.findall(s)]
    if not nums:
        return None, None, "unparsed"
    if len(nums) > 2:
        return min(nums), max(nums), "loose"
    if len(nums) == 1:
        form = "canonical-single" if re.fullmatch(r"\[\s*幕\d+\s*\]", s) else "loose"
        return nums[0], nums[0], form
    lo, hi = nums
    if lo == hi:
        return lo, hi, "same-pair"
    if not re.fullmatch(r"\[\s*幕\d+\s*[,，]\s*幕\d+\s*\]", s):
        return min(lo, hi), max(lo, hi), "loose"
    return (lo, hi, "canonical-range") if lo < hi else (hi, lo, "reversed")


def scan_source(path: Path) -> ChapterSource:
    """掃一支正文源的錨點。"""
    out = ChapterSource(stem=path.stem, path=path)
    text = read_text(path)
    for i, raw in enumerate(text.splitlines(), start=1):
        for m in _ANCHOR_RE.finditer(raw):
            out.anchors.append(
                Anchor(
                    beat=int(m.group(1)),
                    to_beat=int(m.group(2)) if m.group(2) else None,
                    lineno=i,
                )
            )
        h = _HUMAN_RE.match(raw)
        if h:
            out.human.append((i, int(h.group(1))))
            continue
        for c in _COMMENT_RE.finditer(raw):
            if _LOOKS_LIKE_ANCHOR_RE.search(c.group(0)) and not _ANCHOR_RE.fullmatch(
                c.group(0)
            ):
                out.malformed.append((i, c.group(0)[:40]))
    return out


def load_sources(book: Path) -> list[ChapterSource]:
    d = book / "chapters"
    if not d.is_dir():
        return []
    return [
        scan_source(p)
        for p in sorted(d.glob("ch*.md"))
        if not p.name.endswith(AI_SUFFIX) and _CH_STEM_RE.match(p.stem)
    ]


def load_metas(book: Path) -> list[ChapterMeta]:
    d = book / "chapters"
    if not d.is_dir():
        return []
    out: list[ChapterMeta] = []
    for p in sorted(d.glob(f"ch*{AI_SUFFIX}")):
        stem = p.name[: -len(AI_SUFFIX)]
        if not _CH_STEM_RE.match(stem):
            continue
        keys = _frontmatter(read_text(p))
        meta = ChapterMeta(stem=stem, path=p, keys=keys)
        meta.beats_raw = keys.get("對應幕", "")
        if meta.beats_raw:
            meta.first, meta.last, meta.beats_form = _classify_beats(meta.beats_raw)
        out.append(meta)
    return out


def load_index(book: Path) -> tuple[Path | None, list[IndexRow]]:
    """`chapters/_index.ai.md` 的「## 章節索引」表 → 資料列。

    **只取該節裡第一個連續的表格區塊。** 節底下可以有別的表（`書本模板` 就在那裡放
    了一張「不得住在備註欄的三類」對照表），而 markdown 的表格本來就以空行為界——
    掃到節尾會把說明表當成章序列。這個 bug 是本工具自己在 `書本模板` 上抓到的。
    """
    p = book / "chapters" / INDEX_NAME
    if not p.is_file():
        return None, []
    rows: list[IndexRow] = []
    inside = False
    started = False
    for i, raw in enumerate(read_text(p).splitlines(), start=1):
        h = _H2_RE.match(raw)
        if h:
            if started:
                break
            inside = h.group(1).strip().startswith(INDEX_SECTION)
            continue
        if not inside:
            continue
        line = raw.strip()
        if not line.startswith("|"):
            if started:
                break  # 表格到此為止（空行或散文）
            continue
        started = True
        if _SEP_ROW_RE.match(line):
            continue
        cells = tuple(c.strip() for c in line.strip("|").split("|"))
        if cells and cells[0] in ("章", ""):
            continue  # 表頭
        rows.append(IndexRow(lineno=i, cells=cells))
    return p, rows


def _registry(book: Path) -> dict[int, str]:
    """幕號 → 所屬 arc。**這是抉擇 1 B 的全部理由**：這份真相在同套件的
    `structure.parse_book()`，另開套件就得再抄一份。

    **讀不到就硬報錯，不靜默退化**——沒有 registry 時「幕號存在性」這一項會全部
    無聲通過，而它正是本工具的第 1 項。同 `beat_metrics` 2026-07-27 修掉的那個
    spine 假陰性（`scan.parse_spine` 檔頭）。
    """
    return {b.number: a.arc for a in parse_book(book) for b in a.beats}


# ------------------------------------------------------------------ 檢查

def _fmt_list(items: list[str], limit: int = 5) -> str:
    shown = "、".join(items[:limit])
    return shown + (f"…（+{len(items) - limit}）" if len(items) > limit else "")


def lint_report(book: Path) -> tuple[list[str], ChLintStats]:
    """驗一本書的正文層。回 (問題清單, 覆蓋率統計)。

    問題字串**一律以位置起頭**（`chNNNN.md 第 N 行 …`／`chapters/…`），同 `beat-lint`。
    **格式收斂類（同一種病散在幾十支檔）聚合成一行**＋數量＋最壞值，同
    `derived_sync/sentinel.py:long_lines` 的既有形狀：一世之尊是刻意不遷移的病例書，
    逐支報會產生 120 行同型雜訊，把 8 項結構檢查淹掉（那是 E2 尺上還沒有的一格：
    警報疲勞，見 `docs/重構/功能報告/03-正文章節.md` §六 4）。
    """
    problems: list[str] = []
    stats = ChLintStats()

    registry = _registry(book)
    stats.registry = len(registry)

    sources = load_sources(book)
    metas = load_metas(book)
    index_path, index_rows = load_index(book)
    stats.sources = len(sources)
    stats.metas = len(metas)
    stats.index_rows = len(index_rows)

    # ---- 1／2／4／5：錨點本身（幕號存在、章內單調、過渡兩端、非標準寫法）
    owner: dict[int, tuple[str, int]] = {}
    for src in sources:
        prev: Anchor | None = None
        for a in src.anchors:
            if a.transition:
                stats.transitions += 1
            else:
                stats.anchors += 1

            if a.beat not in registry:
                stats.unknown_beats += 1
                problems.append(
                    f"{src.path.name} 第 {a.lineno} 行：錨點 幕{a.beat:03d} 指向不存在的幕"
                    f"（全書幕綱找不到 `## 幕{a.beat:03d}`）"
                )
            if a.to_beat is not None:
                if a.to_beat not in registry:
                    stats.unknown_beats += 1
                    problems.append(
                        f"{src.path.name} 第 {a.lineno} 行：過渡錨點 "
                        f"幕{a.beat:03d}→幕{a.to_beat:03d} 的終點指向不存在的幕"
                    )
                elif a.to_beat <= a.beat:
                    problems.append(
                        f"{src.path.name} 第 {a.lineno} 行：過渡錨點 "
                        f"幕{a.beat:03d}→幕{a.to_beat:03d} 的兩端不是遞增的"
                        f"（它標的是「銜接前一幕到下一幕」的 Sequel）"
                    )
                continue

            # 章內單調只看標準錨點：過渡錨點夾在兩幕之間，本來就不進這條序列。
            if prev is not None and a.beat <= prev.beat:
                problems.append(
                    f"{src.path.name} 第 {a.lineno} 行：錨點 幕{a.beat:03d} 排在"
                    f"第 {prev.lineno} 行的 幕{prev.beat:03d} 之後"
                    f"（章內錨點須單調遞增；正文順序＝幕的演出順序）"
                )
            prev = a

            # ---- 3：一幕不可跨章切開（全書「幕號 → 章」為單射）
            if a.beat in owner and owner[a.beat][0] != src.stem:
                first_stem, first_line = owner[a.beat]
                problems.append(
                    f"{src.path.name} 第 {a.lineno} 行：幕{a.beat:03d} 也出現在 "
                    f"{first_stem}.md 第 {first_line} 行"
                    f"——`章節.schema.md`「一幕不可跨章切開」"
                )
            owner.setdefault(a.beat, (src.stem, a.lineno))

        for lineno, beat in src.human:
            stats.normalize_candidates += 1
            problems.append(
                f"{src.path.name} 第 {lineno} 行：`--- 幕{beat:03d} ---` 是人性寫法，"
                f"請正規化成 `<!-- 幕{beat:03d} -->`（本閘門只報、不代改）"
            )
        for lineno, snippet in src.malformed:
            stats.normalize_candidates += 1
            problems.append(
                f"{src.path.name} 第 {lineno} 行：`{snippet}` 含幕號卻不是標準錨點"
                f"——標準形是 `<!-- 幕NNN -->` 或 `<!-- 幕NNN→幕MMM -->`"
            )

    # ---- 6／7：章衍生檔的 front-matter
    by_stem = {s.stem: s for s in sources}
    loose_forms: list[str] = []
    same_pairs: list[str] = []
    style_dir = book.joinpath(*STYLE_DIR)
    dangling_style: dict[str, list[str]] = {}
    for meta in metas:
        where = meta.path.name
        missing = [k for k in REQUIRED_KEYS if not meta.keys.get(k, "").strip()]
        if missing:
            problems.append(
                f"{where}：front-matter 缺 {'、'.join(missing)}"
                f"（`章節.schema.md`「欄位說明」六欄皆必填）"
            )
        status = meta.keys.get("狀態", "").strip()
        if status and status not in STATUS_VALUES:
            problems.append(
                f"{where}：`狀態` 是 {status!r}，只能是 "
                f"{'／'.join(STATUS_VALUES)}"
            )
        pov = meta.keys.get("POV", "")
        if pov:
            lack = [k for k in POV_SUBKEYS if k not in pov]
            if lack:
                problems.append(
                    f"{where}：`POV` 缺子欄 {'、'.join(lack)}"
                    f"（格式 `{{ 角色: X, 人稱: Y, 距離: Z }}`）"
                )

        # 第 11 項：`風格` 欄指向的檔存在（E1 目的地承諾，2026-07-27 功能 07）。
        # 聚合成一行——93 章寫同一個檔名，逐章報就是 93 行同型雜訊（03 拍板的判準：
        # 病因與修法完全相同時聚合）。
        style_ref = meta.keys.get("風格", "").strip().strip("`").strip()
        if style_ref:
            stats.style_refs += 1
            if not (style_dir / style_ref).is_file():
                stats.style_refs_dangling += 1
                dangling_style.setdefault(style_ref, []).append(meta.stem)

        # 第 12 項：測試執行紀錄的**形狀**（2026-07-28 功能 10 抉擇 3 A）。
        # **有寫才驗**——缺席合法，見 `TEST_RECORD_KEY` 的註解。
        record = meta.keys.get(TEST_RECORD_KEY, "").strip()
        if record:
            stats.test_records += 1
            if not TEST_RECORD_RE.match(record):
                stats.test_records_bad += 1
                problems.append(
                    f"{where}：`{TEST_RECORD_KEY}: {record}` 不合形狀"
                    f"——`YYYY-MM-DD·N高N中N低`（阿拉伯數字，中文數字不算）。"
                    f"由 `write-test` 收尾時寫，`write` 的就緒提醒與 `readiness` 讀它"
                )

        if meta.beats_form == "unparsed" and meta.beats_raw:
            problems.append(
                f"{where}：`對應幕` 解析不了：{meta.beats_raw!r}"
                f"（單幕寫 `[幕001]`、多幕寫 `[幕001, 幕004]`）"
            )
        elif meta.beats_form == "reversed":
            problems.append(f"{where}：`對應幕` 起訖顛倒：{meta.beats_raw!r}")
        elif meta.beats_form == "same-pair":
            same_pairs.append(meta.stem)
        elif meta.beats_form == "loose":
            loose_forms.append(meta.stem)

        src = by_stem.get(meta.stem)
        if src is None:
            problems.append(
                f"{where}：找不到對應的正文源 {meta.stem}.md"
                f"（衍生檔的源不存在，`derived-sync check` 會報 orphan）"
            )
            continue
        if meta.first is None:
            continue

        stats.beats_checked += 1
        declared = {b for b in registry if meta.first <= b <= meta.last}
        anchored = set(src.scene_beats)
        dirty = False
        for b in sorted(declared - anchored):
            dirty = True
            problems.append(
                f"{meta.stem}.md：`對應幕` 宣告涵蓋 幕{b:03d}，正文找不到 "
                f"`<!-- 幕{b:03d} -->` 錨點（漏幕，或該幕併進了鄰幕段落而錨點沒補）"
            )
        for b in sorted(anchored - declared):
            dirty = True
            problems.append(
                f"{meta.stem}.md：正文有 幕{b:03d} 的錨點，卻不在 {where} 的 `對應幕` "
                f"區間（幕{meta.first:03d}–幕{meta.last:03d}）內——重生 front-matter 或修錨點"
            )
        arc = meta.keys.get("所屬arc", "").strip().strip("[]").strip()
        arcs = {registry[b] for b in anchored if b in registry}
        if arc and arcs and arcs != {arc}:
            dirty = True
            problems.append(
                f"{where}：`所屬arc` 寫 {arc}，但正文錨點落在 "
                f"{'、'.join(sorted(arcs))}"
            )
        if dirty:
            stats.beats_mismatch += 1

    if same_pairs:
        problems.append(
            f"chapters/：{len(same_pairs)} 支章衍生檔的 `對應幕` 把單幕寫成 "
            f"`[幕N, 幕N]`，schema 定單幕寫 `[幕N]`、多幕才寫 `[起, 訖]`"
            f"：{_fmt_list(same_pairs)}"
        )
    if loose_forms:
        problems.append(
            f"chapters/：{len(loose_forms)} 支章衍生檔的 `對應幕` 不是標準寫法"
            f"（`[幕N]` 或 `[幕N, 幕M]`）：{_fmt_list(loose_forms)}"
        )
    for ref, stems in sorted(dangling_style.items()):
        problems.append(
            f"chapters/：{len(stems)} 支章衍生檔的 `風格: {ref}` 指向不存在的檔"
            f"（找不到 `{'/'.join(STYLE_DIR)}/{ref}`）：{_fmt_list(stems)}"
        )

    # ---- 8／9／10：`_index.ai.md`
    problems += _lint_index(book, index_path, index_rows, metas, stats)

    # ---- 提示（不計入問題數、不影響 exit code）
    unanchored = sorted(set(registry) - set(owner))
    if unanchored:
        stats.notes.append(
            f"{len(unanchored)}/{len(registry)} 幕還沒寫成正文"
            f"（幕綱有、無錨點）：{_fmt_list([f'幕{b:03d}' for b in unanchored], 8)}"
        )
    return problems, stats


def _lint_index(
    book: Path,
    index_path: Path | None,
    rows: list[IndexRow],
    metas: list[ChapterMeta],
    stats: ChLintStats,
) -> list[str]:
    """`chapters/_index.ai.md`：視圖一致性（第 8 項）＋備註欄兩條（第 9／10 項）。

    **為什麼備註欄要有守衛**：schema 給它的用途只有「標未寫範圍」，實測長成了
    章摘要＋結構階段＋伏筆標記＋幕排序設計註的四合一（一世之尊 13,874 字，
    每列 196 B → 781 B）。其中兩類是**別條軸的第二個家**（伏筆的真相在幕綱、
    結構階段的真相也在幕綱——2026-07-28 功能 11 廢除 `結構.ai.md` 之後**只剩那一份**，
    全書視圖跑 `structure-project`），一類是**不可重生的新資訊住在 rollup 衍生檔**
    （幕排序設計註，重生一次就沒了且沒有 diff 會被審）。
    """
    problems: list[str] = []
    if index_path is None:
        # **缺 rollup 不是問題，是新的正常狀態**（2026-07-28 功能 12 抉擇 1 A）：
        # 那支檔廢除了，章序的權威改由 `ch-lint --emit` 回答（它印的就是本函式
        # 為了比對而算出來的那一份）。本項因此降級成**殘留偵測**：舊檔還在才比對
        # ——既有書照抉擇 8 A 不遷移，那份視圖仍然要與各章 front-matter 一致。
        return problems

    where = f"chapters/{INDEX_NAME}"
    by_stem = {m.stem: m for m in metas}
    listed: set[str] = set()
    long_notes: list[tuple[int, str, int]] = []
    marked: list[tuple[int, str]] = []

    for row in rows:
        chapter = row.cell(0)
        note = row.cell(6)
        if len(note) > NOTE_CHARS:
            long_notes.append((row.lineno, chapter, len(note)))
        if _MARK_RE.search(note):
            marked.append((row.lineno, chapter))

        if chapter.startswith(UNWRITTEN[0]) or chapter in BLANK:
            continue  # 表尾的「（未寫）」列：六欄本來就是 `—`
        listed.add(chapter)
        meta = by_stem.get(chapter)
        if meta is None:
            problems.append(
                f"{where} 第 {row.lineno} 行：列了 {chapter}，"
                f"但沒有對應的 {chapter}{AI_SUFFIX}"
            )
            continue

        stats.rows_checked += 1
        diffs: list[str] = []
        want_beats = (meta.first, meta.last)
        got = _BEAT_NUM_RE.findall(row.cell(1))
        got_beats = (int(got[0]), int(got[-1])) if got else (None, None)
        if want_beats != (None, None) and want_beats != got_beats:
            diffs.append(f"對應幕 表 {row.cell(1)!r} vs 檔 {meta.beats_raw!r}")
        for i, key in ((2, "所屬arc"), (4, "風格"), (5, "狀態")):
            want = meta.keys.get(key, "").strip()
            if want and row.cell(i) != want:
                diffs.append(f"{key} 表 {row.cell(i)!r} vs 檔 {want!r}")
        role = _POV_ROLE_RE.search(meta.keys.get("POV", ""))
        if role and row.cell(3) != role.group(1).strip():
            diffs.append(f"POV 表 {row.cell(3)!r} vs 檔 {role.group(1).strip()!r}")
        if diffs:
            stats.rows_mismatch += 1
            problems.append(
                f"{where} 第 {row.lineno} 行：{chapter} 與 {chapter}{AI_SUFFIX} "
                f"不一致（{'；'.join(diffs)}）——本表是視圖不是第二個家，"
                f"重生它就對了"
            )

    for meta in metas:
        if meta.stem not in listed:
            problems.append(
                f"{where}：{meta.stem} 有章衍生檔卻不在章序表裡"
                f"（`write` 每次新增章要重生本表）"
            )

    if marked:
        problems.append(
            f"{where}：{len(marked)} 列的備註欄含 `埋|收[[伏筆:x]]` 標記"
            f"（第 {'、'.join(str(n) for n, _ in marked[:5])}"
            f"{'…' if len(marked) > 5 else ''} 行）"
            f"——伏筆的單一真實來源是幕綱，這一份沒有任何工具讀。"
            f"查詢走 `foreshadow-project`，別在這裡開第二本帳"
        )
    if long_notes:
        worst = max(long_notes, key=lambda t: t[2])
        problems.append(
            f"{where}：{len(long_notes)}/{len(rows)} 列的備註欄超過 {NOTE_CHARS} 字"
            f"（最長 {worst[2]} 字，第 {worst[0]} 行 {worst[1]}）"
            f"——備註欄只住「（未寫）」標記與一行極短章摘要；"
            f"幕的排序理由屬幕綱檔尾設計註／裁決流，不是章的東西"
        )
    return problems


def lint(book: Path) -> list[str]:
    return lint_report(book)[0]
