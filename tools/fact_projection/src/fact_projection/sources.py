"""事件從哪裡讀進來。

事實軸按「**可不可重生**」拆成兩個落點（見 `結構定義/事實流.schema.md`）：

- `狀態`／`錨` ＝ 該章正文的函數 → 住 `chapters/chNNNN.ai.md` 的 `## 本章事實`
  區塊，隨該章 `.ai.md` 一起走 `derived_sync` 的 hash 偵測。作者改了正文，
  `derived-sync check` 就報 stale，重生即修正——這是 append log 做不到的。
- `約束` ＝ 作者拍板的意圖（正文裡沒有這句話，重讀一萬遍也生不出來）
  → 住 `story/物件/<名>.md` 的「## 不得寫成什麼」，**規則登記表**
  （2026-07-27 從 `story/參照/約束.co.md` 搬過來，見 `objects.py`）。

兩者的讀法不同：狀態／錨是事件流（走 `parse_events` ＋ fold），約束是一條一列的
表（走 `constraints.parse_constraints` ＋ 區間篩選）。合流在 `cli.py`。

**這支檔還負責一件事：讓 lint 能回答「我檢查了幾筆」。** 2026-07-27 前舊格式豁免是
一個整本書的開關，實測 206 個問題報 0、而閘門印的是「格式乾淨」——因為它只會回答
「我發現幾個問題」。`LintStats` 是那條教訓的落地（`設計原則.md` E2）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .chapters import check_chapter_scope, load_chapter_meta
from .constraints import CONSTRAINT_SECTION, Constraint
from .fold import (
    GEN_LEGACY,
    GEN_NEW,
    KIND_CONSTRAINT,
    KIND_STATE,
    Event,
    FoldError,
    parse_events,
)
from .objects import (
    OBJECT_DIRNAME,
    ObjectFile,
    check_near_miss,
    check_objects,
    check_reveal_targets,
    load_objects,
    objects_dir,
    suggest_objects,
)
from .ops import OpError, STATEFUL_DIMENSIONS, SET_DIMENSIONS, parse_ops

# 伏筆標記。**這份 regex 的唯一真相在 `tools/foreshadow_project/src/foreshadow_project/
# scan.py:_MARK_RE`**；工具間零相依（所有 tools/*/pyproject.toml 皆 dependencies = []），
# 故此處複製最小片段。schema 用半形冒號，這裡連全形一起收，錯字不靜默漏掉。
_FORESHADOW_RE = re.compile(r"(?:埋|收)\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]")

CHAPTER_SECTION = "本章事實"

# **這兩個落點已廢除**（2026-07-27）。約束搬進 `story/物件/<名>.md` 的
# 「## 不得寫成什麼」，理由見 `constraints.py`。檔還在＝內容還沒搬，於是那些排除線
# 沒有任何工具在讀，而 `write` 會理直氣壯地違反它們——所以這裡**報成落點錯**，
# 不靜默忽略。（實測沒有任何一本有內容的書用過這兩支檔，故不留讀取路徑。）
RETIRED_CONSTRAINT_NAMES = ("約束.co.md", "約束.md")

# Windows 上的編輯器（含 PowerShell `Set-Content -Encoding utf8`）常寫出帶 BOM 的
# UTF-8。BOM 會黏在第一行行首，讓 `- 幕001…` 的事件行認不出來而被靜默跳過——
# 事實少一筆比報錯還難查。`utf-8-sig` 有 BOM 就吃掉、沒有也照常運作。
# （`derived_sync` 那邊刻意**不**跟進：它讀檔是為了算 hash，換編碼會讓既有
#  `generated-from` 全數失準、整書誤報 stale。）
_ENCODING = "utf-8-sig"

# 2026-07-26 前的單檔 append log。既有書（一世之尊）不遷移，工具照樣讀得動。
LEGACY_STREAM_NAMES = ("事實流.md", "狀態事件流.md")


def resolve_legacy_stream(book: Path) -> Path | None:
    """找舊的單檔事實流；沒有就回 None（＝這本書走新格式）。"""
    ref = book / "story" / "參照"
    for name in LEGACY_STREAM_NAMES:
        p = ref / name
        if p.is_file():
            return p
    return None


def section_lines(text: str, title: str) -> str:
    """抽出 `## <title>` 區塊，**保留原行號**（區塊外的行換成空行）。

    行號要對得上原檔，報錯訊息才指得到人看得懂的位置。
    """
    out: list[str] = []
    inside = False
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = raw.strip()
        if stripped.startswith("## "):
            inside = stripped[3:].strip().startswith(title)
            out.append("")  # 標題行本身不是事件
            continue
        out.append(raw if inside else "")
    return "\n".join(out)


def _chapter_origin(p: Path) -> str:
    return p.name[: -len(".ai.md")]


def retired_constraint_files(book: Path) -> list[Path]:
    """還留在已廢除落點的約束檔。"""
    ref = book / "story" / "參照"
    return [p for n in RETIRED_CONSTRAINT_NAMES if (p := ref / n).is_file()]


ORPHAN_MARK = "〔孤兒〕"


def collect_events(
    book: Path, errors: list[str] | None = None, orphans: list[str] | None = None
) -> tuple[list[Event], str]:
    """收齊全書**事件**（狀態／錨），回傳 (events, mode)。

    mode ∈ {"legacy", "chapters"}，**只用來決定輸出標頭**——真正的世代判斷跟著
    每一筆事件自己的 `generation` 走（見 `fold.GEN_LEGACY`）。2026-07-27 前這裡
    遇到舊格式單檔就 early-return，於是一支檔的存在與否決定整本書要不要跑檢查；
    現在兩個來源**合流**，混格式的書（舊單檔還在、新章已經開始寫）兩邊都讀得到。

    約束不走這裡（它是表不是事件流），見 `collect_constraints`。

    `errors` 傳 list ＝ 收集模式（lint 用），None ＝ 嚴格模式（投影用）。
    `order` 依「舊單檔 → 章序」遞增指派，故跨檔的同位置 tiebreak 是穩定的。
    """
    events: list[Event] = []
    legacy = resolve_legacy_stream(book)
    if legacy is not None:
        # 標來源：混格式時「這一行出自哪一代」是讀者第一個要問的事。
        events += parse_events(
            legacy.read_text(encoding=_ENCODING),
            origin=legacy.name,
            errors=errors,
            generation=GEN_LEGACY,
        )

    chapters = book / "chapters"
    if chapters.is_dir():
        for p in sorted(chapters.glob("ch*.ai.md")):
            stem = _chapter_origin(p)
            origin = stem
            # 孤兒＝正文源已不在（作者合併兩章、或亂序下沉改檔名只改了一半）。
            # `derived-sync check` 早就報 orphan 了，但兩支工具互不知會，於是一個
            # 已經不存在的章釘下的事實，照樣被當成生效中的承諾送進 write 的 context。
            # **不靜默排除**——讓事實憑空消失比標記更危險。
            if not (chapters / f"{stem}.md").is_file():
                origin = f"{stem}{ORPHAN_MARK}"
                msg = (
                    f"{stem}.ai.md 找不到正文源 {stem}.md，其事實仍被納入投影並標"
                    f"{ORPHAN_MARK}——若該章已刪或已改名，連同 .ai.md 一起處理"
                )
                if errors is not None:
                    errors.append(msg)
                if orphans is not None:
                    orphans.append(msg)
            body = section_lines(p.read_text(encoding=_ENCODING), CHAPTER_SECTION)
            events += parse_events(
                body,
                origin=origin,
                start_order=len(events),
                errors=errors,
                generation=GEN_NEW,
            )

    if legacy is None and not chapters.is_dir() and not objects_dir(book).is_dir():
        raise FileNotFoundError(
            f"{book} 下既無 chapters/ 也無 story/{OBJECT_DIRNAME}/"
            f"（舊格式書則需 story/參照/{' 或 '.join(LEGACY_STREAM_NAMES)}）"
        )
    return events, "legacy" if legacy is not None else "chapters"


def collect_constraints(
    book: Path, errors: list[str] | None = None
) -> list[Constraint]:
    """讀約束規則表——它住各支物件檔的「## 不得寫成什麼」。"""
    return [c for o in load_objects(book, errors=errors) for c in o.constraints]


def check_kind_placement(events: list[Event], book: Path) -> list[str]:
    """類型有沒有住錯地方——只有 lint 做，投影不做。

    住錯地方不是格式壞，是**可重生性**錯：約束放進會被重生的章 delta，下次
    重生就沒了（它是作者的意圖，不是正文的函數）。
    """
    problems: list[str] = []
    for e in events:
        if e.kind == KIND_CONSTRAINT:
            problems.append(
                f"{e.origin} 第 {e.lineno} 行是 `約束`：章 delta 會被重生，約束"
                f"寫在這裡下次重生就沒了。約束屬 story/{OBJECT_DIRNAME}/<實體>.md"
                f" 的「## {CONSTRAINT_SECTION}」（規則表，見 物件.schema.md）"
            )
    for p in retired_constraint_files(book):
        problems.append(
            f"story/參照/{p.name}：這個落點已廢除（2026-07-27）。"
            f"把每一列搬進 story/{OBJECT_DIRNAME}/<該列的實體>.md 的"
            f"「## {CONSTRAINT_SECTION}」（表降成 4 欄，"
            "「實體」欄拿掉——它就是檔名），然後刪掉這支檔。"
            "**留著它不會有人讀，那些排除線等於不存在**"
        )
    return problems


def registered_propositions(book: Path) -> set[str]:
    """全書已登記的名字——幕綱的 `埋/收[[伏筆:X]]` ∪ 物件檔名。

    `知識前沿` 的命題名必須命中其中一個。兩個來源是刻意的：幕綱那套是「這條線何時
    埋、何時收」，物件檔那套是「這東西是什麼、不得寫成什麼」——同一個名字的兩個切面，
    不是兩本帳。（2026-07-27 前第二個來源是設定層 `.ai.md` 的 🧊 標記，那個落點已廢除。）
    """
    names: set[str] = set()
    d = book / "story" / "幕綱"
    if d.is_dir():
        for p in sorted(d.glob("*.md")):
            names.update(_FORESHADOW_RE.findall(p.read_text(encoding=_ENCODING)))
    names.update(o.name for o in load_objects(book))
    return names


def check_set_dimension_ops(book: Path, events: list[Event]) -> list[str]:
    """集合維度的內容欄必須是操作串；`知識前沿` 的命題名必須已登記。

    命題名共用伏筆／物件的命名空間是刻意的——知識前沿的命題本來就是「玉佛來歷」
    這類東西，它們在幕綱的 `埋/收[[伏筆:X]]` 或 `story/物件/` 已經登記過。沿用
    同一套名字＝不另立第二本帳，且「這條何時揭」自動接上幕綱的收點（見 `ops.py`）。
    """
    problems: list[str] = []
    known: set[str] | None = None
    for e in events:
        if e.kind != KIND_STATE or e.name not in SET_DIMENSIONS:
            continue
        if e.legacy:
            # 舊格式的 `知識前沿` 是自由 prose，那是刻意的（既有書不遷移）。
            # **這是逐行判斷，不是整本書一個開關**——同一本書裡新章的 delta 照檢。
            continue
        where = f"{e.origin} 第 {e.lineno} 行" if e.origin else f"第 {e.lineno} 行"
        try:
            ops = parse_ops(e.content, e.name)
        except OpError as err:
            problems.append(f"{where}{err}")
            continue
        if e.name not in STATEFUL_DIMENSIONS:
            continue
        if known is None:
            known = registered_propositions(book)
        for op in ops:
            if op.name not in known:
                problems.append(
                    f"{where}命題〔{op.name}〕未登記——`知識前沿` 的命題名須是幕綱"
                    f"裡出現過的伏筆名（`埋/收[[伏筆:…]]`），或 story/"
                    f"{OBJECT_DIRNAME}/ 下某支物件檔的檔名。要嘛先登記，要嘛沿用"
                    "既有的名字（同一件事兩個名字會讓命題分裂成兩筆並存）"
                )
    return problems


# delta 純化的三條門檻。依據＝一世之尊實測（見 `結構定義/事實流.schema.md`）：
# 健康期（arc01–arc04）平均內容長 76 字、括號佔比 36%；病態期（arc09–arc11）
# 194 字、51.9%。純 delta 的範例約 40–50 字。
CONTENT_CHARS = 200
PAREN_RATIO = 0.40
PAREN_MIN_CHARS = 60  # 太短的行算不出有意義的比例，不報

# 這些詞出現在章 delta 的內容欄，幾乎一定是別條軸的東西被夾帶進來。
# （`不得寫成` 是約束表自己的欄位，那裡不套本檢查。）
_SMUGGLED_RE = re.compile(
    r"不得|守死|守住|射程|一字不|on-page|留白|排除線|護欄|降回閥|本輪拍板"
)
_PAREN_RE = re.compile(r"（[^（）]*）")


def check_delta_purity(events: list[Event]) -> list[str]:
    """事件行只該寫「這一幕改變了什麼」。

    實測兩個成長機制：**重抄**（fold 覆蓋逼出的前情提要效應，由集合維度解掉）
    與**夾帶**（事件行是唯一保證會被 `write` 讀到的欄位，於是伏筆狀態、裁決理由、
    下游排除線全往括號裡塞）。本函式守的是後者——沒有它，夾帶會在新書原封重演。

    **兩個世代一律照檢。** 行長與夾帶是行本身的紀律，跟它出生在哪一代無關——
    而舊格式那本書正是這條紀律唯一的實測病例（一路長了 11 個 arc，206 筆）。
    2026-07-27 前它整本被豁免，於是閘門對 206 個問題印「格式乾淨」。
    """
    problems: list[str] = []
    for e in events:
        where = f"{e.origin} 第 {e.lineno} 行" if e.origin else f"第 {e.lineno} 行"
        content = e.content
        if len(content) > CONTENT_CHARS:
            problems.append(
                f"{where}內容欄 {len(content)} 字（上限 {CONTENT_CHARS}）："
                "delta 只寫這一幕改變了什麼。仍然成立的舊事不必重抄"
                "（查得到：`fact-project --history <實體>/<維度>`）"
            )
        paren = sum(len(m) for m in _PAREN_RE.findall(content))
        if len(content) >= PAREN_MIN_CHARS and paren / len(content) > PAREN_RATIO:
            problems.append(
                f"{where}括號內註解佔 {paren / len(content):.0%}"
                f"（上限 {PAREN_RATIO:.0%}）：疑似夾帶設計註。"
                "伏筆埋／收屬幕綱、裁決理由屬 story/參照/裁決流.md、"
                f"下游排除線屬 story/{OBJECT_DIRNAME}/<實體>.md 的"
                f"「## {CONSTRAINT_SECTION}」"
            )
        hit = _SMUGGLED_RE.search(content)
        if hit:
            problems.append(
                f"{where}內容欄出現「{hit.group()}」：那是排除線／裁決理由的語彙。"
                f"排除線屬 story/{OBJECT_DIRNAME}/<實體>.md 的"
                f"「## {CONSTRAINT_SECTION}」，理由屬 story/參照/裁決流.md"
            )
    return problems


def referenced_object_names(
    book: Path, events: list[Event]
) -> dict[str, list[str]]:
    """被引用到的物件名 → 在哪裡被引用（供近似名偵測與「要不要開檔？」提示）。

    兩個來源，都是**共用同一個命名空間**的那些：章 delta 的 `知識前沿` 命題名，
    以及幕綱的 `埋/收[[伏筆:X]]`。（`持有`／`能力` 的名字是道具與招式，schema
    刻意不做跨檔驗證，故不納入。）
    """
    out: dict[str, list[str]] = {}
    for e in events:
        if e.kind != KIND_STATE or e.name not in STATEFUL_DIMENSIONS or e.legacy:
            continue
        try:
            ops = parse_ops(e.content, e.name)
        except OpError:
            continue  # 壞行由 check_set_dimension_ops 報，這裡不重複
        for op in ops:
            out.setdefault(op.name, []).append(f"{e.origin} 第 {e.lineno} 行")
    d = book / "story" / "幕綱"
    if d.is_dir():
        for p in sorted(d.glob("*.md")):
            for name in _FORESHADOW_RE.findall(p.read_text(encoding=_ENCODING)):
                out.setdefault(name, []).append(f"幕綱/{p.name}")
    return out


@dataclass
class LintStats:
    """**我在這本書上檢查了幾筆。**

    `設計原則.md` E2 的可執行推論：每個檢查器都要能回答這個問題，不能只回答
    「我發現幾個問題」。實測教訓——舊格式豁免讓 `fact-lint` 對 206 個問題印
    「事實信封行格式乾淨」，因為它只會報問題數；一句「我檢查了 0 筆」就能讓那個
    bug 活不過一天。**乾淨的時候也要印。**
    """

    chapter_files: int = 0
    fact_lines_new: int = 0
    fact_lines_legacy: int = 0
    constraint_rows: int = 0
    object_files: int = 0
    reveal_marks: int = 0
    chapter_scope_checked: int = 0
    reference_names: int = 0
    notes: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    @property
    def fact_lines(self) -> int:
        return self.fact_lines_new + self.fact_lines_legacy

    def render(self) -> str:
        return (
            f"檢查範圍：{self.chapter_files} 支章 delta／"
            f"{self.fact_lines} 筆事實行"
            f"（新格式 {self.fact_lines_new}·舊格式 {self.fact_lines_legacy}）／"
            f"{self.object_files} 支物件檔／{self.constraint_rows} 條約束／"
            f"{self.reveal_marks} 個揭示層級；"
            f"核對了 {self.chapter_scope_checked} 支章的對應幕區間、"
            f"{self.reference_names} 個引用名"
        )


def lint_report(book: Path) -> tuple[list[str], LintStats]:
    """回傳 (全部問題, 檢查範圍統計)。空問題 list ＝ 乾淨。

    問題分七類：格式壞行、類型住錯地方（含已廢除的約束落點）、物件檔格式、
    約束表壞列、集合維度的操作串與命題名、delta 純化（行長／括號佔比／夾帶語彙）、
    事實行的幕號落錯章。
    """
    errors: list[str] = []
    stats = LintStats()
    try:
        events, _mode = collect_events(book, errors=errors)
        objs: list[ObjectFile] = load_objects(book, errors=errors)
    except FileNotFoundError as e:
        return [str(e)], stats
    except FoldError as e:  # collect 模式理論上不該走到，保險
        return [str(e)], stats

    chapters = book / "chapters"
    stats.chapter_files = (
        len(list(chapters.glob("ch*.ai.md"))) if chapters.is_dir() else 0
    )
    stats.fact_lines_new = sum(1 for e in events if not e.legacy)
    stats.fact_lines_legacy = sum(1 for e in events if e.legacy)
    stats.object_files = len(objs)
    stats.constraint_rows = sum(len(o.constraints) for o in objs)
    stats.reveal_marks = sum(1 for o in objs if o.underwater)

    problems = errors + check_kind_placement(events, book)
    problems += check_objects(objs)
    problems += check_reveal_targets(book, objs, notes=stats.notes)
    problems += check_set_dimension_ops(book, events)
    problems += check_delta_purity(events)

    metas = load_chapter_meta(book)
    scope_problems, checked = check_chapter_scope(metas, events)
    problems += scope_problems
    stats.chapter_scope_checked = checked

    referenced = referenced_object_names(book, events)
    stats.reference_names = len(referenced)
    problems += check_near_miss(objs, referenced)
    stats.hints += suggest_objects(objs, referenced)

    return problems, stats


def lint(book: Path) -> list[str]:
    """`lint_report` 的薄封裝，只要問題清單時用。"""
    return lint_report(book)[0]
