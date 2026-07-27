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


# -------------------------------------------------------- 揭示層級（原 🧊 水下）
#
# **2026-07-27 收斂成單一語法，並修掉一個假陰性。**
#
# 舊狀態：schema 授權**三種**寫法（`共同約定.md` 的行內 `（🧊 水下｜…）`、
# `世界觀.schema.md` 的 front-matter 鍵 `🧊水下:`、`角色.schema.md` 的 `## 🧊 水下`
# 整節），而本模組只認第一種。實測一世之尊：🧊 出現 92 次、解析出 1 條，而
# `foreshadow-project` 印「0 條為可疑點」exit 0——**不是沒有守衛，是有一個守衛在
# 報平安**（`設計原則.md` E2 第五格就是為這一格補的）。
#
# 新狀態：揭示層級只住 `story/物件/<名>.md` 的 front-matter `揭示層級` 欄，三種值：
# `公開`／`水下｜揭示於 收[[伏筆:X]]`／`水下｜跨集留白`。設定層 `.ai.md` 裡再出現
# 🧊 一律報成**落點已廢除**（它在那裡活不過下一次重生）。
#
# 而且無論如何都要印「掃到 N 處／解析 N 處／無法解析 N 處」——見 `cli.format_report`。

_REVEAL_KEY = "揭示層級"
_REVEAL_RE = re.compile(rf"^{_REVEAL_KEY}\s*[:：]\s*(.+?)\s*$")
_UNDERWATER_RE = re.compile(r"^水下\s*[｜|]\s*(.+)$")
_CROSS_BOOK = "跨集留白"
_ICE = "🧊"


@dataclass(frozen=True)
class Ice:
    """一個揭示層級標記。`raw` 留著原文，因為「無法解析」也要報得出是什麼。"""

    target: str | None  # 指向的伏筆名；跨集留白／解析失敗為 None
    cross_book: bool
    file: Path
    lineno: int
    raw: str = ""
    retired_location: bool = False  # 還寫在設定層 .ai.md 的舊 🧊

    @property
    def parsed(self) -> bool:
        return self.target is not None or self.cross_book


def _parse_reveal(value: str) -> tuple[str | None, bool]:
    """`揭示層級` 的值 → (指向的伏筆名, 是否跨集留白)。都是 None/False ＝解析不了。"""
    m = _UNDERWATER_RE.match(value.strip())
    if not m:
        return None, False
    tail = m.group(1)
    if _CROSS_BOOK in tail:
        return None, True
    mark = _MARK_RE.search(tail)
    return (mark.group(2).strip() if mark else None), False


def scan_reveal(book: Path) -> list[Ice]:
    """掃物件檔的 `揭示層級` 欄，外加設定層 `.ai.md` 的殘留 🧊（落點已廢除）。

    注意：`揭示層級` 裡的 `收[[伏筆:x]]` 是**指標**、不是回收點，故不併入 Mark。
    """
    ices: list[Ice] = []
    objects = book / "story" / "物件"
    if objects.is_dir():
        for p in sorted(objects.glob("*.md")):
            if p.stem.startswith("_"):
                continue
            for i, raw in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
                m = _REVEAL_RE.match(raw.strip())
                if not m:
                    continue
                value = m.group(1).strip().strip('"').strip("'")
                if value == "公開":
                    continue  # 公開的不是揭示層級標記，沒什麼要解析
                target, cross = _parse_reveal(value)
                ices.append(
                    Ice(target=target, cross_book=cross, file=p, lineno=i, raw=value)
                )

    settings = book / "story" / "設定"
    if settings.is_dir():
        for p in sorted(settings.rglob("*.ai.md")):
            for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if _ICE in raw:
                    ices.append(
                        Ice(
                            target=None,
                            cross_book=False,
                            file=p,
                            lineno=i,
                            raw=raw.strip()[:60],
                            retired_location=True,
                        )
                    )
    return ices
