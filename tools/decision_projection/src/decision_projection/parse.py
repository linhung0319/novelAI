from __future__ import annotations

import re
from dataclasses import dataclass

COLUMNS = ("日期", "來源", "標的", "裁決", "理由", "射程", "狀態")

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
            if tuple(cells) != COLUMNS:
                raise ParseError(
                    f"第 {i} 行表頭欄位不符：得到 {cells}，應為 {list(COLUMNS)}"
                )
            seen_header = True
            continue
        if len(cells) != len(COLUMNS):
            raise ParseError(
                f"第 {i} 行欄數 {len(cells)}，應為 {len(COLUMNS)}：{raw!r}"
            )
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


def _segments(path: str) -> list[str]:
    """正規化成路徑分段：去掉 `.md`／`.ai.md`／`.co.md` 與頭尾斜線。"""
    p = path.strip().strip("/")
    for suffix in (".ai.md", ".co.md", ".md"):
        if p.endswith(suffix):
            p = p[: -len(suffix)]
            break
    return [s for s in p.split("/") if s]


def matches_target(decision: Decision, target: str) -> bool:
    """標的比對＝**路徑分段**的雙向前綴相符。標的為 `全書` 的裁決一律命中。

    2026-07-27 由字串前綴改成分段前綴，修兩個實測到的 bug：

    - **假陰性（靜默且危險）**：角色源檔升級成目錄形態是 `角色.schema.md` 明文
      建議的路徑，但 `設定/角色/血刀頭陀.md` 與 `設定/角色/血刀頭陀/核心.md`
      互不為字串前綴——一升級，該角色所有既往裁決就靜默失聯，`character` 下一輪
      會重新爭論一次已經定案的事。
    - **假陽性**：`設定/角色/真` 會命中 `真觀`／`真慧`／`真應`。
    """
    if decision.target == TARGET_ALL:
        return True
    a, b = _segments(decision.target), _segments(target)
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return longer[: len(shorter)] == shorter


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


def parse_spine(text: str) -> dict[str, int]:
    """幕綱 `_index.md` 的「全書順序」→ {arc: 排名}。

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
    raise ParseError("幕綱 _index 找不到可解析的『全書順序：』arc 序列")
