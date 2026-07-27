"""章密度對照（`章節.schema.md`「章密度規範」的核對者）。

**為什麼有這一節。** `章節.schema.md` 宣告「中文網文向預設一章約 3000 字（起點體例）」，
而**沒有任何一層對它負責**：唯一在守章長的是 `drift.py`，判準是「相對本書前段」——
一世之尊前段基準 2,616 字/章本身就低於宣告，所以**絕對缺口在結構上測不到**
（實測 13/93 章達 3000、40/93 < 2000）。`共同約定.md` 九說一條書級宣告要成立必須
連帶寫出「單位／達標線／誰核對」，這一條有前兩者、只缺第三者。本模組補上第三者。

**它印的是一個數字，不是一個判定**（作者拍板抉擇 3 B）：不設門檻、不進 `findings`、
不影響 exit code。理由是這條踩在已駁回清單的邊上——「幫基調加一個機讀欄」被駁回的
理由是「任何門檻都會過度回報」，而章長與基調的差別在於**它直接可數**，所以補一個
可覆算的比例是安全的，補一條達標線不是。

**刻意不判「這本書偏不偏網文」**：那需要拿詞表分類中文形容詞（`偏快爽`／`明快`／
`爽利`…），正是上面那條駁回的形狀。改成**原文照抄宣告**擺在數字旁邊，讓作者自己對。
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from pathlib import Path

from .metrics import Metrics

# `章節.schema.md`「章密度規範」的起點體例。**這是參考體例，不是達標線。**
WEB_NOVEL_CHARS = 3000

_STANCE_RE = re.compile(r"^取向定位:\s*(.+)$", re.MULTILINE)
# 只挑兩個子欄印：`節奏速度` 是 schema 那條宣告直接掛的軸，`整體` 是它的上下文。
_SUB_KEYS = ("節奏速度", "整體")


@dataclass(frozen=True)
class Density:
    chapters: int
    hits: int
    median: float
    mean: float
    stance: dict[str, str]
    declared: bool

    @property
    def share(self) -> float:
        return self.hits / self.chapters if self.chapters else 0.0


def read_stance(book: Path) -> tuple[bool, dict[str, str]]:
    """`story/00-摘要.ai.md` front-matter 的 `取向定位` → (有沒有宣告, 子欄)。

    **讀不到就說讀不到**（`設計原則.md` E2：0 也要印）。一個靜默跳過的對照節，
    與「這本書沒有這個問題」在輸出上無法區分。
    """
    p = book / "story" / "00-摘要.ai.md"
    if not p.is_file():
        return False, {}
    m = _STANCE_RE.search(p.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return False, {}
    raw = m.group(1).strip().strip("{}").strip()
    out: dict[str, str] = {}
    for key in _SUB_KEYS:
        sub = re.search(rf"{key}\s*[:：]\s*([^,，}}]+)", raw)
        if sub:
            out[key] = sub.group(1).strip()
    return True, out


def measure(rows: list[Metrics], book: Path) -> Density:
    declared, stance = read_stance(book)
    chars = [m.chars for m in rows]
    return Density(
        chapters=len(rows),
        hits=sum(1 for c in chars if c >= WEB_NOVEL_CHARS),
        median=statistics.median(chars) if chars else 0.0,
        mean=statistics.mean(chars) if chars else 0.0,
        stance=stance,
        declared=declared,
    )


def render(d: Density) -> list[str]:
    lines = ["### 章密度（參考體例，非判定）", ""]
    if d.declared and d.stance:
        lines.append(
            "宣告 "
            + "　".join(f"取向定位.{k}：{v}" for k, v in d.stance.items())
        )
    elif d.declared:
        lines.append("宣告 取向定位：有這一欄，但讀不出 節奏速度／整體 子欄")
    else:
        lines.append(
            "**未宣告取向定位**（`story/00-摘要.ai.md` front-matter 沒有 `取向定位`）"
            "——比例照印，對照基準由作者自己決定"
        )
    if not d.chapters:
        lines.append("0 章正文，無從計數。")
    else:
        lines.append(
            f"{d.hits}/{d.chapters} 章 ≥{WEB_NOVEL_CHARS} 字（{d.share:.0%}；"
            f"中位 {d.median:.0f}，平均 {d.mean:.0f}；去鷹架後的字元數）。"
        )
    lines += [
        "",
        f"> **這是一個數字，不是一個判定。** {WEB_NOVEL_CHARS} 字是網文向（起點體例）的"
        "**參考體例**，`章節.schema.md` 明訂本系統**不設達標線**——章長依張力起伏重分配，"
        "高潮幕該厚、過場幕該薄。章長真正的可疑點判準在上面「漂移可疑點」那一節"
        "（相對本書自己的前段），與本節無關。",
    ]
    return lines
