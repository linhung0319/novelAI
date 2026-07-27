from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class SelectError(Exception):
    """幕綱／設定層解析或定位失敗（找不到 arc、幕號範圍不合法、設定層缺目錄）。"""


# ---------------------------------------------------------------- 已知實體詞彙表

# 角色源檔目錄形態的切面枚舉（見 結構定義/角色.schema.md）。檔名即選擇器。
FACETS = ("核心", "來歷", "能力", "關係", "水下")
# 水下＝揭底資訊。預設**不給**——這是存取控制，不只是分大小：讓 write 在揭底
# 前的章節拿不到它，比同檔內的 🧊 標記強一級。要它得顯式 include_underwater。
UNDERWATER_FACET = "水下"


@dataclass(frozen=True)
class Entity:
    """一個設定層實體。name 取自**源的檔名／目錄名**——源是唯一真實來源，故名即權威名。

    源有兩種形態（`角色.schema.md`）：單檔 `<名>.md`，或目錄 `<名>/<切面>.md`。
    """

    name: str
    kind: str  # 角色 / 世界觀
    source: Path  # 單檔形態＝該 .md；目錄形態＝該目錄
    derived: Path | None  # <名>.ai.md，尚未重生時為 None

    @property
    def dir_form(self) -> bool:
        return self.source.is_dir()

    def source_paths(
        self,
        facets: tuple[str, ...] | None = None,
        include_underwater: bool = False,
    ) -> list[Path]:
        """源這一側該讀哪幾支。單檔形態切不動，一律整檔。"""
        if not self.dir_form:
            return [self.source]
        wanted = set(facets) if facets else set(FACETS)
        if not include_underwater:
            wanted.discard(UNDERWATER_FACET)
        return [p for p in sorted(self.source.glob("*.md")) if p.stem in wanted]

    def read_paths(
        self,
        facets: tuple[str, ...] | None = None,
        include_underwater: bool = False,
    ) -> list[Path]:
        """下游該讀哪幾份＝衍生（四象限分析）＋源的相關切面（他是誰／聲音／能力）。

        兩邊都要：衍生檔依 schema 只放分析，人物描述在源——只讀衍生會拿不到腔調
        與外貌，只讀源會拿不到需求弧線。
        """
        out: list[Path] = []
        if self.derived:
            out.append(self.derived)
        out += self.source_paths(facets, include_underwater)
        return out


def load_entities(book: Path) -> list[Entity]:
    """掃 story/設定/{角色,世界觀}/ 建詞彙表。

    刻意**不解析幕綱「角色」欄的中文文法**（分隔符有 、／· 、還有括號註解、法號別名），
    改以此詞彙表對幕綱文字做比對——方向正確（設定檔定義詞彙），且對標點風格免疫。

    **`<名>.md` 與 `<名>/` 並存時以目錄為準、跳過單檔**（2026-07-27 功能 06）：
    在此之前兩者會各建一個 Entity，於是同一個角色在 `by_name` 裡互相覆蓋，
    而覆蓋的方向取決於 `iterdir` 的排序——結果是**目錄形態的切面永遠選不到**。
    `角色.schema.md` 已明訂兩種形態不得並存（升級是搬移：`git mv <名>.md
    <名>/核心.md`），**報並存是 `char-lint` 的事**；這裡只保證選取結果是
    deterministic 的，不靜默地二選一。
    """
    entities: list[Entity] = []
    for kind in ("角色", "世界觀"):
        d = book / "story" / "設定" / kind
        if not d.is_dir():
            continue
        dir_names = {
            p.name for p in d.iterdir() if p.is_dir() and not p.name.startswith("_")
        }
        for entry in sorted(d.iterdir()):
            if entry.is_dir():  # 目錄形態
                if entry.name.startswith("_"):
                    continue
                name = entry.name
            elif (
                entry.suffix == ".md"
                and not entry.name.endswith(".ai.md")
                and not entry.name.startswith("_")
            ):
                if entry.stem in dir_names:
                    continue  # 並存：目錄為準（見 docstring）
                name = entry.stem
            else:
                continue
            derived = d / f"{name}.ai.md"
            entities.append(
                Entity(
                    name=name,
                    kind=kind,
                    source=entry,
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


@dataclass(frozen=True)
class WorldBasis:
    """一個世界觀主題**為什麼**被選中：靠檔名引用，還是靠內容裡的裸提及。

    2026-07-27（功能 05 抉擇 2 D）新增。**只量、不改選取行為。**

    診斷出來的病：世界觀那一側的 selector 是「拿檔名去掃全幕文字」，而實測
    一世之尊 4 個主題裡 3 個的裸提及率是 **0**——它們全靠幕綱散文寫了
    `見 \\`X.ai.md\\`` 這類**檔名引用**才被命中。也就是說命中的不是內容，是註腳。

    為什麼這一格必須印出來：02 明文要把設計註／檔名引用從幕綱八欄清出去。
    **那個目標達成之日，就是 3/4 個世界觀主題從選取結果消失之日**，而
    `settings-select` 會印一份格式完全正常、不含任何警告的結果，`write` 就在
    缺三份核心規則的情況下動筆（`設計原則.md` E2 最後一格：守衛回報正常的假陰性）。
    """

    name: str
    by_filename: int  # `<名>.ai.md`／`<名>.md` 這類引用的出現次數
    bare: int  # 其餘（真的在講這個主題）

    @property
    def filename_only(self) -> bool:
        return self.bare == 0


@dataclass
class Selection:
    arc: str
    beat_count: int
    selected: list[Hit]  # 角色欄命中（角色）＋全幕文字命中（世界觀）→ 要讀
    mentioned_only: list[Hit]  # 只在角色欄以外出現的角色 → 不讀，報成可疑點
    unknown_dir: list[str]  # 設定層缺目錄的提示
    char_count: int = 0  # 角色命中幾筆（覆蓋率行用，0 也印）
    char_hollow: list[str] = field(default_factory=list)  # 命中但衍生檔是空的
    world_basis: list[WorldBasis] = field(default_factory=list)  # 世界觀的命中依據


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


def _world_basis(
    entities: list[Entity], names: list[str], probes: list[tuple[int, str]]
) -> list[WorldBasis]:
    """對每個命中的世界觀主題，分類它每一處出現是「檔名引用」還是「裸提及」。

    判準是**位置**而非語意：命中處後面緊接 `.ai.md`／`.md` ＝ 檔名引用。這與
    `derived_sync/validate.py` 的 blockquote 位置判準同一個取法——語意判準
    （「這句是在講這個主題還是在指路」）需要讀懂中文，而那正是 `prose-metrics`
    的關鍵詞分類被駁回的形狀。
    """
    by_name = {e.name: e for e in entities}
    out: list[WorldBasis] = []
    for n in names:
        if n not in by_name:
            continue
        fn = bare = 0
        for _, text in probes:
            start = 0
            while (i := text.find(n, start)) != -1:
                tail = text[i + len(n) : i + len(n) + 6]
                if tail.startswith(".ai.md") or tail.startswith(".md"):
                    fn += 1
                else:
                    bare += 1
                start = i + len(n)
        out.append(WorldBasis(name=n, by_filename=fn, bare=bare))
    return out


# ---------------------------------------------------------------- 空殼偵測
# `設計原則.md` E2 的可執行推論（2026-07-27 功能 06 補）：**覆蓋率行要能回答
# 「命中的筆數裡，有幾筆是空的」。** 「命中 N 筆」與「N 筆裡有 M 筆是佔位」是
# 兩個數字，只印前一個等於用命中率冒充可用率。
#
# 實測：本工具對 arc02 印「角色命中 7 筆」——依據正確（幕綱的角色欄）、數字正確，
# 而其中 4 筆是四個必填節全為佔位字串的空殼檔，`beat-test` 測試4 就拿它當基準。
# 三支守衛（`check` 報 fresh／`validate` 只驗結構／本工具只管選取）各自都沒做錯。
#
# **這是 `char-lint` 佔位偵測的第 2 份實作**（工具間零相依，所有
# `tools/*/pyproject.toml` 皆 `dependencies = []`，故複製而非 import）→ 功能 14。
# 判準與那一份一致：**形狀，不是詞表**——值為空，或值整個就是一段括號註記
# （`（源檔未載，待跑 character 補）`）＝它是註記不是內容。
_CHAR_REQUIRED_SECTIONS = ("需求四象限", "預期弧線")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^[-*+]\s+")
_PLACEHOLDER_RE = re.compile(r"[（(][^（()）]*[)）]")


def _slot_value(line: str) -> str | None:
    s = line.strip()
    if not s or s.startswith((">", "|", "#")):
        return None
    s = _BULLET_RE.sub("", s).strip()
    if not s:
        return None
    depth = 0
    for i, ch in enumerate(s):
        if ch in "（(":
            depth += 1
        elif ch in ")）":
            depth = max(0, depth - 1)
        elif ch in "：:" and depth == 0:
            return s[i + 1 :].strip()
    return s


def is_hollow(entity: Entity) -> bool:
    """這個角色的衍生檔缺失，或它的必填節整節都是佔位。"""
    if entity.kind != "角色":
        return False
    if entity.derived is None or not entity.derived.is_file():
        return True
    text = entity.derived.read_text(encoding="utf-8").replace("\r\n", "\n")
    for title in _CHAR_REQUIRED_SECTIONS:
        values: list[str] = []
        found = inside = False
        for raw in text.split("\n"):
            m = _H2_RE.match(raw.strip())
            if m:
                inside = m.group(1).strip().startswith(title)
                found = found or inside
                continue
            if inside and (v := _slot_value(raw)) is not None:
                values.append(v)
        if not found or not values:
            return True
        if all(not v or _PLACEHOLDER_RE.fullmatch(v) for v in values):
            return True
    return False


def parse_facets(spec: str | None) -> tuple[str, ...] | None:
    if not spec:
        return None
    facets = tuple(f.strip() for f in spec.split(",") if f.strip())
    unknown = [f for f in facets if f not in FACETS]
    if unknown:
        raise SelectError(f"--facets 含未知切面 {unknown}（限 {list(FACETS)}）")
    return facets


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
        char_count=len(char_hits),
        char_hollow=sorted(n for n in char_hits if is_hollow(by_name[n])),
        world_basis=_world_basis(worlds, list(world_hits), world_probes),
    )
