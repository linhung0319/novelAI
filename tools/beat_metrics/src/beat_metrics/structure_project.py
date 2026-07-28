"""結構軸投影（`structure-project`）：選用公式 ＋ 階段 ↔ 幕 對應 ＋ 缺哪個必要階段。

**它取代 `story/參照/結構.ai.md`**（2026-07-28 功能 11 廢除）。那支檔宣稱自己是「跨全書
的綜合視圖、**無單一源檔**可 hash」，於是走 `derived_sync` 的 `declarative` 特例：不計入
需處理數、不必也不能 `stamp`。**而那句自述是錯的**——實測對應表 **108/108 幕**都能從
`story/幕綱/arcNN.md` 的 `結構階段` 欄重算（`scan.FIELDS` 早就在解析它），選用公式那一半
的權威 `大綱.schema.md` 早就指定給 `## 選用結構公式`。「無單一源」是 `設計原則.md` **A6**
那個空訊號的唯一支柱，而它撐不住（同輪據此把 A6 第 1 條路補成「**『沒有源』是待驗證的
宣稱，不是前提**」）。

逐格套 D3 的推論（凡把一支檔改成投影，先逐格回答「這一格的機械來源是哪一支檔的哪一欄」）
的結果特別乾淨：全檔 25,117 字元裡**只有 173 字元（0.7%）的 `## α` 答不出來**——那一格
併進大綱的 `## 選用結構公式`（A1 源，`outline-lint` 第 12 項守），其餘全部投影。

**為什麼住 `beat_metrics` 而不是自己開一個套件**（作者拍板抉擇 3 A）：兩個輸入**都已經在
這個套件裡解析**——幕綱八欄的 `結構階段` 在 `scan.scan_arc()`、幕號 registry 與 spine 定序
在 `scan.load_book()`、大綱檔與節內容在 `outline.load_files()`。另開套件＝新增第 8 份幕號
集合實作。**零複製是選它的唯一理由**，所以本模組**一行解析邏輯都不自己寫**：它只做 fold
與比對。（同 09 抉擇 1 B 對 `outline-lint` 的理由，逐字相同。）

**它是投影不是閘門**（同 `readiness`）：可疑點交 `outline-test` 測試4／`beat-test` 測試3
判斷，**一律 exit 0、不做 pass/fail**（`共同約定.md` 五）。格式那一側由 `outline-lint`
第 12 項守。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import formula as fm
from .outline import MERGED_MARK, OutlineFile, SECTION_FORMULA, load_files
from .scan import ArcBeats, load_book

# 廢除的舊檔（兩種命名都認）。**留著它 ＝ `設計原則.md` A5 的「撤銷要從檔案系統看得
# 出來」沒有兌現**：內容還在，身分卻已經被一句話撤銷了。形狀照抄
# `readiness.LEGACY_FILES` 對舊就緒儀表做的事（作者拍板抉擇 7：不遷移病例書，
# **但殘留偵測是必要條件**——否則廢除之後那 58,455 B 徹底隱形）。
LEGACY_FILES = ("結構.md", "結構.ai.md")
REFERENCE_DIR = ("story", "參照")

# 舊檔逐格的機械來源（`設計原則.md` D3 的可執行推論）。**答不出來的那一格要印出來，
# 印出來才看得見它是源**——這正是遷移路徑第 1 步的驗收（A5：撤銷前要回答「內容去哪了」）。
PROVENANCE: tuple[tuple[str, str], ...] = (
    ("甲 對應表三欄（階段｜對應arc｜對應幕）", "story/幕綱/arcNN.md 的 `結構階段` 欄（本投影第二節已重算）"),
    ("乙 對應表的 `備註` 欄", "**無獨立來源**——幕綱 `行動`／`結果` 欄的第二份措辭（實測 8-gram 僅 24.9% 回得到）"),
    ("丙 `## 選用公式`", "story/01-大綱.md｜story/大綱/arcNN.md 的 `## 選用結構公式`（本投影第一節已讀）"),
    ("丁 檔頭沿革 blockquote", "拍板理由→story/參照/裁決流.md｜卷級方向→大綱的 `## 卷級方向（卷X·本卷權威）`｜進度→`readiness` 投影"),
    ("戊 `## α`（作者自訂的變形）", "**無機械來源**＝它是源 → 併進大綱的 `## 選用結構公式`（`大綱.schema.md`）"),
)


def _beat(n: int) -> str:
    """幕號一律回標準形 `幕NNN`（`幕綱.schema.md`「幕號配號規則」，至少三位）。

    `Beat.number` 是 int，直接內插會把 `幕001` 印成 `幕1`——那不是同一個識別符，
    貼進別的檔就是一個 `beat-lint`／`outline-lint` 抓得到的懸空引用。
    """
    return f"幕{n:03d}"


@dataclass(frozen=True)
class Run:
    """對應表的一列：同一個 arc 內連續同階段的幕。`stage` 為 None ＝無頂層 token。"""

    arc: str
    stage: str | None
    first: int
    last: int

    def render(self) -> str:
        span = _beat(self.first)
        if self.last != self.first:
            span += f"–{_beat(self.last)}"
        n = self.last - self.first + 1
        return f"| {self.stage or '（無頂層 token）'} | {self.arc} | {span} | {n} 幕 |"


@dataclass
class Scope:
    """一個宣告範圍：一支大綱檔的 `## 選用結構公式` ＋ 它管到的那幾個 arc。"""

    where: str
    arcs: list[str] = field(default_factory=list)
    formulas: list[fm.Formula] = field(default_factory=list)
    unknown: bool = False  # 節在、但一個 registry 名字都沒命中
    missing_section: bool = False  # 連 `## 選用結構公式` 節都沒有

    @property
    def primary(self) -> fm.Formula | None:
        """主公式＝節內第一個命中的 registry 名字（其餘是巢狀／並用）。"""
        return self.formulas[0] if self.formulas else None


@dataclass
class ProjectStats:
    """**我在這本書上投影了幾筆。**（`設計原則.md` E2 的可執行推論，0 也印。）

    最需要這一行的是 `no_token`：**「幾幕的 `結構階段` 欄不以頂層階段 token 起頭」是
    「這個投影看不見多少」的單一數字**。實測某本書 3/108 幕（arc05 幕405–407）的那一欄
    只寫巢狀子公式的階段（`（輪回世界任務）破·瀕死低點…`），而 `幕綱.schema.md` 對
    巢狀公式怎麼寫進這一欄**沒有定義** → 已記進功能 02 的已知疑點。**不印這個數字，
    投影就會拿 105 幕冒充 108 幕。**
    """

    arcs: int = 0
    beats: int = 0
    with_field: int = 0
    no_token: int = 0
    no_token_beats: list[int] = field(default_factory=list)
    outline_files: int = 0
    with_section: int = 0
    declared: int = 0
    unknown_names: int = 0
    legacy: list[tuple[str, int]] = field(default_factory=list)


def _is_retired(f: OutlineFile) -> bool:
    """退役源不是權威（`設計原則.md` A5）。判準與 `outline._check_coexistence` 同一個。"""
    return f.kind == "已併入" or f.status == MERGED_MARK


def _scopes(arcs: list[ArcBeats], files: list[OutlineFile], reg: fm.Registry) -> list[Scope]:
    """arc → 宣告它的那支大綱檔。**路由沿用 `beat-sheet` 的大綱來源判斷**
    （09 抉擇 4 反轉後的那一條）：先找未退役的 `大綱/arcNN.md`，找不到才落到 `01-大綱.md`。
    另開一條路由＝同一個問題兩個答案。
    """
    scoped = {f.arc: f for f in files if f.kind == "scoped" and not _is_retired(f)}
    full = next((f for f in files if f.kind == "全書"), None)

    order: list[str] = []
    by_where: dict[str, Scope] = {}
    for a in arcs:
        src = scoped.get(a.arc) or full
        where = src.where if src is not None else "（無大綱檔）"
        if where not in by_where:
            sc = Scope(where=where)
            if src is None:
                sc.missing_section = True
            else:
                body = src.body(SECTION_FORMULA)
                if body is None:
                    sc.missing_section = True
                else:
                    sc.formulas = reg.match(body)
                    sc.unknown = not sc.formulas
            by_where[where] = sc
            order.append(where)
        by_where[where].arcs.append(a.arc)
    return [by_where[w] for w in order]


def _runs(arc: ArcBeats, stages: tuple[str, ...], stats: ProjectStats) -> list[Run]:
    """一個 arc 的幕序列 → 合併後的對應表列。**同 arc 內連續同階段合併成一列。**"""
    out: list[Run] = []
    for b in arc.beats:
        stats.beats += 1
        raw = b.fields.get("結構階段", "").strip()
        if raw:
            stats.with_field += 1
        stage = fm.leading_stage(raw, stages) if (raw and stages) else None
        if stage is None:
            stats.no_token += 1
            stats.no_token_beats.append(b.number)
        if out and out[-1].stage == stage and out[-1].last == b.number - 1:
            out[-1] = Run(arc.arc, stage, out[-1].first, b.number)
        else:
            out.append(Run(arc.arc, stage, b.number, b.number))
    return out


def _scan_legacy(book: Path, stats: ProjectStats) -> None:
    """殘留偵測（抉擇 7）。**在覆蓋率行渲染之前跑**——先渲染再掃，覆蓋率那一格會恆為 0，
    而第五節同時印「在」：一支自己跟自己矛盾的報表，正是它要抓的那種病。
    """
    d = book.joinpath(*REFERENCE_DIR)
    for name in LEGACY_FILES:
        p = d / name
        if p.is_file():
            stats.legacy.append((name, p.stat().st_size))


def _legacy(stats: ProjectStats) -> list[str]:
    """第五節：舊 `story/參照/結構.{md,ai.md}` 在不在 ＋ 逐格「內容去哪了」。

    **0 也印**（抉擇 7 ＋ A5）。不在時印一行「不在」，那一行才代表「這本書已經遷完了」；
    只在檔還在時才印，就是把「已遷移」與「工具沒讀到」變成同一個綠燈。
    """
    rel = "/".join(REFERENCE_DIR)
    lines = [f"### 五、舊 `{rel}/結構.{{md,ai.md}}`（廢除於 2026-07-28·功能 11）", ""]
    if not stats.legacy:
        lines.append("舊檔：**不在**（已廢除，選用公式住大綱、對應表走本投影）")
        return lines
    for name, size in stats.legacy:
        lines.append(f"舊檔：**在** —— `{rel}/{name}`，{size:,} B")
    lines += [
        "",
        "逐格「這一格的機械來源是哪一支檔的哪一欄」（`設計原則.md` D3／A5 的驗收步驟）：",
        "",
    ]
    for cell, source in PROVENANCE:
        lines.append(f"- **{cell}** → {source}")
    lines += [
        "",
        "> 廢檔前要把「無機械來源」那一格搬到它的落點（戊 → 大綱的 `## 選用結構公式`），"
        "其餘直接刪。**病例書刻意不遷移**，所以這一節會一直印；成長哨兵也會一直報它的體積。",
    ]
    return lines


def project(book: Path, only_arc: str | None = None) -> tuple[str, ProjectStats]:
    """投影一本書的結構軸。回 (報表, 覆蓋率統計)。"""
    stats = ProjectStats()
    _scan_legacy(book, stats)
    arcs = load_book(book)
    everything = load_files(book)
    files = [f for f in everything if not f.skeleton]
    reg = fm.load(book)

    stats.arcs = len(arcs)
    stats.outline_files = len(files)
    scopes = _scopes(arcs, files, reg)
    for sc in scopes:
        if not sc.missing_section:
            stats.with_section += 1
        stats.declared += len(sc.formulas)
        if sc.unknown:
            stats.unknown_names += 1

    stage_of: dict[str, tuple[str, ...]] = {}
    scope_of: dict[str, Scope] = {}
    for sc in scopes:
        p = sc.primary
        for a in sc.arcs:
            stage_of[a] = p.stages if p else ()
            scope_of[a] = sc

    by_arc = {a.arc: _runs(a, stage_of.get(a.arc, ()), stats) for a in arcs}

    lines = [
        f"## 結構軸投影 {book.name}（{stats.arcs} 個 arc；零 LLM、可覆算）",
        "",
        "> 它取代已廢除的 `story/參照/結構.ai.md`（2026-07-28 功能 11）。"
        "**這裡的每一格都是重算出來的**，沒有第二份手抄表可以跟幕綱漂移。",
        "",
    ]
    if reg.connected:
        staged = sum(1 for f in reg.formulas.values() if f.is_staged)
        lines.append(
            f"registry：**{len(reg.formulas)} 套公式**（`{fm.KNOWLEDGE_DIR}/{fm.FORMULA_FILE}`；"
            f"{staged} 套有必要階段／{len(reg.formulas) - staged} 套流程型；"
            f"該檔 {reg.sections} 個 `##` 節中 {reg.annotated_sections} 節帶註記）"
        )
    else:
        lines.append(
            f"registry：**未接**——找不到 `{fm.KNOWLEDGE_DIR}/{fm.FORMULA_FILE}`"
            "（從書資料夾往上找不到同時含 `技巧知識庫/` 與 `結構定義/` 的套件根）。"
            "**缺哪個必要階段這一節因此算不了**，不是「0 缺」"
        )
    for p in reg.problems:
        lines.append(f"（registry 問題）{p}——格式由 `outline-lint` 第 12 項守")

    # ---- 一、選用公式
    lines += ["", "### 一、選用公式（大綱宣告；路由同 `beat-sheet`：先找未退役的 `大綱/arcNN.md`）", ""]
    for sc in scopes:
        span = "、".join(sc.arcs)
        if sc.missing_section:
            lines.append(f"- **{span}** ← `{sc.where}`：**缺 `## {SECTION_FORMULA}` 節**")
            continue
        if sc.unknown:
            lines.append(
                f"- **{span}** ← `{sc.where}`：節在，但**沒有一個 registry 裡的公式名**"
                f"（registry：{reg.names or '未接'}）"
            )
            continue
        p = sc.primary
        assert p is not None
        rest = "／".join(f.name for f in sc.formulas[1:])
        tail = f"；巢狀／並用：{rest}" if rest else ""
        stages = "、".join(p.stages) if p.is_staged else "（流程型公式·不對映幕）"
        lines.append(f"- **{span}** ← `{sc.where}`：**{p.name}**（必要階段：{stages}）{tail}")

    # ---- 二、階段 ↔ 幕 對應
    shown = [a.arc for a in arcs if only_arc is None or a.arc == only_arc]
    lines += ["", "### 二、階段 ↔ 幕 對應（`story/幕綱/arcNN.md` 的 `結構階段` 欄）", ""]
    if only_arc and not shown:
        lines.append(f"（找不到 {only_arc}）")
    else:
        lines += ["| 階段 | 對應 arc | 對應幕 | 幕數 |", "|------|---------|--------|------|"]
        for a in shown:
            lines += [r.render() for r in by_arc[a]]

    # ---- 三、可疑點
    lines += ["", "### 三、可疑點（機械；`α` 變形可能解釋它，**不做 pass/fail**）", ""]
    hits: list[str] = []
    for sc in scopes:
        p = sc.primary
        if p is None or not p.is_staged:
            continue
        if only_arc and only_arc not in sc.arcs:
            continue
        seen: list[str] = []
        for a in sc.arcs:
            for r in by_arc[a]:
                if r.stage and (not seen or seen[-1] != r.stage):
                    seen.append(r.stage)
        missing = [s for s in p.stages if s not in seen]
        if missing:
            hits.append(
                f"- [缺必要階段] {'、'.join(sc.arcs)}（{p.name}）：缺 **{'、'.join(missing)}**"
                f"——宣告的範圍裡沒有任何一幕的 `結構階段` 以它起頭"
            )
        # **錯序只在單一 arc 內驗**（不跨 arc）。理由與 09 對裸 `arcNN` token 的處置
        # 同一條（E1：驗不到就不宣稱）：一支 `01-大綱.md` 可以同時宣告「卷一整體套一次
        # 起承轉合」與「卷二每個 arc 各套一次」，而**「這一次套的範圍是一整卷還是一個
        # arc」在系統裡沒有任何機讀宣告**。跨 arc 驗的話，`合`（arc04 卷一收尾）之後
        # 接 `起`（arc05 新的一輪）會被報成錯序——**那正好與它要抓的病相反**。
        rank = {s: i for i, s in enumerate(p.stages)}
        for a in sc.arcs:
            inner: list[str] = []
            for r in by_arc[a]:
                if r.stage and (not inner or inner[-1] != r.stage):
                    inner.append(r.stage)
            back = [
                (inner[i - 1], inner[i])
                for i in range(1, len(inner))
                if rank.get(inner[i], -1) < rank.get(inner[i - 1], -1)
            ]
            if back:
                x, y = back[0]
                hits.append(
                    f"- [階段序非遞增] {a}（{p.name}）：arc 內 {len(back)} 處"
                    f"（第一處：「{x}」之後是「{y}」）——刻意的變形要在大綱的 "
                    f"`## {SECTION_FORMULA}` 標成 α，否則下游讀不出這是設計還是錯序"
                )
    lines += hits or ["（無）"]
    lines += [
        "",
        "> **缺哪個必要階段是按「宣告範圍」算聯集**（不是逐 arc）：一支 `01-大綱.md` 可以"
        "同時宣告「卷一整體套一次」與「卷二每個 arc 各套一次」，而**那個差別系統裡沒有"
        "機讀宣告**——逐 arc 算會把合法的卷級套用報成缺三個階段。**逐 arc 的覆蓋直接看"
        "第二節**（那張表就是逐 arc 的）。**錯序同理，只在單一 arc 內驗。**",
    ]

    # ---- 四、覆蓋率
    worst = "、".join(_beat(b) for b in stats.no_token_beats[:6]) + (
        "…" if len(stats.no_token_beats) > 6 else ""
    )
    lines += [
        "",
        "### 四、覆蓋率（0 也印）",
        "",
        f"掃了 {stats.arcs} 支幕綱／{stats.beats} 幕"
        f"（{stats.with_field} 幕有 `結構階段` 欄／"
        f"**{stats.no_token} 幕的欄不以頂層階段 token 起頭**"
        + (f"：{worst}）" if stats.no_token_beats else "）"),
        f"大綱 {stats.outline_files} 支檔／{len(scopes)} 個宣告範圍"
        f"（{stats.with_section} 個有 `## {SECTION_FORMULA}` 節·"
        f"宣告 {stats.declared} 個公式名·**{stats.unknown_names} 個範圍 registry 查無**）",
        f"舊 `結構.{{md,ai.md}}`：{len(stats.legacy)} 支仍在"
        + (f"（{'、'.join(n for n, _ in stats.legacy)}）" if stats.legacy else ""),
        "",
        "> `結構階段` 欄不以頂層階段 token 起頭的那幾幕**不入集合差**——"
        "巢狀公式怎麼寫進這一欄 `幕綱.schema.md` 還沒有定義（→ 功能 02）。"
        "**印出來才不會拿部分覆蓋冒充全覆蓋**（`設計原則.md` E2）。",
        "",
    ]
    lines += _legacy(stats)
    return "\n".join(lines).rstrip() + "\n", stats
