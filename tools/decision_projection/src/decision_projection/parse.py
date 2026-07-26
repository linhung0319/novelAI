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


def _cells(line: str) -> list[str]:
    # 去頭尾的 |，再切；不處理跳脫的 \| （裁決流不該有）
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_decisions(text: str) -> list[Decision]:
    """讀裁決流表格。非表格行（標題、引言）跳過；壞行報錯、不靜默丟。"""
    out: list[Decision] = []
    seen_header = False
    for i, raw in enumerate(text.splitlines(), start=1):
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


def matches_target(decision: Decision, target: str) -> bool:
    """標的比對＝前綴相符。

    `設定/角色/少年/` 命中其下所有切面；標的為 `全書` 的裁決一律命中。
    """
    if decision.target == TARGET_ALL:
        return True
    return decision.target.startswith(target) or target.startswith(decision.target)


def select(
    decisions: list[Decision],
    target: str | None = None,
    active_only: bool = False,
    since: str | None = None,
) -> list[Decision]:
    out = decisions
    if target:
        out = [d for d in out if matches_target(d, target)]
    if active_only:
        out = [d for d in out if d.active]
    if since:
        if not _DATE_RE.match(since):
            raise ParseError(f"--since 須為 YYYY-MM-DD，得到 {since!r}")
        out = [d for d in out if d.date >= since]
    return out
