"""幕綱檔的**全檔結構**解析（分區／承諾／伏筆標記／狀態表／前因引用）。

**為什麼與 `scan.py` 分兩個模組。** `scan.py` 只解析八欄，而且**刻意不讀檔尾設計註**
——它服務 `beat-metrics` 的統計，量的必須與 `write` 抄的同一批東西（`scan.py` 檔頭）。
`beat-lint` 要驗的是**格式承諾**，範圍是整支檔：分區在不在、幕號撞不撞、
`[[幕NNN]]` 指得到嗎、承諾區的排除線抓不抓得出來。職責不同，但**共用同一組 regex**
（同套件內 import，不複製——套件之間才複製，見 `scan.py` 檔頭）。

八欄與其內容一律走 `scan.scan_arc()`，本模組不自己再解析一次欄位：
`前因`／`伏筆` 的續行併回邏輯只該有一份，兩份會漂。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .scan import _ARC_FILE_RE, Beat, ScanError, read_text, scan_arc

# 分區（`幕綱.schema.md`「arc 檔的內部結構」）。四種以外的 `##` 都是未定義分區。
PROMISE_HEAD = "本 arc 承諾"
STATUS_HEAD = "本 arc 伏筆狀態"
DESIGN_HEAD = "設計註"

# **這份 regex 的唯一真相在 `tools/foreshadow_project/src/foreshadow_project/scan.py:_MARK_RE`**；
# 工具間零相依，故複製最小片段。schema 用半形冒號，這裡連全形一起收，錯字不靜默漏掉。
_MARK_RE = re.compile(r"(埋|收)\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]")
_BEAT_REF_RE = re.compile(r"\[\[幕(\d+)\]\]")

_PROMISE_HEAD_RE = re.compile(rf"^##\s*{PROMISE_HEAD}\s*$")
_STATUS_HEAD_RE = re.compile(r"^##\s*本\s*arc\s*伏筆狀態")
_DESIGN_HEAD_RE = re.compile(rf"^##\s*{DESIGN_HEAD}")
_H2_RE = re.compile(r"^##\s+(.*?)\s*$")
_BULLET_RE = re.compile(r"^-\s*(.+?)\s*[：:]\s*(.*)$")
_SUBITEM_RE = re.compile(r"^\s+-\s*(.+?)\s*$")
_TAIL_HOOK_RE = re.compile(r"^-\s*幕尾鉤\s*[：:]")
_SEP_ROW_RE = re.compile(r"^\|[\s:|-]+\|$")
# 測試執行紀錄的宣告行（2026-07-28 功能 10 抉擇 3 A）。**只認檔頭**——第一個
# `##` 之前，與 `幕綱.schema.md`「分區是硬規定」一致（檔頭是本 arc 的元資料區）。
# 位置判準，不是內容判準：全檔掃會撈到設計註裡談 beat-test 的散文。
_BEAT_TEST_RE = re.compile(r"^\s*beat-test\s*[：:]\s*(.*?)\s*$")

# `⚠️ 尚未產出` ＝ `書本模板/` 的空骨架標記：檔案存在只是先把位置佔好。
# 對骨架報「八欄全空、伏筆 x 不存在」是雜訊——但**跳過幾支要印出來**，否則就是
# 另一個「守衛報平安」（`設計原則.md` E2 第五格）。
SKELETON_MARK = "尚未產出"

# 空欄位的各種寫法。`伏筆：—` 是 schema 明訂的合法值（本幕無伏筆）。
EMPTY_VALUES = frozenset({"", "—", "–", "-", "－", "無"})


@dataclass(frozen=True)
class Mark:
    """一個 `埋|收[[伏筆:x]]` 標記。只認幕的「伏筆」欄（`幕綱.schema.md` 單一真實來源）。"""

    kind: str
    name: str
    beat: int
    arc: str
    lineno: int


@dataclass(frozen=True)
class BeatRef:
    """一條 `前因 [[幕NNN]]` 引用。`target` 是被指向的幕號。"""

    target: int
    beat: int
    arc: str
    lineno: int


@dataclass(frozen=True)
class StatusRow:
    arc: str
    name: str
    planted: str
    paid: str
    note: str
    lineno: int


@dataclass(frozen=True)
class Promise:
    """承諾區的一條 top-level 條目。`items` 是它底下的縮排子項（排除線走這裡）。"""

    label: str
    value: str
    items: tuple[str, ...]
    lineno: int


@dataclass
class ArcStructure:
    arc: str
    path: Path
    skeleton: bool = False
    beats: list[Beat] = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)
    refs: list[BeatRef] = field(default_factory=list)
    rows: list[StatusRow] = field(default_factory=list)
    promises: list[Promise] = field(default_factory=list)
    has_promise_section: bool = False
    has_status_table: bool = False
    design_note_lines: int = 0
    unknown_sections: list[tuple[int, str]] = field(default_factory=list)
    tail_hook_beats: list[int] = field(default_factory=list)
    # 檔頭的 `beat-test:` 宣告行（值, 行號）。沒有就是 None——**缺席是合法狀態**。
    beat_test: tuple[str, int] | None = None

    @property
    def exclusions(self) -> tuple[str, ...]:
        """承諾區的排除線（`不得發生` 的子項）。

        落點留在 arc 檔（抉擇 4 B：射程天然綁 arc），但由 `fact-project --for-beat`
        一起讀到，`write` 不會漏——**兩個家在查詢層合流**。
        """
        for p in self.promises:
            if p.label == "不得發生":
                return p.items
        return ()


def _label(raw: str) -> str:
    """`**不得發生**` → `不得發生`；`**措辭硬約束**（…）` → `措辭硬約束`。

    作者實際寫的是粗體包裹＋括註（實測 arc11 承諾區八條全是這個形狀），
    schema 範例寫的是裸標籤。**兩種都要認**——標籤的形狀不該決定排除線抓不抓得到。
    """
    s = raw.replace("*", "").strip()
    return re.split(r"[（(]", s, maxsplit=1)[0].strip()


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_arc(path: Path, arc: str) -> ArcStructure:
    """解析一支 arc 幕綱的全檔結構。八欄本身走 `scan.scan_arc()`。"""
    out = ArcStructure(arc=arc, path=path)
    text = read_text(path)
    out.skeleton = SKELETON_MARK in text
    out.beats = scan_arc(path, arc).beats

    # 幕內容（標記／引用）從八欄取，續行併回的邏輯只有 scan.py 一份。
    for b in out.beats:
        for kind, name in _MARK_RE.findall(b.fields.get("伏筆", "")):
            out.marks.append(
                Mark(kind=kind, name=name.strip(), beat=b.number, arc=arc, lineno=b.lineno)
            )
        for m in _BEAT_REF_RE.finditer(b.fields.get("前因", "")):
            out.refs.append(
                BeatRef(target=int(m.group(1)), beat=b.number, arc=arc, lineno=b.lineno)
            )

    section: str | None = None
    pending: Promise | None = None
    items: list[str] = []

    def _flush() -> None:
        nonlocal pending, items
        if pending is not None:
            out.promises.append(
                Promise(
                    label=pending.label,
                    value=pending.value,
                    items=tuple(items),
                    lineno=pending.lineno,
                )
            )
        pending, items = None, []

    for i, raw in enumerate(text.splitlines(), start=1):
        if section is None and out.beat_test is None:
            # 檔頭（第一個 `##` 之前）：測試執行紀錄的宣告行。
            head = _BEAT_TEST_RE.match(raw)
            if head:
                out.beat_test = (head.group(1), i)
        if raw.startswith("##"):
            _flush()
            head = _H2_RE.match(raw)
            title = head.group(1) if head else raw.strip("# ").strip()
            if re.match(r"^幕\d+", title):
                section = "beat"
            elif _PROMISE_HEAD_RE.match(raw):
                section, out.has_promise_section = "promise", True
            elif _STATUS_HEAD_RE.match(raw):
                section, out.has_status_table = "status", True
            elif _DESIGN_HEAD_RE.match(raw):
                section = "design"
            else:
                section = "unknown"
                out.unknown_sections.append((i, title))
            continue

        if section == "beat":
            if _TAIL_HOOK_RE.match(raw.strip()):
                out.tail_hook_beats.append(out.beats[-1].number if out.beats else 0)
        elif section == "design":
            if raw.strip():
                out.design_note_lines += 1
        elif section == "promise":
            if _SUBITEM_RE.match(raw) and pending is not None:
                items.append(_SUBITEM_RE.match(raw).group(1))
            elif raw.startswith("-"):
                m = _BULLET_RE.match(raw.strip())
                if m:
                    _flush()
                    pending = Promise(
                        label=_label(m.group(1)), value=m.group(2), items=(), lineno=i
                    )
        elif section == "status":
            line = raw.strip()
            if not line.startswith("|") or _SEP_ROW_RE.match(line):
                continue
            cells = _cells(line)
            if len(cells) < 4 or cells[0] in ("伏筆", ""):
                continue  # 表頭
            out.rows.append(
                StatusRow(
                    arc=arc,
                    name=cells[0],
                    planted=cells[1],
                    paid=cells[2],
                    note=cells[3],
                    lineno=i,
                )
            )
    _flush()
    return out


def arc_files(book: Path) -> dict[str, Path]:
    d = book / "story" / "幕綱"
    if not d.is_dir():
        raise ScanError(f"找不到幕綱目錄：{d}")
    return {p.stem: p for p in sorted(d.glob("*.md")) if _ARC_FILE_RE.match(p.stem)}


def parse_book(book: Path) -> list[ArcStructure]:
    """依檔名排序解析全書。**這裡刻意不依 spine 定序**——spine 本身是 `beat-lint`
    的受檢對象之一，用一個還沒驗過的東西替受檢資料定序是循環依賴。
    """
    files = arc_files(book)
    if not files:
        raise ScanError(f"{book / 'story' / '幕綱'} 下沒有 arcNN.md")
    return [parse_arc(p, a) for a, p in sorted(files.items())]
