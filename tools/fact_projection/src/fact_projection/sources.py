"""事件從哪裡讀進來。

事實軸按「**可不可重生**」拆成兩個落點（見 `結構定義/事實流.schema.md`）：

- `狀態`／`錨` ＝ 該章正文的函數 → 住 `chapters/chNNNN.ai.md` 的 `## 本章事實`
  區塊，隨該章 `.ai.md` 一起走 `derived_sync` 的 hash 偵測。作者改了正文，
  `derived-sync check` 就報 stale，重生即修正——這是 append log 做不到的。
- `約束` ＝ 作者拍板的意圖（正文裡沒有這句話，重讀一萬遍也生不出來）
  → 住 `story/參照/約束.co.md`，**規則登記表**（見 `constraints.py` 的說明）。

兩者的讀法不同：狀態／錨是事件流（走 `parse_events` ＋ fold），約束是一條一列的
表（走 `constraints.parse_constraints` ＋ 區間篩選）。合流在 `cli.py`。
"""

from __future__ import annotations

import re
from pathlib import Path

from .constraints import Constraint, check_duplicates, parse_constraints
from .fold import KIND_CONSTRAINT, KIND_STATE, Event, FoldError, parse_events
from .ops import OpError, STATEFUL_DIMENSIONS, SET_DIMENSIONS, parse_ops

# 伏筆標記。**這份 regex 的唯一真相在 `tools/foreshadow_project/src/foreshadow_project/
# scan.py:_MARK_RE`**；工具間零相依（所有 tools/*/pyproject.toml 皆 dependencies = []），
# 故此處複製最小片段。schema 用半形冒號，這裡連全形一起收，錯字不靜默漏掉。
_FORESHADOW_RE = re.compile(r"(?:埋|收)\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]")

CHAPTER_SECTION = "本章事實"
CONSTRAINT_TABLE = "約束.co.md"
# 2026-07-26–2026-07-27 之間的 4 欄信封 append log。既有書不遷移，工具照樣讀得動。
CONSTRAINT_LOG_LEGACY = "約束.md"

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


def resolve_constraint_file(book: Path) -> tuple[Path | None, bool]:
    """找約束檔，回傳 (路徑, 是否為舊格式 append log)。都沒有就 (None, False)。"""
    ref = book / "story" / "參照"
    table = ref / CONSTRAINT_TABLE
    if table.is_file():
        return table, False
    log = ref / CONSTRAINT_LOG_LEGACY
    if log.is_file():
        return log, True
    return None, False


ORPHAN_MARK = "〔孤兒〕"


def collect_events(
    book: Path, errors: list[str] | None = None, orphans: list[str] | None = None
) -> tuple[list[Event], str]:
    """收齊全書**事件**（狀態／錨；舊格式書另含約束），回傳 (events, mode)。

    mode ∈ {"legacy", "chapters"}。約束表不走這裡，見 `collect_constraints`。

    `errors` 傳 list ＝ 收集模式（lint 用），None ＝ 嚴格模式（投影用）。
    `order` 依「章序 → 約束 log」遞增指派，故跨檔的同位置 tiebreak 是穩定的。
    """
    legacy = resolve_legacy_stream(book)
    if legacy is not None:
        # 舊格式只有一支檔，標來源等於每行都印同一個檔名——留空，別加雜訊。
        return parse_events(
            legacy.read_text(encoding=_ENCODING), errors=errors
        ), "legacy"

    events: list[Event] = []
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
            )

    path, is_legacy_log = resolve_constraint_file(book)
    if is_legacy_log and path is not None:
        events += parse_events(
            path.read_text(encoding=_ENCODING),
            origin=CONSTRAINT_LOG_LEGACY,
            start_order=len(events),
            errors=errors,
        )
    elif path is None and not events and not chapters.is_dir():
        raise FileNotFoundError(
            f"{book} 下既無 chapters/ 也無 story/參照/{CONSTRAINT_TABLE}"
            f"（舊格式書則需 story/參照/{' 或 '.join(LEGACY_STREAM_NAMES)}"
            f" 或 {CONSTRAINT_LOG_LEGACY}）"
        )
    return events, "chapters"


def collect_constraints(
    book: Path, errors: list[str] | None = None
) -> list[Constraint]:
    """讀約束規則表。舊格式（append log／legacy 單檔）回空——那些走事件流。"""
    path, is_legacy_log = resolve_constraint_file(book)
    if path is None or is_legacy_log or resolve_legacy_stream(book) is not None:
        return []
    out = parse_constraints(
        path.read_text(encoding=_ENCODING), origin=CONSTRAINT_TABLE, errors=errors
    )
    if errors is not None:
        errors += check_duplicates(out, origin=CONSTRAINT_TABLE)
    return out


def check_kind_placement(events: list[Event]) -> list[str]:
    """類型有沒有住錯地方——只有 lint 做，投影不做。

    住錯地方不是格式壞，是**可重生性**錯：約束放進會被重生的章 delta，下次
    重生就沒了；狀態／錨放進約束檔，作者改正文時就沒人管得了。
    """
    problems: list[str] = []
    for e in events:
        if e.origin == CONSTRAINT_LOG_LEGACY and e.kind != KIND_CONSTRAINT:
            problems.append(
                f"{e.origin} 第 {e.lineno} 行是 `{e.kind}`：{CONSTRAINT_LOG_LEGACY}"
                f" 只住 `約束`。狀態／錨屬該章 chNNNN.ai.md 的「## {CHAPTER_SECTION}」"
                "（它們是正文的函數，要能隨正文重生）"
            )
        elif e.origin != CONSTRAINT_LOG_LEGACY and e.kind == KIND_CONSTRAINT:
            problems.append(
                f"{e.origin} 第 {e.lineno} 行是 `約束`：章 delta 會被重生，約束"
                f"寫在這裡下次重生就沒了。約束屬 story/參照/{CONSTRAINT_TABLE}"
                "（規則表，見 事實流.schema.md）"
            )
    return problems


def registered_propositions(book: Path) -> set[str]:
    """全書已登記的伏筆名——掃幕綱的 `埋/收[[伏筆:X]]` 與設定層 `.ai.md` 的 🧊 標記。

    🧊 水下標記的語法是「（🧊 水下｜揭示於 收[[伏筆:X]]）」（`共同約定.md` 六），
    故同一條 regex 同時吃到兩個來源。
    """
    names: set[str] = set()
    for d, pattern in (
        (book / "story" / "幕綱", "*.md"),
        (book / "story" / "設定", "**/*.ai.md"),
    ):
        if not d.is_dir():
            continue
        for p in sorted(d.glob(pattern)):
            names.update(_FORESHADOW_RE.findall(p.read_text(encoding=_ENCODING)))
    return names


def check_set_dimension_ops(book: Path, events: list[Event]) -> list[str]:
    """集合維度的內容欄必須是操作串；`知識前沿` 的命題名必須已在幕綱登記。

    命題名共用伏筆命名空間是刻意的——知識前沿的命題本來就是「玉佛來歷」這類
    東西，它們在幕綱的 `埋/收[[伏筆:X]]` 已經登記過。沿用同一套名字＝不另立
    第二本帳，且「這條何時揭」自動接上幕綱的收點（見 `ops.py`）。
    """
    problems: list[str] = []
    known: set[str] | None = None
    for e in events:
        if e.kind != KIND_STATE or e.name not in SET_DIMENSIONS:
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
                    "裡出現過的伏筆名（`埋/收[[伏筆:…]]`）或 🧊 水下標記指向的名字。"
                    "要嘛先在幕綱登記，要嘛沿用既有的名字（同一件事兩個名字會讓"
                    "命題分裂成兩筆並存）"
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
    """
    problems: list[str] = []
    for e in events:
        if e.origin == CONSTRAINT_LOG_LEGACY:
            continue  # 舊格式約束的內容欄本來就會寫「不得…」
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
                "伏筆埋／收屬幕綱、裁決理由屬 裁決流.co.md、"
                f"下游排除線屬 story/參照/{CONSTRAINT_TABLE}"
            )
        hit = _SMUGGLED_RE.search(content)
        if hit:
            problems.append(
                f"{where}內容欄出現「{hit.group()}」：那是排除線／裁決理由的語彙。"
                f"排除線屬 story/參照/{CONSTRAINT_TABLE}（規則表），"
                "理由屬 story/參照/裁決流.co.md"
            )
    return problems


def lint(book: Path) -> list[str]:
    """回傳全部問題；空 list ＝ 乾淨。

    五類：格式壞行、類型住錯地方、約束表壞列、集合維度的操作串與命題名、
    delta 純化（行長／括號佔比／夾帶語彙）。
    """
    errors: list[str] = []
    try:
        events, mode = collect_events(book, errors=errors)
        collect_constraints(book, errors=errors)
    except FileNotFoundError as e:
        return [str(e)]
    except FoldError as e:  # collect 模式理論上不該走到，保險
        return [str(e)]
    problems = errors + check_kind_placement(events)
    if mode != "legacy":  # 舊格式書刻意不遷移，不套新格式的紀律
        problems += check_set_dimension_ops(book, events)
        problems += check_delta_purity(events)
    return problems
