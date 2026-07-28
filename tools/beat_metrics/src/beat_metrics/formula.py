"""結構公式 registry：`技巧知識庫/結構公式.md` 的「公式 → 必要階段」對映。

**為什麼這支存在**（2026-07-28 功能 11）：`outline-test/SKILL.md` 測試4 十天來逐字
寫著「抽取對應表階段名，與 `結構公式.md` 該公式的**必要階段清單**做**集合差**（機械）」
——而那份清單一直只寫在 `**【起】**` 這種粗體 bullet 與散文裡，六套公式**六種形狀**，
**沒有 registry**。那個「機械」從來沒有跑過（`設計原則.md` C3：每一種 ID 都要有一份
registry，抽取器只能命中既有 ID）。

**registry 與它的真相同居一檔，所以結構上不可能漂移**——這是作者拍板抉擇 4 B 的理由，
也是「一份會漂移而無人維護的機讀資料」這個形狀**第五次提案而第一次被接受**的原因：
前四次（05 世界觀主題別名表／06 幕綱集合名對照表／07 禁用語域欄／10 機械就緒規則）都是
**另開一份**會與真相分家的資料，而且**隨書成長**；這一份是封閉的（系統自己定義的六套＋
一套巢狀子公式）、**不隨任何一本書成長**，而且就寫在那六節旁邊。

**射程寫死**（`結構公式.md` 檔頭那段 blockquote）：只准這一種註記、只准出現在那一支檔，
`技巧知識庫/` 其餘部分維持零 schema。要加第八套公式就加一行。

**兩個消費者**：`outline-lint` 第 12 項（大綱宣告的公式名要命中 registry）與
`structure-project`（集合差與錯序）。**唯一真相在本模組**，兩邊 import，不各抄一份。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .scan import read_text

KNOWLEDGE_DIR = "技巧知識庫"
SCHEMA_DIR = "結構定義"
FORMULA_FILE = "結構公式.md"

# `<!-- 結構公式: 起承轉合 | 必要階段: 起,承,轉,合 -->`
# 半形逗號分隔；`—`（或三種破折號之一）＝流程型公式、不對映幕。
_ANNOTATION_RE = re.compile(
    r"^<!--\s*結構公式\s*[:：]\s*(?P<name>.+?)\s*\|\s*必要階段\s*[:：]\s*(?P<stages>.+?)\s*-->\s*$"
)
_H2_RE = re.compile(r"^##\s+")
_DASHES = frozenset("—–-－")


@dataclass(frozen=True)
class Formula:
    """一套公式。`stages` 為空 tuple ＝流程型（`必要階段: —`），不做集合差。"""

    name: str
    stages: tuple[str, ...]
    lineno: int

    @property
    def is_staged(self) -> bool:
        return bool(self.stages)


@dataclass
class Registry:
    """`結構公式.md` 讀出來的 registry。**讀不到不是 0 套，是「未接」**——兩者分開，
    混在一起就是新的假陰性（`設計原則.md` E2：只印「我發現幾個問題」的守衛，
    在它自己被關掉時會印「乾淨」）。
    """

    path: Path | None = None
    formulas: dict[str, Formula] = field(default_factory=dict)
    sections: int = 0  # `結構公式.md` 的 `##` 節數
    annotated_sections: int = 0  # 其中帶註記的節數
    problems: list[str] = field(default_factory=list)

    @property
    def connected(self) -> bool:
        return self.path is not None

    def match(self, text: str) -> list[Formula]:
        """一段文字裡宣告了哪幾套公式（**字面比對 registry 名稱，不做語意分類**）。

        依名稱長度由長到短比對，避免短名字吃掉長名字；回傳依在文中首次出現的位置排序，
        **第一個是主公式**（下游的集合差用它，其餘印成巢狀／並用）。
        """
        hits: list[tuple[int, Formula]] = []
        taken: list[tuple[int, int]] = []
        for f in sorted(self.formulas.values(), key=lambda f: -len(f.name)):
            pos = text.find(f.name)
            while pos >= 0:
                if not any(a <= pos < b for a, b in taken):
                    taken.append((pos, pos + len(f.name)))
                    hits.append((pos, f))
                    break
                pos = text.find(f.name, pos + 1)
        return [f for _, f in sorted(hits, key=lambda kv: kv[0])]

    @property
    def names(self) -> str:
        return "／".join(sorted(self.formulas))


def package_root(start: Path) -> Path | None:
    """從書資料夾往上找「同時含 `技巧知識庫/` 與 `結構定義/`」的目錄。

    這正是 `共同約定.md` 一「資源定位」對 skill 下的規則，工具用同一條——**不寫死
    絕對路徑、也不假設書一定是套件根的直接子目錄**。
    """
    here = start.resolve()
    for d in (here, *here.parents):
        if (d / KNOWLEDGE_DIR).is_dir() and (d / SCHEMA_DIR).is_dir():
            return d
    return None


def load(book: Path) -> Registry:
    """讀 registry。找不到套件根或那支檔 → `connected` 為 False（印「未接」，不猜）。"""
    root = package_root(book)
    if root is None:
        return Registry()
    p = root / KNOWLEDGE_DIR / FORMULA_FILE
    if not p.is_file():
        return Registry()
    reg = Registry(path=p)
    annotated: set[int] = set()
    current: int | None = None
    for i, raw in enumerate(read_text(p).splitlines(), start=1):
        if _H2_RE.match(raw):
            reg.sections += 1
            current = reg.sections
            continue
        m = _ANNOTATION_RE.match(raw.strip())
        if not m:
            continue
        if current is not None:
            annotated.add(current)
        name = m.group("name").strip()
        raw_stages = m.group("stages").strip()
        if not name:
            reg.problems.append(f"{FORMULA_FILE}:{i}：註記的公式名是空的")
            continue
        if name in reg.formulas:
            reg.problems.append(
                f"{FORMULA_FILE}:{i}：公式名「{name}」重複"
                f"（前一筆在第 {reg.formulas[name].lineno} 行）"
                "——名稱是下游大綱要照抄的字串，重複等於同一套公式有兩個答案"
            )
            continue
        if raw_stages and all(c in _DASHES for c in raw_stages):
            stages: tuple[str, ...] = ()
        else:
            stages = tuple(s.strip() for s in raw_stages.split(",") if s.strip())
            if not stages:
                reg.problems.append(
                    f"{FORMULA_FILE}:{i}：公式「{name}」的必要階段清單是空的"
                    "——流程型公式寫 `必要階段: —`，別留白"
                )
                continue
        reg.formulas[name] = Formula(name=name, stages=stages, lineno=i)
    reg.annotated_sections = len(annotated)
    if reg.connected and not reg.formulas and not reg.problems:
        reg.problems.append(
            f"{FORMULA_FILE}：一行 `<!-- 結構公式: … | 必要階段: … -->` 都沒有"
            "——registry 是空的，集合差算不了，而輸出會看起來完全正常"
        )
    return reg


def leading_stage(value: str, stages: tuple[str, ...]) -> str | None:
    """幕綱 `結構階段` 欄的值 → 頂層階段 token。**位置判準：必須在值的開頭。**

    `起·失衡開場（…）` → `起`；`平凡失衡` → `平凡失衡`；
    `（輪回世界任務）破·瀕死低點…` → `None`（只寫巢狀子公式的階段，**沒有頂層 token**）。

    **不猜**：認不出來就回 None，由覆蓋率行印「N 幕的欄不以頂層階段 token 起頭」。
    這與 `style-lint` 第 4 項的顆粒度 token、`char-lint` 第 8 項的括號外 token 同一種
    判準——**不得改成語意判準**（那是 `prose-metrics` 關鍵詞分類／世界觀主題別名表／
    幕綱集合名對照表三次被駁回的形狀）。

    > 巢狀公式怎麼寫進這一欄，`幕綱.schema.md` 至今沒有定義（實測某本書 3/108 幕因此
    > 機械不可判）→ 已記進功能 02 的已知疑點。本函式只誠實地數，不替它發明格式。
    """
    v = value.strip().lstrip("*＊ ")
    for s in sorted(stages, key=len, reverse=True):
        if v.startswith(s):
            return s
    return None
