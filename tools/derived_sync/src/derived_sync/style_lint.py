"""風格軸的格式閘門（`style-lint`）。

**為什麼它存在**（2026-07-27 功能 07 重構輪）：風格軸的方向是對的（源→衍生分權
乾淨、`derived-sync check` 從未報錯過），病集中在**一個地方**——

  `風格.ai.md` 的五個 front-matter 欄是本軸唯一的產物，`風格.schema.md` 稱它們是
  「`write-test` 的機讀核對基準」，而那個基準在一世之尊上是**空的**：`可用句式`
  4/4 檔位違反 schema 自己列的三條 ❌（讀感形容詞／重拍裝置授權／無顆粒度），
  **0/4 宣告顆粒度級別、0/4 給出可數的數字**，而它已經封章、`check` 報 fresh、
  五輪重生沒有任何守衛吭過聲。

**與 `world-lint`／`char-lint` 不是同一個病**（這一點決定了本模組存在而不是刪欄）：
05 的世界觀四欄與 06 的角色三欄是「零解析器 ＋ **零消費者**」，正解是刪欄；風格
這五欄**消費者存在而且指得出行號**（`write/SKILL.md:109`、`write-test/SKILL.md:29,34`、
`revise/SKILL.md:24` 逐欄指名），只是消費者是 **LLM 不是程式**。`設計原則.md` **A4**
同輪據此改寫——位元由「程式會不會解析它」改成「**有沒有人逐欄取值，程式或 LLM
都算**」，並補上一句：**LLM 取值者比程式取值者更需要 lint**，因為程式讀壞格式會
當場炸，LLM 會安靜地讀錯，而錯的那一格會直接進正文。

同輪新增的 **E1 第四條推論**是本模組第 4 項的來源：「凡 schema 宣稱某欄『供 X
核對』，那個欄必須同時定義**什麼樣的值算可核對**，且該判準機械可判。」`風格.schema.md`
是唯一一支把這件事寫出來的 schema（`可用句式` 的 ✅/❌ 表 ＋「值寫得可數」）而它
零實作——**規格寫對了、閘門沒接上，比沒寫規格更接近 E2 最後一格**。

**判準一律是結構判準或位置判準，不得用詞表。** 「這是不是讀感形容詞」用詞表判，
正是 `prose-metrics` 關鍵詞分類、世界觀主題別名表、幕綱集合名對照表**三次被駁回
的同一個形狀**（見 `docs/重構/02-待用構想.md` 已駁回清單）。所以第 4 項問的是
「值裡有沒有 `分句|句|段` token、有沒有阿拉伯數字」，第 2／5 項問的是「有沒有
括號」——都是機械可判、與中文語意無關的事。

**與 `validate` 的分工**（同 `world-lint`／`char-lint`）：`validate` 管所有 `.ai.md`
共通的結構（front-matter 必填鍵、`##` 節枚舉、裁決 blockquote）；本模組管**風格
專屬**的欄語意與正文掃描。兩者同套件、共用 `_split_frontmatter`——風格 `.ai.md`
的格式真相只有一份（先例：`object-lint` 是 `fact-lint` 的聚焦入口、`ch-lint` 與
`beat-lint` 同套件共用一份幕號 registry）。

**已知的複製**：本模組帶進**第 4 份 front-matter 解析**（`validate`／`world_lint`／
`char_lint` 各一）與**第 4 份跨產物欄位比對**（第 6 項 `基調參照` ≡ `00-摘要.ai.md`
的 `基調`，形狀同 `world-lint` 第 4 項／`char-lint` 第 5 項／`ch-lint` 第 6 項）。
工具間零相依（所有 `tools/*/pyproject.toml` 皆 `dependencies = []`），故複製而非
import → 收斂與否交功能 14。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .core import AI_SUFFIX
from .md import KEY_RE, front_matter_of

# 留下來的五個語意欄。**每一個都要在本模組被真的讀到**，否則依 A4／E1 它不配留在
# front-matter（見檔頭）。`風格.schema.md` 有一張逐欄對照表指名這裡的項次。
BANNED_KEY = "禁用詞表"
ADDRESS_KEY = "稱謂系統"
SENTENCE_KEY = "可用句式"
REGISTER_KEY = "語域"
TONE_KEY = "基調參照"
SEMANTIC_KEYS = (BANNED_KEY, ADDRESS_KEY, SENTENCE_KEY, REGISTER_KEY, TONE_KEY)
REQUIRED_KEYS = ("generated-from", "generated-at") + SEMANTIC_KEYS

# `稱謂系統` 裡「這一組是禁用的」那個鍵——它底下的 entry 與 `禁用詞表` 同一種東西，
# 所以套同一條判準（第 3 項尾）。
FORBIDDEN_GROUP = "禁"

# 顆粒度三級，**由細到粗**。這個順序是第 4c 項的全部依據：`風格.schema.md`
# 「不得所有檔位都碎在同一個最粗的一級」。
GRANULARITY = ("分句", "句", "段")
COARSEST = GRANULARITY[-1]

# 摘要衍生檔那一側（第 6 項的比對對象）。
SUMMARY_DERIVED = "00-摘要.ai.md"
SUMMARY_KEY = "基調"

STYLE_DIRNAME = "風格"

# 顆粒度 token 的**位置判準**：只認「值的開頭」或「緊接 `碎在` 之後」的那一個。
#
# **第一版寫成「值裡有沒有 `分句|句|段` 這個字」，實測是假陰性**——`短句快節奏＋
# 破折號…` 與 `短促碎句動詞驅動` 都含「句」字，於是 4/4 讀感形容詞裡有 2 個被判
# 成「已宣告句層」，閘門對著本輪要抓的那一格報乾淨。**那正是它誕生的理由**
#（E2 最後一格：守衛回報正常的假陰性），所以判準收緊成位置。
#
# 收緊到「位置」而不是「詞表」是刻意的：`風格.schema.md` 自己的兩個 ✅ 範例都寫成
# `碎在<級>`（`碎在分句（8字上下、串 4–5 個），句子不斷開`／`碎在句（一句一分句）`），
# 所以這是**照抄 schema 既有的正規形**，不是新發明的語法；同時 `碎在句（一句一分句）`
# 這種「後面還提到別級」的寫法靠位置就分得開。裸寫 `分句（串 4–5 個）` 也吃。
# **不得改成「這是不是讀感形容詞」的詞表判斷**——那是三次被駁回的形狀（見檔頭）。
_GRAN_RE = re.compile(r"(?:^\s*|碎在\s*)[「『]?(分句|句|段)")
_DIGIT_RE = re.compile(r"[0-9]")
# 括號一律算（全形半形皆是）：帶括號的 entry 不是詞，是**一類詞的描述**。
_PAREN_ANY_RE = re.compile(r"[（()）]")
# 半形括號單獨再抓一次：那是**人破結構**那一側的病徵（B1），`fact-lint` 早就在抓
# 同一個東西（作者把全形打成半形，整本書的事實投影 raise）。
_PAREN_HALF_RE = re.compile(r"[()]")

_CH_STEM_RE = re.compile(r"^ch\d+$")
# 候選清單印幾筆就夠（超過印「…」）。同 `world_lint`／`char_lint` 的 6。
_SHOWN = 6


@dataclass(frozen=True)
class Problem:
    path: Path
    detail: str
    hint: str


@dataclass
class StyleStats:
    """**我在這本書上檢查了幾筆**（`設計原則.md` E2 的可執行推論）。

    每一項都印，**0 也印**。這一軸最需要這一行的是**禁用詞掃描**那一段：現況是
    `develop` 的 commit message 逐字寫「禁用詞 0」——那正是 E2 說的「只回答發現
    幾個問題，不回答我檢查了幾筆」。**「11 個 entry，其中 2 個不可字面掃，掃 93
    章命中 0 次」與「禁用詞 0」是兩份完全不同的訊息。**

    依 06 補的那條推論（覆蓋率行要能回答「命中的裡面幾筆是空的」），`keys` 與
    `empty_keys`、`banned_entries` 與 `banned_descriptive`、`slots` 與
    `slots_no_granularity`／`slots_no_digit` 都是**必須成對出現**的數字。
    """

    files: int = 0
    skeleton: int = 0
    keys: int = 0
    empty_keys: int = 0
    banned_entries: int = 0
    banned_descriptive: int = 0
    address_groups: int = 0
    address_words: int = 0
    slots: int = 0
    slots_no_granularity: int = 0
    slots_no_digit: int = 0
    tone_state: str = "未比對"
    chapters: int = 0
    literal_entries: int = 0
    scan_hits: int = 0
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        return (
            f"檢查範圍：{self.files} 支 風格{AI_SUFFIX}"
            f"（{self.skeleton} 支尚未封章的骨架跳過）／"
            f"{self.keys} 個 front-matter 語意欄（**{self.empty_keys} 個是空的**）；\n"
            f"          {self.slots} 個 {SENTENCE_KEY} 檔位"
            f"（**{self.slots_no_granularity} 個無顆粒度 token"
            f"·{self.slots_no_digit} 個無數字**）；\n"
            f"          {self.banned_entries} 個 {BANNED_KEY} entry"
            f"（**{self.banned_descriptive} 個含括號·不可字面掃**）"
            f"·{ADDRESS_KEY} {self.address_groups} 組 {self.address_words} 個詞；\n"
            f"          {TONE_KEY} vs {SUMMARY_DERIVED}：{self.tone_state}；\n"
            f"          掃了 {self.chapters} 章正文／{self.literal_entries} 個字面 entry，"
            f"禁用詞命中 {self.scan_hits} 次。"
        )


# ---------------------------------------------------------------- 解析 helper


def style_dir(book: Path) -> Path:
    return book / "story" / "設定" / STYLE_DIRNAME


def _split_top(s: str) -> list[str]:
    """依**最外層**逗號切分（括號／方括號／大括號內的逗號不算）。

    自寫而不用 yaml：所有 `tools/*/pyproject.toml` 皆 `dependencies = []`。這一支
    只要能切 `{ a: [x, y], b: [z] }` 與 `[詞, 詞（註）, 詞]` 兩種形狀就夠。
    """
    out: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in s:
        if ch in "[{（(":
            depth += 1
        elif ch in "]}）)":
            depth = max(0, depth - 1)
        if ch in ",，" and depth == 0:
            out.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return [x for x in out if x]


def _parse_list(value: str) -> list[str]:
    """`[a, b, c]` → ['a','b','c']（不帶方括號的值也照吃）。"""
    s = value.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    return _split_top(s)


def _parse_mapping(value: str) -> list[tuple[str, str]]:
    """`{ k: v, k2: v2 }` → [(k, v), …]；解析不到冒號的項回 (「」, 原文)。

    回 list 不回 dict 是刻意的——重複鍵要看得見（dict 會靜默吃掉一個）。
    """
    s = value.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    out: list[tuple[str, str]] = []
    for part in _split_top(s):
        m = KEY_RE.match(part)
        if m:
            out.append((m.group(1).strip(), m.group(2).strip()))
        else:
            out.append(("", part))
    return out


def granularity_of(value: str) -> str | None:
    """這個檔位宣告的顆粒度級別；沒有宣告回 None。

    **位置判準，不是語意判準**：不問「這句話在描述什麼」，只問「值的開頭或
    `碎在` 之後是不是那三個 token 之一」（見 `_GRAN_RE` 的註解——第一版「含這個字
    就算」實測放過了 `短句快節奏`／`短促碎句動詞驅動` 兩個讀感形容詞）。
    """
    m = _GRAN_RE.search(value)
    return m.group(1) if m else None


# ---------------------------------------------------------------- 六項檢查


def _check_banned(p: Path, raw: str, stats: StyleStats) -> tuple[list[Problem], list[str]]:
    """第 2 項：`禁用詞表` 的 entry 必須是**可字面掃的詞**。回 (問題, 字面 entry)。

    **判準是位置（有沒有括號），不是語意。** 實測一世之尊 11 個 entry 有 2 個是
    「一類詞的描述」——`老周式暱稱(老X)`、`兄弟(現代語氣)`——它們要的是語意判斷，
    而它們被寫進了一張宣稱「掃到即候選命中」的機讀清單。於是自動掃描永遠回報 0，
    而人看到 0 就不看了。裸掃那兩類：`兄弟` 3 次全是合法的「師兄弟」、`老X` 形態
    133 次（`老僧` 31、`老奴` 9…）全部合法。

    抉擇 2 A（作者拍板）：**收斂成純字面詞**，那兩條規則降級成 `風格.md` 的散文
    ——它們本來就只有 LLM 讀得動。已駁回選項 B（加並列欄 `禁用語域`），見
    `docs/重構/02-待用構想.md`。
    """
    entries = _parse_list(raw)
    stats.banned_entries += len(entries)
    descriptive = [e for e in entries if _PAREN_ANY_RE.search(e)]
    stats.banned_descriptive += len(descriptive)
    literal = [e for e in entries if not _PAREN_ANY_RE.search(e)]
    if not descriptive:
        return [], literal
    shown = "、".join(descriptive[:_SHOWN]) + ("…" if len(descriptive) > _SHOWN else "")
    return [
        Problem(
            p,
            f"`{BANNED_KEY}` 有 {len(descriptive)}/{len(entries)} 個 entry 含括號"
            f"（＝一類詞的描述，不是可字面掃的詞）：{shown}",
            f"`{BANNED_KEY}` 是**機讀清單**（掃到即候選命中），"
            "描述式的判準（「某類詞在某語域下才禁」）降級成源 `風格.md` "
            "「時代・文化色」的散文——schema 早就把家分好了（表給快掃、理由供裁決），"
            "現況只是沒照做。混在表裡的下場是自動掃描永遠回報 0，而人看到 0 就不看了",
        )
    ], literal


def _check_address(p: Path, raw: str, stats: StyleStats) -> list[Problem]:
    """第 3 項：`稱謂系統` 可解析為 `{分組: [詞…]}`；`禁` 組的 entry 同第 2 項判準。

    **分組名自由**（實測本書用 `佛門`／`江湖`，schema 範例用 `敬稱`——那本來就不是
    封閉枚舉，驗不到的就不要宣稱，E1）。這裡只驗形狀：值是不是一組清單。
    """
    out: list[Problem] = []
    groups = _parse_mapping(raw)
    bad_shape = [k or v[:20] for k, v in groups if not v.strip().startswith("[")]
    for key, value in groups:
        if not value.strip().startswith("["):
            continue
        words = _parse_list(value)
        stats.address_groups += 1
        stats.address_words += len(words)
        if key == FORBIDDEN_GROUP:
            descriptive = [w for w in words if _PAREN_ANY_RE.search(w)]
            if descriptive:
                out.append(
                    Problem(
                        p,
                        f"`{ADDRESS_KEY}` 的 `{FORBIDDEN_GROUP}` 組有 "
                        f"{len(descriptive)} 個 entry 含括號："
                        f"{'、'.join(descriptive[:_SHOWN])}",
                        f"同 `{BANNED_KEY}` 那一條——`{FORBIDDEN_GROUP}` 組底下裝的"
                        "是同一種東西（可字面掃的詞），描述式的判準寫進源 `風格.md`",
                    )
                )
    if bad_shape:
        out.append(
            Problem(
                p,
                f"`{ADDRESS_KEY}` 有 {len(bad_shape)} 項不是 `分組: [詞…]` 的形狀："
                f"{'、'.join(str(x) for x in bad_shape[:_SHOWN])}",
                f"格式是 `{ADDRESS_KEY}: {{ 敬稱: [先生, 小姐], {FORBIDDEN_GROUP}: [老X] }}`"
                "（分組名自由，形狀不自由；見 風格.schema.md）",
            )
        )
    return out


def _check_sentence(p: Path, raw: str, stats: StyleStats) -> list[Problem]:
    """第 4 項：`可用句式` 的三小條——顆粒度 token／阿拉伯數字／不得全落最粗一級。

    **這是本模組存在的主要理由**（`設計原則.md` E1 第四推論的實作）。`風格.schema.md`
    早就寫了 ✅/❌ 三條判準 ＋「值寫得可數」，`develop/SKILL.md:42` 甚至把它寫成
    「**不得封章**」的閘門——而那是 LLM 自律，實測沒擋住：4/4 檔位全是讀感形容詞、
    0/4 宣告級別、0/4 給數字，順利封章、`check` 報 fresh。抉擇 1 B（作者拍板）：
    **報，並且 `develop` 落檔前必跑**——把 schema 與 `共同約定.md` 早就承諾過的
    行為接上實作。

    **判準是結構的**：有沒有 `分句|句|段` token、有沒有阿拉伯數字。**不得改成詞表
    判「這是不是讀感形容詞」**——那是三次被駁回的形狀（見檔頭）。已駁回的代價是
    抓不到「顆粒度寫對了但形容詞照堆」，那是 `write-test` 的事，不是閘門的事。

    **未宣告 ＝ 最粗的一級**（第 4c 項的算法）：這不是本模組新造的判準，是
    `風格.schema.md` 自己那條實測結論——「不指定顆粒度時，LLM 一律在**最粗的一級**
    實現讀感，因為那視覺上最碎」（同一句「短句為主」，原著實現在分句層、生成版
    實現在段落層，句層差一倍）。所以 0/4 宣告的書，效果上就是全部落在最粗一級，
    第 4c 項照報——那正是 schema:95 那條規則要擋的狀態。
    """
    out: list[Problem] = []
    slots = _parse_mapping(raw)
    if not slots:
        return [
            Problem(
                p,
                f"`{SENTENCE_KEY}` 解析不到任何檔位：{raw[:60]}",
                f"格式是 `{SENTENCE_KEY}: {{ 日常吐槽: 碎在分句（8字上下、串 4–5 個）, "
                "武道宏大: 碎在句（一句一分句） }`（見 風格.schema.md）",
            )
        ]

    no_gran: list[str] = []
    no_digit: list[str] = []
    levels: list[str] = []
    for name, value in slots:
        stats.slots += 1
        label = name or value[:12]
        gran = granularity_of(value)
        if gran is None:
            no_gran.append(label)
            levels.append(COARSEST)  # 未宣告＝最粗（schema 的實測判準，見 docstring）
        else:
            levels.append(gran)
        if not _DIGIT_RE.search(value):
            no_digit.append(label)

    stats.slots_no_granularity += len(no_gran)
    stats.slots_no_digit += len(no_digit)

    # 4a／4b **各聚合成一行**（03 重構輪拍板的判準：同一種病散在幾筆、病因與修法
    # 完全相同時聚合。逐檔位報 = 4 行同型雜訊）。
    if no_gran:
        out.append(
            Problem(
                p,
                f"`{SENTENCE_KEY}` 有 {len(no_gran)}/{len(slots)} 個檔位沒有顆粒度 token"
                f"（`{'`／`'.join(GRANULARITY)}` 其一）：{'、'.join(no_gran[:_SHOWN])}",
                "這一欄**只做一件事：宣告本書的碎感由哪一級標點承擔**。"
                "「短句快節奏」是**讀感**不是形式，而 LLM 讀到讀感一律在最粗的一級"
                "實現它（schema 的實測：同一句描述，原著落在分句層、生成版落在段落層）。"
                "寫成 `碎在分句（8字上下、串 4–5 個）`",
            )
        )
    if no_digit:
        out.append(
            Problem(
                p,
                f"`{SENTENCE_KEY}` 有 {len(no_digit)}/{len(slots)} 個檔位沒有可數的數字："
                f"{'、'.join(no_digit[:_SHOWN])}",
                "**值寫得可數，這條路才走得通**——`write` 落筆要數得出來"
                "（宣告「碎在分句」＝一個句號前串幾個逗號分句），"
                "`write-test` 要拿 `prose-metrics` 的四項輔助量對照它。"
                "只寫「碎在分句」而沒給數字，那 44 個數字仍然無從對照",
            )
        )
    if levels and all(lv == COARSEST for lv in levels):
        undeclared = len(no_gran)
        why = (
            f"（其中 {undeclared} 個未宣告——**未宣告＝最粗的一級**，"
            "見 風格.schema.md「判準」那條實測）"
            if undeclared
            else ""
        )
        out.append(
            Problem(
                p,
                f"`{SENTENCE_KEY}` 的 {len(levels)} 個檔位全落在最粗的一級"
                f"（`{COARSEST}`）{why}",
                "**至少要有一檔碎在分句層**（流水句、複句、綿延描寫）。"
                "`write` 步驟6「不全篇一種句長勻平」唯一的執行路徑就是這張表；"
                "各檔全在同一級時，在檔位之間切換仍然全篇同一個樣子——"
                "**要求存在，而執行路徑被掏空**。`develop` 落檔前遇到這一項"
                "**停下回問作者，不得直接封章**（風格.schema.md／共同約定.md 九）",
            )
        )
    return out


def _check_register(p: Path, raw: str) -> list[Problem]:
    """第 5 項：`語域` 非空、不得有半形括號。

    **守的是人破結構那一側**（`設計原則.md` B1）：作者把全形括號打成半形，實測讓
    整本書的事實投影 raise，`fact-lint` 早就在抓同一個病徵而這一軸零檢查。
    實測值 `敘述層可現代(刻意喜劇裝置)／對白層書面古樸` 就是半形。
    """
    if _PAREN_HALF_RE.search(raw):
        return [
            Problem(
                p,
                f"`{REGISTER_KEY}` 有半形括號：{raw[:60]}",
                "全形 `（）`——半形括號是**人破結構**那一側最常見的病徵"
                "（同 `fact-lint` 在抓的那一條：一個半形括號讓整本書的事實投影 raise）",
            )
        ]
    return []


def _check_tone(book: Path, p: Path, raw: str, stats: StyleStats) -> list[Problem]:
    """第 6 項：`基調參照` ≡ `00-摘要.ai.md` 的 `基調`（跨產物比對）。

    **為什麼要比對而不是改成指標字串**：`風格.schema.md` 明文「不另立第二份定義」，
    而實測基調字串住在**四個地方**（`00-摘要.md` 源／`00-摘要.ai.md` 的 `基調` 欄／
    `風格.md` 源／此處）。四者目前一致，而 `00-摘要.md` 一改，`風格.ai.md` 的 hash
    （只覆蓋 `風格.md`）**不會 stale**——這條跨檔相依沒有 hash 邊，漂了永遠不會發現。

    **權威是摘要那一側**（schema：基調要變改源 `00-摘要.md`，風格檔隨之重生承接）。
    「四份拷貝該砍到剩幾份」是功能 08 的題目，本輪只補上守衛。
    """
    target = book / "story" / SUMMARY_DERIVED
    if not target.is_file():
        stats.tone_state = f"**未比對·{SUMMARY_DERIVED} 不存在**"
        return [
            Problem(
                p,
                f"`{TONE_KEY}` 的比對對象 `story/{SUMMARY_DERIVED}` 不存在",
                f"`{TONE_KEY}` 是**承接**不是第二份定義（風格.schema.md「規則」）："
                "基調的真實來源是源 `00-摘要.md`，衍生 `00-摘要.ai.md` 的 `基調` 欄"
                "是本項的比對基準。摘要衍生檔還沒產出時，這一欄等於沒有依據",
            )
        ]
    fm = front_matter_of(target)
    if fm is None:
        # 尚未封章的骨架（模板／新書）：`check` 已經報成 unstamped，重複報是雜訊。
        stats.tone_state = f"未比對（{SUMMARY_DERIVED} 尚未封章）"
        return []
    want = fm.get(SUMMARY_KEY, "").strip()
    if not want:
        stats.tone_state = f"**未比對·{SUMMARY_DERIVED} 無 `{SUMMARY_KEY}` 欄**"
        return [
            Problem(
                p,
                f"`{TONE_KEY}` 比對不了：`{SUMMARY_DERIVED}` 沒有 `{SUMMARY_KEY}` 欄",
                "見 摘要.schema.md：`基調` 是摘要衍生檔的必填欄，也是本欄的唯一權威",
            )
        ]
    if want != raw.strip():
        stats.tone_state = "**不符**"
        return [
            Problem(
                p,
                f"`{TONE_KEY}` 與 `{SUMMARY_DERIVED}` 的 `{SUMMARY_KEY}` 不一致：\n"
                f"           風格 `{raw.strip()}`\n"
                f"           摘要 `{want}`",
                "基調的真實來源是源 `00-摘要.md`（風格.schema.md「規則」：不另立"
                "第二份定義）。改基調去改摘要源檔、重生兩支衍生檔——"
                "**這條跨檔相依沒有 hash 邊**（`風格.ai.md` 的 digest 只覆蓋 "
                "`風格.md`），所以漂移只有本項看得見",
            )
        ]
    stats.tone_state = "相符"
    return []


# ---------------------------------------------------------------- 正文掃描


def scan_chapters(book: Path, literal: list[str], stats: StyleStats) -> None:
    """字面禁用詞的正文掃描（抉擇 3 A）。**只印覆蓋率與候選，不做 pass/fail。**

    命中**不計入問題數、不影響 exit code**——「掃到即候選命中」是 `風格.schema.md`
    的原話，**候選不是判定**（合法用法真的存在：實測裸掃 `兄弟` 的 3 次全部是
    「師兄弟」）。複判交 `write-test` 測試5／10(a) 病徵10。

    **為什麼要機械化**：現況是 `write-test` 由 LLM 逐條全文掃，產出的訊息是
    commit message 裡那句「禁用詞 0」——只回答發現幾個問題，不回答檢查了幾筆
    （E2）。**「掃了 93 章／9 個字面 entry（另 2 個含括號·不可字面掃）／命中 0 次」
    才是可用的訊息。**

    **多檔形態下取所有風格檔字面 entry 的聯集**：逐章依 `chNNNN.ai.md` 的 `風格`
    欄分派是更精確的做法，但 0 本書拆過多檔（那條 forward-compat 路徑本身就標著
    「零實作的行為承諾」），現在做等於憑空設計。`ch-lint` 已經在守那一欄指向的檔
    存在——**真的有書拆多檔時，這裡跟著改**。
    """
    d = book / "chapters"
    if not d.is_dir():
        return
    chapters = [
        p
        for p in sorted(d.glob("ch*.md"))
        if not p.name.endswith(AI_SUFFIX) and _CH_STEM_RE.match(p.stem)
    ]
    stats.chapters = len(chapters)
    stats.literal_entries = len(literal)
    if not chapters or not literal:
        return
    hits: dict[str, list[tuple[str, int]]] = {}
    for p in chapters:
        text = p.read_text(encoding="utf-8")
        for word in literal:
            n = text.count(word)
            if n:
                hits.setdefault(word, []).append((p.stem, n))
    stats.scan_hits = sum(n for v in hits.values() for _, n in v)
    for word, where in sorted(hits.items(), key=lambda kv: -sum(n for _, n in kv[1])):
        total = sum(n for _, n in where)
        shown = "、".join(f"{stem}×{n}" for stem, n in where[:_SHOWN])
        if len(where) > _SHOWN:
            shown += "…"
        stats.notes.append(
            f"`{word}` 命中 {total} 次／{len(where)} 章：{shown}"
        )


# ---------------------------------------------------------------- 入口


def lint_book(book: Path) -> tuple[list[Problem], StyleStats]:
    stats = StyleStats()
    problems: list[Problem] = []
    literal_all: list[str] = []

    d = style_dir(book)
    if not d.is_dir():
        return problems, stats

    for p in sorted(d.glob(f"*{AI_SUFFIX}")):
        if p.name.startswith("_"):
            continue  # rollup（多檔形態才有，格式比照世界觀 _總覽；本輪零實作）
        stats.files += 1
        fm = front_matter_of(p)
        if fm is None:
            # 尚未封章的骨架：`check` 已經報成 unstamped，重複報是雜訊
            #（同 validate／world-lint／char-lint 的骨架處置）。
            stats.skeleton += 1
            continue

        # ---- 第 1 項：七鍵齊全（空值也算缺——一個空的「機讀核對基準」比沒有更糟）
        missing = [k for k in REQUIRED_KEYS if not fm.get(k, "").strip()]
        for k in SEMANTIC_KEYS:
            if k in fm:
                stats.keys += 1
                if not fm[k].strip():
                    stats.empty_keys += 1
        if missing:
            problems.append(
                Problem(
                    p,
                    f"front-matter 缺（或空）{'、'.join(missing)}",
                    "`generated-*` 跑 `derived-sync stamp <該檔>` 封章、別手填；"
                    f"五個語意欄（{'／'.join(SEMANTIC_KEYS)}）是本軸**唯一的產物**，"
                    "每一欄都在 `style-lint` 裡指得出讀它的那一項（風格.schema.md "
                    "有逐欄對照表）——**衍生檔的本體 2026-07-27 已廢除**，"
                    "腔調散文的唯一落點是源 `風格.md`",
                )
            )

        # ---- 第 2 項
        if fm.get(BANNED_KEY, "").strip():
            probs, literal = _check_banned(p, fm[BANNED_KEY], stats)
            problems += probs
            literal_all += literal
        # ---- 第 3 項
        if fm.get(ADDRESS_KEY, "").strip():
            problems += _check_address(p, fm[ADDRESS_KEY], stats)
        # ---- 第 4 項
        if fm.get(SENTENCE_KEY, "").strip():
            problems += _check_sentence(p, fm[SENTENCE_KEY], stats)
        # ---- 第 5 項
        if fm.get(REGISTER_KEY, "").strip():
            problems += _check_register(p, fm[REGISTER_KEY])
        # ---- 第 6 項
        if fm.get(TONE_KEY, "").strip():
            problems += _check_tone(book, p, fm[TONE_KEY], stats)

    # ---- 正文掃描（提示，不計入問題數）
    scan_chapters(book, sorted(set(literal_all)), stats)
    return problems, stats
