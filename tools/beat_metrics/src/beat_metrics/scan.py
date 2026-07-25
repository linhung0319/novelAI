"""幕綱八欄解析（`結構定義/幕綱.schema.md`「固定欄位（八項）」）。

**為什麼自帶解析器、不與 `foreshadow_project` 共用**：本 repo 的 tools/ 慣例是各套件
零依賴、小 regex 各自持有（`_BEAT_HEAD_RE` 今天同時存在於 `foreshadow_project/scan.py`
與 `derived_sync/sentinel.py`）。`foreshadow_project` 只認「伏筆」一欄——它刻意不解析
其餘七欄，因為多解析一欄就多一種誤配對的來源。本檔要的是全八欄，職責不同。

**只讀八欄，不讀檔尾設計註**——這正是 `幕綱.schema.md`「設計註只讀不抄」的機械版：
`write` 抄的是欄位，所以量的也只能是欄位。把設計註算進來會讓「把治理文字搬到檔尾」
這個正確動作看起來像沒有改善。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class ScanError(Exception):
    """幕綱檔無法定位或解析。"""


FIELDS = ("角色", "時空", "行動", "衝突", "結果", "前因", "伏筆", "結構階段")

# 八欄裡有兩欄是**結構化連結欄**，不是散文：`前因` 只寫 `[[幕NNN]]`、`伏筆` 只寫
# `埋/收[[伏筆:x]]` 與 `arcNN（未拆）`／「見伏筆狀態表」這類指標（`幕綱.schema.md`
# 「連結規範」「本 arc 伏筆狀態」）。把它們算進母題重複與元管理掃描會製造大量假陽性：
# 實測未排除時「見伏筆狀態」「伏筆狀態表」佔滿每個 arc 的重複前三名，而 `arcNN（未拆）`
# 讓連 arc01 都被判成分區衛生違規。**指標欄的重複是格式，不是母題。**
PROSE_FIELDS = ("角色", "時空", "行動", "衝突", "結果", "結構階段")

# 母題重複再少一欄：`角色` 是**名單**，不是散文。主角每一幕都要列，「孟奇（真定）」
# 與「（心裡·不在場：…）」這類括註格式因此在每個 arc 都會重複——那是 schema 要求的
# 樣板，不是母題在迴圈。實測未排除時 arc11 的重複前五名有兩名是角色欄樣板
# （「心裡不在場」×5、「孟奇真定妙音」×5），排除後 arc01↔arc11 的分離從 8 倍升到 11 倍。
MOTIF_FIELDS = ("時空", "行動", "衝突", "結果", "結構階段")

_BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)\s*[·・]?\s*(.*)$")
# 全形／半形冒號都收：schema 寫全形，實檔兩種都出現過，錯字不該靜默漏掉。
_FIELD_RE = re.compile(rf"^-\s*({'|'.join(FIELDS)})\s*[：:]\s*(.*)$")
_ARC_FILE_RE = re.compile(r"^arc[0-9A-Za-z]+$")


@dataclass
class Beat:
    number: int
    title: str
    arc: str
    lineno: int
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def prose(self) -> str:
        """六個散文欄併成一串——元管理字樣掃描以此為母體（見 `PROSE_FIELDS`）。"""
        return "".join(self.fields.get(k, "") for k in PROSE_FIELDS)

    @property
    def motif_body(self) -> str:
        """母題重複的母體：再去掉名單型的 `角色` 欄（見 `MOTIF_FIELDS`）。"""
        return "".join(self.fields.get(k, "") for k in MOTIF_FIELDS)


@dataclass
class ArcBeats:
    arc: str
    path: Path
    beats: list[Beat] = field(default_factory=list)


def scan_arc(path: Path, arc: str) -> ArcBeats:
    """掃一個 arc 幕綱的八欄。

    續行（欄位值換行續寫）併回該欄；`##` 之後、第一個欄位之前的散文（arc 檔頭、
    幕註）一律丟棄——它們不是欄位，不該進統計。
    """
    out = ArcBeats(arc=arc, path=path)
    current: Beat | None = None
    current_field: str | None = None
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if raw.startswith("##"):
            m = _BEAT_HEAD_RE.match(raw)
            if m:
                current = Beat(
                    number=int(m.group(1)), title=m.group(2).strip(), arc=arc, lineno=i
                )
                out.beats.append(current)
            else:
                current = None  # 「本 arc 伏筆狀態」等非幕小節
            current_field = None
            continue

        if current is None:
            continue

        stripped = raw.strip()
        m = _FIELD_RE.match(stripped)
        if m:
            current_field = m.group(1)
            current.fields[current_field] = m.group(2).strip()
        elif current_field and stripped and not stripped.startswith(("-", "|", ">", "（", "(")):
            # 續行：欄位值被換行斷開時接回去。以 `-` 開頭的是下一個 bullet，
            # 以 `（` 開頭的是幕註（schema：幕註不是欄位），都不接。
            current.fields[current_field] += stripped
        else:
            current_field = None
    return out


def load_book(book: Path) -> list[ArcBeats]:
    """依 `幕綱/_index.md`「全書順序」定序——與 foreshadow_project 同源的紀律：
    **判先後不能比幕號大小**（arc 會亂序下沉，幕號不代表全書順序）。
    """
    d = book / "story" / "幕綱"
    if not d.is_dir():
        raise ScanError(f"找不到幕綱目錄：{d}")
    files = {p.stem: p for p in sorted(d.glob("*.md")) if _ARC_FILE_RE.match(p.stem)}
    if not files:
        raise ScanError(f"{d} 下沒有 arcNN.md")

    order = _spine(d / "_index.md")
    ranked = sorted(files, key=lambda a: (order.get(a, len(order)), a))
    return [scan_arc(files[a], a) for a in ranked]


_SPINE_RE = re.compile(r"全書順序：(.+)$")
_ARC_TOKEN_RE = re.compile(r"arc[0-9A-Za-z]+")


def _spine(index: Path) -> dict[str, int]:
    """讀不到 spine 就回空 dict——本工具全部是**逐 arc 統計**，定序只影響
    「誰是前段基準」。缺 spine 時退回檔名排序仍可用，不值得為此中止。
    """
    if not index.is_file():
        return {}
    for raw in index.read_text(encoding="utf-8").splitlines():
        m = _SPINE_RE.search(raw)
        if not m:
            continue
        arcs: list[str] = []
        for tok in _ARC_TOKEN_RE.findall(m.group(1)):
            if tok not in arcs:
                arcs.append(tok)
        if arcs:
            return {a: r for r, a in enumerate(arcs)}
    return {}


_POV_RE = re.compile(r"^視角結構:.*?POV\s*[:：]\s*([^,，}\s]+)", re.MULTILINE)


def load_pov(book: Path) -> str | None:
    """主角＝`00-摘要.ai.md` front-matter `視角結構.POV`。

    **讀不到就回 None、不猜**：純內在幕比例是「主角獨處」的比例，猜錯主角會讓
    整項數字失真且無從察覺——報「不適用」比報一個錯的數字誠實。
    """
    p = book / "story" / "00-摘要.ai.md"
    if not p.is_file():
        return None
    m = _POV_RE.search(p.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else None
