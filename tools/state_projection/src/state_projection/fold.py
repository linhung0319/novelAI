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


_SPINE_RE = re.compile(r"全書順序：(.+)$")
_ARC_TOKEN_RE = re.compile(r"arc[0-9A-Za-z]+")


def parse_spine(text: str) -> dict[str, int]:
    for raw in text.splitlines():
        m = _SPINE_RE.search(raw)
        if not m:
            continue
        arcs: list[str] = []
        for tok in _ARC_TOKEN_RE.findall(m.group(1)):
            if tok not in arcs:
                arcs.append(tok)
        if arcs:
            return {arc: rank for rank, arc in enumerate(arcs)}
    raise FoldError("幕綱 _index 找不到可解析的『全書順序：』arc 序列")


@dataclass(frozen=True)
class Slot:
    entity: str
    dimension: str
    content: str
    source_beat: int
    source_arc: str


def _pos(spine: dict[str, int], arc: str, beat: int) -> tuple[int, int]:
    if arc not in spine:
        raise FoldError(f"arc {arc!r} 不在 spine（全書順序）中，無法定位")
    return (spine[arc], beat)


def project(
    events: list[Event], spine: dict[str, int], target_beat: int, target_arc: str
) -> list[Slot]:
    target = _pos(spine, target_arc, target_beat)
    # 對每個事件都定位（含被過濾的），arc 無法定位即報錯、不靜默丟。
    positioned = [(_pos(spine, e.arc, e.beat), e) for e in events]
    kept = sorted(
        ((p, e) for p, e in positioned if p <= target),
        key=lambda pe: (pe[0], pe[1].lineno),  # 同位置以檔序後者勝
    )
    slots: dict[tuple[str, str], Slot] = {}
    for _p, e in kept:
        slots[(e.entity, e.dimension)] = Slot(
            entity=e.entity,
            dimension=e.dimension,
            content=e.content,
            source_beat=e.beat,
            source_arc=e.arc,
        )
    return list(slots.values())
