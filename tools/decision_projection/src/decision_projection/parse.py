from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ("日期", "來源", "標的", "裁決", "理由", "射程", "狀態")

# `story/參照/待裁決.md`：AI 的**觀察**（下游發現「根源在上游」的一句話）。
# **刻意四欄、沒有 `狀態` 欄**——這張表只住待裁決的，狀態是恆真的。
# 診斷輪實測舊設計那個只允許一個值的 `狀態` 欄：7 列平均 171 字元、最長 440、
# 佔整列 61%，人的裁決被塞進 AI 那一筆的最後一格（同一個病徵的第三個案例，
# 前兩個是 `chapters/_index.ai.md` 備註欄與 `幕綱/_index.md` arc 概覽）。
# **離開＝刪列**，理由 append 進 `裁決流.md`。
PENDING_COLUMNS = ("日期", "來源", "標的", "發現")

STATUS_ACTIVE = "生效中"
STATUS_EXPIRED = "已過射程"
STATUS_PROMOTED = "已升為通則"
STATUSES = (STATUS_ACTIVE, STATUS_EXPIRED, STATUS_PROMOTED)

# 標的欄寫 `全書` 的裁決管所有檔，任何 --target 都命中。
TARGET_ALL = "全書"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")


class ParseError(Exception):
    """裁決流解析失敗（欄數不符、日期格式錯、未知狀態值）。"""


# 射程寫法：`全書`／`至arcNN`／`本輪`。`至arcNN` 是唯一能機械判定的一種。
SCOPE_ALL = "全書"
SCOPE_ROUND = "本輪"
_SCOPE_UNTIL_RE = re.compile(r"^至\s*(arc[0-9A-Za-z]+)$")


@dataclass(frozen=True)
class Decision:
    date: str
    source: str
    target: str
    ruling: str
    rationale: str
    scope: str
    status: str
    lineno: int

    @property
    def active(self) -> bool:
        return self.status == STATUS_ACTIVE

    @property
    def scope_arc(self) -> str | None:
        """射程寫 `至arcNN` 時的那個 arc；其餘寫法回 None（判不了）。"""
        m = _SCOPE_UNTIL_RE.match(self.scope.strip())
        return m.group(1) if m else None

    def expired_at(self, spine: dict[str, int], current_arc: str) -> bool:
        """射程是否已過。**由程式從 `射程` 欄算，不靠人維護 `狀態` 欄。**

        2026-07-27 前 `射程` 欄程式從頭到尾沒讀過，`--active-only` 濾的是手動維護
        的 `狀態` 欄，於是 schema 宣稱的「過期的由程式按射程過濾掉，不必有人負責刪」
        並不成立——實測「至arc07」的裁決在 arc11 仍回「生效中」。
        """
        arc = self.scope_arc
        if arc is None or arc not in spine or current_arc not in spine:
            return False
        return spine[current_arc] > spine[arc]


def _cells(line: str) -> list[str]:
    # 去頭尾的 |，再切；不處理跳脫的 \| （裁決流不該有）
    return [c.strip() for c in line.strip().strip("|").split("|")]


def strip_html_comments(lines: list[str]) -> list[tuple[int, str]]:
    """濾掉 `<!-- ... -->` 區塊，回傳 [(原始行號, 行)]。

    schema 與書本模板會把範例列放在註解裡；那些**不是裁決**，讀進來會讓
    查詢吐出根本不存在的決定。
    """
    out: list[tuple[int, str]] = []
    in_comment = False
    for i, raw in enumerate(lines, start=1):
        line = raw
        if in_comment:
            if "-->" in line:
                in_comment = False
                line = line.split("-->", 1)[1]
            else:
                continue
        while "<!--" in line:
            before, _, rest = line.partition("<!--")
            if "-->" in rest:
                line = before + rest.split("-->", 1)[1]
            else:
                line = before
                in_comment = True
                break
        if line.strip():
            out.append((i, line))
    return out


def parse_decisions(text: str) -> list[Decision]:
    """讀裁決流表格。非表格行（標題、引言、HTML 註解）跳過；壞行報錯、不靜默丟。"""
    out: list[Decision] = []
    for cells, i in _parse_table(text, COLUMNS, ""):
        date, source, target, ruling, rationale, scope, status = cells
        if not _DATE_RE.match(date):
            raise ParseError(f"第 {i} 行日期格式須為 YYYY-MM-DD，得到 {date!r}")
        if status not in STATUSES:
            raise ParseError(
                f"第 {i} 行未知狀態 {status!r}（限 {list(STATUSES)}）"
            )
        out.append(
            Decision(
                date=date,
                source=source,
                target=target,
                ruling=ruling,
                rationale=rationale,
                scope=scope,
                status=status,
                lineno=i,
            )
        )
    return out


@dataclass(frozen=True)
class Pending:
    """`待裁決.md` 的一列＝一則**觀察**（決定權在 AI），不是一項裁決。

    兩者拆開是 Q0／Q1 的直接後果：「觀察」是 AI 的、「裁決」是人的，一列混兩種
    決定權就該拆成兩筆。它們共用 `標的` 選擇器，所以查詢層合流；但落在兩支檔。
    """

    date: str
    source: str
    target: str
    finding: str
    lineno: int


def _parse_table(
    text: str, columns: tuple[str, ...], what: str
) -> list[tuple[list[str], int]]:
    """讀一張固定欄的 markdown 表，回傳 [(cells, 行號)]。

    非表格行（標題、引言、HTML 註解）跳過；**壞行報錯、不靜默丟**。
    `裁決流` 與 `待裁決` 共用這一份——兩張表的差別只有欄名清單。
    """
    out: list[tuple[list[str], int]] = []
    seen_header = False
    for i, raw in strip_html_comments(text.splitlines()):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        if _SEP_RE.match(line):
            continue
        cells = _cells(line)
        if not seen_header:
            # 第一列表格必須是表頭，用它確認欄序沒被改過
            if tuple(cells) != columns:
                raise ParseError(
                    f"第 {i} 行{what}表頭欄位不符：得到 {cells}，應為 {list(columns)}"
                )
            seen_header = True
            continue
        if len(cells) != len(columns):
            raise ParseError(
                f"第 {i} 行欄數 {len(cells)}，應為 {len(columns)}：{raw!r}"
            )
        out.append((cells, i))
    return out


def parse_pending(text: str) -> list[Pending]:
    """讀待裁決表。表頭多一欄（尤其是 `狀態`）會在這裡當場炸。"""
    out: list[Pending] = []
    for cells, lineno in _parse_table(text, PENDING_COLUMNS, "待裁決"):
        date, source, target, finding = cells
        if not _DATE_RE.match(date):
            raise ParseError(f"第 {lineno} 行日期格式須為 YYYY-MM-DD，得到 {date!r}")
        out.append(
            Pending(
                date=date, source=source, target=target, finding=finding, lineno=lineno
            )
        )
    return out


def select_pending(rows: list[Pending], target: str | None = None) -> list[Pending]:
    if not target:
        return rows
    return [q for q in rows if target_matches(q.target, target)]


def _segments(path: str) -> list[str]:
    """正規化成路徑分段：去掉 `.md`／`.ai.md` 與頭尾斜線。

    **`.co.md` 2026-07-30（驗證輪階段 1c）從這裡移除。** 它是 `共同約定.md:42`
    那條半真承諾的另一半：標的比對剝得掉舊後綴，而掃描起點認不得——同一份資料，
    查詢說「找到了」、閘門說「沒有這一層」。實測 0 本書用過 `.co.md` 任何檔。
    """
    p = path.strip().strip("/")
    for suffix in (".ai.md", ".md"):
        if p.endswith(suffix):
            p = p[: -len(suffix)]
            break
    return [s for s in p.split("/") if s]


def target_matches(row_target: str, query: str) -> bool:
    """標的比對的**字串核心**，`裁決流` 與 `待裁決` 共用（兩張表同一個選擇器）。"""
    if row_target.strip() == TARGET_ALL:
        return True
    a, b = _segments(row_target), _segments(query)
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return longer[: len(shorter)] == shorter


def matches_target(decision: Decision, target: str) -> bool:
    """標的比對＝**路徑分段**的雙向前綴相符。標的為 `全書` 的裁決一律命中。

    2026-07-27 由字串前綴改成分段前綴，修兩個實測到的 bug：

    - **假陰性（靜默且危險）**：角色源檔升級成目錄形態是 `角色.schema.md` 明文
      建議的路徑，但 `設定/角色/血刀頭陀.md` 與 `設定/角色/血刀頭陀/核心.md`
      互不為字串前綴——一升級，該角色所有既往裁決就靜默失聯，`character` 下一輪
      會重新爭論一次已經定案的事。
    - **假陽性**：`設定/角色/真` 會命中 `真觀`／`真慧`／`真應`。
    """
    return target_matches(decision.target, target)


def select(
    decisions: list[Decision],
    target: str | None = None,
    active_only: bool = False,
    since: str | None = None,
    spine: dict[str, int] | None = None,
    as_of_arc: str | None = None,
) -> list[Decision]:
    """篩裁決。`active_only` 同時看兩件事：

    1. `狀態` 欄（人維護的：`已升為通則` 要濾掉）
    2. `射程` 欄（**程式算的**：傳了 `spine` 與 `as_of_arc` 就自動判 `至arcNN` 過期沒）

    兩者是「或」的關係——任一判定為過期就濾掉。
    """
    out = decisions
    if target:
        out = [d for d in out if matches_target(d, target)]
    if active_only:
        out = [d for d in out if d.active]
        if spine is not None and as_of_arc is not None:
            out = [d for d in out if not d.expired_at(spine, as_of_arc)]
    if since:
        if not _DATE_RE.match(since):
            raise ParseError(f"--since 須為 YYYY-MM-DD，得到 {since!r}")
        out = [d for d in out if d.date >= since]
    return out


# spine 的落點（2026-07-28 功能 12 抉擇 2 A；**回退 2026-07-30 移除**）。
#
# `全書順序：` 是作者的創作決定（哪一段先發生），沒有任何檔算得出來——它是 A1 源，
# 而它原本住在一支被 `beat-lint` 當「視圖 ≡ 資料夾」驗的索引檔裡。一支檔同時裝
# 「權威在自己身上的源」與「權威在別處的視圖」＝六問 Q0 的違反，所以 12 把它搬進
# 同層的 `_順序.md`。
#
# **舊落點 `_index.md` 的回退（驗證輪階段 1c）移除。** 實測活用戶**只有 `一世之尊`**
# ——`書本模板`／`驗證範例` 早就是 `_順序.md`，`harry_potter`／`gothic_witch`／
# `芯片巫師` 沒有幕綱層。四份回退實作服務一本刻意不遷移的病例書。
#
# **它換成墓碑，不是換成靜默**：檔在就報「舊落點還在、2026-07-30 起不再讀」，
# 並指出 `git mv` 那一行過去即可。依 `設計原則.md` A5，撤銷一個落點的身分要從
# 機制看得出來——不讀又不報，會讓「這本書沒有 spine」與「這本書的 spine 住舊落點」
# 變成同一句話。
#
# **回退活著的時候，這件事只有 1/4 成立**（功能 14 的 V9）：12 承諾四支工具都要讓
# 回退可見，而只有 `beat-lint` 有 `spine_legacy` 欄。現在四支都印，因為墓碑就是輸出。
SPINE_FILES = ("_順序.md",)
RETIRED_SPINE_FILES = ("_index.md",)


def spine_path(book: Path) -> Path:
    """回 spine 檔的落點。**唯一落點**——不在時照樣回它，讓錯誤訊息指向該建的那支。"""
    return book / "story" / "幕綱" / SPINE_FILES[0]


def retired_spine_files(book: Path) -> list[Path]:
    """還留在已廢除落點的 spine（`_index.md`）。**檔在就要說出來**（A5）。"""
    d = book / "story" / "幕綱"
    return [p for n in RETIRED_SPINE_FILES if (p := d / n).is_file()]


def spine_note(book: Path) -> str:
    """`spine 讀自 X` ——**舊落點還在時要說出來**（功能 14 V9；階段 1c 改墓碑）。"""
    p = spine_path(book)
    if p.is_file():
        return f"spine 讀自 `{p.name}`"
    retired = retired_spine_files(book)
    if retired:
        return (
            f"spine **找不到**（新落點 `{SPINE_FILES[0]}` 不在）；"
            f"偵測到舊落點 `{retired[0].name}`——**2026-07-30 起不再讀它**，"
            f"`git mv` 那一行過去即可"
        )
    return "spine **找不到**"


def parse_spine(text: str) -> dict[str, int]:
    """幕綱 `_順序.md`（舊書：`_index.md`）的「全書順序」→ {arc: 排名}。

    **這份解析的唯一真相在 `tools/fact_projection/src/fact_projection/fold.py:parse_spine`**；
    工具間零相依（所有 tools/*/pyproject.toml 皆 dependencies = []），故複製最小片段。
    """
    spine_re = re.compile(r"全書順序：(.+)$")
    arc_re = re.compile(r"arc[0-9A-Za-z]+")
    for raw in text.splitlines():
        m = spine_re.search(raw)
        if not m:
            continue
        arcs: list[str] = []
        for tok in arc_re.findall(m.group(1)):
            if tok not in arcs:
                arcs.append(tok)
        if arcs:
            return {arc: rank for rank, arc in enumerate(arcs)}
    raise ParseError("幕綱順序檔找不到可解析的『全書順序：』arc 序列")
