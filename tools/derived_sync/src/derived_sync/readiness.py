"""就緒軸：源檔閘門（`readiness-lint`）＋現況投影（`readiness`）。

**為什麼這兩支存在**（2026-07-28 功能 10 重構輪）：`story/參照/就緒儀表.ai.md` 是
一支住著**六種決定權完全不同的內容**的檔，實測在一世之尊上長到 **292,591 B**
（全書最大、佔全書 11.3%、六天 254.7×），其中 **53.8%（68,776 字元）是拍板日誌**
——而三節「現況」投影出來只有 **306 字元（419× 壓縮）**、輸入 100% 現成。

最狠的一格是**結構性的**：那支檔在**任何命名下都拿不到格式守衛**——舊名
`就緒儀表.md` 讓 `check_book` 的 `rglob("*.ai.md")` 掃不到；新名 `.ai.md` 讓
`_is_declarative` 在 `validate_file` 早退三次（front-matter 必填鍵／裁決
blockquote／節枚舉），而其中兩項與那個豁免的理由（無單一源可 hash）完全無關。
覆蓋率行還把它印成「0 支宣告式」——讀起來像「這本書沒有這種檔」。

**處置是拆**（`設計原則.md` **A6**「無源衍生 ＝ 一個必須解掉的衝突，不是一種
檔」，同輪新增）：不可重生的兩筆（成熟度判斷、清單的勾）留在 A1 源檔
`story/參照/就緒.md`，由 `readiness-lint` 守；可重生的四筆（機械現況、局部下沉、
待裁決筆數、就緒清單的機械前哨）改由 `readiness` 當場算，**不落檔**。

**跨套件的機械來源一律印「未接」＋該跑的指令**（抉擇 6 A）：`outline-lint`／
`beat-lint`／`ch-lint` 在 `tools/beat_metrics`、`decision-project` 在
`tools/decision_projection`，而所有 `tools/*/pyproject.toml` 皆 `dependencies = []`。
**不 subprocess、不複製**——零相依政策要不要改是功能 14 的題目，在它裁之前蓋
跨套件橋等於替一個還沒定案的政策先付維護成本（D2 是目前唯一能說「不要做」的
原則）。**「未接」要印出來、0 也印**：那一格是給 14 看的儀表，不是隱藏的欠債。

**「未接」與「無機械來源」是兩件事，本模組分開數**：前者有來源、只是這一輪不
接；後者是**這一格根本沒有任何機械來源，它純粹是作者判斷**（`設計原則.md` D3
2026-07-28 補的推論：凡把一支檔改成投影，先逐格回答「這一格的機械來源是哪一支
檔的哪一欄」，答不出來的那幾格是真正的源）。混在一起就是新的假陰性。

**已知的複製**：第 3 節重算 `chNNNN.ai.md` 的 `所屬arc`，那是 `ch-lint` 第 8 項
之外的**第 2 份**（同套件內沒有那份實作，跨套件零相依故不 import）→ 功能 14。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .char_lint import lint_book as char_lint_book
from .char_lint import source_names as char_sources
from .core import AI_SUFFIX, _split_frontmatter, check_book
from .style_lint import lint_book as style_lint_book
from .summary_lint import lint_book as summary_lint_book
from .summary_lint import summary_paths
from .world_lint import lint_book as world_lint_book
from .world_lint import topic_sources as world_topics

# ---------------------------------------------------------------- schema 常數
# `結構定義/就緒.schema.md` 的唯一真相。改這裡就要改那裡（反之亦然）。
READINESS_DIR = ("story", "參照")
READINESS_FILE = "就緒.md"
# 廢除的舊檔（兩種命名都認）。留著它＝`設計原則.md` A5 的「撤銷要從檔案系統看得
# 出來」沒有兌現：內容還在、身分卻已經被一句話撤銷了。
LEGACY_FILES = ("就緒儀表.md", "就緒儀表.ai.md")
# 日誌的家（04 蓋好的）。舊名一併吃，同 `sentinel.DESTINATIONS`。
DECISION_LOG = ("裁決流.md", "裁決流.co.md")

SECTIONS = ("產物軸 × 深度成熟度", "就緒清單")
DEPTHS = ("粗", "大綱", "幕綱", "正文")
HEADER = ("產物軸",) + DEPTHS
AXES = ("設定層·世界觀", "設定層·角色", "設定層·風格", "主線＋題旨＋基調", "結構")
# **封閉五 token**（抉擇 4 A）。實測舊儀表 20 格中 7 格溢位、最長 3,647 字元，
# 而 `long_lines` 一筆都沒報——它量的是**行**，病在**格**（832 字元的那一行含
# 107／92 字元的違枚舉格）。**門檻量錯了單位**，所以這裡用結構判準不用長度。
TOKENS = ("空白", "草擬", "就緒", "已鎖定", "—")
# 只有這兩個值需要跟機械前哨對帳——`空白`／`草擬` 本來就在說「還沒好」。
MATURE = ("就緒", "已鎖定")
# 六條清單：(比對用前綴, 骨架裡的全文)。比對用前綴是為了容許作者在後面加註記。
CHECKLIST: tuple[tuple[str, str], ...] = (
    ("能用一句話說清主線", "能用一句話說清主線"),
    ("題旨可寫成", "題旨可寫成「因為 X 導致 Y」"),
    ("結局方向已拍板", "結局方向已拍板"),
    ("主角／視角已定", "主角／視角已定，且主角「需要」明確"),
    ("世界觀無擋路的硬矛盾", "世界觀無擋路的硬矛盾"),
    ("基調已定", "基調已定（一句話），風格檔已承接展開"),
)

_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_SEP_ROW_RE = re.compile(r"^\|[\s:|-]+\|$")
_ITEM_RE = re.compile(r"^-\s*\[([ xX])\]\s*(.*?)\s*$")
# 檔頭宣告行／front-matter 欄的形狀（抉擇 3 A）。守的是**結構**：日期 ＋
# `N高N中N低` 的阿拉伯數字。**不驗測試結果好不好**——那是 `beat-test` 的事。
TEST_RECORD_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s*[·・]\s*(\d+)高(\d+)中(\d+)低\s*$")
_BEAT_TEST_LINE_RE = re.compile(r"^\s*beat-test\s*[:：]\s*(.*?)\s*$")
_ARC_RE = re.compile(r"^arc[0-9A-Za-z]+$")
_ARC_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])(arc[0-9A-Za-z]+)")
_DASHES = frozenset("—–-－")
_SHOWN = 40  # 溢位格印前幾個字元


def readiness_path(book: Path) -> Path:
    return book.joinpath(*READINESS_DIR, READINESS_FILE)


def _label(raw: str) -> str:
    """`**設定層·角色（需要／弧線）**` → `設定層·角色`。

    形狀照抄 `beat_metrics.structure._label`：**標籤的寫法不該決定它比不比得上**。
    """
    s = raw.replace("*", "").strip()
    return re.split(r"[（(]", s, maxsplit=1)[0].strip()


def _norm_cell(raw: str) -> str:
    """格值正規化：剝粗體與空白；三種破折號一律當 `—`。

    **只正規化字形，不正規化語意**——`就緒（卷一）` 仍然是溢位（它在寫沿革，
    而沿革的家是 `裁決流.md`）。
    """
    s = raw.replace("*", "").strip()
    if s and all(c in _DASHES for c in s):
        return "—"
    return s


# ---------------------------------------------------------------- 源檔解析


@dataclass
class ReadinessSource:
    path: Path
    exists: bool = False
    sections: list[tuple[int, str]] = field(default_factory=list)
    header: list[str] | None = None
    header_lineno: int = 0
    rows: list[tuple[int, list[str]]] = field(default_factory=list)
    items: list[tuple[int, bool, str]] = field(default_factory=list)

    def judgement(self) -> dict[tuple[str, str], str]:
        """(產物軸, 深度) → 作者判斷的 token。認不出來的格不進這張表。"""
        out: dict[tuple[str, str], str] = {}
        for _, cells in self.rows:
            axis = _label(cells[0]) if cells else ""
            if axis not in AXES:
                continue
            for i, depth in enumerate(DEPTHS, start=1):
                if i < len(cells):
                    out[(axis, depth)] = _norm_cell(cells[i])
        return out


def parse_source(book: Path) -> ReadinessSource:
    p = readiness_path(book)
    src = ReadinessSource(path=p)
    if not p.is_file():
        return src
    src.exists = True
    section: str | None = None
    for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        m = _H2_RE.match(raw)
        if m:
            section = m.group(1).strip()
            src.sections.append((i, section))
            continue
        line = raw.strip()
        if section and section.startswith(SECTIONS[0]):
            if not line.startswith("|") or _SEP_ROW_RE.match(line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if src.header is None:
                src.header, src.header_lineno = cells, i
            else:
                src.rows.append((i, cells))
        elif section and section.startswith(SECTIONS[1]):
            it = _ITEM_RE.match(line)
            if it:
                src.items.append((i, it.group(1).lower() == "x", it.group(2)))
    return src


# ---------------------------------------------------------------- lint


@dataclass(frozen=True)
class Problem:
    path: Path
    detail: str
    hint: str


@dataclass
class ReadinessLintStats:
    """**我在這本書上檢查了幾筆**（`設計原則.md` E2）。**0 也印。**

    最需要這一行的兩格是 `legacy` 與 `decision_log`：舊儀表還在、而日誌的家不
    存在時，這一軸的「已經重構好了」是假的——那 68,776 字元級的內容無處可搬。
    """

    source_exists: bool = False
    sections: int = 0
    cells: int = 0
    bad_cells: int = 0
    items: int = 0
    checked: int = 0
    legacy: list[str] = field(default_factory=list)
    decision_log: bool = False

    def render(self) -> str:
        return (
            f"檢查範圍：`{'/'.join(READINESS_DIR)}/{READINESS_FILE}`"
            f"{'在' if self.source_exists else '**不在**'}"
            f"／{self.sections} 個 `##` 節；"
            f"狀態表 {self.cells} 格（**{self.bad_cells} 格不是五 token 之一**）；"
            f"就緒清單 {self.items} 條（{self.checked} 條已勾）；"
            "舊 `就緒儀表`："
            + (f"**{'、'.join(self.legacy)} 仍在**" if self.legacy else "已不在")
            + f"；`裁決流.md` {'在' if self.decision_log else '**不在**'}"
        )


def lint_book(book: Path) -> tuple[list[Problem], ReadinessLintStats]:
    """驗 `story/參照/就緒.md`。七項，逐項對應 `就緒.schema.md` 的一條承諾。"""
    out: list[Problem] = []
    stats = ReadinessLintStats()
    src = parse_source(book)
    ref = book.joinpath(*READINESS_DIR)
    stats.legacy = [n for n in LEGACY_FILES if (ref / n).is_file()]
    stats.decision_log = any((ref / n).is_file() for n in DECISION_LOG)
    stats.source_exists = src.exists
    stats.sections = len(src.sections)

    # ---- 1：源檔存在（從源側掃：`check` 從 `rglob("*.ai.md")` 出發，看不到這一格）
    if not src.exists:
        out.append(
            Problem(
                src.path,
                "不存在——這一軸唯一的源檔（作者的成熟度判斷與就緒清單住這裡）",
                "照 `書本模板/story/參照/就緒.md` 的骨架建一支（< 1,500 B）；"
                "機械現況不必抄進去，跑 `readiness` 當場算",
            )
        )

    # ---- 7：舊檔仍在（A5：撤銷要從檔案系統看得出來）＋日誌的目的地存在性（E1）
    if stats.legacy:
        detail = f"舊檔 {'、'.join(stats.legacy)} 仍在（`就緒儀表` 已於 2026-07-28 廢除）"
        hint = (
            "內容分三類搬（`就緒.schema.md`「既有書的內容怎麼搬過來」）："
            "拍板理由與已駁回 → story/參照/裁決流.md；"
            "`derived-sync check＝…`／「本輪動檔」→ 刪（工具當場重算）；"
            "「下一步」→ 刪。**搬之前先印保真率交作者確認**，成熟度那兩筆落 "
            f"`{READINESS_FILE}`"
        )
        if not stats.decision_log:
            detail += "，而 `story/參照/裁決流.md` 不存在"
            hint = (
                "**目的地不存在**：照 `書本模板/story/參照/裁決流.md` 的骨架先建一支。"
                "實測那支舊檔 53.8% 是拍板日誌——沒有裁決流，它無處可搬，"
                "只會繼續留在一支沒有任何格式守衛的檔裡。" + hint
            )
        out.append(Problem(ref / stats.legacy[0], detail, hint))

    if not src.exists:
        return out, stats

    # ---- 2：恰兩節、節名 ≡ 枚舉、不得有第三節
    titles = [t for _, t in src.sections]
    stray = [(ln, t) for ln, t in src.sections if not t.startswith(SECTIONS)]
    if stray:
        out.append(
            Problem(
                src.path,
                f"{len(stray)} 個枚舉外的節："
                + "、".join(f"第 {ln} 行「{t[:24]}」" for ln, t in stray[:4])
                + ("…" if len(stray) > 4 else ""),
                f"本檔**恰兩節**（{'／'.join(SECTIONS)}），**不得有第三節**——"
                "第三節就是日誌回來的入口。沿革與拍板理由屬 story/參照/裁決流.md；"
                "「哪個 arc 下沉到哪一層」跑 `readiness` 第 3 節，不手抄",
            )
        )
    for want in SECTIONS:
        if not any(t.startswith(want) for t in titles):
            out.append(
                Problem(src.path, f"缺「## {want}」節", "見 `結構定義/就緒.schema.md`「檔案格式」")
            )

    # ---- 3：表頭恰五欄且欄名 ≡ 枚舉（沒有備註欄）
    if src.header is None:
        out.append(
            Problem(
                src.path,
                "「## 產物軸 × 深度成熟度」底下沒有表格",
                "五欄五列，見 `結構定義/就緒.schema.md`「檔案格式」",
            )
        )
    else:
        got = tuple(_label(c) for c in src.header)
        if got != HEADER:
            extra = [c for c in got if c not in HEADER]
            out.append(
                Problem(
                    src.path,
                    f"第 {src.header_lineno} 行：表頭是 {len(got)} 欄 {'｜'.join(got)}，"
                    f"schema 定 {len(HEADER)} 欄 {'｜'.join(HEADER)}"
                    + (f"（多出：{'、'.join(extra)}）" if extra else ""),
                    "**沒有備註欄**（抉擇 4 A）：實測舊儀表的備註欄佔（狀態格＋備註）"
                    "的 72.0%、三列超過 8,000 字元。深度欄是四個——`正文` 是實測長出來"
                    "的第五欄，現實是對的，schema 已補",
                )
            )

    # ---- 4：恰五列、列名 ≡ 五個產物軸（雙向）
    got_axes = [_label(cells[0]) if cells else "" for _, cells in src.rows]
    missing = [a for a in AXES if a not in got_axes]
    unknown = [(ln, a) for (ln, _), a in zip(src.rows, got_axes) if a not in AXES]
    if missing:
        out.append(
            Problem(
                src.path,
                f"狀態表缺 {len(missing)} 個產物軸：{'、'.join(missing)}",
                "五個產物軸是封閉的（設定層三子軸／主線＋題旨＋基調／結構）；"
                "某一軸還沒開始就填 `空白`，不是刪列",
            )
        )
    for ln, a in unknown:
        out.append(
            Problem(
                src.path,
                f"第 {ln} 行：列名「{a[:24]}」不是 schema 的五個產物軸之一",
                "列名可帶括註（`設定層·角色（需要／弧線）`），但括號前的部分要一致",
            )
        )

    # ---- 5：每格 ∈ 五 token（結構判準，不是長度門檻）
    bad: list[str] = []
    for ln, cells in src.rows:
        axis = _label(cells[0]) if cells else ""
        for i, depth in enumerate(DEPTHS, start=1):
            if i >= len(cells):
                continue
            stats.cells += 1
            val = _norm_cell(cells[i])
            if val not in TOKENS:
                stats.bad_cells += 1
                shown = val[:_SHOWN] + ("…" if len(val) > _SHOWN else "")
                bad.append(f"第 {ln} 行 {axis or '?'}／{depth}（{len(val)} 字元）：{shown}")
    if bad:
        out.append(
            Problem(
                src.path,
                f"{len(bad)} 格不是五 token 之一（{'／'.join(TOKENS)}）："
                + "；".join(bad[:4])
                + ("…" if len(bad) > 4 else ""),
                "溢位的內容各有各的家：「為什麼判就緒」與翻案沿革屬 "
                "story/參照/裁決流.md（`標的`＝story/參照/就緒.md）；"
                "「幾支檔·封章沒·lint 幾筆」跑 `readiness` 當場算；"
                "「哪個 arc 下沉到哪一層」跑 `readiness` 第 3 節；"
                "「⚠️N 筆待裁決」跑 `decision-project`。"
                "**已駁回「留一個 ≤N 字的備註欄」**——實測分佈 1→3,647 連續無空隙，"
                "任何長度門檻都是任意值",
            )
        )

    # ---- 6：就緒清單恰六條、checkbox 形狀、條目 ≡ schema 六條
    stats.items = len(src.items)
    stats.checked = sum(1 for _, c, _ in src.items if c)
    texts = [t for _, _, t in src.items]
    for i, (key, full) in enumerate(CHECKLIST):
        if i < len(texts) and texts[i].startswith(key):
            continue
        got = texts[i][:24] if i < len(texts) else "（缺）"
        out.append(
            Problem(
                src.path,
                f"就緒清單第 {i + 1} 條應為「{full}」，實際是「{got}」",
                "六條的文字與順序固定（`結構定義/就緒.schema.md`）；"
                "條目後面可以加註記，但開頭要對得上——`readiness` 逐條印機械前哨時"
                "靠序號對位",
            )
        )
    if len(texts) > len(CHECKLIST):
        out.append(
            Problem(
                src.path,
                f"就緒清單有 {len(texts)} 條，schema 定 {len(CHECKLIST)} 條",
                "多出來的那幾條若是別的軸的待辦，屬 story/參照/待裁決.md 或 raw/",
            )
        )
    return out, stats


# ---------------------------------------------------------------- 投影


@dataclass(frozen=True)
class CellFact:
    """一格的機械來源。`kind` 決定它怎麼印，也決定它進哪一個計數。"""

    kind: str  # lint（接得到）／未接（跨套件）／無（沒有機械來源）／不適用
    source: str
    detail: str
    problems: int | None = None


@dataclass
class ReadinessStats:
    source_exists: bool = False
    cells: int = 0
    wired: int = 0
    unwired: int = 0
    no_source: int = 0
    n_a: int = 0
    mismatches: int = 0
    items: int = 0
    full: int = 0
    partial: int = 0
    item_unwired: int = 0
    arcs: int = 0

    def render(self) -> str:
        return (
            f"檢查範圍：`{'/'.join(READINESS_DIR)}/{READINESS_FILE}`"
            f"{'在' if self.source_exists else '**不在**（作者判斷那一欄一律印「不存在」）'}；"
            f"狀態表 {self.cells} 格（{self.wired} 格有機械前哨"
            f"·**{self.unwired} 格未接**·{self.no_source} 格無機械來源"
            f"·{self.n_a} 格不適用）"
            f"，**{self.mismatches} 格作者判斷與前哨不一致**；"
            f"就緒清單 {self.items} 條（{self.full} 條完整"
            f"·{self.partial} 條**部分**·{self.item_unwired} 條**未接**）；"
            f"局部下沉掃了 {self.arcs} 個 arc"
        )


def _cmd(pkg: str, tool: str, book: Path) -> str:
    return f"uv run --project <套件根>/tools/{pkg} {tool} --book {book}"


def _safe(fn, book: Path):
    """某一軸的資料夾還不存在時不該讓整支投影炸掉——那一格印「未比對」。"""
    try:
        return fn(book)
    except (FileNotFoundError, ValueError, OSError):
        return None


def _derived_state(results: list | None, book: Path, sub: tuple[str, ...]) -> str:
    """某個資料夾底下衍生檔的新鮮度（`check_book` 的同一份結果，全書只掃一次）。"""
    if results is None:
        return "未比對"
    prefix = book.joinpath(*sub)
    hit = [r for r in results if r.derived.is_relative_to(prefix)]
    if not hit:
        return "0 支衍生"
    tally = {k: sum(1 for r in hit if r.status == k) for k in ("stale", "unstamped", "orphan")}
    return (
        f"{len(hit)} 支衍生（stale {tally['stale']}"
        f"·unstamped {tally['unstamped']}·orphan {tally['orphan']}）"
    )


def _mechanical(book: Path) -> tuple[dict[tuple[str, str], CellFact], dict[str, object]]:
    """20 格的機械來源。**逐格回答「這一格的機械來源是哪一支檔的哪一欄」**
    （`設計原則.md` D3 的推論）——答不出來的就誠實印「無機械來源」。"""
    ctx: dict[str, object] = {}
    facts: dict[tuple[str, str], CellFact] = {}

    def lint_cell(name: str, res, extra: str) -> CellFact:
        if res is None:
            return CellFact("lint", name, "未比對（找不到該軸的資料夾）", None)
        problems, _ = res
        return CellFact("lint", name, f"{len(problems)} 筆問題｜{extra}", len(problems))

    world = _safe(world_lint_book, book)
    char = _safe(char_lint_book, book)
    style = _safe(style_lint_book, book)
    summary = _safe(summary_lint_book, book)
    ctx["world"], ctx["char"], ctx["style"], ctx["summary"] = world, char, style, summary
    fresh = _safe(check_book, book)

    topics = _safe(world_topics, book) or []
    facts[("設定層·世界觀", "粗")] = lint_cell(
        "world-lint",
        world,
        f"源 {len(topics)} 支主題檔·{_derived_state(fresh, book, ('story', '設定', '世界觀'))}",
    )
    names = _safe(char_sources, book)
    n_char = len(names[0]) if names else 0
    facts[("設定層·角色", "粗")] = lint_cell(
        "char-lint",
        char,
        f"源 {n_char} 支·{_derived_state(fresh, book, ('story', '設定', '角色'))}",
    )
    facts[("設定層·風格", "粗")] = lint_cell(
        "style-lint", style, _derived_state(fresh, book, ("story", "設定", "風格"))
    )
    src, derived = summary_paths(book)
    facts[("主線＋題旨＋基調", "粗")] = lint_cell(
        "summary-lint",
        summary,
        f"源{'在' if src.is_file() else '**不在**'}"
        f"·衍生{'在' if derived.is_file() else '**不在**'}",
    )

    # 跨套件那三支：印「未接」＋該跑的指令（抉擇 6 A）。
    outline = CellFact("未接", "outline-lint", _cmd("beat_metrics", "outline-lint", book))
    facts[("主線＋題旨＋基調", "大綱")] = outline
    facts[("結構", "大綱")] = outline
    facts[("結構", "幕綱")] = CellFact(
        "未接", "beat-lint", _cmd("beat_metrics", "beat-lint", book)
    )
    facts[("結構", "正文")] = CellFact("未接", "ch-lint", _cmd("beat_metrics", "ch-lint", book))
    return facts, ctx


def _no_source_reason(axis: str, depth: str) -> str:
    """這一格為什麼沒有機械來源。**寫得出理由才准印「無」**——否則它就是漏接。"""
    if axis.startswith("設定層"):
        return f"設定層沒有「{depth}」這一級的產物，成熟度純粹是作者判斷"
    return f"「{axis}／{depth}」沒有任何產物在記它，這一格是真正的源（D3 推論）"


def _section_axes(
    book: Path,
    src: ReadinessSource,
    stats: ReadinessStats,
    facts: dict[tuple[str, str], CellFact],
) -> list[str]:
    judged = src.judgement()
    lines = [f"### 1 · 產物軸 × 深度成熟度（{len(AXES)} 軸 × {len(DEPTHS)} 深度）", ""]
    for axis in AXES:
        for depth in DEPTHS:
            stats.cells += 1
            token = judged.get((axis, depth), "（未填）" if src.exists else "（`就緒.md` 不存在）")
            fact = facts.get((axis, depth))
            if token == "—":
                stats.n_a += 1
                body = "（不適用）"
            elif fact is None:
                stats.no_source += 1
                body = f"（無機械來源）{_no_source_reason(axis, depth)}"
            elif fact.kind == "未接":
                stats.unwired += 1
                body = f"**未接** {fact.source}：{fact.detail}"
            else:
                stats.wired += 1
                body = f"{fact.source}：{fact.detail}"
            lines.append(f"- {axis}／{depth}　作者＝{token}　｜ {body}")
            if (
                token in MATURE
                and fact is not None
                and fact.kind == "lint"
                and (fact.problems or 0) > 0
            ):
                stats.mismatches += 1
                lines.append(
                    f"  ⚠️ **不一致**：作者判斷＝{token}，而 {fact.source} 報 {fact.problems} 筆"
                    f"（跑 `uv run --project <套件根>/tools/derived_sync {fact.source}"
                    f" --book {book}` 看是哪幾筆）"
                )
    lines += [
        "",
        f"- ⚠️N 筆待裁決　｜ **未接** decision-project："
        f"{_cmd('decision_projection', 'decision-project', book)}",
        "  （04 起 N 一律從它的覆蓋率行讀，**不要自己數**——實測人工被動偵測的結果是"
        " 26 處字樣 vs 實際 0 筆）",
        "",
    ]
    return lines


def _section_checklist(
    book: Path, src: ReadinessSource, stats: ReadinessStats, ctx: dict[str, object]
) -> list[str]:
    """六條逐條印「機械前哨 ｜ 覆蓋度 ｜ 作者的勾」。

    **覆蓋度誠實分三級**（抉擇 5 A）：#1 與 #5 只有**部分**覆蓋，一律印「部分」，
    **不得印成通過**——那正是 E2 最後一格要防的事（一個報平安的守衛比沒有守衛
    更糟）。**也不為它們補新閘門**：「能不能用一句話說清主線」與「矛盾消掉沒有」
    都是語意判斷，補了就是詞表——那是四次被駁回的同一個形狀。
    """
    _, derived = summary_paths(book)
    fm: dict[str, str] = {}
    if derived.is_file():
        raw, _ = _split_frontmatter(derived.read_text(encoding="utf-8"))
        for line in raw or []:
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.split("#", 1)[0].strip()

    summary = ctx.get("summary")
    world = ctx.get("world")
    style = ctx.get("style")
    s_stats = summary[1] if summary else None
    w_n = len(world[0]) if world else None
    st_n = len(style[0]) if style else None

    # `_總覽.ai.md` 的「待確認／潛在矛盾」節在不在——**節在** ≠ **矛盾消掉了**，
    # 所以 #5 的覆蓋度永遠是「部分」。
    overview = book / "story" / "設定" / "世界觀" / "_總覽.ai.md"
    has_conflict_section = overview.is_file() and "待確認" in overview.read_text(encoding="utf-8")

    def state(ok: bool | None, yes: str, no: str) -> str:
        return "未比對" if ok is None else (yes if ok else no)

    rows: list[tuple[str, str, str]] = [
        (
            "summary-lint 第 2 項（衍生 `主線` 欄非空）",
            "**部分**（驗欄非空，**不驗「一句話」**）",
            state(bool(fm.get("主線")) if derived.is_file() else None, "通過", "`主線` 欄是空的"),
        ),
        (
            "outline-lint 第 6 項（`題旨：` 因果句型）",
            "**未接**（跨套件）",
            _cmd("beat_metrics", "outline-lint", book),
        ),
        (
            "outline-lint 第 6 項（`結局：` 非空非模糊）",
            "**未接**（跨套件）",
            _cmd("beat_metrics", "outline-lint", book),
        ),
        (
            "summary-lint 第 4／5 項（人稱封閉枚舉＋`POV` 抽得出來）",
            "完整",
            f"人稱：{s_stats.person_state}" if s_stats else "未比對",
        ),
        (
            "world-lint ＋ `_總覽.ai.md`「待確認／潛在矛盾」節",
            "**部分**（驗節在，**不驗矛盾消掉沒有**）",
            (f"world-lint {w_n} 筆" if w_n is not None else "未比對")
            + f"·矛盾節{'在' if has_conflict_section else '不在'}",
        ),
        (
            "summary-lint 第 6／8 項 ＋ style-lint 六項",
            "完整",
            (f"基調兩方比對：{s_stats.tone_state}·達標線落在：{s_stats.threshold_where}"
             if s_stats else "未比對")
            + (f"·style-lint {st_n} 筆" if st_n is not None else ""),
        ),
    ]

    lines = [f"### 2 · 就緒清單（{len(CHECKLIST)} 條）", ""]
    for i, ((_, full), (vanguard, coverage, result)) in enumerate(zip(CHECKLIST, rows), start=1):
        stats.items += 1
        if coverage.startswith("完整"):
            stats.full += 1
        elif "未接" in coverage:
            stats.item_unwired += 1
        else:
            stats.partial += 1
        if not src.exists:
            mark = "（`就緒.md` 不存在）"
        elif i <= len(src.items):
            mark = "[x]" if src.items[i - 1][1] else "[ ]"
        else:
            mark = "（缺）"
        lines.append(f"- {i}. {full}　作者 {mark}")
        lines.append(f"     前哨 {vanguard}｜覆蓋度 {coverage}｜{result}")
    lines.append("")
    return lines


def _chapter_arcs(book: Path) -> dict[str, int]:
    """`chapters/chNNNN.ai.md` 的 `所屬arc` → 章數。

    **這是 `所屬arc` 的第 2 份解析**（第 1 份是 `ch-lint` 第 8 項，在
    `tools/beat_metrics`）。工具間零相依故複製最小片段 → 收斂與否交功能 14。
    """
    out: dict[str, int] = {}
    d = book / "chapters"
    if not d.is_dir():
        return out
    for p in sorted(d.glob(f"ch*{AI_SUFFIX}")):
        fm, _ = _split_frontmatter(p.read_text(encoding="utf-8"))
        for line in fm or []:
            if line.strip().startswith("所屬arc"):
                for tok in _ARC_TOKEN_RE.findall(line):
                    out[tok] = out.get(tok, 0) + 1
                break
    return out


def beat_test_record(path: Path) -> str | None:
    """幕綱 arc 檔**檔頭**（第一個 `##` 之前）的 `beat-test:` 宣告行的值。

    落點與形狀見 `幕綱.schema.md`；格式由 `beat-lint` 守（抉擇 3 A）。這裡只讀
    值，**不判它合不合格**——一份投影不該同時是第二個閘門。
    """
    if not path.is_file():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("##"):
            break
        m = _BEAT_TEST_LINE_RE.match(raw)
        if m:
            return m.group(1)
    return None


def _section_descent(book: Path, stats: ReadinessStats) -> list[str]:
    """局部下沉：**100% 可重算**（檔案系統 ＋ `所屬arc`），所以它不落檔。

    舊儀表手抄這一節的下場是它與 `outline-lint` 的資訊行**直接矛盾**（儀表寫
    「已併入」，lint 報「8 支標了已併入卻仍住在 `大綱/`」）。
    """
    outline_dir = book / "story" / "大綱"
    retired = outline_dir / "_已併入"
    beat_dir = book / "story" / "幕綱"
    chapters = _chapter_arcs(book)

    arcs: set[str] = set(chapters)
    for d in (outline_dir, retired, beat_dir):
        if d.is_dir():
            arcs |= {p.stem for p in d.glob("*.md") if _ARC_RE.match(p.stem)}

    lines = ["### 3 · 局部下沉（每 arc 一列，由檔案系統與 `所屬arc` 重算）", ""]
    if not arcs:
        lines += ["（0 個 arc——大綱／幕綱／正文都還沒有任何 arcNN）", ""]
        return lines
    lines += ["| arc | 大綱 | 幕綱 | 正文 | beat-test 紀錄 |", "|---|---|---|---|---|"]
    for arc in sorted(arcs):
        stats.arcs += 1
        if (outline_dir / f"{arc}.md").is_file():
            outline = "✓"
        elif (retired / f"{arc}.md").is_file():
            outline = "已併入"
        else:
            outline = "—"
        beat_path = beat_dir / f"{arc}.md"
        if beat_path.is_file():
            beat = "骨架" if "尚未產出" in beat_path.read_text(encoding="utf-8") else "✓"
        else:
            beat = "—"
        n = chapters.get(arc, 0)
        record = beat_test_record(beat_path) or "無"
        lines.append(f"| {arc} | {outline} | {beat} | {n and f'{n} 章' or '—'} | {record} |")
    lines.append("")
    return lines


def project_book(book: Path) -> tuple[list[str], ReadinessStats]:
    """三節，**全部 0 也印**。回 (輸出行, 覆蓋率)。"""
    src = parse_source(book)
    stats = ReadinessStats(source_exists=src.exists)
    facts, ctx = _mechanical(book)
    lines = [f"## 就緒現況 {book.name}（零 LLM、可覆算；非門檻）", ""]
    lines += _section_axes(book, src, stats, facts)
    lines += _section_checklist(book, src, stats, ctx)
    lines += _section_descent(book, stats)
    return lines, stats
