"""從幕綱導出「這一幕該給哪些 context」——**由程式選，不由 LLM 填**。

現況 `write` 步驟 1.5 是這樣呼叫投影的：

    fact-project --as-of 幕NNN --entities <POV主角＋關鍵配角>
                                          ^^^^^^^^^^^^^^^^^^ LLM 自己填

選取的決定權還在 LLM 手上——那正是「書愈長，context 愈塞不下」時最不該交給
LLM 的一件事。但「這一幕有誰在場」是**確定性資料**，就寫在幕綱每一幕的
`- 角色：` 欄；「這一幕動到哪些伏筆」寫在 `- 伏筆：` 欄。

**幕綱角色欄的解析邏輯，唯一真相在 `tools/settings_select/src/settings_select/
select.py`**（`parse_beats`／`_ROLE_FIELD_RE`／`load_entities`／`_hits`）。工具間零
相依（所有 tools/*/pyproject.toml 皆 dependencies = []），故此處複製最小片段。
沿用它那個關鍵決定：**不解析角色欄的中文文法**（分隔符有 、／· ，還有括號註解與
法號別名），改以「設定層檔名建的詞彙表」對幕綱文字做比對——方向正確（設定檔定義
詞彙），且對標點風格免疫。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ARC_FILE_RE = re.compile(r"^arc[0-9A-Za-z]+$")
_BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)\s*[·・]?\s*(.*)$")
_ROLE_FIELD_RE = re.compile(r"^-\s*角色：\s*(.*)$")
_FORESHADOW_FIELD_RE = re.compile(r"^-\s*伏筆：\s*(.*)$")
# 與 `sources._FORESHADOW_RE` 同一份（擁有者：foreshadow_project/scan.py）
_MARK_RE = re.compile(r"(?:埋|收)\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]")


class BeatLookupError(Exception):
    """幕綱裡找不到這一幕，或設定層缺目錄。"""


@dataclass(frozen=True)
class BeatContext:
    arc: str
    beat: int
    entities: list[str]  # 角色欄命中的設定層實體（保持出現序）
    foreshadows: list[str]  # 伏筆欄提到的伏筆名


def _entity_vocabulary(book: Path) -> list[str]:
    """權威實體名＝設定層檔名／目錄名 **∪ 物件檔名**（源是唯一真實來源）。

    **為什麼一定要含物件檔**：約束住 `story/物件/<實體>.md`，而它的「實體」就是檔名
    （C1）。一個只以物件檔存在的實體（例如作者替某配角立了排除線，但還沒替他寫
    `設定/角色/<名>.md`）若不在詞彙表裡，`--for-beat` 就會把它的約束**靜默篩掉**
    ——實測過這個洞：`同伴` 的排除線整條從投影裡消失，而 `write` 會理直氣壯地違反它。
    漏一條排除線比多給一點 context 嚴重得多。
    """
    names: list[str] = []
    for kind in ("角色", "世界觀"):
        d = book / "story" / "設定" / kind
        if not d.is_dir():
            continue
        for entry in sorted(d.iterdir()):
            if entry.is_dir():
                names.append(entry.name)
            elif (
                entry.suffix == ".md"
                and not entry.name.endswith(".ai.md")
                and not entry.name.startswith("_")
            ):
                names.append(entry.stem)
    objects = book / "story" / "物件"
    if objects.is_dir():
        for entry in sorted(objects.glob("*.md")):
            if not entry.stem.startswith(("_", ".")) and entry.stem not in names:
                names.append(entry.stem)
    return names


def find_beat(book: Path, beat: int) -> BeatContext:
    """在全書幕綱裡定位一幕，回傳它的在場實體與伏筆。"""
    d = book / "story" / "幕綱"
    if not d.is_dir():
        raise BeatLookupError(f"找不到幕綱目錄：{d}")
    vocabulary = _entity_vocabulary(book)
    for p in sorted(d.glob("*.md")):
        if not _ARC_FILE_RE.match(p.stem):
            continue
        role_field = ""
        fore_field = ""
        inside = False
        for raw in p.read_text(encoding="utf-8-sig").splitlines():
            if raw.startswith("##"):
                m = _BEAT_HEAD_RE.match(raw)
                # 非幕小節（承諾區／伏筆狀態表／設計註）同樣結束當前幕，否則檔尾
                # 那張表會被併進最後一幕、把選取結果污染回全讀。
                inside = bool(m) and int(m.group(1)) == beat
                if inside:
                    role_field = fore_field = ""
                continue
            if not inside:
                continue
            rm = _ROLE_FIELD_RE.match(raw.strip())
            if rm and not role_field:
                role_field = rm.group(1).strip()
            fm = _FORESHADOW_FIELD_RE.match(raw.strip())
            if fm and not fore_field:
                fore_field = fm.group(1).strip()
        if role_field or fore_field:
            # 依**在角色欄裡出現的位置**排序，不依詞彙表順序——幕綱慣例是 POV
            # 主角寫在最前面，這個序對下游有意義。
            hits = sorted(
                (n for n in vocabulary if n in role_field), key=role_field.index
            )
            return BeatContext(
                arc=p.stem,
                beat=beat,
                entities=hits,
                foreshadows=list(dict.fromkeys(_MARK_RE.findall(fore_field))),
            )
    raise BeatLookupError(
        f"全書幕綱裡找不到 幕{beat:03d}（找的是 `## 幕{beat:03d}` 小節）"
    )
