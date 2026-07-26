"""集合維度的內容欄語法（`知識前沿`／`持有`／`能力`）。

**為什麼要結構化。** slot 覆蓋語意要求「最新一筆要能獨立代表當下狀態」，於是每
寫一筆新事實，LLM 都得把仍然成立的舊事重述一遍——它在行內手動做 replay。實測
一世之尊（93 章）：事件**筆數**每 arc 都是 15–36 沒有成長，**單行長度**卻從
arc01 的 186 字脹到 arc11 的 709 字（最長 1,728），而「孟奇·知識前沿」這一個
slot 的 98 筆歷史合計 50,714 字。外推 500 章＝投影 19 萬字元，塞不進 context。

把內容欄從散文換成集合運算之後，每一筆只寫**這一幕改變了什麼**，行長被結構限死；
「當下狀態」由 fold 算出來，不必任何人重抄。

六維裡只有這三維是集合：

- `知識前沿` ＝ 一組命題，每個命題有 `已知`／`尚不知` 兩態，會互相轉換。
- `持有`／`能力` ＝ 單純的集合，只有加入與離開。
- `位置`／`所屬`／`關係` 維持**覆蓋**——它們本來就是純量（一個人只在一個地方），
  實測成長也最小（位置 55→135 字，是三維裡最輕的）。

**命題名共用伏筆命名空間**（僅 `知識前沿`）：`知識前沿` 的命題本來就是「玉佛來歷」
「原身身世」這類東西，而它們在幕綱的 `埋/收[[伏筆:X]]` 已經登記過了。沿用同一套
名字＝不另立第二本帳，且「這條何時揭」自動接上幕綱的收點。驗證在 `sources.lint`。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

KNOWN = "已知"
UNKNOWN = "尚不知"
STATES = (KNOWN, UNKNOWN)

# 有態的集合維度（命題有已知／尚不知兩態）vs 無態的（只有進出）
STATEFUL_DIMENSIONS = frozenset({"知識前沿"})
PLAIN_SET_DIMENSIONS = frozenset({"持有", "能力"})
SET_DIMENSIONS = STATEFUL_DIMENSIONS | PLAIN_SET_DIMENSIONS

# 操作之間的分隔。內容欄的其餘部分必須被操作完全覆蓋，否則報錯——這是
# 「delta 只寫這一幕改變了什麼」這條紀律唯一在守的東西。
_SEPARATORS = "、,，;；　 \t"

_OP_RE = re.compile(
    r"(?P<sign>[+＋]|[−\-－])?"
    r"(?P<state>已知|尚不知)?"
    r"〔(?P<name>[^〔〕]+)〕"
    r"(?:\s*(?:→|->|=>)\s*(?P<to>已知|尚不知))?"
    r"(?:（(?P<note>[^（）]*)）)?"
)

_PLUS = "+＋"


class OpError(ValueError):
    """內容欄不是合法的集合運算。"""


@dataclass(frozen=True)
class Op:
    action: str  # set / drop
    name: str
    state: str = ""  # set 到哪一態（無態維度為空）
    note: str = ""


def parse_ops(content: str, dimension: str) -> list[Op]:
    """把內容欄解析成操作串；解析不了就 raise（不靜默當成散文吞掉）。"""
    stateful = dimension in STATEFUL_DIMENSIONS
    ops: list[Op] = []
    covered = 0
    for m in _OP_RE.finditer(content):
        gap = content[covered : m.start()]
        if gap.strip(_SEPARATORS):
            raise OpError(f"操作之間夾了非操作文字 {gap.strip()!r}")
        covered = m.end()
        ops.append(_build_op(m, dimension, stateful))
    if not ops:
        # 一個操作都認不出來＝這一欄還是散文。先報這句，它比「結尾有非操作文字」
        # 更能說清楚該怎麼改。
        raise OpError(
            f"`{dimension}` 的內容欄須為集合運算"
            f"（{'＋已知〔X〕／＋尚不知〔X〕／〔X〕→已知／−〔X〕' if stateful else '＋〔X〕／−〔X〕'}）"
            f"，得到自由文字：{content[:40]!r}"
        )
    tail = content[covered:]
    if tail.strip(_SEPARATORS):
        raise OpError(f"結尾有非操作文字 {tail.strip()!r}")
    return ops


def _build_op(m: re.Match[str], dimension: str, stateful: bool) -> Op:
    sign, state, name = m.group("sign"), m.group("state"), m.group("name")
    to, note = m.group("to"), m.group("note") or ""
    name = name.strip()

    if sign and sign not in _PLUS:  # 減號＝離開集合
        if state or to:
            raise OpError(f"−〔{name}〕不得再帶狀態")
        return Op(action="drop", name=name, note=note)

    if not stateful:
        if state or to:
            raise OpError(f"`{dimension}` 沒有已知／尚不知兩態，〔{name}〕不得帶狀態")
        if not sign:
            raise OpError(f"〔{name}〕缺少 ＋／− ——說不出這一幕是得到還是失去")
        return Op(action="set", name=name, note=note)

    if to:  # 〔X〕→已知：轉態
        if sign or state:
            raise OpError(f"轉態寫成〔{name}〕→{to} 即可，別再加 ＋ 或前置狀態")
        return Op(action="set", name=name, state=to, note=note)
    if sign and state:  # ＋已知〔X〕：新增命題
        return Op(action="set", name=name, state=state, note=note)
    raise OpError(
        f"〔{name}〕語法不完整——新增寫 ＋已知〔{name}〕／＋尚不知〔{name}〕，"
        f"轉態寫〔{name}〕→已知，移除寫 −〔{name}〕"
    )


def apply_ops(
    current: list[tuple[str, str]], ops: list[Op]
) -> list[tuple[str, str]]:
    """把操作套到當下集合上，回傳新集合（[(名, 態)]，態為空＝無態維度）。

    保持插入序：先出現的命題排前面，讀起來就是這個角色知識邊界的長出順序。
    """
    out = list(current)
    index = {name: i for i, (name, _) in enumerate(out)}
    for op in ops:
        if op.action == "drop":
            if op.name in index:
                out = [(n, s) for n, s in out if n != op.name]
                index = {name: i for i, (name, _) in enumerate(out)}
            continue
        if op.name in index:
            out[index[op.name]] = (op.name, op.state)
        else:
            index[op.name] = len(out)
            out.append((op.name, op.state))
    return out


def render(items: list[tuple[str, str]], dimension: str) -> str:
    """把折好的集合印成人／LLM 都讀得懂的一行。"""
    if not items:
        return "（空）"
    if dimension not in STATEFUL_DIMENSIONS:
        return "、".join(f"〔{n}〕" for n, _ in items)
    parts = []
    for state in STATES:
        names = [f"〔{n}〕" for n, s in items if s == state]
        if names:
            parts.append(f"{state}：{'、'.join(names)}")
    return "｜".join(parts)
