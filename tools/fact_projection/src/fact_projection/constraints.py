"""約束＝**規則登記表**，不是事件流。

見 `結構定義/事實流.schema.md`。從「怎麼產生／怎麼被用」推：

- **產生**＝離散的拍板事件（低頻，一次一條），由 `character`／`worldbuild`／
  `beat-sheet`／`write-test` 在作者拍板後寫下。
- **使用**＝永遠只問「此刻對某實體有哪些排除線生效」。沒有人查它的歷史——
  歷史查詢（為什麼這樣定）是 `裁決流.co.md` 的工作。
- **一生會變的**只有射程與是否解除，內容幾乎不變。

append log 處理「延長射程」的方式是再 append 一行同名的去覆蓋——舊行從此不再被
讀到卻永遠不會消失（實測一世之尊某條約束一生只調整兩次，卻佔 3 行、2 行是死的）。
而且「拍板點」被綁成「生效點」，**表達不出回溯生效**（作者寫到 arc05 才想立一條
該從 arc01 起生效的排除線）。故改成一條一列、欄位就地編輯的表。

**刻意不設「狀態」欄**：狀態可由「解除於」導出。`裁決流` 那個必須人手動維護的
狀態欄，正是「`射程` 欄程式從未讀、所謂『不必有人負責刪』不成立」的失效來源
（見 `裁決流.schema.md`）；同一個坑不踩第二次。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .fold import KIND_CONSTRAINT, FoldError, Slot, strip_html_comments

COLUMNS = ("約束名", "實體", "不得寫成", "生效自", "解除於")

# 生效自寫這個＝從全書開頭就生效（回溯生效的表達方式，不必偽造一個拍板幕號）。
SINCE_ALL = "全書"
# 解除於留白的幾種寫法都吃——這一欄是作者最常手動填的，別讓破折號的形狀決定成敗。
_EMPTY = frozenset({"", "—", "–", "-", "－", "無", "n/a", "N/A"})

_POS_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）$")
_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")


@dataclass(frozen=True)
class Position:
    beat: int
    arc: str

    def __str__(self) -> str:  # pragma: no cover - 純顯示
        return f"幕{self.beat:03d}（{self.arc}）"


@dataclass(frozen=True)
class Constraint:
    name: str
    entity: str
    content: str
    since: Position | None  # None＝全書（自始生效）
    until: Position | None  # None＝尚未解除
    lineno: int

    @property
    def token(self) -> str:
        return f"{KIND_CONSTRAINT}〔{self.name}〕"

    def to_slot(self, origin: str) -> Slot:
        return Slot(
            entity=self.entity,
            token=self.token,
            kind=KIND_CONSTRAINT,
            name=self.name,
            content=self.content,
            source_beat=self.since.beat if self.since else None,
            source_arc=self.since.arc if self.since else SINCE_ALL,
            origin=origin,
        )


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _parse_position(raw: str, where: str, column: str) -> Position | None:
    s = raw.strip()
    if s in _EMPTY:
        return None
    m = _POS_RE.match(s)
    if not m:
        hint = ""
        if any(c in s for c in "()"):
            hint = "（疑似全形／半形誤打：arc 外層須為全形括號 （））"
        raise FoldError(
            f"{where}「{column}」須為『幕NNN（arcAA）』"
            f"{'或『' + SINCE_ALL + '』' if column == '生效自' else '或留白（—）'}"
            f"，得到 {raw!r}{hint}"
        )
    return Position(beat=int(m.group(1)), arc=m.group(2).strip())


def parse_constraints(
    text: str, origin: str = "", errors: list[str] | None = None
) -> list[Constraint]:
    """讀約束表。非表格行（標題、引言、HTML 註解）跳過；壞行報錯、不靜默丟。

    `errors` 為 None（預設）＝ 嚴格模式，遇壞行即 raise——投影走這條，因為投影
    吐出不完整的約束比報錯危險（漏一條排除線＝下游理直氣壯地違反它）。傳入 list
    ＝收集模式，讓 `fact-lint` 能一次報完全部。
    """
    out: list[Constraint] = []
    seen_header = False
    for i, raw in strip_html_comments(text.splitlines()):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        if _SEP_RE.match(line):
            continue
        cells = _cells(line)
        where = f"{origin} 第 {i} 行" if origin else f"第 {i} 行"
        if not seen_header:
            # 第一列表格必須是表頭，用它確認欄序沒被改過
            if tuple(cells) != COLUMNS:
                msg = f"{where}表頭欄位不符：得到 {cells}，應為 {list(COLUMNS)}"
                if errors is None:
                    raise FoldError(msg)
                errors.append(msg)
                return out
            seen_header = True
            continue
        try:
            if len(cells) != len(COLUMNS):
                raise FoldError(
                    f"{where}欄數 {len(cells)}，應為 {len(COLUMNS)}：{raw!r}"
                )
            name, entity, content, since_raw, until_raw = cells
            if not name or not entity:
                raise FoldError(f"{where}「約束名」與「實體」不得留白：{raw!r}")
            if since_raw.strip() == SINCE_ALL:
                since = None  # 全書＝自始生效
            else:
                since = _parse_position(since_raw, where, "生效自")
                if since is None:
                    raise FoldError(
                        f"{where}「生效自」不得留白——要全程生效請寫『{SINCE_ALL}』"
                    )
            until = _parse_position(until_raw, where, "解除於")
        except FoldError as e:
            if errors is None:
                raise
            errors.append(str(e))
            continue
        out.append(
            Constraint(
                name=name,
                entity=entity,
                content=content,
                since=since,
                until=until,
                lineno=i,
            )
        )
    return out


def active_at(
    constraints: list[Constraint],
    spine: dict[str, int],
    target_beat: int,
    target_arc: str,
    origin: str,
    notes: list[str] | None = None,
) -> list[Slot]:
    """篩出在目標幕生效的約束：`生效自 ≤ 目標` 且（未解除 或 `目標 < 解除於`）。

    **arc 不在 spine 時報成資訊、不 raise**（比照 `共同約定.md` 六對 🧊 標記的
    處置：「揭示點還不存在是合法狀態」）。約束天生會領先幕綱——`character` 替
    反派立排除線時，那個 arc 通常還沒排幕；讓它炸掉整份投影是設計不一致。
    """
    if target_arc not in spine:
        raise FoldError(f"arc {target_arc!r} 不在 spine（全書順序）中，無法定位")
    target = (spine[target_arc], target_beat)

    def rank(p: Position, column: str, c: Constraint) -> tuple[int, int] | None:
        if p.arc not in spine:
            if notes is not None:
                notes.append(
                    f"約束〔{c.name}〕的「{column}」指向 {p.arc}，該 arc 尚未排進"
                    f"「全書順序」——視為尚未抵達（非錯誤，見 共同約定.md 六）"
                )
            return None
        return (spine[p.arc], p.beat)

    out: list[Slot] = []
    for c in constraints:
        if c.since is not None:
            since = rank(c.since, "生效自", c)
            if since is None or since > target:
                continue  # 尚未生效（含 arc 未排幕＝尚未抵達）
        if c.until is not None:
            until = rank(c.until, "解除於", c)
            if until is not None and target >= until:
                continue  # 已解除
        out.append(c.to_slot(origin))
    return out
