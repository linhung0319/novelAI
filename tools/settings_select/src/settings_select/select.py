from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class SelectError(Exception):
    """幕綱／設定層解析或定位失敗（找不到 arc、幕號範圍不合法、設定層缺目錄）。"""


# ---------------------------------------------------------------- 已知實體詞彙表

@dataclass(frozen=True)
class Entity:
    """一個設定層實體。name 取自**源檔檔名**——源是唯一真實來源，故檔名即權威名。"""

    name: str
    kind: str  # 角色 / 世界觀
    source: Path
    derived: Path | None  # <名>.ai.md，尚未重生時為 None

    @property
    def read_path(self) -> Path:
        """下游該讀哪一份：有衍生讀衍生（機器事實＋分析），否則退回源。"""
        return self.derived or self.source


def load_entities(book: Path) -> list[Entity]:
    """掃 story/設定/{角色,世界觀}/ 建詞彙表。

    刻意**不解析幕綱「角色」欄的中文文法**（分隔符有 、／· 、還有括號註解、法號別名），
    改以此詞彙表對幕綱文字做比對——方向正確（設定檔定義詞彙），且對標點風格免疫。
    """
    entities: list[Entity] = []
    for kind in ("角色", "世界觀"):
        d = book / "story" / "設定" / kind
        if not d.is_dir():
            continue
        for src in sorted(d.glob("*.md")):
            if src.name.endswith(".ai.md") or src.name.startswith("_"):
                continue
            derived = src.parent / f"{src.stem}.ai.md"
            entities.append(
                Entity(
                    name=src.stem,
                    kind=kind,
                    source=src,
                    derived=derived if derived.exists() else None,
                )
            )
    if not entities:
        raise SelectError(f"找不到任何設定層實體：{book / 'story' / '設定'}")
    return entities


# ---------------------------------------------------------------- 幕綱解析

_BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)\s*[·・]?\s*(.*)$")
_ROLE_FIELD_RE = re.compile(r"^-\s*角色：\s*(.*)$")


@dataclass
class Beat:
    number: int
    title: str
    role_field: str = ""
    body: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.body)


def parse_beats(text: str) -> list[Beat]:
    """把 arc 幕綱切成幕。檔頭（承諾區）與檔尾（伏筆狀態表／設計註）不屬於任何幕，捨棄。

    任何**不是幕標題的 `##` 小節**都會結束當前幕——否則檔尾的「## 本 arc 伏筆狀態」
    會被併進最後一幕，那張表提到大量實體，會把選取結果整個污染回全讀。
    """
    beats: list[Beat] = []
    cur: Beat | None = None
    for raw in text.splitlines():
        if raw.startswith("##"):
            m = _BEAT_HEAD_RE.match(raw)
            if m:
                cur = Beat(number=int(m.group(1)), title=m.group(2).strip())
                beats.append(cur)
            else:
                cur = None  # 非幕小節（承諾區／伏筆表／設計註）→ 離開幕範圍
            continue
        if cur is None:
            continue
        cur.body.append(raw)
        rm = _ROLE_FIELD_RE.match(raw.strip())
        if rm and not cur.role_field:
            cur.role_field = rm.group(1).strip()
    return beats


_RANGE_RE = re.compile(r"^幕?(\d+)\s*[-–~]\s*幕?(\d+)$")


def parse_beat_range(spec: str) -> tuple[int, int]:
    s = spec.strip()
    m = _RANGE_RE.match(s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo > hi:
            raise SelectError(f"幕號範圍起大於訖：{spec!r}")
        return lo, hi
    m2 = re.match(r"^幕?(\d+)$", s)
    if m2:
        n = int(m2.group(1))
        return n, n
    raise SelectError(f"--beats 格式須為『幕1001-1005』或『幕1001』，得到 {spec!r}")


# ---------------------------------------------------------------- 選取

@dataclass(frozen=True)
class Hit:
    entity: Entity
    beats: tuple[int, ...]


@dataclass
class Selection:
    arc: str
    beat_count: int
    selected: list[Hit]  # 角色欄命中（角色）＋全幕文字命中（世界觀）→ 要讀
    mentioned_only: list[Hit]  # 只在角色欄以外出現的角色 → 不讀，報成可疑點
    unknown_dir: list[str]  # 設定層缺目錄的提示


def _hits(
    entities: list[Entity], probes: list[tuple[int, str]]
) -> dict[str, list[int]]:
    """probes = [(幕號, 待掃文字)]。回傳 {實體名: [命中的幕號]}（保持出現序）。"""
    found: dict[str, list[int]] = {}
    for e in entities:
        for beat_no, text in probes:
            if e.name in text:
                found.setdefault(e.name, [])
                if beat_no not in found[e.name]:
                    found[e.name].append(beat_no)
    return found


def select(
    book: Path, arc: str, beats_spec: str | None = None
) -> Selection:
    arc_path = book / "story" / "幕綱" / f"{arc}.md"
    if not arc_path.is_file():
        raise SelectError(f"找不到幕綱：{arc_path}")
    entities = load_entities(book)
    by_name = {e.name: e for e in entities}

    all_beats = parse_beats(arc_path.read_text(encoding="utf-8"))
    if not all_beats:
        raise SelectError(f"{arc_path} 解析不到任何『## 幕NNN』小節")
    if beats_spec:
        lo, hi = parse_beat_range(beats_spec)
        chosen = [b for b in all_beats if lo <= b.number <= hi]
        if not chosen:
            raise SelectError(f"{arc} 內沒有幕號落在 {beats_spec} 範圍內")
    else:
        chosen = all_beats

    chars = [e for e in entities if e.kind == "角色"]
    worlds = [e for e in entities if e.kind == "世界觀"]

    # 角色：以「角色」欄為準——那是幕綱對「這一幕有誰」的正式宣告。
    role_probes = [(b.number, b.role_field) for b in chosen]
    char_hits = _hits(chars, role_probes)
    # 世界觀：無對應欄位，掃全幕文字。
    world_probes = [(b.number, b.text) for b in chosen]
    world_hits = _hits(worlds, world_probes)

    # 只在角色欄以外出現的角色＝可能是幕綱漏填角色欄，報出來但**不自動納入**（否則又回到過讀）。
    body_probes = [(b.number, b.text) for b in chosen]
    body_hits = _hits(chars, body_probes)
    mentioned = {n: bs for n, bs in body_hits.items() if n not in char_hits}

    selected = [
        Hit(by_name[n], tuple(bs))
        for n, bs in sorted(char_hits.items(), key=lambda kv: kv[1][0])
    ] + [
        Hit(by_name[n], tuple(bs))
        for n, bs in sorted(world_hits.items(), key=lambda kv: kv[1][0])
    ]
    mentioned_only = [
        Hit(by_name[n], tuple(bs))
        for n, bs in sorted(mentioned.items(), key=lambda kv: kv[1][0])
    ]

    missing_dirs = [
        kind
        for kind in ("角色", "世界觀")
        if not (book / "story" / "設定" / kind).is_dir()
    ]
    return Selection(
        arc=arc,
        beat_count=len(chosen),
        selected=selected,
        mentioned_only=mentioned_only,
        unknown_dir=missing_dirs,
    )
