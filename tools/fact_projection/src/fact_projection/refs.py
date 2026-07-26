"""反向索引：**誰依賴了這條事實**。

事實軸原本只有正向（事實 → 下游）。拆軸（2026-07-26）修好了「ledger 對不上正文」
那一半——改了 ch0009 的正文，`derived-sync check` 報 `ch0009.ai.md` stale，重生即
修正。但反向那一半沒人管：

    作者把 ch0009 的錨從「青銅牌」改成「銀牌」
      → ch0009 的 delta 修好了 ✅
      → ch0040–ch0055 的正文裡還寫著「青銅牌」 ❌
         （ch0040.md 沒動、hash 沒變，derived-sync 完全沉默）

而正文的矛盾比 ledger 的矛盾嚴重——那是讀者會看到的。

兩種查法，對應兩種依賴：

- `--entity`：掃各章 `## 本章事實` 的**實體欄**。實體是信封的結構化欄位，不必猜
  字串，所以這一路是精確的。
- `--anchor`：錨天生是「數字／專名／道具語彙」＝**可 grep 的字面串**，所以能直接
  去正文裡找。這一路是啟發式的——輸出是**候選清單交 LLM 複判**，不是判決。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .fold import Event

# 把錨的內容切成可 grep 的字面片段：標點是天然邊界，括號註解整段丟掉
# （那是說明，不是會出現在正文裡的字面）。
_PAREN_RE = re.compile(r"（[^（）]*）")
_PUNCT_RE = re.compile(r"[、，。；：！？「」『』（）()\[\]，,.;:!?\s／/·]+")
MIN_TERM_CHARS = 2


@dataclass(frozen=True)
class EntityRef:
    origin: str  # ch0040
    beat: int
    arc: str
    token: str
    content: str


@dataclass(frozen=True)
class AnchorHit:
    term: str  # 從錨的值切出來的字面片段
    chapter: str  # ch0040
    count: int


def entity_refs(
    events: list[Event],
    entity: str,
    spine: dict[str, int],
    after: tuple[int, int] | None = None,
) -> list[EntityRef]:
    """哪些章的 delta 提到這個實體。`after` ＝ `(arc 排名, 幕號)`，只回它之後的。"""
    out: list[EntityRef] = []
    for e in events:
        if entity not in e.entity:  # 關係型 `A↔B` 也要命中
            continue
        if e.arc not in spine:
            continue
        if after is not None and (spine[e.arc], e.beat) <= after:
            continue
        out.append(
            EntityRef(
                origin=e.origin, beat=e.beat, arc=e.arc, token=e.token, content=e.content
            )
        )
    out.sort(key=lambda r: (spine[r.arc], r.beat))
    return out


def literal_terms(content: str) -> list[str]:
    """把錨的值切成可 grep 的字面片段。"""
    stripped = _PAREN_RE.sub("", content)
    terms = [t.strip() for t in _PUNCT_RE.split(stripped)]
    seen: list[str] = []
    for t in terms:
        if len(t) >= MIN_TERM_CHARS and t not in seen:
            seen.append(t)
    return seen


def _prose(book: Path) -> list[tuple[str, str]]:
    chapters = book / "chapters"
    if not chapters.is_dir():
        return []
    return [
        (p.stem, p.read_text(encoding="utf-8-sig"))
        for p in sorted(chapters.glob("ch*.md"))
        if not p.name.endswith(".ai.md")  # 正文源才算依賴，衍生檔走 --entity
    ]


def _longest_hit(segment: str, text: str) -> str | None:
    """這一章裡找得到的**最長**寫法。

    錨的值常帶修飾（「缺一角的青銅牌」），但下游正文多半只寫中心語（「青銅牌」）
    ——中文複合名詞把中心語擺在最後，所以由長到短試後綴、取第一個有命中的。
    由長到短是刻意的：先試「青銅牌」再試「銅牌」，避免回報一個過寬的詞。

    **逐章各判一次**（不是全書挑一個最長的）：ch0001 逐字寫著全稱、ch0040 只寫
    中心語是常態，全書挑一個會讓 ch0040 整章消失——而那正是要找的東西。
    """
    for size in range(len(segment), MIN_TERM_CHARS - 1, -1):
        cand = segment[len(segment) - size :]
        if cand in text:
            return cand
    return None


def anchor_hits(book: Path, values: list[str]) -> list[AnchorHit]:
    """拿錨的（新舊）值去 grep 全書正文，回傳命中的章與次數。

    只回**有命中**的片段——沒命中的片段是切壞的，報出來只是雜訊。
    """
    segments: list[str] = []
    for v in values:
        for seg in literal_terms(v):
            if seg not in segments:
                segments.append(seg)
    out: list[AnchorHit] = []
    for name, text in _prose(book):
        seen: set[str] = set()
        for seg in segments:
            t = _longest_hit(seg, text)
            # 同一章裡「巴掌大」與「缺一角的青銅牌」可能各自命中，但兩個片段
            # 退化成同一個詞時只報一次
            if t and t not in seen:
                seen.add(t)
                out.append(AnchorHit(term=t, chapter=name, count=text.count(t)))
    return out
