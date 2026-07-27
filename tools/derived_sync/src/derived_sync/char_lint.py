"""角色軸的格式閘門（`char-lint`）。

**為什麼它存在**（2026-07-27 功能 06 重構輪）：角色軸是重構盤點目前量到最壞的
一支，而它壞的方式是「守衛全部回報正常」——

  - **12/24 支衍生檔的四個必填節全是佔位字串**（84 處「（源檔未載，待跑
    `character` 補）」）。衍生層唯一宣稱的用途是當 `beat-test` 測試4「角色需求
    弧線」的基準，而對半數角色它是空的，**而三支守衛全部說沒事**：`check` 印
    fresh（源真的沒變，它報得沒錯）、`validate` 只驗節枚舉不驗節內容、
    `settings-select` 照樣把它算進「角色命中 N 筆」。
  - **「源檔有、衍生檔不存在」在定義上掃不到**：`core.check_book` 從
    `rglob("*.ai.md")` 出發。系統對這件事的處置是**手工建 13 支空殼衍生檔去餵
    掃描器**，那些檔的頭註逐字寫著這個理由。空殼檔是症狀，掃描方向才是病。
  - **7 個 front-matter 宣告欄零解析器**（162 個欄位實例，程式讀取 0 個），
    `伏筆` 已漂 1/12、`弧線類型` 24 支全填而全 repo 零消費者。
  - **rollup 視圖 ≡ front-matter 無人比對**：實測 10 筆不一致，其中 4 列的列名
    是自由造字（`真慧（方阿七）` vs 檔名 `真慧`）——那讓「拿 rollup 的列名去找檔」
    永遠落空，而沒有任何東西會報。

依 `設計原則.md` **A4**（會被解析的檔必須有一支 lint）、**E1**（每條格式承諾都要
指名檢查器；同輪新增的「凡宣稱『每一支 X 都有一支 Y』就要從 X 側掃」）、**E2**
（覆蓋率行要能回答「命中的裡面幾筆是空的」），作者拍板六個抉擇，本模組是它們的
閘門。**留下來的四個 front-matter 欄（`定位`／`所屬arc`／`暫定`／`伏筆`）由本模組
第 3／5 項真的讀** ——那是抉擇 1 B 成立的條件，不是加分項：讀不到就該刪掉。

**與 `validate` 的分工**（同 `world-lint`）：`validate` 管所有 `.ai.md` 共通的結構
（front-matter 必填鍵、`##` 節枚舉、裁決 blockquote）；本模組管**角色專屬**的欄
語意、節內容、rollup 視圖一致性與源側存在性。兩者同套件、共用 `_split_frontmatter`
——角色 `.ai.md` 的格式真相只有一份（先例：`object-lint` 是 `fact-lint` 的聚焦
入口、`ch-lint` 與 `beat-lint` 同套件）。

**已知的複製**：第 4 項的 `埋|收[[伏筆:x]]` regex 是這個 repo 的**第 5 份**
（`beat_metrics`／`fact_projection`／`world_lint` 各一）；第 5 項的「rollup 視圖
≡ 各檔 front-matter」是**第 3 份**（`ch-lint` 對 `chapters/_index.ai.md`、
`world-lint` 對 `_總覽.ai.md`）。工具間零相依（所有 `tools/*/pyproject.toml` 皆
`dependencies = []`），故複製而非 import。**三份 rollup 比對的差別只有欄名，是
零相依政策下最值得先收斂的一組** → 功能 14。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .core import AI_SUFFIX, _split_frontmatter

# 2026-07-27（功能 06 抉擇 1 B）**刪掉的三個宣告欄**＋01 已搬走的 `🧊水下`。
# 留著它們不是「舊格式還能用」——是「schema 已經不宣稱它們機讀，而檔裡還寫著
# 一個看起來機讀的值」，那正是漂移的形狀。既有書會被報，那是預期的（病例書不遷移）。
RETIRED_KEYS = ("角色", "弧線類型", "影響力", "🧊水下")

# 留下來的欄。**每一個都要在本模組被真的讀到**，否則依 A4／E1 它不配留在
# front-matter（見檔頭）。`定位` 是必填（rollup 那一欄的機械來源）。
REQUIRED_KEYS = ("generated-from", "generated-at", "定位")
POSITION_KEY = "定位"
POSITIONS = ("主角", "反派", "配角")
ARC_KEY = "所屬arc"
TENTATIVE_KEY = "暫定"
# front-matter 寫布林、rollup 那一欄寫中文——兩邊的對照在此，比對時歸一。
TENTATIVE_FM = {"true": True, "false": False}
TENTATIVE_ROLLUP = {"是": True, "否": False}
FORESHADOW_KEY = "伏筆"

# 衍生檔的封閉四節（唯一真相在 `validate.DERIVED_SECTIONS["角色"]`，這裡只列
# 本模組要看**內容**的那些，不重複定義枚舉本身）。
SECTIONS = ("需求四象限", "預期弧線", "馬斯洛層次", "對衝關係")
# 這兩節是 schema 的必填（「每個主角衍生檔至少填四象限與預期弧線」），
# 也正是 `beat-test` 測試4 拿來當基準的那兩節。
REQUIRED_SECTIONS = ("需求四象限", "預期弧線")

ROLLUP_STEM = "_index"
ROLLUP_SECTION = "角色清單"
# rollup 五欄：角色｜定位｜一行需求｜所屬arc｜暫定
COL_NAME, COL_POSITION, COL_NEED, COL_ARC, COL_TENTATIVE = range(5)

# `一行需求` 欄的**內容判準**（抉擇 5 A：不新增數字門檻，行長交給既有的
# `ROLLUP_LINE_CHARS=400`）。實測分佈 118 中位 → 1,024 最長是**連續的、沒有
# 空隙**，所以硬定一個數字只會是任意值；真正的病是那一欄裝了 01 已廢除的
# 揭示層級語法與章號（＝它變成第二份真相的信號）。
NEED_FORBIDDEN = (
    (re.compile(r"🧊"), "🧊（揭示層級 2026-07-27 移出設定層，住 story/物件/<名>.md）"),
    (re.compile(r"【表面】"), "【表面】/【水下】分層（同上，已廢除）"),
    (re.compile(r"ch\d{3,}"), "章號（rollup 一列是摘要，不是正文索引）"),
)

# 角色欄 token 只認**括號外**的（抉擇 6 B）。這是**位置判準不是語意判準**：
# `孟奇（真定）、主宰（六道輪回之主，只聞其聲）` 裡，括號外的是這一幕的正式
# 宣告，括號內是註記（法號、在不在場、背景人群）。同一個取法的先例是
# `validate.decision_blockquotes`（只算第一個 `##` 之後）與 `settings_select`
# 的 `_world_basis`（緊接 `.md` ＝檔名引用）——語意判準需要讀懂中文，而那正是
# `prose-metrics` 的關鍵詞分類被駁回的形狀。
_PAREN_RE = re.compile(r"[（(][^（()）]*[)）]")
_TOKEN_SPLIT_RE = re.compile(r"[、／/·,，;；:：\s]+")
_TOKEN_STRIP = "*`＊ 　"
# 只報出現 ≥N 次的（抉擇 6 B）：43 種查無 token 大多是合法的敘述性寫法
# （`被護的弱者`），逐一報就是新的警報疲勞來源。
TOKEN_MIN_HITS = 3

_KEY_RE = re.compile(r"^([^\s:：]+)\s*[:：]\s*(.*)$")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_FS_GROUP_RE = re.compile(r"(埋|收)\s*[:：]\s*\[([^\]]*)\]")
_BEAT_FS_RE = re.compile(r"\[\[伏筆[:：]([^\]]+)\]\]")
_ROLE_FIELD_RE = re.compile(r"^-\s*角色[:：]\s*(.*)$")
_BULLET_RE = re.compile(r"^[-*+]\s+")


@dataclass(frozen=True)
class Problem:
    path: Path
    detail: str
    hint: str


@dataclass
class CharStats:
    """**我在這本書上檢查了幾筆**（`設計原則.md` E2 的可執行推論）。

    每一項都印，**0 也印**。這一軸的教訓特別直接：`settings-select` 印「角色
    命中 7 筆」時，那 7 筆裡有 4 筆是四節全空的空殼——依據正確、數字正確、
    三支守衛各自無錯。所以本行有兩個數字是**必須成對出現**的：
    `sources` 對 `sources_without_derived`、`req_slots` 對 `placeholder_slots`。
    """

    sources: int = 0
    dir_form: int = 0
    coexist: int = 0
    derived: int = 0
    sources_without_derived: int = 0
    skeleton: int = 0
    files_with_retired: int = 0
    retired_keys: int = 0
    slots: int = 0
    placeholder_slots: int = 0
    req_slots: int = 0
    req_placeholder_slots: int = 0
    hollow_sections: int = 0
    hollow_files: int = 0
    foreshadow_names: int = 0
    foreshadow_unknown: int = 0
    registry_beats: int = 0
    registry_objects: int = 0
    rollup_found: bool = False
    rollup_rows: int = 0
    role_fields: int = 0
    role_tokens: int = 0
    role_tokens_unknown: int = 0
    role_tokens_frequent: int = 0

    def render(self) -> str:
        rollup = "有" if self.rollup_found else "**缺**"
        return (
            f"檢查範圍：{self.sources} 支源（{self.dir_form} 支目錄形態"
            f"·{self.coexist} 支單檔與目錄並存）／"
            f"{self.derived} 支 <名>.ai.md（**{self.sources_without_derived} 支源沒有衍生檔**"
            f"·{self.skeleton} 支尚未封章的骨架跳過）；"
            f"{self.files_with_retired} 支仍帶已廢除的欄／共 {self.retired_keys} 個；"
            f"四節共 {self.slots} 個 slot（**{self.placeholder_slots} 個是佔位**），"
            f"其中必填兩節 {self.req_slots} 個（**{self.req_placeholder_slots} 個是佔位**"
            f"·{self.hollow_sections} 節整節是佔位、散在 {self.hollow_files} 支檔）；"
            f"{self.foreshadow_names} 個伏筆名（{self.foreshadow_unknown} 個 registry 查無）"
            f"·registry ＝幕綱 {self.registry_beats} 個標記名 ∪ 物件檔 {self.registry_objects} 支；"
            f"rollup {rollup}·角色清單 {self.rollup_rows} 列 vs 資料夾 {self.sources} 支源；"
            f"幕綱角色欄 {self.role_fields} 個·括號外 {self.role_tokens} 個 token"
            f"（{self.role_tokens_unknown} 個 registry 查無"
            f"·其中 {self.role_tokens_frequent} 個出現 ≥{TOKEN_MIN_HITS} 次）"
        )


# ---------------------------------------------------------------- 解析 helper


def char_dir(book: Path) -> Path:
    return book / "story" / "設定" / "角色"


def _front_matter(p: Path) -> dict[str, str] | None:
    fm, _ = _split_frontmatter(p.read_text(encoding="utf-8"))
    if fm is None:
        return None
    out: dict[str, str] = {}
    for line in fm:
        m = _KEY_RE.match(line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def _section_body(text: str, title: str) -> list[str] | None:
    """某個 `##` 節的內容行；節不存在回 None（與「節在但空的」是兩件事）。"""
    out: list[str] = []
    found = inside = False
    for raw in text.replace("\r\n", "\n").split("\n"):
        m = _H2_RE.match(raw.strip())
        if m:
            inside = m.group(1).strip().startswith(title)
            found = found or inside
            continue
        if inside:
            out.append(raw)
    return out if found else None


def _table_rows(lines: list[str]) -> list[list[str]]:
    """Markdown 表格的**資料列**（表頭與 `|---|` 分隔列都不算）。

    判準是位置：`|---|` 分隔列**之後**的才是資料。形狀與取法同 `world_lint`
    ——不能只跳分隔列，那會把表頭當成一筆資料。
    """
    rows: list[list[str]] = []
    after_sep = False
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            if not s:
                after_sep = False  # 空行結束一張表
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and all(set(c) <= set("-: ") for c in cells):
            after_sep = True
            continue
        if after_sep:
            rows.append(cells)
    return rows


def source_names(book: Path) -> tuple[list[str], list[str], list[str]]:
    """資料夾裡的角色名 ＝ 這一軸的權威角色集合（C1：檔名即 ID）。

    回傳 (全部, 目錄形態的, 單檔與目錄並存的)。源是唯一真實來源，所以「有哪些
    角色」由源檔名回答，不由 rollup 的表回答（那是視圖，D1：視圖不是第二個家）。
    """
    d = char_dir(book)
    if not d.is_dir():
        return [], [], []
    singles = {
        p.stem
        for p in d.glob("*.md")
        if not p.name.endswith(AI_SUFFIX) and not p.name.startswith("_")
    }
    dirs = {
        p.name
        for p in d.iterdir()
        if p.is_dir() and not p.name.startswith("_") and any(p.glob("*.md"))
    }
    return sorted(singles | dirs), sorted(dirs), sorted(singles & dirs)


def foreshadow_registry(book: Path) -> tuple[set[str], int, int]:
    """伏筆 ID 的 registry ＝ 幕綱既有標記名 ∪ `story/物件/<名>.md` 檔名。

    回傳 (名字集合, 幕綱標記名數, 物件檔數)。**兩邊都算 registry** 是因為
    `物件.schema.md` 明訂「沒有物件檔的 ID 是合法的」（開檔走內容測試 G4），
    所以只比對物件檔會把大半合法 ID 報成問題。取法與 `world_lint` 同一把尺。
    """
    beat_names: set[str] = set()
    d = book / "story" / "幕綱"
    if d.is_dir():
        for p in sorted(d.glob("*.md")):
            for m in _BEAT_FS_RE.finditer(p.read_text(encoding="utf-8")):
                beat_names.add(m.group(1).strip())
    obj = book / "story" / "物件"
    obj_names = {p.stem for p in obj.glob("*.md")} if obj.is_dir() else set()
    return beat_names | obj_names, len(beat_names), len(obj_names)


def _parse_foreshadow(value: str) -> list[str]:
    """`{ 埋: [a, b], 收: [c] }` → ['a','b','c']。解析不到就回空清單。"""
    out: list[str] = []
    for _, inner in _FS_GROUP_RE.findall(value):
        out += [n.strip() for n in inner.split(",") if n.strip()]
    return out


def _parse_list(value: str) -> list[str] | None:
    """`[a, b]` → ['a','b']；不是方括號清單回 None。空清單 `[]` 回 []。"""
    s = value.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return None
    return [x.strip() for x in s[1:-1].split(",") if x.strip()]


def _slot_value(line: str) -> str | None:
    """一行內容 → 它的「值」。不是內容行（空行／blockquote／表格）回 None。

    `- 想要（誤導／假目標）：（源檔未載…）` 的值是 `（源檔未載…）`——切的是
    **第一個括號深度為 0 的全形冒號**，不是第一個冒號（label 本身常帶括號註記）。
    """
    s = line.strip()
    if not s or s.startswith(">") or s.startswith("|") or s.startswith("#"):
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


def _is_placeholder(value: str) -> bool:
    """這個 slot 是不是佔位。

    **判準是形狀，不是詞表**：值為空，或值**整個就是一段括號註記**
    （`（源檔未載，待跑 character 補）`）＝它是註記不是內容。
    這樣不必維護「未載／待補／TBD」這種會漏、會誤判的詞表——同一個理由，
    `prose-metrics` 的「偏網文關鍵詞」與 `validate` 的 blockquote 分類判準
    都被駁回過，正解一律是位置／形狀判準。
    """
    v = value.strip()
    if not v:
        return True
    return bool(re.fullmatch(r"[（(][^（()）]*[)）]", v))


def _role_tokens(field_text: str) -> list[str]:
    """幕綱「角色」欄 → 括號外的 token（見 `_PAREN_RE` 的註解：位置判準）。"""
    outside = _PAREN_RE.sub("、", field_text)
    out = []
    for t in _TOKEN_SPLIT_RE.split(outside):
        t = t.strip(_TOKEN_STRIP).strip()
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------- 檢查項


def check_existence(book: Path, stats: CharStats) -> list[Problem]:
    """第 2／7 項：每支源都有衍生檔（**從源側掃**）；單檔與目錄不得並存。

    第 2 項是 `設計原則.md` E1 新推論（2026-07-27 功能 06）的實作：**從 Y 出發
    掃描的守衛，對「Y 不存在」永遠回報乾淨。** `derived-sync check` 從
    `rglob("*.ai.md")` 出發，所以「源有衍生無」在定義上掃不到——而系統對這件事
    的處置是手工建 13 支空殼檔去餵它。修症狀（報空殼）不修根因（掃描方向），
    下一批角色會再長出一批空殼。

    第 7 項守的是抉擇 3 的實作條件：`settings_select.load_entities` 逐項掃
    資料夾，`<名>.md` 與 `<名>/` 並存會產生**兩個同名 Entity**。所以「小角色
    也能有水下」不靠單檔＋一個切面目錄硬湊，而是**升目錄形態、只建用得到的
    切面**（最少 `核心.md`＋`水下.md`）。
    """
    out: list[Problem] = []
    d = char_dir(book)
    if not d.is_dir():
        return out
    names, dirs, coexist = source_names(book)
    stats.sources = len(names)
    stats.dir_form = len(dirs)
    stats.coexist = len(coexist)

    missing = [n for n in names if not (d / f"{n}{AI_SUFFIX}").is_file()]
    if missing:
        stats.sources_without_derived = len(missing)
        shown = "、".join(missing[:6]) + ("…" if len(missing) > 6 else "")
        out.append(
            Problem(
                d,
                f"{len(missing)} 支源檔沒有對應的衍生檔：{shown}",
                "跑 `character`（或 `develop`／`organize`）替它生成 `<名>.ai.md` 再 "
                "`derived-sync stamp`。**不要為了讓工具看得見而建空殼檔**——"
                "四節都是佔位的衍生檔對 `beat-test` 有害（它拿那四個字串當弧線基準），"
                "而 `settings-select` 會照樣把它算進命中數（2026-07-27 功能 06 已駁回）",
            )
        )
    if coexist:
        out.append(
            Problem(
                d,
                f"{len(coexist)} 個角色的 `<名>.md` 與 `<名>/` 並存：{'、'.join(coexist)}",
                "兩種形態不得並存（角色.schema.md「兩種形態怎麼選」）——"
                "`settings-select` 的 `load_entities` 逐項掃資料夾，並存會產生兩個同名 "
                "Entity。升級是**搬移**：`git mv <名>.md <名>/核心.md`，原單檔不留",
            )
        )
    return out


def check_derived(book: Path, stats: CharStats) -> list[Problem]:
    """第 1／3／4 項：必填節不得是佔位、front-matter 欄語意、伏筆歸一。"""
    out: list[Problem] = []
    d = char_dir(book)
    if not d.is_dir():
        return out
    registry, n_beats, n_objs = foreshadow_registry(book)
    stats.registry_beats = n_beats
    stats.registry_objects = n_objs
    unknown_fs: list[tuple[Path, str]] = []
    hollow: list[tuple[Path, int, int]] = []  # (檔, 必填節佔位 slot, 整節是佔位的節數)
    retired_by_key: dict[str, int] = {}
    retired_files: list[Path] = []

    for p in sorted(d.glob(f"*{AI_SUFFIX}")):
        if p.name.startswith("_"):
            continue
        stats.derived += 1
        text = p.read_text(encoding="utf-8")
        fm = _front_matter(p)

        # ---- 第 1 項：節內容（骨架也驗——空殼檔正是這一項的標的）
        file_ph = 0
        file_hollow = 0
        for title in SECTIONS:
            required = title in REQUIRED_SECTIONS
            body = _section_body(text, title)
            if body is None:
                if required:
                    out.append(
                        Problem(
                            p,
                            f"缺必填節 `## {title}`",
                            "衍生檔的四節是封閉枚舉，`需求四象限`／`預期弧線` 是必填"
                            "（見 角色.schema.md）——`beat-test` 測試4 拿它們當基準",
                        )
                    )
                continue
            values = [v for v in (_slot_value(ln) for ln in body) if v is not None]
            ph = [v for v in values if _is_placeholder(v)]
            # 一個一行都沒有的節仍然是一個 slot（而且是佔位的那一種）——不這樣算，
            # 「四節全空」的檔會在覆蓋率行上印成「0 個 slot」，那正是要抓的假陰性。
            n_slots = max(len(values), 1)
            n_ph = len(ph) if values else 1
            entirely = not values or len(ph) == len(values)
            stats.slots += n_slots
            stats.placeholder_slots += n_ph
            if required:
                stats.req_slots += n_slots
                stats.req_placeholder_slots += n_ph
                file_ph += n_ph
                if entirely:
                    file_hollow += 1
        if file_ph:
            hollow.append((p, file_ph, file_hollow))
        stats.hollow_sections += file_hollow
        if file_hollow:
            stats.hollow_files += 1

        if fm is None:
            # 尚未封章的骨架：`check` 已經報成 unstamped，重複報 front-matter
            # 是雜訊（同 validate 與 world_lint）。**節內容照驗**——空殼檔多半
            # 就是「有 front-matter 但四節是佔位」，而全新骨架的節也該被算進
            # 覆蓋率，否則這支工具會對一本全是骨架的書印「檢查了 0 個 slot」。
            stats.skeleton += 1
            continue

        # ---- 第 3 項：已廢除的欄（聚合成一行，見函式末）
        retired = [k for k in RETIRED_KEYS if k in fm]
        if retired:
            stats.files_with_retired += 1
            stats.retired_keys += len(retired)
            retired_files.append(p)
            for k in retired:
                retired_by_key[k] = retired_by_key.get(k, 0) + 1

        # ---- 第 3 項：留下來的四欄真的被讀（抉擇 1 B 的成立條件）
        missing = [k for k in REQUIRED_KEYS if k not in fm]
        if missing:
            out.append(
                Problem(
                    p,
                    f"front-matter 缺 {'、'.join(missing)}",
                    "`generated-*` 跑 `derived-sync stamp <該檔>` 封章、別手填；"
                    f"`定位` 是 rollup 那一欄的機械來源，限 {'／'.join(POSITIONS)}",
                )
            )
        pos = fm.get(POSITION_KEY)
        if pos is not None and pos not in POSITIONS:
            out.append(
                Problem(
                    p,
                    f"`{POSITION_KEY}: {pos[:40]}` 不是枚舉值",
                    f"限 {'／'.join(POSITIONS)}。非枚舉的補充（為什麼是承重、"
                    "什麼時候升格）屬 `story/參照/裁決流.md`，不塞進枚舉欄",
                )
            )
        tent = fm.get(TENTATIVE_KEY)
        if tent is not None and tent.lower() not in TENTATIVE_FM:
            out.append(
                Problem(
                    p,
                    f"`{TENTATIVE_KEY}: {tent[:40]}` 不是布林值",
                    "限 `true`／`false`（語意＝待作者拍板）。"
                    "「為什麼還暫定／撤 false 的條件」屬 `story/參照/裁決流.md`"
                    "——枚舉欄裝非枚舉內容就是欄位溢位（實測最長 79 字元）",
                )
            )
        arcs = fm.get(ARC_KEY)
        if arcs is not None and _parse_list(arcs) is None:
            out.append(
                Problem(
                    p,
                    f"`{ARC_KEY}: {arcs[:40]}` 不是方括號清單",
                    f"格式是 `{ARC_KEY}: [arc01, arc03]`（rollup 那一欄的機械來源）",
                )
            )

        # ---- 第 4 項：伏筆歸一
        raw = fm.get(FORESHADOW_KEY)
        if raw is not None and raw.strip() not in ("", "[]", "{}"):
            # **空的宣告是合法的**（`{ 埋: [], 收: [] }` ＝這個角色不牽伏筆），
            # 所以「解析不到」要看**結構**在不在，不看名字有沒有。第一版把 15 支
            # 空宣告全報成問題——那正是這一輪在抓的假陽性的鏡像。
            if not _FS_GROUP_RE.search(raw):
                out.append(
                    Problem(
                        p,
                        f"`{FORESHADOW_KEY}:` 解析不到 `埋`／`收` 兩組：{raw[:60]}",
                        "格式是 `伏筆: { 埋: [名, 名], 收: [名] }`（見 角色.schema.md）",
                    )
                )
            names = _parse_foreshadow(raw)
            stats.foreshadow_names += len(names)
            for n in names:
                if n not in registry:
                    unknown_fs.append((p, n))

    # ---- 三類同型問題聚合成一行（03 重構輪拍板的判準：同一種病散在幾十支檔、
    # 而且病因與修法完全相同時聚合）。實測一世之尊逐支報是 24＋12 行同型雜訊，
    # 會把真正該看的 rollup 不一致與伏筆懸空淹掉。
    if retired_files:
        by_key = "、".join(
            f"{k}×{n}" for k, n in sorted(retired_by_key.items(), key=lambda kv: -kv[1])
        )
        shown = "、".join(p.name for p in retired_files[:6])
        if len(retired_files) > 6:
            shown += "…"
        out.append(
            Problem(
                d,
                f"{len(retired_files)} 支衍生檔仍帶已廢除的 front-matter 欄："
                f"共 {stats.retired_keys} 個（{by_key}）：{shown}",
                "`角色` 是檔名的複本（檔名才是 ID，C1）；`弧線類型` 全 repo 零消費者"
                "（連 schema 都沒宣稱過一個假的）——它想說的寫進 `## 預期弧線` 散文；"
                "`影響力` 05 已在世界觀刪過同名欄，改寫進 `## 對衝關係` 或 "
                "`story/物件/<名>.md` 的「## 為什麼存在」；`🧊水下` 屬 "
                "story/物件/<名>.md 的 `揭示層級`。2026-07-27 依 A4 刪除",
            )
        )
    if hollow:
        worst = max(hollow, key=lambda t: t[1])
        shown = "、".join(p.name for p, _, _ in hollow[:6])
        if len(hollow) > 6:
            shown += "…"
        out.append(
            Problem(
                d,
                f"{len(hollow)} 支衍生檔的必填節有佔位："
                f"共 {stats.req_placeholder_slots} 個 slot"
                f"（{stats.hollow_sections} 節整節是佔位；"
                f"最壞 {worst[0].name} {worst[1]} 處）：{shown}",
                "`beat-test` 測試4 拿 `需求四象限`／`預期弧線` 當角色弧線的基準，"
                "拿到佔位字串時它不會知道——而 `check` 報 fresh（源真的沒變）、"
                "`validate` 只驗節枚舉、`settings-select` 照樣算進命中數。"
                "正解是跑 `character` 補實，不是留著空殼讓三支守衛一起報平安",
            )
        )
    if unknown_fs:
        stats.foreshadow_unknown = len(unknown_fs)
        shown = "、".join(f"{n}（{p.name}）" for p, n in unknown_fs[:6])
        if len(unknown_fs) > 6:
            shown += "…"
        out.append(
            Problem(
                d,
                f"{len(unknown_fs)} 個伏筆名在 registry 查無：{shown}",
                "**提示不是門檻**——沒有物件檔的 ID 是合法的（物件.schema.md G4），"
                "但這裡的名字既沒有幕綱標記也沒有物件檔，等於又一份自由造字的名冊（C3）。"
                "正解是改成幕綱既用的那個名字，或開一支 story/物件/<名>.md",
            )
        )
    return out


def check_rollup(book: Path, stats: CharStats) -> list[Problem]:
    """第 5／6 項：`_index.ai.md` 的視圖 ≡ 各檔 front-matter；兩欄的內容判準。

    **這是三支 rollup 裡最後一個補上比對的**（`ch-lint` 對 `chapters/_index.ai.md`、
    `world-lint` 對 `_總覽.ai.md` 已有）。實測一世之尊 10 筆不一致，其中 4 列的
    列名是自由造字（`真慧（方阿七）`，檔名是 `真慧`）——那直接違反 C1／C3：
    **檔名是 ID，rollup 的鍵應該就是它**；加了別名之後任何「拿列名去找檔」的
    動作都會落空，而沒有任何東西會報。
    """
    out: list[Problem] = []
    d = char_dir(book)
    if not d.is_dir():
        return out
    rollup = d / f"{ROLLUP_STEM}{AI_SUFFIX}"
    names, _, _ = source_names(book)
    if not rollup.is_file():
        legacy = d / f"{ROLLUP_STEM}.md"
        if not legacy.is_file():
            if names:
                out.append(
                    Problem(
                        d,
                        f"資料夾有 {len(names)} 支源檔但沒有 {ROLLUP_STEM}{AI_SUFFIX}",
                        "照 `書本模板/story/設定/角色/_index.ai.md` 的骨架建一支再重生",
                    )
                )
            return out
        rollup = legacy
    stats.rollup_found = True
    text = rollup.read_text(encoding="utf-8")
    if _split_frontmatter(text)[0] is None:
        # 尚未封章的骨架：表裡是佔位列，逐項比對只會報一堆幽靈列。那個狀態
        # `check` 已經報成 unstamped（同 validate／world_lint 的骨架處置）。
        return out

    body = _section_body(text, ROLLUP_SECTION)
    if body is None:
        out.append(
            Problem(
                rollup,
                f"找不到 `## {ROLLUP_SECTION}` 節",
                "rollup 只有一個節（角色.schema.md）；其餘內容屬各角色的 `.ai.md` "
                "或 `story/參照/裁決流.md`",
            )
        )
        return out
    rows = _table_rows(body)
    stats.rollup_rows = len(rows)

    listed = [r[COL_NAME] for r in rows if r and r[COL_NAME]]
    ghost = [n for n in listed if n not in names]
    missing = [n for n in names if n not in listed]
    if ghost or missing:
        bits = []
        if missing:
            bits.append(f"{len(missing)} 支源檔沒進清單：{'、'.join(missing)}")
        if ghost:
            bits.append(
                f"{len(ghost)} 列的列名不是檔名："
                + "、".join(ghost[:6])
                + ("…" if len(ghost) > 6 else "")
            )
        out.append(
            Problem(
                rollup,
                f"{ROLLUP_SECTION} 與資料夾不一致——" + "；".join(bits),
                "**列名就是檔名，不得加括號別名**（C1／C3：檔名是 ID）。"
                "`真慧（方阿七）` 這種寫法讓「拿列名去找檔」永遠落空，"
                "而別名本身屬該角色源檔的散文或 `story/物件/<名>.md`。"
                "清單是**視圖**不是第二個家（D1）：列 ≡ 資料夾裡的源，重生即對齊",
            )
        )

    need_hits: dict[str, list[str]] = {}  # 病徵 → 命中的列名（聚合用）
    for r in rows:
        if not r or not r[COL_NAME]:
            continue
        name = r[COL_NAME]
        # 第 6 項：`一行需求` 的內容判準（不設專用長度門檻，見 NEED_FORBIDDEN）
        if len(r) > COL_NEED:
            for rx, why in NEED_FORBIDDEN:
                if rx.search(r[COL_NEED]):
                    need_hits.setdefault(why, []).append(name)
        derived = d / f"{name}{AI_SUFFIX}"
        if not derived.is_file():
            continue
        fm = _front_matter(derived)
        if fm is None:
            continue
        # 第 5 項：三欄 ≡ front-matter
        if len(r) > COL_POSITION and fm.get(POSITION_KEY) is not None:
            if not r[COL_POSITION].startswith(fm[POSITION_KEY]):
                out.append(
                    Problem(
                        rollup,
                        f"「{name}」列 `定位` 寫 {r[COL_POSITION][:30]!r}，"
                        f"front-matter 是 {fm[POSITION_KEY]!r}",
                        "rollup 是視圖，這一欄的機械來源是該檔的 front-matter",
                    )
                )
        if len(r) > COL_ARC and (want := _parse_list(fm.get(ARC_KEY, ""))) is not None:
            got = [x.strip() for x in r[COL_ARC].split(",") if x.strip()]
            if got != want:
                out.append(
                    Problem(
                        rollup,
                        f"「{name}」列 `所屬arc` 寫 {r[COL_ARC][:40]!r}，"
                        f"front-matter 是 {fm.get(ARC_KEY, '')[:40]!r}",
                        "同上：機械來源是 front-matter 的 `所屬arc`",
                    )
                )
        if len(r) > COL_TENTATIVE and fm.get(TENTATIVE_KEY) is not None:
            cell = r[COL_TENTATIVE]
            want_b = TENTATIVE_FM.get(fm[TENTATIVE_KEY].lower())
            got_b = next(
                (v for k, v in TENTATIVE_ROLLUP.items() if cell.startswith(k)), None
            )
            if got_b is None or (want_b is not None and got_b != want_b):
                out.append(
                    Problem(
                        rollup,
                        f"「{name}」列 `暫定` 寫 {cell[:40]!r}，"
                        f"front-matter 是 {fm[TENTATIVE_KEY]!r}",
                        f"這一欄只能是 {'／'.join(TENTATIVE_ROLLUP)}（≡ front-matter 的布林）。"
                        "「為什麼還暫定／撤 false 的條件」屬 `story/參照/裁決流.md`"
                        "——**schema 規定某欄只能是枚舉值時，非枚舉內容一定要有去處**，"
                        "否則它就溢位在這一格（實測最長 79 字元）",
                    )
                )

    # 第 6 項聚合成一行（同上：同型、同修法）。實測一世之尊 10 列命中。
    if need_hits:
        rows_hit = {n for names_ in need_hits.values() for n in names_}
        bits = "；".join(
            f"{why}：{len(names_)} 列（{'、'.join(names_[:4])}"
            + ("…" if len(names_) > 4 else "")
            + "）"
            for why, names_ in need_hits.items()
        )
        out.append(
            Problem(
                rollup,
                f"{len(rows_hit)} 列的 `一行需求` 含不該出現的語法——{bits}",
                "**這一欄是摘要不是副本**——要展開就去讀該角色的 `.ai.md`。"
                "行長由成長哨兵的 `ROLLUP_LINE_CHARS`（400）管；本項只管內容"
                "（抉擇 5 A：實測 118 中位→1,024 最長是**連續分佈、沒有空隙**，"
                "所以不硬定一個任意的專用數字門檻，改用內容判準）",
            )
        )
    return out


def check_role_fields(book: Path, stats: CharStats) -> list[Problem]:
    """第 8 項：幕綱「角色」欄裡 registry 查無的 token（**只報出現 ≥3 次的**）。

    **抉擇 6 B。** 實測一世之尊 14 幕的角色欄寫的是集合名 `同伴組`，
    `settings-select` 展不開它，那些幕會少選 3–4 個角色——而它印「角色命中 8 筆」
    時真相是 11–12 個角色在場。這一項讓那個落差可見（D2：命中率與命中依據都要印）。

    **不建集合名對照表**（抉擇 6 C 已駁回，形狀同 05 駁回的「世界觀主題別名表」：
    一份會漂移而無人維護的機讀資料）。**只報 ≥3 次**是因為 43 種查無 token 大多
    是合法的敘述性寫法（`被護的弱者`），逐一報就是新的警報疲勞來源。
    """
    out: list[Problem] = []
    d = book / "story" / "幕綱"
    if not d.is_dir():
        return out
    names, _, _ = source_names(book)
    known = set(names)
    counts: dict[str, int] = {}
    for p in sorted(d.glob("*.md")):
        for ln in p.read_text(encoding="utf-8").splitlines():
            m = _ROLE_FIELD_RE.match(ln.strip())
            if not m:
                continue
            stats.role_fields += 1
            for t in _role_tokens(m.group(1)):
                stats.role_tokens += 1
                if t not in known:
                    counts[t] = counts.get(t, 0) + 1
    stats.role_tokens_unknown = sum(counts.values())
    frequent = sorted(
        ((n, c) for n, c in counts.items() if c >= TOKEN_MIN_HITS),
        key=lambda kv: (-kv[1], kv[0]),
    )
    stats.role_tokens_frequent = len(frequent)
    if frequent:
        shown = "、".join(f"{n}×{c}" for n, c in frequent[:8])
        if len(frequent) > 8:
            shown += "…"
        out.append(
            Problem(
                d,
                f"{len(frequent)} 個角色欄 token 在角色 registry 查無且出現 "
                f"≥{TOKEN_MIN_HITS} 次：{shown}",
                "**提示不是門檻**（不擋路）。多半是集合名（`同伴組`）或別名"
                "（正文專名 vs 設定法號）——`settings-select` 拿檔名比對角色欄，"
                "展不開集合名，那幾幕會少選幾個角色而輸出一切正常。"
                "正解是**在角色欄逐一列出成員**（或用該角色的檔名），"
                "**不要建一份集合名對照表**（2026-07-27 功能 06 抉擇 6 C 已駁回："
                "那是一份會漂移而無人維護的機讀資料）",
            )
        )
    return out


def lint_book(book: Path) -> tuple[list[Problem], CharStats]:
    stats = CharStats()
    problems = (
        check_existence(book, stats)
        + check_derived(book, stats)
        + check_rollup(book, stats)
        + check_role_fields(book, stats)
    )
    return problems, stats
