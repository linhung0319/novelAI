from __future__ import annotations

import re
from dataclasses import dataclass

DIMENSIONS = frozenset({"知識前沿", "關係", "持有", "位置", "能力", "所屬"})


class FoldError(Exception):
    """事件流/spine 解析或定位失敗（格式壞行、未知維度、無法定位）。"""


@dataclass(frozen=True)
class Event:
    beat: int
    arc: str
    entity: str
    dimension: str
    content: str
    lineno: int


# 位置從左端解析：幕NNN（arcAA）後第一個 · 為位置/實體分隔；實體之後（含名字內的 ·）全歸實體。
_POS_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）\s*·\s*(.+)$")


def parse_events(text: str) -> list[Event]:
    events: list[Event] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("-"):
            continue
        body = line[1:].strip()
        if not body.startswith("幕"):  # 非事件行（標題/說明/其他 bullet）→ 跳過
            continue
        if "：" not in body:
            raise FoldError(f"第 {i} 行事件缺少內容分隔『：』：{raw!r}")
        head, _, content = body.partition("：")
        left, sep, dim = head.rpartition("·")  # 維度是無點枚舉，最後一個 · 必為實體/維度分隔
        if not sep:
            raise FoldError(f"第 {i} 行事件缺少維度分隔『·』：{raw!r}")
        dimension = dim.strip()
        if dimension not in DIMENSIONS:
            raise FoldError(
                f"第 {i} 行未知變化維度 {dimension!r}（限 {sorted(DIMENSIONS)}）"
            )
        m = _POS_RE.match(left.strip())
        if not m:
            raise FoldError(f"第 {i} 行位置/實體格式不符：{raw!r}")
        events.append(
            Event(
                beat=int(m.group(1)),
                arc=m.group(2).strip(),
                entity=m.group(3).strip(),
                dimension=dimension,
                content=content.strip(),
                lineno=i,
            )
        )
    return events
