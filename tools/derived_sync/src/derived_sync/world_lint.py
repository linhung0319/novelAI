"""世界觀軸的格式閘門（`world-lint`）。

**為什麼它存在**（2026-07-27 功能 05 重構輪）：`世界觀.schema.md` 曾宣告六個
front-matter 欄，其中五個（`影響力`／`主從`／`維度`／`升格哨兵`／`伏筆`）寫成
機讀格式——而 `tools/` 底下**零解析器、零 lint**，`validate.py` 的 `REQUIRED_KEYS`
只有 `generated-from`／`generated-at` 兩個。`升格哨兵` 甚至在 schema 裡寫著
「供 beat-test/sync 盯」，而那兩支 skill 全文零次提及它。

實測後果是三處漂移，全部「壞了永遠不會發現」：
  - `升格哨兵: false` 的兩個主題，在 `_總覽` 的升格哨兵彙總裡有 6 條共 3,742 字元
  - `維度` 四支的聯集無人宣告「時間」，而 `_總覽` 的「時間」列有內容
  - `伏筆` 8 個宣告名裡 2 個在幕綱查無（`beat-lint` 比對的是物件檔，不是這裡）

依 `設計原則.md` **A4**「一支檔若被逐欄解析，就去找它的 lint；找不到，那支檔現在
不配被解析」，作者拍板抉擇 1 **C**：四個零消費者的欄**刪掉**（內容降級成
`## 影響力` 節的散文），`主題` 留（機械），`伏筆` 留但**與 01／02 的 registry 歸一**
——它不是第三份名冊，是對既有 ID 的引用。本模組就是那個「留下來的部分」的閘門，
以及「刪掉的部分真的刪了」的閘門（第 2 項）。

**與 `validate` 的分工**：`validate` 管所有 `.ai.md` 共通的結構（front-matter 必填
鍵、`##` 節枚舉、裁決 blockquote）；本模組管**世界觀專屬**的欄語意與 rollup 視圖
一致性。兩者同套件、共用 `_split_frontmatter` 與 `SETTINGS_KINDS`——世界觀 `.ai.md`
的格式真相只有一份（先例：`object-lint` 是 `fact-lint` 的聚焦入口、`ch-lint` 與
`beat-lint` 同套件共用一份幕號 registry）。

**已知的複製**：第 3 項要的 `埋|收[[伏筆:x]]` regex 與掃幕綱、第 4 項的
「rollup 視圖 ≡ 各檔 front-matter」形狀，在 `beat_metrics`／`fact_projection` 各有
一份。工具間零相依（所有 `tools/*/pyproject.toml` 皆 `dependencies = []`），故複製
而非 import——**這是第 8 份同類複製**（spine 4、伏筆 regex 3、目的地存在性 2），
該不該收斂交功能 14。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .core import AI_SUFFIX, lede
from .md import FORESHADOW_RE, front_matter_of, section_body, split_frontmatter, table_rows

# 2026-07-27（功能 05）**刪掉的四個宣告欄**＋01 已搬走的 `🧊水下`。
# 留著它們不是「舊格式還能用」——是「schema 已經不宣稱它們機讀，而檔裡還寫著
# 一個看起來機讀的值」，那正是漂移的形狀。既有書會被報，那是預期的（病例書不遷移）。
RETIRED_KEYS = ("影響力", "主從", "維度", "升格哨兵", "🧊水下")

# 留下來的欄。`主題` 是機械的（≡ 檔名）；`伏筆` 是對 registry 的引用。
REQUIRED_KEYS = ("generated-from", "generated-at", "主題")
FORESHADOW_KEY = "伏筆"

# 背景維度盤點的封閉七維（`技巧知識庫/世界觀與背景.md` 二 的背景七維度）。
# 順序不管，集合要一致——實測 rollup 的「時間」列有內容而無人宣告該維度，
# 那個漂移在 `維度` 欄刪掉之後只剩這一項守得到。
DIMENSIONS = ("時間", "空間", "活動", "地點", "組織", "社會", "自身")

# `伏筆: { 埋: [a, b], 收: [c] }`
_FS_GROUP_RE = re.compile(r"(埋|收)\s*[:：]\s*\[([^\]]*)\]")
# 散文裡的檔名引用：`` `X.ai.md` ``、`設定/世界觀/X.ai.md`
_AI_REF_RE = re.compile(r"([^\s`（）()、，。／/]+)" + re.escape(AI_SUFFIX))

ROLLUP_STEM = "_總覽"
INDEX_SECTION = "核心規則索引"
DIM_SECTION = "背景維度盤點"


@dataclass(frozen=True)
class Problem:
    path: Path
    detail: str
    hint: str


@dataclass
class WorldStats:
    """**我在這本書上檢查了幾筆**（`設計原則.md` E2 的可執行推論）。

    每一項都印，**0 也印**。第 3 項的 `foreshadow_unknown` 尤其要印——「檢查了
    0 個伏筆名」與「8 個全部命中」在只報問題數的檢查器裡輸出一模一樣，而前者
    代表它沒讀到你的檔。
    """

    topics: int = 0
    topics_with_retired: int = 0
    retired_keys: int = 0
    foreshadow_names: int = 0
    foreshadow_unknown: int = 0
    registry_beats: int = 0
    registry_objects: int = 0
    index_rows: int = 0
    folder_topics: int = 0
    dim_rows: int = 0
    # 源檔第一段（2026-07-28 功能 12 抉擇 3 B）。`一句話定位` 那個 LLM 摘要節廢除
    # 之後，「這個主題是什麼」改由源檔 H1 之後第一段回答（`world-lint --emit` 印它）。
    blank_ledes: int = 0
    ai_refs: int = 0
    ai_refs_dangling: int = 0
    rollup_found: bool = False

    def render(self) -> str:
        rollup = "有" if self.rollup_found else "**缺**"
        return (
            f"檢查範圍：{self.topics} 支 <主題>.ai.md"
            f"（{self.topics_with_retired} 支仍帶已廢除的欄／共 {self.retired_keys} 個）；"
            f"{self.foreshadow_names} 個伏筆名（{self.foreshadow_unknown} 個 registry 查無）"
            f"·registry ＝幕綱 {self.registry_beats} 個標記名 ∪ 物件檔 {self.registry_objects} 支；"
            f"rollup {rollup}·核心規則索引 {self.index_rows} 列 vs 資料夾 {self.folder_topics} 支源檔·"
            f"背景維度 {self.dim_rows} 列（封閉七維）；"
            f"幕綱檔名引用 {self.ai_refs} 處（{self.ai_refs_dangling} 個懸空）；"
            f"源檔第一段：**{self.blank_ledes}/{self.folder_topics} 支是空的**"
        )


def topic_sources(book: Path) -> list[str]:
    """資料夾裡的主題名（源 `<主題>.md` 的 stem）＝這一軸的權威主題集合。

    源是唯一真實來源，所以「有哪些主題」由源檔名回答，不由 rollup 的表回答
    （那是視圖，D1：視圖不是第二個家）。
    """
    d = book / "story" / "設定" / "世界觀"
    if not d.is_dir():
        return []
    return sorted(
        p.stem
        for p in d.glob("*.md")
        if not p.name.endswith(AI_SUFFIX) and not p.name.startswith("_")
    )


def foreshadow_registry(book: Path) -> tuple[set[str], int, int]:
    """伏筆 ID 的 registry ＝ 幕綱既有標記名 ∪ `story/物件/<名>.md` 檔名。

    回傳 (名字集合, 幕綱標記名數, 物件檔數)。**兩邊都算 registry** 是因為
    `物件.schema.md` 明訂「沒有物件檔的 ID 是合法的」（開檔走內容測試 G4），
    所以只比對物件檔會把大半合法 ID 報成問題。
    """
    names: set[str] = set()
    beat_names: set[str] = set()
    d = book / "story" / "幕綱"
    if d.is_dir():
        for p in sorted(d.glob("*.md")):
            for m in FORESHADOW_RE.finditer(p.read_text(encoding="utf-8")):
                beat_names.add(m.group(1).strip())
    obj = book / "story" / "物件"
    obj_names = {p.stem for p in obj.glob("*.md")} if obj.is_dir() else set()
    names |= beat_names | obj_names
    return names, len(beat_names), len(obj_names)


def _parse_foreshadow(value: str) -> list[str]:
    """`{ 埋: [a, b], 收: [c] }` → ['a','b','c']。解析不到就回空清單。"""
    out: list[str] = []
    for _, inner in _FS_GROUP_RE.findall(value):
        out += [n.strip() for n in inner.split(",") if n.strip()]
    return out


def check_topics(book: Path, stats: WorldStats) -> list[Problem]:
    """第 1／2／3 項：front-matter 三鍵、已廢除的欄、伏筆歸一。"""
    out: list[Problem] = []
    d = book / "story" / "設定" / "世界觀"
    if not d.is_dir():
        return out
    registry, n_beats, n_objs = foreshadow_registry(book)
    stats.registry_beats = n_beats
    stats.registry_objects = n_objs
    unknown: list[tuple[Path, str]] = []
    for p in sorted(d.glob(f"*{AI_SUFFIX}")):
        if p.name.startswith("_"):
            continue
        stats.topics += 1
        fm = front_matter_of(p)
        if fm is None:
            # 尚未封章的骨架：`check` 已經報成 unstamped，重複報是雜訊（同 validate）
            continue
        stem = p.name[: -len(AI_SUFFIX)]

        missing = [k for k in REQUIRED_KEYS if k not in fm]
        if missing:
            out.append(
                Problem(
                    p,
                    f"front-matter 缺 {'、'.join(missing)}",
                    "`generated-*` 跑 `derived-sync stamp <該檔>` 封章、別手填；"
                    "`主題` 寫檔名（見 世界觀.schema.md）",
                )
            )
        if fm.get("主題") and fm["主題"] != stem:
            out.append(
                Problem(
                    p,
                    f"`主題: {fm['主題']}` 與檔名 `{stem}` 不一致",
                    "檔名就是選擇器（C1）：`settings-select` 比對的是檔名，"
                    "front-matter 的 `主題` 只是給人看的複述，兩者不一致時檔名為準",
                )
            )

        retired = [k for k in RETIRED_KEYS if k in fm]
        if retired:
            stats.topics_with_retired += 1
            stats.retired_keys += len(retired)
            out.append(
                Problem(
                    p,
                    f"{len(retired)} 個已廢除的 front-matter 欄：{'、'.join(retired)}",
                    "`影響力`／`主從` 改寫進 `## 影響力` 散文；`升格哨兵` 想說的"
                    "「這個主題帶硬約束」由 story/物件/<名>.md 有沒有對應檔直接回答；"
                    "`維度` 只活在 _總覽 的背景維度盤點；`🧊水下` 屬 story/物件/<名>.md 的"
                    "`揭示層級`。四欄零解析器零消費者且已實測漂移，2026-07-27 依 A4 刪除",
                )
            )

        raw = fm.get(FORESHADOW_KEY)
        if raw is not None and raw not in ("", "[]", "{}"):
            names = _parse_foreshadow(raw)
            if not names:
                out.append(
                    Problem(
                        p,
                        f"`伏筆:` 解析不到任何名字：{raw[:60]}",
                        "格式是 `伏筆: { 埋: [名, 名], 收: [名] }`（見 世界觀.schema.md）",
                    )
                )
            stats.foreshadow_names += len(names)
            for n in names:
                if n not in registry:
                    unknown.append((p, n))
    if unknown:
        stats.foreshadow_unknown = len(unknown)
        shown = "、".join(f"{n}（{p.name}）" for p, n in unknown[:6])
        if len(unknown) > 6:
            shown += "…"
        out.append(
            Problem(
                book / "story" / "設定" / "世界觀",
                f"{len(unknown)} 個伏筆名在 registry 查無：{shown}",
                "**提示不是門檻**——沒有物件檔的 ID 是合法的（物件.schema.md G4），"
                "但這裡的名字既沒有幕綱標記也沒有物件檔，等於第三份自由造字的名冊（C3）。"
                "正解是改成幕綱既用的那個名字，或開一支 story/物件/<名>.md",
            )
        )
    return out


def check_rollup(book: Path, stats: WorldStats) -> list[Problem]:
    """第 4／5 項：rollup 的兩欄視圖 ≡ 資料夾；背景維度 ≡ 封閉七維。

    **只驗 `主題`／`檔` 兩欄。** `主從`／`影響力`／`帶升格哨兵` 三欄在抉擇 1 C 之後
    沒有機械來源（它們是 AI 重生時重讀各檔 `## 影響力` 的判斷），依 E1 不驗、
    schema 也不宣稱它們與任何檔一致——**驗不到的就不要宣稱**。
    """
    out: list[Problem] = []
    d = book / "story" / "設定" / "世界觀"
    rollup = d / f"{ROLLUP_STEM}{AI_SUFFIX}"
    folder = topic_sources(book)
    stats.folder_topics = len(folder)
    if not rollup.is_file():
        # 舊命名的書可能叫 `_總覽.md`；兩種都吃（同 sentinel 的 `_base_stem`）
        legacy = d / f"{ROLLUP_STEM}.md"
        if not legacy.is_file():
            # **缺 rollup 不是問題，是新的正常狀態**（2026-07-28 功能 12 抉擇 1 A）：
            # 那支檔廢除了，世界觀總覽改跑 `world-lint --emit`。本項因此降級成
            # **殘留偵測**：舊檔還在才比對（既有書照抉擇 8 A 不遷移，那份視圖仍然
            # 要與資料夾一致，否則它會靜默漂成第二份真相）。
            return out
        rollup = legacy
    stats.rollup_found = True
    text = rollup.read_text(encoding="utf-8")
    if split_frontmatter(text)[0] is None:
        # 尚未封章的骨架（`書本模板` 那份、或剛建的新書）：它的表裡是佔位列，
        # 逐項比對只會報一堆「幽靈列」。那個狀態 `check` 已經報成 unstamped，
        # 重複報是雜訊——同 `validate` 與本模組 check_topics 的骨架處置。
        return out

    rows = table_rows(section_body(text, INDEX_SECTION) or [])
    stats.index_rows = len(rows)
    listed = [r[0] for r in rows if r and r[0]]
    missing = [t for t in folder if t not in listed]
    ghost = [t for t in listed if t not in folder]
    if missing or ghost:
        bits = []
        if missing:
            bits.append(f"{len(missing)} 支源檔沒進索引：{'、'.join(missing)}")
        if ghost:
            bits.append(f"{len(ghost)} 列指向不存在的主題：{'、'.join(ghost)}")
        out.append(
            Problem(
                rollup,
                f"{INDEX_SECTION} 與資料夾不一致——" + "；".join(bits),
                "索引是**視圖**不是第二個家（D1）：`主題`／`檔` 兩欄由資料夾裡的 "
                "`<主題>.md` 決定，新增或拆分主題後重生 _總覽 即可。"
                f"（`主從`／`影響力`／`帶升格哨兵` 三欄無機械來源，本閘門不驗）",
            )
        )
    for r in rows:
        if len(r) >= 5 and r[0] and r[4]:
            want = f"{r[0]}{AI_SUFFIX}"
            if r[4].strip("`") != want:
                out.append(
                    Problem(
                        rollup,
                        f"{INDEX_SECTION} 的「{r[0]}」列 `檔` 欄寫 {r[4]}，應為 {want}",
                        "`檔` 欄是機械的：主題名決定檔名（C1）",
                    )
                )

    dim_rows = table_rows(section_body(text, DIM_SECTION) or [])
    stats.dim_rows = len(dim_rows)
    listed_dims = [r[0] for r in dim_rows if r and r[0]]
    dim_missing = [x for x in DIMENSIONS if x not in listed_dims]
    dim_extra = [x for x in listed_dims if x not in DIMENSIONS]
    if dim_missing or dim_extra:
        bits = []
        if dim_missing:
            bits.append(f"缺 {'、'.join(dim_missing)}")
        if dim_extra:
            bits.append(f"多出 {'、'.join(dim_extra)}")
        out.append(
            Problem(
                rollup,
                f"{DIM_SECTION} 不是封閉七維——" + "；".join(bits),
                "背景七維度是封閉枚舉（時間／空間／活動／地點／組織／社會／自身，"
                "見 技巧知識庫/世界觀與背景.md 二）。空白維度**不必硬填**，"
                "但那一列要在、狀態欄寫「空白」——少一列與「這個維度沒人做」看起來一樣",
            )
        )
    return out


def check_filename_refs(book: Path, stats: WorldStats) -> list[Problem]:
    """第 6 項：幕綱散文裡的 `<名>.ai.md` 引用，其目標檔存在。

    **這是抉擇 3（觸頂拆主題）那條程序的守衛。** 拆檔會改檔名，而**檔名就是選擇器**
    ——實測幕綱有 74 處 `見 \\`X.ai.md\\`` 這類引用（其中 27 處指 `江湖勢力.ai.md`），
    拆檔那天若漏改，`settings-select` 與那 27 處引用會同時斷，而輸出不含任何警告。

    比對的是**全書所有 `.ai.md` 的 basename 集合**，不只世界觀——幕綱也引角色檔，
    而「引用的檔不存在」在哪一軸都是同一種病。0 個懸空要印出來（那是有意義的 0）。
    """
    out: list[Problem] = []
    d = book / "story" / "幕綱"
    if not d.is_dir():
        return out
    known = {p.name for p in book.rglob(f"*{AI_SUFFIX}")}
    dangling: list[tuple[Path, int, str]] = []
    for p in sorted(d.glob("*.md")):
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            for m in _AI_REF_RE.finditer(ln):
                name = m.group(1).split("/")[-1] + AI_SUFFIX
                stats.ai_refs += 1
                if name not in known:
                    dangling.append((p, i, name))
    if dangling:
        stats.ai_refs_dangling = len(dangling)
        shown = "、".join(f"{n}（{p.name}:{i}）" for p, i, n in dangling[:6])
        if len(dangling) > 6:
            shown += "…"
        out.append(
            Problem(
                d,
                f"{len(dangling)} 處檔名引用指向不存在的檔：{shown}",
                "檔名就是選擇器：拆主題／改名時舊引用要一併改（見 世界觀.schema.md"
                "「主題檔觸頂怎麼拆」步驟 4）。漏改的那幾幕會靜默地選不到那支設定檔，"
                "而 `settings-select` 會印一份格式完全正常、不含警告的結果",
            )
        )
    return out


def check_lede(book: Path, stats: WorldStats) -> list[Problem]:
    """第 7 項：每支源檔 H1 之後要有非空行（2026-07-28 功能 12 抉擇 3 B）。

    **E1 的直接產物**：抉擇 3 B 廢掉 `## 一句話定位` 那個 LLM 摘要節之後，
    「這個主題是什麼」的落點改成源檔的第一段，而 `world-lint --emit` 會印它。
    宣稱了一個格式就要交出守它的檢查器——不然空的那幾支會**靜默印空白**，
    而挑主題的人拿到一份看起來完整的清單（E2 最後一格）。

    實測一世之尊 4/4 支非空、中位 104 字元、最長 132、**0 支超過 rollup 的 400**。
    **不設長度門檻**（同 `char-lint` 第 9 項）：這一項只問「有沒有」。
    """
    d = book / "story" / "設定" / "世界觀"
    if not d.is_dir():
        return []
    topics = topic_sources(book)
    blank = [t for t in topics if not lede(d / f"{t}.md")]
    stats.blank_ledes = len(blank)
    if not blank:
        return []
    return [
        Problem(
            d,
            f"{len(blank)}/{len(topics)} 支源檔的 H1 之後沒有非空行：{'、'.join(blank)}",
            "`world-lint --emit` 的「一句話」欄讀的就是那一段"
            "（2026-07-28 抉擇 3 B：`## 一句話定位` 那個 LLM 摘要節廢除，改印源檔第一段）。"
            "在源檔 H1 底下補一句「這個主題是什麼」即可——**它是源，你寫的就是真相**",
        )
    ]


def lint_book(book: Path) -> tuple[list[Problem], WorldStats]:
    stats = WorldStats()
    problems = (
        check_topics(book, stats)
        + check_rollup(book, stats)
        + check_filename_refs(book, stats)
        + check_lede(book, stats)
    )
    return problems, stats
