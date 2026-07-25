from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class ScanError(Exception):
    """幕綱／spine 解析失敗（找不到 spine、arc 無法定位）。"""


# `埋[[伏筆:x]]` / `收[[伏筆:x]]`。schema 用半形冒號，這裡連全形一起收，錯字不靜默漏掉。
_MARK_RE = re.compile(r"(埋|收)\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]")
_BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)\s*[·・]?\s*(.*)$")
_FORE_FIELD_RE = re.compile(r"^-\s*伏筆：\s*(.*)$")
_STATUS_HEAD_RE = re.compile(r"^##\s*本\s*arc\s*伏筆狀態")
_UNBUILT_RE = re.compile(r"(arc[0-9A-Za-z]+)（未拆）")


@dataclass(frozen=True)
class Mark:
    kind: str  # 埋 / 收
    name: str
    beat: int
    arc: str
    lineno: int


@dataclass(frozen=True)
class StatusRow:
    """「本 arc 伏筆狀態」表的一列。這張表是**視圖**，不是埋/收的第二個家。"""

    arc: str
    name: str
    planted_cell: str
    paid_cell: str
    note: str
    lineno: int


@dataclass(frozen=True)
class Violation:
    kind: str
    arc: str
    lineno: int
    detail: str


@dataclass
class ArcScan:
    arc: str
    marks: list[Mark] = field(default_factory=list)
    rows: list[StatusRow] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    beat_numbers: list[int] = field(default_factory=list)


def scan_arc(path: Path, arc: str) -> ArcScan:
    """掃一個 arc 幕綱。

    **只認幕的「伏筆」欄**為埋/收標記來源（`幕綱.schema.md`「單一真實來源」）。
    狀態表與備註散文裡若出現字面標記，那不是埋設點——照它配對會把還沒埋的伏筆
    判成已閉合，因此另報成 violation。
    """
    out = ArcScan(arc=arc)
    in_beat = False
    in_status = False
    beat_no = 0
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if raw.startswith("##"):
            m = _BEAT_HEAD_RE.match(raw)
            if m:
                in_beat, in_status = True, False
                beat_no = int(m.group(1))
                out.beat_numbers.append(beat_no)
            else:
                in_beat = False
                in_status = bool(_STATUS_HEAD_RE.match(raw))
            continue

        stripped = raw.strip()
        if in_beat:
            fm = _FORE_FIELD_RE.match(stripped)
            if fm:
                for kind, name in _MARK_RE.findall(fm.group(1)):
                    out.marks.append(
                        Mark(kind=kind, name=name.strip(), beat=beat_no, arc=arc, lineno=i)
                    )
            elif _MARK_RE.search(stripped) and not stripped.startswith("- 伏筆"):
                # 幕內其他欄位出現字面標記＝會被誤掃，schema 要求只寫伏筆名純文字
                out.violations.append(
                    Violation(
                        kind="標記出現在伏筆欄以外",
                        arc=arc,
                        lineno=i,
                        detail=stripped[:80],
                    )
                )
            continue

        if in_status and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 4 or cells[0] in ("伏筆", "") or set(cells[0]) <= {"-", ":"}:
                continue  # 表頭／分隔列
            if _MARK_RE.search(stripped):
                out.violations.append(
                    Violation(
                        kind="狀態表內出現字面 埋/收 標記",
                        arc=arc,
                        lineno=i,
                        detail=cells[0][:40],
                    )
                )
            out.rows.append(
                StatusRow(
                    arc=arc,
                    name=cells[0],
                    planted_cell=cells[1],
                    paid_cell=cells[2],
                    note=cells[3],
                    lineno=i,
                )
            )
    return out


# ---------------------------------------------------------------- spine

_SPINE_RE = re.compile(r"全書順序：(.+)$")
_ARC_TOKEN_RE = re.compile(r"arc[0-9A-Za-z]+")


def parse_spine(text: str) -> dict[str, int]:
    """與 state_projection 同源的定序規則：判先後**不能比幕號大小**，走全書順序。"""
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
    raise ScanError("幕綱 _index 找不到可解析的『全書順序：』arc 序列")


# ---------------------------------------------------------------- 🧊

_ICE_RE = re.compile(r"🧊[^｜|]*[｜|]\s*([^）)\n]*)")


@dataclass(frozen=True)
class Ice:
    target: str | None  # 指向的伏筆名；跨集留白為 None
    cross_book: bool
    file: Path
    lineno: int


def scan_ice(book: Path) -> list[Ice]:
    """掃設定層 .ai.md 的 🧊 揭示層級標記（`共同約定.md` 六）。

    注意：🧊 裡的 `收[[伏筆:x]]` 是**指標**、不是回收點，故不併入 Mark。
    """
    ices: list[Ice] = []
    root = book / "story" / "設定"
    if not root.is_dir():
        return ices
    for p in sorted(root.rglob("*.ai.md")):
        for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if "🧊" not in raw:
                continue
            for body in _ICE_RE.findall(raw):
                m = _MARK_RE.search(body)
                if m:
                    ices.append(Ice(target=m.group(2).strip(), cross_book=False, file=p, lineno=i))
                elif "跨集留白" in body or "不揭" in body:
                    ices.append(Ice(target=None, cross_book=True, file=p, lineno=i))
    return ices
