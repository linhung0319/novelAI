"""摘要軸的格式閘門（`summary-lint`）。

**為什麼它存在**（2026-07-27 功能 08 重構輪）：摘要軸的方向是對的（A1／A2 乾淨、
`derived-sync check` 從未失效過、源→衍生分權清楚），問題是**它是量到守衛覆蓋率
最低的一軸**——

  - **`摘要.schema.md` 的 8 條「檢查點」，0 條有機械實作。** 其中「人稱只能填系統
    支援值，填了非支援值**停下回問作者、不得直接封章**」是一個**封閉二值枚舉、
    機械完全可判**的閘門，而唯一存在的那本書填的正是非支援值（`第一人稱貼身`）、
    順利封章、寫了 93 章。事實鏈是 `raw/` 一句形容詞 → `develop` 原樣抄進源檔 →
    成為 `write` 的 POV 權威，**全程沒有一處問過**。
  - **front-matter 11 鍵中 8 鍵被逐欄取值（2 個是程式取值者）而整支檔零 lint**：
    `beat_metrics.scan.load_pov` 讀 `視角結構`、`style_lint` 第 6 項讀 `基調`，
    其餘 6 鍵由 10 支 SKILL.md 逐欄指名。依 A4（07 改寫後）**取值者是 LLM 也算**。
  - **`基調主從`／`終局` 是「機讀格式 ＋ 零解析器 ＋ 零消費者」的第三個實例**
    （05 世界觀四欄、06 角色三欄）。`終局` 更進一步——**連 schema 都沒宣告過它**，
    534 字元、是本檔最長的 front-matter 行，而 `validate` 只驗缺不驗多。
  - **唯一有真實傷害路徑的縫**：基調字串住在四個地方，守衛只覆蓋 `.ai.md` ↔
    `.ai.md` 那一條邊（`style-lint` 第 6 項）。`風格.md` 的那一份與 `00-摘要.md`
    正規化後**逐字相同、零守衛**，而 07 把 `write`／`write-test`／`revise` 改成
    「源散文＋衍生五欄兩邊都讀」之後，**舊基調會直接進正文**——而 `check`／
    `style-lint`／`validate` 三支守衛**各自都沒做錯**（E2 第五種形態，在跨產物
    邊上復發）。

**A4 對源檔那一格在本輪之前無解，所以本輪同時改了原則。** 摘要**源檔**被 10 支
SKILL.md 逐節指名取值，而它是自由源：「補 lint」被 `共同約定.md` 零 明文反對，
「改成整檔讀」**就是現況**（讀了整檔，然後在腦內取那一節）——兩條路都指向現況，
風險完全沒降。`設計原則.md` A4 因此補上第三條路：**把那幾欄的權威移到衍生層並在
那裡補 lint，源檔維持自由散文**。本模組就是「在那裡補 lint」的那一半，同輪 12 支
SKILL.md 的讀檔步驟改成「源散文＋衍生六個語意欄」。

**與 `validate` 的分工**（同 `world-lint`／`char-lint`／`style-lint`）：`validate`
管所有 `.ai.md` 共通的結構（front-matter 必填鍵、`##` 節枚舉、裁決 blockquote）；
本模組管**摘要專屬**的欄語意、跨產物比對與源檔提示。兩者同套件、共用
`_split_frontmatter` 與 `SUMMARY_*` 路徑常數——摘要 `.ai.md` 的格式真相只有一份。

**判準一律是結構判準或位置判準，不得用詞表。** 第 3 項問「值是不是以 `第三人稱`
開頭且含 `有限`／`全知`」、第 5 項問「正規化後兩邊字面相不相等」、第 7 項問「同一
行裡有沒有單位 token 與阿拉伯數字」——都與中文語意無關。**唯二的例外是兩個
「只印、不擋」的提示**（駁回語彙／`已定案` 字樣），它們**不計入問題數、不影響
exit code**，因為那兩件事的切分線是語意判斷、lint 守不住：作者拍板時要有人做
切分，本模組只負責讓它可見。

**已知的複製**：本模組帶進**第 5 份 front-matter 解析**（`validate`／`world_lint`／
`char_lint`／`style_lint` 各一）、**第 5 份跨產物欄位比對**（第 5 項，而**它的形狀
與前四份都不同——比的是源檔散文 ↔ 衍生欄**，前四份都是欄↔欄或欄↔資料夾）、
**第 5 份目的地存在性檢查**（第 6 項，前四份：`beat-lint` 設計註、`derived-sync`
的 `missing_destinations`、`decision-lint` 兩處、`ch-lint` 的 `風格` 欄），以及
`beat_metrics.scan._POV_RE` 的第 2 份。工具間零相依（所有 `tools/*/pyproject.toml`
皆 `dependencies = []`），故複製而非 import → 收斂與否交功能 14。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .core import _split_frontmatter
from .style_lint import style_dir
from .validate import SUMMARY_DERIVED, SUMMARY_DIR, SUMMARY_SOURCE

# 留下來的欄。**每一個都要在本模組被真的讀到**（或指得出讀它的那一行），否則依
# A4／E1 它不配留在 front-matter。`摘要.schema.md` 有一張逐欄對照表指名這裡的項次。
MAINLINE_KEY = "主線"
THEME_KEY = "題旨"
TONE_KEY = "基調"
POV_KEY = "視角結構"
STANCE_KEY = "取向定位"
SUSPENSE_KEY = "貫穿大懸念"
SEMANTIC_KEYS = (MAINLINE_KEY, THEME_KEY, TONE_KEY, POV_KEY, STANCE_KEY, SUSPENSE_KEY)
STAMP_KEYS = ("generated-from", "generated-at")
REQUIRED_KEYS = STAMP_KEYS + SEMANTIC_KEYS

# 2026-07-27（功能 08）刪掉的三個欄。留著它們不是「舊格式還能用」——是「schema
# 已經不宣稱它們機讀，而檔裡還寫著一個看起來機讀的值」，那正是漂移的形狀。
#   `基調主從`：零取值者（grep 12 支 SKILL.md ＋ 7 個 tools 套件：0 次），內容
#               本來就在源「基調」節裡（`貼身喜劇（主）＋宏大縹緲（從）`）。
#   `終局`    ：零取值者 ＋ **schema 從沒定義過它**（自生欄，534 字元），內容
#               完整存在於源「結局方向」節與衍生「取向定位分析」節。
#   `節奏檔位`：**權威已外移**到 `story/幕綱/arcNN.md` 檔頭，而這一份覆蓋 1/11
#               arc（9.1%）——值合法、有消費者、而不可用（E1 第四推論）。
RETIRED_KEYS = ("基調主從", "終局", "節奏檔位")

# 第 3 項：`摘要.schema.md`「系統支援的人稱」那張封閉二值表。
# **結構判準**：以 `第三人稱` 開頭 ＋ 含 `有限` 或 `全知` 其一。實測值寫成
# `第三人稱有限·DeepPOV`（schema 範例）、`第三人稱有限視角（含 Deep POV）` 等
# 多種寫法，所以不能用等值比對；但也不能放寬成「含第三人稱就好」——那會放過
# 「第三人稱與第一人稱交錯」。
PERSON_SUBKEY = "人稱"
PERSON_PREFIX = "第三人稱"
PERSON_KINDS = ("有限", "全知")

# 源檔的兩個節（比對用 startswith／in，容許作者加註記）。
TONE_SECTION = "基調"
ADHOC_SECTION = "臨場拍板"

# 兩個**只印、不擋**的提示用的固定小清單（抉擇 1／6，作者拍板）。
# **這兩份是詞表，而那正是它們不做 pass/fail 的理由**：任何詞表都會漏、會誤判，
# 所以它們只負責讓一件語意上的事「可見」，不負責判定。
SETTLED_MARKS = ("已定案", "已鎖定", "已寫定")
REJECTION_MARKS = ("捨棄", "排斥", "否決", "圓不回來", "作廢", "不走")

_KEY_RE = re.compile(r"^([^\s:：]+)\s*[:：]\s*(.*)$")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
# 「臨場拍板」節裡的一「條」＝**頂格**的編號或項目符號（縮排的是續行，見 `_source_notes`）。
_TOP_ITEM_RE = re.compile(r"^(?:\d+[.)]|[-*+])\s+")
# **`beat_metrics.scan._POV_RE` 的同一把尺**（第 4 項要驗的就是「那一支解析得出來」，
# 所以這裡必須是逐字相同的 regex，不是等價的另一種寫法）。
_POV_RE = re.compile(r"^視角結構:.*?POV\s*[:：]\s*([^,，}\s}]+)", re.MULTILINE)
# 第 6 項的 registry 與引用。
_BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)")
_BEAT_REF_RE = re.compile(r"幕(\d+)")
_ARC_REF_RE = re.compile(r"(?<![A-Za-z0-9])(arc\d+)")
# 第 7 項：**單位 token ＋阿拉伯數字要落在同一行**。形狀照抄 `style-lint` 第 4 項
# （顆粒度 token ＋阿拉伯數字落在同一個檔位值裡）。整檔比對是沒有意義的——
# 任何一份散文檔裡都有日期與 arc 編號，那會讓每本書都無條件通過。
_UNIT_RE = re.compile(r"每\s*(?:章|卷|話|幕|arc|Arc|ARC)|全書")
_DIGIT_RE = re.compile(r"[0-9]")
# 第 5 項的正規化：剝粗體標記、剝**括號內容**（`（主）`／`（從）` 是註記不是基調）、
# 剝尾端標點與空白。**位置／形狀判準，不是詞表**。
_BOLD_RE = re.compile(r"\*+")
_PAREN_GROUP_RE = re.compile(r"[（(][^（()）]*[)）]")
_PLACEHOLDER_RE = re.compile(r"[（(][^（()）]*[)）]")
_TRAIL_PUNCT = "。．.，,、；;：:！!？?　 \t"

# 候選清單印幾筆就夠。同 `world_lint`／`char_lint`／`style_lint` 的 6。
_SHOWN = 6


@dataclass(frozen=True)
class Problem:
    path: Path
    detail: str
    hint: str


@dataclass
class SummaryStats:
    """**我在這本書上檢查了幾筆**（`設計原則.md` E2 的可執行推論）。

    每一項都印，**0 也印**。這一軸最需要這一行的是**三個「未比對」狀態**：
    人稱、基調、達標線——它們各有一條「因為上游還沒落檔所以整項跳過」的路徑，
    而跳過與通過在舊的輸出裡長得一模一樣。

    依 06 補的那條推論（覆蓋率行要能回答「命中的裡面幾筆是空的」），
    `keys` 與 `empty_keys`、`refs` 與 `refs_dangling`、`adhoc_items` 與
    `adhoc_settled` 都是**必須成對出現**的數字。
    """

    source: int = 0
    derived: int = 0
    source_without_derived: int = 0
    skeleton: int = 0
    keys: int = 0
    empty_keys: int = 0
    retired: int = 0
    person_state: str = "未比對"
    tone_state: str = "未比對"
    style_copy: str = "未比對"
    threshold_where: str = "未比對"
    refs: int = 0
    refs_dangling: int = 0
    registry_beats: int = 0
    registry_arcs: int = 0
    rejection_hits: int = 0
    adhoc_items: int = 0
    adhoc_settled: int = 0
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        return (
            f"檢查範圍：{self.source} 支摘要源／{self.derived} 支衍生"
            f"（**{self.source_without_derived} 支源沒有衍生檔**"
            f"·{self.skeleton} 支尚未封章的骨架跳過）；\n"
            f"          front-matter {self.keys} 個語意欄（**{self.empty_keys} 個是空的**）"
            f"·{self.retired} 個已廢除的欄；\n"
            f"          人稱：{self.person_state}；"
            f"基調兩方比對（源 ≡ 衍生 `{TONE_KEY}`）：{self.tone_state}；\n"
            f"          `風格.md` 是否仍帶基調複本：{self.style_copy}；"
            f"基調達標線落在：{self.threshold_where}；\n"
            f"          掃了 {self.refs} 個幕號·arc 引用（**{self.refs_dangling} 個懸空**）"
            f"·registry ＝幕綱 {self.registry_beats} 幕 ∪ {self.registry_arcs} 支 arc 檔；\n"
            f"          源檔 {self.rejection_hits} 處駁回語彙"
            f"·「{ADHOC_SECTION}」類節 {self.adhoc_items} 條"
            f"（**{self.adhoc_settled} 條帶已定案字樣**）"
        )


# ---------------------------------------------------------------- 解析 helper


def summary_paths(book: Path) -> tuple[Path, Path]:
    """(源, 衍生)。路徑的唯一真相在 `validate.py`（`SUMMARY_*`）。"""
    d = book.joinpath(*SUMMARY_DIR)
    return d / SUMMARY_SOURCE, d / SUMMARY_DERIVED


def _front_matter(p: Path) -> dict[str, str] | None:
    """`.ai.md` 的 front-matter → 扁平 dict；沒有 front-matter 回 None。

    **值要剝掉 `#` 之後的註解**：`摘要.schema.md` 的範例本身就在值後面寫註解
    （`節奏檔位: { 卷一: 開頭段 }   # 只記起點·不滾動`），不剝的話第 5 項的
    字串比對會對著一段註解比（同 `style_lint._front_matter`）。
    """
    fm, _ = _split_frontmatter(p.read_text(encoding="utf-8"))
    if fm is None:
        return None
    out: dict[str, str] = {}
    for line in fm:
        m = _KEY_RE.match(line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).split("#", 1)[0].strip()
    return out


def _section_body(text: str, title: str) -> list[str] | None:
    """某個 `##` 節的內容行；節不存在回 None（與「節在但空的」是兩件事）。

    比對用 `startswith`——作者會在標題後加註記（`## 基調（氛圍／筆調）`、
    `## 臨場拍板、非定版（待後續拍板，別鎖死）`）。取法同 `char_lint`。
    """
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


def _first_line(body: list[str] | None) -> str:
    """節的首句 ＝ 第一個非空、非 blockquote 的行。"""
    for ln in body or []:
        s = ln.strip()
        if s and not s.startswith(">"):
            return s
    return ""


def normalize_tone(s: str) -> str:
    """基調字串的正規化（第 5 項與「風格複本」提示共用同一把尺）。

    剝三樣東西：**粗體標記**（源檔那句寫成 `**…**`）、**括號內容**
    （`（主）`／`（從）` 是主從註記，衍生欄不抄它們）、**尾端標點與空白**。

    **這是形狀判準不是語意判準**：不問「這兩句話是不是同一個意思」（那需要讀懂
    中文，是三次被駁回的形狀），只問「剝掉這三種裝飾之後字面相不相等」。
    """
    s = _BOLD_RE.sub("", s)
    s = _PAREN_GROUP_RE.sub("", s)
    s = s.replace(" ", "").replace("　", "")
    return s.strip().strip(_TRAIL_PUNCT)


def _is_placeholder(value: str) -> bool:
    """這一句是不是骨架的佔位（整句就是一段括號註記）。

    形狀判準，取法同 `char_lint._is_placeholder`——不必維護「未載／待補／TBD」
    這種會漏、會誤判的詞表。`書本模板` 的基調節就是這一格：
    `（一句話定調，如「哥特恐怖＋黑色幽默」。…）`。
    """
    v = value.strip()
    if not v:
        return True
    return bool(_PLACEHOLDER_RE.fullmatch(v))


def _parse_mapping(value: str) -> list[tuple[str, str]]:
    """`{ k: v, k2: v2 }` → [(k, v), …]，依**最外層**逗號切（括號內的不算）。"""
    s = value.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    out: list[tuple[str, str]] = []
    depth = 0
    buf: list[str] = []
    parts: list[str] = []
    for ch in s:
        if ch in "[{（(":
            depth += 1
        elif ch in "]}）)":
            depth = max(0, depth - 1)
        if ch in ",，" and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    for part in parts:
        if not part:
            continue
        m = _KEY_RE.match(part)
        out.append((m.group(1).strip(), m.group(2).strip()) if m else ("", part))
    return out


def beat_registry(book: Path) -> tuple[set[str], set[str]]:
    """(幕號集合, arc 檔名集合) ＝ 第 6 項的目的地 registry。

    取法與 `char_lint.foreshadow_registry` 同一把尺（掃 `story/幕綱/*.md`），
    不 import `beat_metrics`——工具間零相依。
    """
    beats: set[str] = set()
    arcs: set[str] = set()
    d = book / "story" / "幕綱"
    if not d.is_dir():
        return beats, arcs
    for p in sorted(d.glob("*.md")):
        if not p.name.startswith("_"):
            arcs.add(p.stem)
        for ln in p.read_text(encoding="utf-8").splitlines():
            m = _BEAT_HEAD_RE.match(ln.strip())
            if m:
                beats.add(m.group(1))
    return beats, arcs


# ---------------------------------------------------------------- 檢查項


def _check_keys(p: Path, fm: dict[str, str], stats: SummaryStats) -> list[Problem]:
    """第 1／2 項：八鍵齊全且非空；不得再有已廢除的三個欄。"""
    out: list[Problem] = []
    for k in SEMANTIC_KEYS:
        if k in fm:
            stats.keys += 1
            if not fm[k].strip():
                stats.empty_keys += 1
    missing = [k for k in REQUIRED_KEYS if not fm.get(k, "").strip()]
    if missing:
        out.append(
            Problem(
                p,
                f"front-matter 缺（或空）{'、'.join(missing)}",
                "`generated-*` 跑 `derived-sync stamp <該檔>` 封章、別手填；"
                f"六個語意欄（{'／'.join(SEMANTIC_KEYS)}）是下游 10 支 skill 的"
                "機讀入口，**每一欄都在 `summary-lint` 或別支工具裡指得出讀它的"
                "那一行**（摘要.schema.md 有逐欄對照表）——空值也算缺，"
                "一個空的機讀基準比沒有更糟（讀的人以為有）",
            )
        )
    retired = [k for k in RETIRED_KEYS if k in fm]
    if retired:
        stats.retired = len(retired)
        out.append(
            Problem(
                p,
                f"front-matter 仍帶 {len(retired)} 個已廢除的欄：{'、'.join(retired)}",
                "`基調主從` 零取值者，內容本來就在源「基調」節（`（主）`／`（從）`）；"
                "`終局` 零取值者**且 schema 從沒定義過它**（自生欄，實測 534 字元），"
                "內容完整存在於源「結局方向」節與衍生「取向定位分析」節；"
                "`節奏檔位` 的**權威已外移**到 `story/幕綱/arcNN.md` 檔頭"
                "（這一份實測覆蓋 1/11 arc ＝ 9.1%，下游照字面讀會以為"
                "「這本書現在還在開頭段」）。2026-07-27 依 A4 刪除",
            )
        )
    return out


def _check_pov(p: Path, text: str, fm: dict[str, str], stats: SummaryStats) -> list[Problem]:
    """第 3／4 項：人稱 ∈ 封閉二值枚舉；`視角結構` 能被 `load_pov` 的同一把尺解析。

    **第 3 項是本模組存在的主要理由。** `摘要.schema.md` 早就寫了那張二值表 ＋
    「填了非支援值，**停下回問作者，不得直接封章**」——而那是 LLM 自律，實測沒
    擋住：唯一的書填 `第一人稱貼身`、順利封章、93 章成書。整套系統的視角規則
    （`beat-test` 測試5 知識洩漏、`write` 步驟6 POV 知識邊界、head-hopping 判準）
    都是照第三人稱有限視角寫的——**閘門是小改動，支援第一人稱是大工程**。

    **第 4 項守的是另一種失效**：`beat_metrics` 解析不到 POV 時只印一行
    「讀不到——不猜」。那很誠實，但**沒有人負責去修**，於是「純內在幕比例」
    這一項會長期報「不適用」而報告看起來完全正常。
    """
    out: list[Problem] = []
    raw = fm.get(POV_KEY, "").strip()
    if not raw:
        return out  # 缺欄已由第 1 項報，這裡不重複

    person = next((v for k, v in _parse_mapping(raw) if k == PERSON_SUBKEY), None)
    if person is None:
        stats.person_state = f"**未比對·`{POV_KEY}` 解析不到 `{PERSON_SUBKEY}` 子欄**"
        out.append(
            Problem(
                p,
                f"`{POV_KEY}` 解析不到 `{PERSON_SUBKEY}` 子欄：{raw[:60]}",
                f"格式是 `{POV_KEY}: {{ 線: 單線, POV: <角色>, {PERSON_SUBKEY}: "
                "第三人稱有限·DeepPOV }`（見 摘要.schema.md）",
            )
        )
    elif person.startswith(PERSON_PREFIX) and any(k in person for k in PERSON_KINDS):
        stats.person_state = "合法"
    else:
        stats.person_state = f"**非支援值（{person[:20]}）**"
        out.append(
            Problem(
                p,
                f"`{PERSON_SUBKEY}: {person[:40]}` 不是系統支援值",
                "系統支援的人稱只有**第三人稱有限視角（含 Deep POV）**與"
                "**第三人稱全知**兩個（摘要.schema.md「系統支援的人稱」）。"
                "`develop`／`organize` 落檔前遇到這一項**停下回問作者、不得直接封章**"
                "——**回問時要把理由講給作者聽，不要只說「不支援」**：作者要的"
                "多半是「那種貼身的喜感」而不是那個人稱，而貼身喜感在第三人稱 "
                "Deep POV 一樣做得到（視角與敘事人稱.md §一）。整套系統的視角規則"
                "（beat-test 測試5、write 步驟6、head-hopping 判準）都是照第三人稱"
                "有限視角寫的——**閘門是小改動，支援第一人稱是讓每一層各自長出"
                "第二套判準**。既有書不回頭改（一世之尊是保留的病例）",
            )
        )

    # 第 4 項：用 `beat_metrics.scan` 那條 regex 對整份檔文字跑一次
    if not _POV_RE.search(text):
        out.append(
            Problem(
                p,
                f"`{POV_KEY}` 的 `POV` 抽不出來（`beat_metrics.load_pov` 的同一把尺）",
                "`beat-metrics` 的「純內在幕比例」拿 `POV` 當主角，抽不到時它印"
                "「讀不到——不猜」——**那很誠實，但沒有人負責去修**，於是整項會長期"
                "報「不適用」而報告看起來完全正常。`POV` 要寫成 "
                f"`{POV_KEY}: {{ 線: 單線, POV: <角色名>, … }}`，"
                "而且該欄要在 front-matter 頂格起一行",
            )
        )
    return out


def _check_tone(
    p: Path, fm: dict[str, str], source_tone: str, stats: SummaryStats
) -> list[Problem]:
    """第 5 項：源 `00-摘要.md` 基調節首句 ≡ 衍生 `基調` 欄（正規化後比字面）。

    **這是本輪唯一一條有真實傷害路徑的縫的一半。** 基調字串實測住在四個地方，
    而 07 之前只有 `.ai.md` ↔ `.ai.md` 那條邊有守（`style-lint` 第 6 項）。
    抉擇 4 A 把 `風格.md` 的複製句改成指標（**砍到三份**），於是剩下的三份是
    「源（權威）＋兩個機讀欄（各有 lint）」——**沒有任何一條邊是「源↔源、
    零守衛、逐字相同」**。本項守的是剩下那條源↔衍生的邊。

    **抉擇 4 同時把本項從三方降級成兩方**：`風格.md` 那一端不再是比對對象，
    因為它不該再有一份可比的東西；它還帶不帶複本改由覆蓋率行的提示回答。
    """
    raw = fm.get(TONE_KEY, "").strip()
    if not raw:
        return []  # 缺欄已由第 1 項報
    if not source_tone:
        stats.tone_state = f"**未比對·源檔沒有可讀的「{TONE_SECTION}」節**"
        return [
            Problem(
                p,
                f"`{TONE_KEY}` 比對不了：源 `{SUMMARY_SOURCE}` 沒有「## {TONE_SECTION}」"
                "節（或該節只有佔位）",
                "基調的**唯一權威是源檔**（摘要.schema.md：基調要變改此源，"
                "風格檔隨之重生）。衍生欄是抄本——抄本存在而正本不存在時，"
                "`style-lint` 第 6 項與本項都在拿一個沒有來源的字串當基準",
            )
        ]
    if normalize_tone(source_tone) != normalize_tone(raw):
        stats.tone_state = "**不符**"
        return [
            Problem(
                p,
                f"`{TONE_KEY}` 與源 `{SUMMARY_SOURCE}`「{TONE_SECTION}」節首句不一致：\n"
                f"           源   `{source_tone[:60]}`\n"
                f"           衍生 `{raw[:60]}`",
                "衍生欄是**抄本**，正本是源檔那一句（正規化只剝粗體、括號註記、"
                "尾端標點——`（主）`／`（從）` 這類主從註記不必抄進欄）。"
                "改基調去改源 `00-摘要.md` 再重生兩支衍生檔。"
                "**這條邊在 2026-07-27 之前零守衛**，而 `style-lint` 第 6 項"
                "只守 `.ai.md` ↔ `.ai.md` 那一條——兩支衍生對得上、而它們一起"
                "對不上源，三支守衛會同時報正常",
            )
        ]
    stats.tone_state = "相符"
    return []


def _check_refs(p: Path, fm: dict[str, str], book: Path, stats: SummaryStats) -> list[Problem]:
    """第 6 項：front-matter 值裡的 `幕NNN`／`arcNN` 引用不懸空（目的地存在性）。

    實測 `貫穿大懸念` 欄寫著 `交棒點: arc05 幕411 坐實`，而**零檢查**——那個幕
    確實存在於 `arc05.md:142`，**是運氣不是機制**。這是 repo 裡第 5 份同類實作
    （`設計原則.md` E1 的 02 推論：箭頭指向空氣，而箭頭本身格式完全合法）。
    """
    beats, arcs = beat_registry(book)
    stats.registry_beats = len(beats)
    stats.registry_arcs = len(arcs)
    dangling: list[str] = []
    for k, v in fm.items():
        if k in STAMP_KEYS:
            continue  # hash 與日期不是引用
        for n in _BEAT_REF_RE.findall(v):
            stats.refs += 1
            if n not in beats:
                dangling.append(f"幕{n}（{k}）")
        for a in _ARC_REF_RE.findall(v):
            stats.refs += 1
            if a not in arcs:
                dangling.append(f"{a}（{k}）")
    if not dangling:
        return []
    stats.refs_dangling = len(dangling)
    shown = "、".join(dangling[:_SHOWN]) + ("…" if len(dangling) > _SHOWN else "")
    return [
        Problem(
            p,
            f"{len(dangling)} 個幕號·arc 引用在幕綱查無：{shown}",
            "摘要是**粗層**，它引用一個幕號就是在宣稱「那一點已經坐實」"
            "（實測 `貫穿大懸念` 的 `交棒點: arc05 幕411`）。幕綱重排／改號之後"
            "那個宣稱會靜靜地變成假的，而摘要不會 stale（它的 digest 只覆蓋"
            "源 `00-摘要.md`）——**這條跨檔相依沒有 hash 邊，只有本項看得見**",
        )
    ]


def _check_threshold(
    book: Path, src: Path, tone_body: list[str] | None, stats: SummaryStats
) -> list[Problem]:
    """第 7 項：基調宣告要寫出**單位**與**達標線**（`共同約定.md` 九）。

    **兩邊至少一邊有**（2026-07-28 作者拍板）：抉擇 4 A 把 `風格.md` 定義成
    「基調在句子層怎麼落」的執行細則，而達標線正是執行細則——實測那句
    「每章至少 1 次讓讀者鼻子出一口氣」就住在 `風格.md`，而它正是 `摘要.schema.md`
    拿來當範例的那一句。所以本項驗**摘要基調節 ∪ 源 `風格.md`**，不逼作者
    把一句執行細則複製回摘要（那正是本輪在砍的複本）。

    **判準是結構的**：單位 token（`每章`／`每 arc`／`每卷`／`全書`）與阿拉伯數字
    要**落在同一行**。形狀照抄 `style-lint` 第 4 項——整檔比對沒有意義，任何一份
    散文檔裡都有日期與 arc 編號，那會讓每本書都無條件通過。**不得改用詞表判
    「這是不是讀感形容詞」**（三次被駁回的形狀）。

    代價照實承擔：抓不到「單位與數字都寫了但那個數字量不到」。那是
    `write-test` 測試5 的事（逐 arc、相對本書前段的語意判斷），不是閘門的事。
    """
    if tone_body is None or _is_placeholder(_first_line(tone_body)):
        stats.threshold_where = "未比對（源檔尚未落基調）"
        return []

    def _has(lines: list[str]) -> bool:
        return any(_UNIT_RE.search(ln) and _DIGIT_RE.search(ln) for ln in lines)

    style_src = style_dir(book) / "風格.md"
    style_lines = (
        style_src.read_text(encoding="utf-8").splitlines() if style_src.is_file() else []
    )
    in_summary = _has(tone_body)
    in_style = _has(style_lines)
    if in_summary and in_style:
        stats.threshold_where = "摘要＋風格"
    elif in_summary:
        stats.threshold_where = "摘要"
    elif in_style:
        stats.threshold_where = "風格"
    else:
        stats.threshold_where = "**兩邊都沒有**"
        return [
            Problem(
                src,
                "基調宣告沒有寫出單位與達標線"
                f"（源「{TONE_SECTION}」節與源 `風格.md` 都找不到"
                "「單位 token ＋阿拉伯數字」落在同一行）",
                "**寫不出這三件的不是宣告，是願望**（共同約定.md 九）："
                "(i) 單位——這條在哪個尺度上成立（每章／每 arc／全書）；"
                "(ii) 達標線——怎樣算做到了，寫成可數或可指認的形式；"
                "(iii) 誰核對——這一條是 `write-test` 測試5（**逐 arc、相對本書前段**）。"
                "「貼身喜劇」是定調不是達標線，「每章至少 1 次讓讀者鼻子出一口氣」"
                "才是。達標線寫在摘要「基調」節或源 `風格.md`（它是基調在句子層"
                "怎麼落的執行細則）都算。`develop`／`organize` 落檔前遇到這一項"
                "**停下回問作者、不得直接封章**",
            )
        ]
    return []


# ---------------------------------------------------------------- 只印不擋的提示


def _style_copy_state(book: Path, source_tone: str) -> str:
    """`風格.md` 是不是還帶一份基調複本（抉擇 4 A 的可見度）。

    **只印、不擋**：一世之尊不遷移，所以它那一句複本會留著——它是本輪唯一有
    真實傷害路徑的縫的**活體證據**，覆蓋率行要能讓它可見。判準是正規化後
    其中一邊是另一邊的子字串（源檔那句後面常接「一句話：『…』」）。
    """
    if not source_tone:
        return "未比對"
    style_src = style_dir(book) / "風格.md"
    if not style_src.is_file():
        return "未比對（無源 `風格.md`）"
    body = _section_body(style_src.read_text(encoding="utf-8"), TONE_SECTION)
    if body is None:
        return "否"
    got = normalize_tone(_first_line(body))
    want = normalize_tone(source_tone)
    if got and want and (want in got or got in want):
        return "**是**（該改成指標：基調的定義在 `00-摘要.md`）"
    return "否"


def _source_notes(text: str, stats: SummaryStats) -> None:
    """兩個「只印、不擋」的提示（抉擇 1／6，作者拍板）。

    **它們不計入問題數、不影響 exit code**，因為兩件事的切分線都是**語意判斷**：

    - **駁回語彙**（抉擇 1 C）：源檔實測 51.4% 是裁決理由與已駁回方案，而它是
      **唯一每支 skill 都無條件整檔讀的源檔**——那 3,054 字元每次落筆都進
      context。正解是「**被捨棄的方案＋為什麼捨棄**搬進 `story/參照/裁決流.md`、
      已採用的結論留源檔、理由壓成一句」，而**哪一句是哪一半只有人判得出來**。
      本項只讓量可見。
    - **「臨場拍板」節帶已定案字樣**（抉擇 6）：實測 3 條裡有一大半寫著
      「已定案／已鎖定／已寫定」——**標題在說謊**，下游讀到「非定版」會以為
      可以翻案，而其中一條是已鎖死的因果鏈。`M > 0` 就是那個信號。
    """
    # **blockquote 行不算**（位置判準，同 `validate.decision_blockquotes` 的取法）：
    # 源檔的頭註與骨架指示一律寫在 `>` 裡，而那些指示本身就在講「被**捨棄**的方案要
    # 搬去哪」——不排除的話，`書本模板` 會因為自己的說明文字被報 2 處，**閘門對著
    # 一支空骨架亂叫**。實測一世之尊的 7 處全在正文散文裡，排除後不變。
    body_text = "\n".join(
        ln for ln in text.replace("\r\n", "\n").split("\n") if not ln.strip().startswith(">")
    )
    stats.rejection_hits = sum(body_text.count(w) for w in REJECTION_MARKS)
    if stats.rejection_hits:
        by_word = "、".join(
            f"{w}×{body_text.count(w)}" for w in REJECTION_MARKS if body_text.count(w)
        )
        stats.notes.append(
            f"源檔有 {stats.rejection_hits} 處駁回語彙（{by_word}）"
            "——**被捨棄的方案＋為什麼捨棄**屬 `story/參照/裁決流.md`"
            "（`標的`＝`00-摘要.md`），已採用的結論留源檔、理由壓成一句。"
            "摘要是唯一每支 skill 都無條件整檔讀的源檔"
        )

    body = _section_body(text, ADHOC_SECTION)
    if body is None:
        return
    # 一「條」＝一個**頂格**的編號／項目符號，連同它底下所有縮排的續行。
    # **縮排是位置判準**：把續行也算成一條，實測會把 3 條數成 6 條；而只看頂格
    # 那一行的字樣，又會漏掉本節最該報的那一條（`2.` 的標題只寫「玄悲收徒的時點
    # 與頂罪動機」，`已鎖定`／`已寫定` 全在它的續行裡——那是一條已鎖死的因果鏈
    # 躺在「非定版」標題底下）。所以**條數看頂格、字樣看整段**。
    items: list[list[str]] = []
    for ln in body:
        if _TOP_ITEM_RE.match(ln):
            items.append([ln])
        elif items and ln.strip():
            items[-1].append(ln)
    stats.adhoc_items = len(items)
    settled = [it for it in items if any(w in "\n".join(it) for w in SETTLED_MARKS)]
    stats.adhoc_settled = len(settled)
    if settled:
        stats.notes.append(
            f"源檔「{ADHOC_SECTION}」類節 {len(items)} 條，其中 **{len(settled)} 條"
            f"帶 {'／'.join(SETTLED_MARKS)} 字樣**——**標題在說謊**："
            "下游讀到「非定版」會以為可以翻案。已定案的條目**歸位到對應的承重節**"
            "（理由那一半走裁決流）；切完仍真正未定的進 `raw/`。"
            "**不要塞進 `story/參照/待裁決.md`**——那一支的 `來源` 欄語意是"
            "「下游 skill 的觀察」，作者自己的未決會讓那一欄失真"
        )


# ---------------------------------------------------------------- 入口


def lint_book(book: Path) -> tuple[list[Problem], SummaryStats]:
    stats = SummaryStats()
    problems: list[Problem] = []
    src, derived = summary_paths(book)
    if not src.is_file() and not derived.is_file():
        return problems, stats  # 沒有摘要軸的書（只有 raw/ 的書真的存在）

    source_text = src.read_text(encoding="utf-8") if src.is_file() else ""
    tone_body = _section_body(source_text, TONE_SECTION) if source_text else None
    source_tone = _first_line(tone_body)
    if _is_placeholder(source_tone):
        source_tone = ""  # 骨架的括號註記不是基調

    if src.is_file():
        stats.source = 1
        _source_notes(source_text, stats)
        problems += _check_threshold(book, src, tone_body, stats)
    stats.style_copy = _style_copy_state(book, source_tone)

    # ---- 第 0 項：源有、衍生無（**從源側掃**）
    #
    # `設計原則.md` E1 的 06 推論：**從 Y 出發掃描的守衛，對「Y 不存在」永遠回報
    # 乾淨。** `core.check_book` 從 `rglob("*.ai.md")` 出發，所以這一格在定義上
    # 掃不到——而角色軸對同一個洞的代償是**手工建 13 支空殼衍生檔去餵掃描器**。
    # 空殼檔是症狀，掃描方向才是病，所以這裡照 `char-lint` 第 2 項從源側問一次。
    if src.is_file() and not derived.is_file():
        stats.source_without_derived = 1
        problems.append(
            Problem(
                src,
                f"源檔在，但沒有 `{SUMMARY_DERIVED}`",
                "跑 `develop`／`organize` 從源重生它（50/100/200 字壓縮＋高概念＋"
                "取向定位分析＋機讀 front-matter）再 `derived-sync stamp`。"
                "**`check` 從 `.ai.md` 那一側掃，所以這一格它永遠報乾淨**——"
                "而下游 10 支 skill 讀的機讀欄全在這支檔裡。"
                "**不要為了讓工具看得見而建空殼檔**（2026-07-27 功能 06 已駁回）",
            )
        )
        return problems, stats

    if not derived.is_file():
        return problems, stats
    stats.derived = 1

    text = derived.read_text(encoding="utf-8")
    fm = _front_matter(derived)
    if fm is None:
        # 尚未封章的骨架：`check` 已經報成 unstamped，重複報是雜訊
        #（同 validate／world-lint／char-lint／style-lint 的骨架處置）。
        stats.skeleton = 1
        return problems, stats

    problems += _check_keys(derived, fm, stats)
    problems += _check_pov(derived, text, fm, stats)
    problems += _check_tone(derived, fm, source_tone, stats)
    problems += _check_refs(derived, fm, book, stats)
    return problems, stats
