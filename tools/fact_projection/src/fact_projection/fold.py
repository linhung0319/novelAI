from __future__ import annotations

import re
from dataclasses import dataclass

# 狀態的 6 維（封閉枚舉，跨小說通用）——語意與子專案 C 原版逐字相同。
DIMENSIONS = frozenset({"知識前沿", "關係", "持有", "位置", "能力", "所屬"})

KIND_STATE = "狀態"
KIND_ANCHOR = "錨"
KIND_CONSTRAINT = "約束"
KINDS = (KIND_STATE, KIND_ANCHOR, KIND_CONSTRAINT)

# 約束退場靠顯式解除，不加第 5 欄（見 結構定義/事實流.schema.md）。
RELEASE_PREFIX = "（解除）"


class FoldError(Exception):
    """事實流/spine 解析或定位失敗（格式壞行、未知類型 token、無法定位）。"""


@dataclass(frozen=True)
class Event:
    beat: int
    arc: str
    entity: str
    token: str  # 第三欄原文：6 維之一，或 錨〔名〕／約束〔名〕
    kind: str  # 狀態／錨／約束
    name: str  # 狀態＝維度名；錨/約束＝〔〕內的名字
    content: str
    lineno: int

    @property
    def released(self) -> bool:
        return self.content.startswith(RELEASE_PREFIX)


# 位置從左端解析：幕NNN（arcAA）後第一個 · 為位置/實體分隔；實體之後（含名字內的 ·）全歸實體。
_POS_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）\s*·\s*(.+)$")
# 錨／約束的 token 帶名字；名字內不得再有全形方括號。
_TYPED_TOKEN_RE = re.compile(r"^(錨|約束)〔([^〔〕]+)〕$")


def classify_token(token: str) -> tuple[str, str]:
    """第三欄 token → (kind, name)。未知 token 報錯、不靜默丟。"""
    if token in DIMENSIONS:
        return KIND_STATE, token
    m = _TYPED_TOKEN_RE.match(token)
    if m:
        return m.group(1), m.group(2).strip()
    raise FoldError(
        f"未知類型 token {token!r}"
        f"（限 6 維狀態 {sorted(DIMENSIONS)}，或 錨〔名〕／約束〔名〕）"
    )


def strip_html_comments(lines: list[str]) -> list[tuple[int, str]]:
    """濾掉 `<!-- ... -->` 區塊，回傳 [(原始行號, 行)]。

    schema 與書本模板會把範例事件放在註解裡；那些**不是事件**，讀進來會
    因為引用了不存在的 arc 而整份投影報錯。
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


def parse_events(text: str) -> list[Event]:
    events: list[Event] = []
    for i, raw in strip_html_comments(text.splitlines()):
        line = raw.strip()
        if not line.startswith("-"):
            continue
        body = line[1:].strip()
        if not body.startswith("幕"):  # 非事件行（標題/說明/其他 bullet）→ 跳過
            continue
        if "：" not in body:
            raise FoldError(f"第 {i} 行事件缺少內容分隔『：』：{raw!r}")
        head, _, content = body.partition("：")
        # token 內無 ·（6 維無點；錨/約束的〔〕內也不容 ·），故最後一個 · 必為實體/token 分隔
        left, sep, tok = head.rpartition("·")
        if not sep:
            raise FoldError(f"第 {i} 行事件缺少類型分隔『·』：{raw!r}")
        token = tok.strip()
        try:
            kind, name = classify_token(token)
        except FoldError as e:
            raise FoldError(f"第 {i} 行{e}") from None
        m = _POS_RE.match(left.strip())
        if not m:
            raise FoldError(f"第 {i} 行位置/實體格式不符：{raw!r}")
        events.append(
            Event(
                beat=int(m.group(1)),
                arc=m.group(2).strip(),
                entity=m.group(3).strip(),
                token=token,
                kind=kind,
                name=name,
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
    token: str
    kind: str
    name: str
    content: str
    source_beat: int
    source_arc: str

    @property
    def released(self) -> bool:
        return self.content.startswith(RELEASE_PREFIX)


def _pos(spine: dict[str, int], arc: str, beat: int) -> tuple[int, int]:
    if arc not in spine:
        raise FoldError(f"arc {arc!r} 不在 spine（全書順序）中，無法定位")
    return (spine[arc], beat)


def project(
    events: list[Event],
    spine: dict[str, int],
    target_beat: int,
    target_arc: str,
    kinds: tuple[str, ...] | None = None,
    active_only: bool = False,
) -> list[Slot]:
    """as-of 投影。三類型共用同一套 fold：slot key ＝(實體, token)，序最新勝。

    kinds=None 代表全開。active_only 剔除內容以「（解除）」起頭的 slot
    ——約束的退場靠顯式解除，見 結構定義/事實流.schema.md。
    """
    target = _pos(spine, target_arc, target_beat)
    # 對每個事件都定位（含被過濾的），arc 無法定位即報錯、不靜默丟。
    positioned = [(_pos(spine, e.arc, e.beat), e) for e in events]
    kept = sorted(
        ((p, e) for p, e in positioned if p <= target),
        key=lambda pe: (pe[0], pe[1].lineno),  # 同位置以檔序後者勝
    )
    slots: dict[tuple[str, str], Slot] = {}
    for _p, e in kept:
        slots[(e.entity, e.token)] = Slot(
            entity=e.entity,
            token=e.token,
            kind=e.kind,
            name=e.name,
            content=e.content,
            source_beat=e.beat,
            source_arc=e.arc,
        )
    out = list(slots.values())
    if kinds is not None:
        out = [s for s in out if s.kind in kinds]
    if active_only:
        out = [s for s in out if not s.released]
    return out
