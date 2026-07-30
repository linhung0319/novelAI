from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .ops import OpError, apply_ops, parse_ops, render

# 狀態的 6 維（封閉枚舉，跨小說通用）——語意與子專案 C 原版逐字相同。
DIMENSIONS = frozenset({"知識前沿", "關係", "持有", "位置", "能力", "所屬"})

# 關係類實體寫 `A↔B`，視為一個雙向 slot（見 結構定義/事實流.schema.md 逐欄定義）。
RELATION_SEP = "↔"

KIND_STATE = "狀態"
KIND_ANCHOR = "錨"
KIND_CONSTRAINT = "約束"
KINDS = (KIND_STATE, KIND_ANCHOR, KIND_CONSTRAINT)

# 約束退場靠顯式解除，不加第 5 欄（見 結構定義/事實流.schema.md）。
RELEASE_PREFIX = "（解除）"

# **「格式世代」欄 2026-07-30（驗證輪階段 1c）移除。**
#
# 它的沿革值得留著，因為它記錄了一個豁免被收窄兩次、最後歸零的完整過程：
#
# 1. 2026-07-27 前，舊格式豁免是一個**整本書**的開關——`story/參照/` 底下只要存在
#    一支 `狀態事件流.md`，純化三條與集合維度檢查就整本跳過，只印一行 stderr。
#    實測後果：一世之尊 206 個問題報 0，而且那 206 個一路長了 11 個 arc 沒人吭聲。
# 2. 2026-07-27 收窄成**逐行**：世代跟著那一行的來源走，差別只剩集合維度
#    （舊格式的 `知識前沿` 是自由 prose）；純化三條兩代一律照檢。
# 3. 2026-07-30 舊單檔事實流的**讀取路徑**移除（見 `sources.RETIRED_STREAM_NAMES`），
#    於是 `legacy` 這個值**再也沒有生產者**——每一筆事件都出自章 delta。
#
# **一個沒有生產者的枚舉值，與一條永遠為真的 if 是同一件事。** 留著它只會讓下一個
# 讀這段程式的人以為系統還吃兩種格式。事件的來源仍然說得出來——那是 `origin` 欄。


class LayerMissing(FileNotFoundError):
    """**這本書還沒有這一層**——與「這本書的格式壞了」是兩件事（功能 14，抉擇 6 A）。

    契約：**exit 2，而且照樣印覆蓋率行**（`共同約定.md`「輸出與 exit 契約」）。
    **它是 `FileNotFoundError` 的子類**，所以既有的 `except FileNotFoundError`
    照舊接得住，只有想分辨的地方才要多接一層。
    """


class FoldError(Exception):
    """事實流/spine 解析或定位失敗（格式壞行、未知類型 token、無法定位）。"""


@dataclass(frozen=True)
class Event:
    beat: int
    arc: str
    entity: str
    token: str  # 第三欄原文：6 維之一，或 錨〔名〕／約束〔名〕
    kind: str  # 狀態／錨／約束
    name: str  # 狀態＝維度名；錨/約束＝〔〕內的名字
    content: str
    lineno: int
    origin: str = ""  # 來源檔識別（ch0009），供投影標注與報錯
    order: int = 0  # 跨檔全域序號；同位置的 tiebreak（取代單檔時代的 lineno）

    @property
    def released(self) -> bool:
        return self.content.startswith(RELEASE_PREFIX)


# 位置從左端解析：幕NNN（arcAA）後第一個 · 為位置/實體分隔；實體之後（含名字內的 ·）全歸實體。
_POS_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）\s*·\s*(.+)$")
# 錨／約束的 token 帶名字；名字內不得再有全形方括號。
_TYPED_TOKEN_RE = re.compile(r"^(錨|約束)〔([^〔〕]+)〕$")


def classify_token(token: str) -> tuple[str, str]:
    """第三欄 token → (kind, name)。未知 token 報錯、不靜默丟。"""
    if token in DIMENSIONS:
        return KIND_STATE, token
    m = _TYPED_TOKEN_RE.match(token)
    if m:
        return m.group(1), m.group(2).strip()
    raise FoldError(
        f"未知類型 token {token!r}"
        f"（限 6 維狀態 {sorted(DIMENSIONS)}，或 錨〔名〕／約束〔名〕）"
    )


def strip_html_comments(lines: list[str]) -> list[tuple[int, str]]:
    """濾掉 `<!-- ... -->` 區塊，回傳 [(原始行號, 行)]。

    schema 與書本模板會把範例事件放在註解裡；那些**不是事件**，讀進來會
    因為引用了不存在的 arc 而整份投影報錯。
    """
    out: list[tuple[int, str]] = []
    in_comment = False
    for i, raw in enumerate(lines, start=1):
        line = raw
        if in_comment:
            if "-->" in line:
                in_comment = False
                line = line.split("-->", 1)[1]
            else:
                continue
        while "<!--" in line:
            before, _, rest = line.partition("<!--")
            if "-->" in rest:
                line = before + rest.split("-->", 1)[1]
            else:
                line = before
                in_comment = True
                break
        if line.strip():
            out.append((i, line))
    return out


def parse_events(
    text: str,
    origin: str = "",
    start_order: int = 0,
    errors: list[str] | None = None,
) -> list[Event]:
    """解析事件行。

    `errors` 為 None（預設）＝ 嚴格模式，遇壞行即 raise——投影走這條，因為投影
    吐出不完整的事實比報錯危險。傳入 list ＝ 收集模式，把每個壞行的訊息 append
    進去並跳過該行，讓 `lint` 能一次報完全部而不是只報第一個。
    """
    events: list[Event] = []
    for i, raw in strip_html_comments(text.splitlines()):
        line = raw.strip()
        if not line.startswith("-"):
            continue
        body = line[1:].strip()
        if not body.startswith("幕"):  # 非事件行（標題/說明/其他 bullet）→ 跳過
            continue
        where = f"{origin} 第 {i} 行" if origin else f"第 {i} 行"
        try:
            if "：" not in body:
                raise FoldError(f"{where}事件缺少內容分隔『：』：{raw!r}")
            head, _, content = body.partition("：")
            # token 內無 ·（6 維無點；錨/約束的〔〕內也不容 ·），故最後一個 · 必為實體/token 分隔
            left, sep, tok = head.rpartition("·")
            if not sep:
                raise FoldError(f"{where}事件缺少類型分隔『·』：{raw!r}")
            token = tok.strip()
            try:
                kind, name = classify_token(token)
            except FoldError as e:
                raise FoldError(f"{where}{e}") from None
            m = _POS_RE.match(left.strip())
            if not m:
                raise FoldError(f"{where}位置/實體格式不符：{raw!r}")
        except FoldError as e:
            if errors is None:
                raise
            errors.append(str(e))
            continue
        events.append(
            Event(
                beat=int(m.group(1)),
                arc=m.group(2).strip(),
                entity=m.group(3).strip(),
                token=token,
                kind=kind,
                name=name,
                content=content.strip(),
                lineno=i,
                origin=origin,
                order=start_order + len(events),
            )
        )
    return events


_SPINE_RE = re.compile(r"全書順序：(.+)$")
_ARC_TOKEN_RE = re.compile(r"arc[0-9A-Za-z]+")

# spine 的落點（2026-07-28 功能 12 抉擇 2 A；**回退 2026-07-30 移除**）。
#
# `全書順序：` 是作者的創作決定（哪一段先發生），沒有任何檔算得出來——它是 A1 源，
# 而它原本住在一支被 `beat-lint` 當「視圖 ≡ 資料夾」驗的索引檔裡。一支檔同時裝
# 「權威在自己身上的源」與「權威在別處的視圖」＝六問 Q0 的違反，所以 12 把它搬進
# 同層的 `_順序.md`。
#
# **舊落點 `_index.md` 的回退（驗證輪階段 1c）移除。** 實測活用戶**只有 `一世之尊`**
# ——`書本模板`／`驗證範例` 早就是 `_順序.md`，`harry_potter`／`gothic_witch`／
# `芯片巫師` 沒有幕綱層。四份回退實作服務一本刻意不遷移的病例書。
#
# **它換成墓碑，不是換成靜默**：檔在就報「舊落點還在、2026-07-30 起不再讀」，
# 並指出 `git mv` 那一行過去即可。依 `設計原則.md` A5，撤銷一個落點的身分要從
# 機制看得出來——不讀又不報，會讓「這本書沒有 spine」與「這本書的 spine 住舊落點」
# 變成同一句話。
#
# **回退活著的時候，這件事只有 1/4 成立**（功能 14 的 V9）：12 承諾四支工具都要讓
# 回退可見，而只有 `beat-lint` 有 `spine_legacy` 欄。現在四支都印，因為墓碑就是輸出。
SPINE_FILES = ("_順序.md",)
RETIRED_SPINE_FILES = ("_index.md",)


def spine_path(book: Path) -> Path:
    """回 spine 檔的落點。**唯一落點**——不在時照樣回它，讓錯誤訊息指向該建的那支。"""
    return book / "story" / "幕綱" / SPINE_FILES[0]


def retired_spine_files(book: Path) -> list[Path]:
    """還留在已廢除落點的 spine（`_index.md`）。**檔在就要說出來**（A5）。"""
    d = book / "story" / "幕綱"
    return [p for n in RETIRED_SPINE_FILES if (p := d / n).is_file()]


def spine_note(book: Path) -> str:
    """`spine 讀自 X` ——**舊落點還在時要說出來**（功能 14 V9；階段 1c 改墓碑）。"""
    p = spine_path(book)
    if p.is_file():
        return f"spine 讀自 `{p.name}`"
    retired = retired_spine_files(book)
    if retired:
        return (
            f"spine **找不到**（新落點 `{SPINE_FILES[0]}` 不在）；"
            f"偵測到舊落點 `{retired[0].name}`——**2026-07-30 起不再讀它**，"
            f"`git mv` 那一行過去即可"
        )
    return "spine **找不到**"


def parse_spine(text: str) -> dict[str, int]:
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
    raise FoldError("幕綱順序檔找不到可解析的『全書順序：』arc 序列")


@dataclass(frozen=True)
class Slot:
    entity: str
    token: str
    kind: str
    name: str
    content: str
    source_beat: int | None  # None＝無單一釘下點（約束表寫「生效自：全書」）
    source_arc: str
    origin: str = ""  # 這條事實由哪支檔釘下（ch0009／物件/同伴.md）
    # 集合維度（知識前沿／持有／能力）折出來的成員 [(名, 態)]；態為空＝無態維度。
    # 留著結構而不只留 content，是為了讓上層還能再篩一層（見 cli 的命題層選取）。
    items: tuple[tuple[str, str], ...] = field(default=())

    @property
    def released(self) -> bool:
        return self.content.startswith(RELEASE_PREFIX)

    @property
    def source_label(self) -> str:
        """人眼可讀的來源位置。約束可以「全書生效」，那時沒有幕號可印。"""
        if self.source_beat is None:
            return self.source_arc or "全書"
        return f"幕{self.source_beat:03d}（{self.source_arc}）"


def _pos(spine: dict[str, int], arc: str, beat: int) -> tuple[int, int]:
    if arc not in spine:
        raise FoldError(f"arc {arc!r} 不在 spine（全書順序）中，無法定位")
    return (spine[arc], beat)


def project(
    events: list[Event],
    spine: dict[str, int],
    target_beat: int,
    target_arc: str,
    kinds: tuple[str, ...] | None = None,
    active_only: bool = False,
    set_dims: frozenset[str] = frozenset(),
) -> list[Slot]:
    """as-of 投影。slot key ＝(實體, token)。

    兩種折法，依維度分（見 `ops.py`）：

    - **集合維度**（`set_dims`，即 `知識前沿`／`持有`／`能力`）：內容欄是操作串，
      逐筆套上去。這是「每筆 delta 只寫這一幕改變了什麼」得以成立的機制。
    - **純量維度**（其餘）與錨：序最新勝，逐字沿用原語意。

    `set_dims` 預設空＝全部走覆蓋。**2026-07-30 起它套在每一行上**——舊單檔
    事實流的讀取路徑移除之後，「這一行折不成集合」這個豁免沒有生產者了。

    kinds=None 代表全開。active_only 剔除內容以「（解除）」起頭的 slot
    ——舊格式約束的退場靠顯式解除，見 結構定義/事實流.schema.md。
    """
    target = _pos(spine, target_arc, target_beat)
    # 對每個事件都定位（含被過濾的），arc 無法定位即報錯、不靜默丟。
    positioned = [(_pos(spine, e.arc, e.beat), e) for e in events]
    kept = sorted(
        ((p, e) for p, e in positioned if p <= target),
        key=lambda pe: (pe[0], pe[1].order),  # 同位置以收集序後者勝（跨檔穩定）
    )
    slots: dict[tuple[str, str], Slot] = {}
    accum: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for _p, e in kept:
        key = (e.entity, e.token)
        content, items = e.content, ()
        if e.kind == KIND_STATE and e.name in set_dims:
            where = f"{e.origin} 第 {e.lineno} 行" if e.origin else f"第 {e.lineno} 行"
            try:
                merged = apply_ops(accum.get(key, []), parse_ops(e.content, e.name))
            except OpError as err:
                raise FoldError(f"{where}{err}") from None
            accum[key] = merged
            content, items = render(merged, e.name), tuple(merged)
        slots[key] = Slot(
            entity=e.entity,
            token=e.token,
            kind=e.kind,
            name=e.name,
            content=content,
            source_beat=e.beat,
            source_arc=e.arc,
            origin=e.origin,
            items=items,
        )
    out = list(slots.values())
    if kinds is not None:
        out = [s for s in out if s.kind in kinds]
    if active_only:
        out = [s for s in out if not s.released]
    return out
