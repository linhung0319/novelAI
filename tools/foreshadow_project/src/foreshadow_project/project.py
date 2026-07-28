from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .scan import (
    ArcScan,
    Ice,
    Mark,
    ScanError,
    StatusRow,
    Violation,
    _UNBUILT_RE,
    parse_spine,
    scan_arc,
    scan_reveal,
)

_ARC_FILE_RE = re.compile(r"^arc[0-9A-Za-z]+$")

CLOSED = "閉合"
OPEN_DECLARED = "未收·已宣告"
OPEN_UNDECLARED = "未收·未宣告"
PAID_UNPLANTED = "收而未埋"


@dataclass
class Thread:
    name: str
    plants: list[Mark] = field(default_factory=list)
    pays: list[Mark] = field(default_factory=list)
    rows: list[StatusRow] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.pays and not self.plants:
            return PAID_UNPLANTED
        if self.pays:
            return CLOSED
        return OPEN_DECLARED if self.rows else OPEN_UNDECLARED

    @property
    def suspect(self) -> bool:
        """已在「本 arc 伏筆狀態」表誠實列出的跨 arc／留白＝資訊，不算可疑點。"""
        return self.status in (OPEN_UNDECLARED, PAID_UNPLANTED)


@dataclass
class Report:
    spine: dict[str, int]
    threads: list[Thread]
    violations: list[Violation]
    ice_resolved: list[tuple[Ice, str]]
    ice_pending: list[tuple[Ice, str]]
    ice_suspect: list[tuple[Ice, str]]
    ice_scanned: int  # 掃到幾處（含解析不了的）——沒有這個數字就會出現「0 條可疑」的假陰性
    expired_unbuilt: list[tuple[StatusRow, str]]
    scanned_arcs: list[str]

    @property
    def ice_unparsed(self) -> int:
        return len(self.ice_suspect)


def _pos(spine: dict[str, int], m: Mark) -> tuple[int, int]:
    if m.arc not in spine:
        raise ScanError(f"arc {m.arc!r} 不在 spine（全書順序）中，無法定位")
    return (spine[m.arc], m.beat)


# spine 的落點（2026-07-28 功能 12 抉擇 2 A）：**新落點優先、舊落點回退**。
# `全書順序：` 是 A1 源（作者的創作決定），2026-07-28 從索引檔搬進同層的 `_順序.md`
# ——它原本與一支「視圖 ≡ 資料夾」的索引同居一檔（六問 Q0 的違反）。
# 舊書照抉擇 8 A 不遷移，所以回退保留；**讓回退可見的責任在 `beat-lint`**。
SPINE_FILES = ("_順序.md", "_index.md")


def spine_path(book: Path) -> Path:
    d = book / "story" / "幕綱"
    for name in SPINE_FILES:
        p = d / name
        if p.is_file():
            return p
    return d / SPINE_FILES[0]


def build(book: Path) -> Report:
    beats_dir = book / "story" / "幕綱"
    index = spine_path(book)
    if not index.is_file():
        raise ScanError(f"找不到幕綱順序檔：{index}（舊書可能還住在 `_index.md`）")
    spine = parse_spine(index.read_text(encoding="utf-8"))

    scans: list[ArcScan] = []
    for p in sorted(beats_dir.glob("*.md")):
        if not _ARC_FILE_RE.match(p.stem):
            continue
        scans.append(scan_arc(p, p.stem))
    built = {s.arc for s in scans if s.beat_numbers}

    threads: dict[str, Thread] = {}
    for s in scans:
        for m in s.marks:
            t = threads.setdefault(m.name, Thread(name=m.name))
            (t.plants if m.kind == "埋" else t.pays).append(m)
    # 狀態表是視圖：以「表格第一欄含有該伏筆名」寬鬆對應（表裡常帶括號註解）
    for s in scans:
        for row in s.rows:
            for name, t in threads.items():
                if name in row.name:
                    t.rows.append(row)

    for t in threads.values():
        t.plants.sort(key=lambda m: _pos(spine, m))
        t.pays.sort(key=lambda m: _pos(spine, m))

    # `arcNN（未拆）` 到期核對：該 arc 已拆出幕號、這一端卻還沒回填實際幕號
    expired: list[tuple[StatusRow, str]] = []
    for s in scans:
        for row in s.rows:
            for cell in (row.planted_cell, row.paid_cell):
                for arc in _UNBUILT_RE.findall(cell):
                    if arc in built:
                        expired.append((row, arc))

    # 揭示層級：**四種結果都要有數字**。舊版只算 resolved／suspect，而 resolved 算了
    # 卻不印，於是 92 處出現、91 處根本沒被當成標記時，輸出仍是「0 條為可疑點」。
    ices = scan_reveal(book)
    unbuilt = [arc for arc in spine if arc not in built]
    ice_resolved: list[tuple[Ice, str]] = []
    ice_pending: list[tuple[Ice, str]] = []
    ice_suspect: list[tuple[Ice, str]] = []
    for ice in ices:
        if ice.retired_location:
            ice_suspect.append(
                (
                    ice,
                    "落點已廢除：揭示層級只住 story/物件/<名>.md 的 `揭示層級` 欄"
                    "——寫在會被重生的設定層 .ai.md 裡，下次重生就沒了",
                )
            )
            continue
        if ice.cross_book:
            ice_resolved.append((ice, f"跨集留白，本書不揭"))
            continue
        if ice.target is None:
            ice_suspect.append(
                (
                    ice,
                    "語法解析不了：只有三種寫法（公開／水下｜揭示於 收[[伏筆:X]]／"
                    "水下｜跨集留白）",
                )
            )
            continue
        t = threads.get(ice.target)
        if t and t.pays:
            m = t.pays[0]
            ice_resolved.append((ice, f"揭示於 幕{m.beat:03d}（{m.arc}）"))
        elif t:
            # 資訊、非可疑點（共同約定.md 六：揭示點還不存在是合法狀態）
            ice_pending.append((ice, "揭示點待落幕（該伏筆已埋、尚無收點）"))
        elif unbuilt:
            ice_pending.append(
                (ice, f"揭示點待落幕（{'、'.join(unbuilt)} 尚未拆幕）")
            )
        else:
            ice_suspect.append(
                (ice, "全書幕綱既無這條伏筆的埋也無收，也沒有未拆的 arc 可以解釋")
            )

    return Report(
        spine=spine,
        threads=sorted(
            threads.values(),
            key=lambda t: _pos(spine, (t.plants or t.pays)[0]),
        ),
        violations=[v for s in scans for v in s.violations],
        ice_resolved=ice_resolved,
        ice_pending=ice_pending,
        ice_suspect=ice_suspect,
        ice_scanned=len(ices),
        expired_unbuilt=expired,
        scanned_arcs=[s.arc for s in scans],
    )


def entering(report: Report, arc: str) -> list[Thread]:
    """進入 arcNN 時仍開著的伏筆＋本 arc 自己動到的——`beat-sheet` 要的接口查詢。"""
    if arc not in report.spine:
        raise ScanError(f"arc {arc!r} 不在 spine（全書順序）中")
    rank = report.spine[arc]
    out: list[Thread] = []
    for t in report.threads:
        touches_here = any(m.arc == arc for m in t.plants + t.pays)
        planted_before = any(report.spine[m.arc] < rank for m in t.plants)
        paid_before = any(report.spine[m.arc] < rank for m in t.pays)
        if touches_here or (planted_before and not paid_before):
            out.append(t)
    return out
