"""章衍生檔的 front-matter：`對應幕` 區間與 `所屬arc`。

**這支模組補的是一條掉在分工縫裡的承諾。** `章節.schema.md` 明文要求「事實行的幕號
須落在本檔 `對應幕` 區間內、arc 須與 `所屬arc` 相符」，但：

- `fact-lint` 只讀事實行，不讀 front-matter；
- `derived-sync validate` 只讀 front-matter，不讀事實行。

兩支工具各有一半，於是**沒有人在守它**（實測 `grep 對應幕 tools/**/*.py` 只命中測試
與 `prose_metrics`）。壞掉的後果不會炸：一筆事實掛在錯的章上，投影照樣吐出來、`write`
照樣遵守它，只是它的「來源」欄指著一支跟它無關的章——等到有人回頭查來源才發現。

規則歸屬在 `fact-lint` 這一側是刻意的：**它是事實行的性質**（這一行的位置欄對不對），
front-matter 只是用來比對的尺。`validate` 那邊仍然只管 `.ai.md` 的結構。

順帶產出「哪些幕已經寫成正文了」——約束的到期提醒（`解除於` 指向的幕已寫成 →
提示作者確認）要用它。那是 E2 第六個永久盲點目前唯一的補償機制。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

AI_SUFFIX = ".ai.md"
_ENCODING = "utf-8-sig"
_FM_FENCE = "---"

KEY_BEATS = "對應幕"
KEY_ARC = "所屬arc"

# `對應幕: [幕001, 幕004]`（schema 形）與 `幕001–幕004`（`_index` 表裡的寫法）都吃。
# 這一欄是機讀的，但它終究是人會看、偶爾會手改的一行——破折號的形狀不該決定成敗。
_BEAT = r"幕?(\d+)"
_RANGE_RE = re.compile(
    rf"^\[?\s*{_BEAT}\s*(?:[,，]|[-–—~～至]|\.\.)\s*{_BEAT}\s*\]?$"
)
_SINGLE_RE = re.compile(rf"^\[?\s*{_BEAT}\s*\]?$")


@dataclass(frozen=True)
class ChapterMeta:
    stem: str  # ch0009
    first_beat: int | None
    last_beat: int | None
    arc: str
    problems: tuple[str, ...] = ()

    @property
    def has_frontmatter(self) -> bool:
        return self.first_beat is not None or bool(self.arc)

    def covers(self, beat: int) -> bool:
        if self.first_beat is None or self.last_beat is None:
            return False
        return self.first_beat <= beat <= self.last_beat


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != _FM_FENCE:
        return {}
    out: dict[str, str] = {}
    for raw in lines[1:]:
        if raw.strip() == _FM_FENCE:
            break
        key, sep, value = raw.partition(":")
        if sep:
            out[key.strip()] = value.split("#", 1)[0].strip()
    return out


def parse_chapter_meta(stem: str, text: str) -> ChapterMeta:
    fm = _frontmatter(text)
    arc = fm.get(KEY_ARC, "").strip().strip("[]").strip()
    raw = fm.get(KEY_BEATS, "").strip()
    problems: list[str] = []
    first = last = None
    if raw:
        m = _RANGE_RE.match(raw)
        if m:
            first, last = int(m.group(1)), int(m.group(2))
            if first > last:
                problems.append(
                    f"{stem}{AI_SUFFIX} 的 `{KEY_BEATS}` 起訖顛倒：{raw!r}"
                )
                first, last = last, first
        else:
            s = _SINGLE_RE.match(raw)
            if s:
                first = last = int(s.group(1))
            else:
                problems.append(
                    f"{stem}{AI_SUFFIX} 的 `{KEY_BEATS}` 解析不了：{raw!r}"
                    "（應為 `[幕001, 幕004]`；單一幕寫 `[幕001, 幕001]`）"
                )
    return ChapterMeta(
        stem=stem,
        first_beat=first,
        last_beat=last,
        arc=arc,
        problems=tuple(problems),
    )


def load_chapter_meta(book: Path) -> dict[str, ChapterMeta]:
    """讀全書章衍生檔的 front-matter。`stem` → meta。"""
    out: dict[str, ChapterMeta] = {}
    d = book / "chapters"
    if not d.is_dir():
        return out
    for p in sorted(d.glob(f"ch*{AI_SUFFIX}")):
        stem = p.name[: -len(AI_SUFFIX)]
        out[stem] = parse_chapter_meta(stem, p.read_text(encoding=_ENCODING))
    return out


def check_chapter_scope(
    metas: dict[str, ChapterMeta], events: list
) -> tuple[list[str], int]:
    """事實行的幕號 ∈ 該章 `對應幕`、arc ＝ `所屬arc`。回 (問題, 核對過的章數)。

    **完全沒有 front-matter 的章直接略過**——那是「還沒封章」，`derived-sync check`
    已經報成 `unstamped`，這裡重複報是雜訊（分工：`check` 問產出了沒，本支問形狀對不對）。
    **但有事實行卻缺這兩欄就要報**：那時候沒有任何東西能核對這些事實掛對了沒。
    """
    problems: list[str] = []
    checked: set[str] = set()
    for e in events:
        if e.legacy or not e.origin:
            continue  # 舊格式單檔沒有「所屬章」這回事
        stem = e.origin.split("〔")[0]  # 去掉 ORPHAN_MARK
        meta = metas.get(stem)
        if meta is None or not meta.has_frontmatter:
            continue
        checked.add(stem)
        where = f"{e.origin} 第 {e.lineno} 行"
        if meta.first_beat is None:
            problems.append(
                f"{where}有事實行，但 {stem}{AI_SUFFIX} 的 front-matter 沒有"
                f"可解析的 `{KEY_BEATS}`——少了它，沒有任何東西能核對這些事實"
                "掛對了章沒有"
            )
        elif not meta.covers(e.beat):
            problems.append(
                f"{where}的幕{e.beat:03d} 不在本章 `{KEY_BEATS}` 區間"
                f"（幕{meta.first_beat:03d}–幕{meta.last_beat:03d}）內"
                "——要嘛這筆事實掛錯章，要嘛正文的幕錨點變了而 front-matter 沒重生"
            )
        if not meta.arc:
            problems.append(
                f"{where}有事實行，但 {stem}{AI_SUFFIX} 缺 `{KEY_ARC}`"
            )
        elif e.arc != meta.arc:
            problems.append(
                f"{where}的 arc 寫 {e.arc}，但本章 `{KEY_ARC}` 是 {meta.arc}"
            )
    for meta in metas.values():
        problems += list(meta.problems)
    return problems, len(checked)


def written_beats(metas: dict[str, ChapterMeta], arc: str) -> list[tuple[int, int, str]]:
    """某個 arc 已寫成正文的幕區間 [(起, 訖, 章)]。"""
    return [
        (m.first_beat, m.last_beat, m.stem)
        for m in metas.values()
        if m.arc == arc and m.first_beat is not None and m.last_beat is not None
    ]


def covering_chapter(metas: dict[str, ChapterMeta], arc: str, beat: int) -> str | None:
    """哪一章寫了這一幕？沒有就 None（那一幕還沒寫成正文）。"""
    for first, last, stem in sorted(written_beats(metas, arc)):
        if first <= beat <= last:
            return stem
    return None
