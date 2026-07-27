"""幕綱格式閘門（`beat-lint`）。

**為什麼這支工具存在。** 幕綱是全系統唯一「被四支工具逐行解析、卻零檢查器」的
強格式產物：`foreshadow_project`／`beat_metrics`／`fact_projection`／`settings_select`
全是**消費者**（解析來算東西），沒有一支是**守衛**（解析來驗格式）。而 `幕綱.schema.md`
白紙黑字宣稱了幕號唯一、固定八項、`[[幕NNN]]` 指向前因、分區是硬規定——**一條都沒人守**
（`設計原則.md` E1：填不出檢查器就不准在 schema 裡宣稱那個格式）。

最壞的一格是懸空前因（`設計原則.md` E2 第五格·假陰性）：`beat-test/SKILL.md` 明文說它
「是最高優先級的**機械事實，不需 LLM 判斷**」，讀的人會以為工具接手了、於是不看——
但 2026-07-27 之前，**repo 裡沒有任何一支工具解析過 `[[幕NNN]]`**。一世之尊的 157 條
引用 0 懸空，是人手維持的乾淨，不是系統保證的乾淨。

**這支工具守的是「人破結構」那一側**（`設計原則.md` B1）：幕號、`[[幕NNN]]`、分區、
spine 全是人手打的識別符與結構，與 `derived-sync validate` 同類；`fact-lint` 的純化三條
守的是另一側（AI 破格的克制）。

`beat-lint` 不判內容好壞——那是 `beat-test`（LLM 審稿）與 `beat-metrics`（相對基準的
漂移統計）的事。本檔只回答「這份檔還是不是它宣稱的那個格式」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .scan import ScanError, parse_spine, read_text
from .structure import EMPTY_VALUES, SKELETON_MARK, ArcStructure, arc_files, parse_book

FIELDS = ("角色", "時空", "行動", "衝突", "結果", "前因", "伏筆", "結構階段")

# 兩欄可以合法留「—」：`伏筆`＝本幕無伏筆；`前因`＝首幕無前因（`書本模板` 的
# 骨架就寫著「首幕可為「—」」）。**不在這裡判「非首幕卻沒有前因」**——那是孤兒幕，
# 屬因果連續性（`beat-test` 測試1 的 LLM 語意判斷），不是格式問題。
# 實測 `驗證範例` 幕005 正是刻意留著的孤兒幕缺陷樣本，本閘門放它過是對的分工。
OPTIONAL_EMPTY = frozenset({"前因", "伏筆"})

# 幕號預配號段：arcNN ＝ 幕((NN-1)×100+1) … 幕(NN×100)（`幕綱.schema.md`「幕號配號規則」）。
BLOCK = 100
_ARC_NUM_RE = re.compile(r"^arc(\d+)$")
_ARC_TOKEN_RE = re.compile(r"arc[0-9A-Za-z]+")
_SPINE_RE = re.compile(r"全書順序：(.+)$")
# 名字尾巴的括註：`寺裡那個開門的人（真觀）` → base `寺裡那個開門的人`。
_TRAILING_PAREN_RE = re.compile(r"^(.+?)\s*[（(][^（()）]*[)）]\s*$")

# 設計註的搬移目的地（`幕綱.schema.md`「設計註要搬走」）。
# 2026-07-27（功能 04）`.co.md` 這個檔類廢除，正名 `裁決流.md`；舊名也吃
# （`裁決流.schema.md` 沿革：更早的書可能仍是 `.co.md`）。
DECISION_LOG = ("裁決流.md", "裁決流.co.md")


@dataclass
class LintStats:
    """**我在這本書上檢查了幾筆。**

    `設計原則.md` E2 的可執行推論：每個檢查器都要能回答這個問題，不能只回答
    「我發現幾個問題」。**乾淨的時候也要印，0 也要印**——「我檢查了 0 筆」本身
    就是最有用的那一筆訊息。

    本工具最需要這一行的兩格是 `refs` 與 `status_prose_rows`：前者若印 0，代表
    `[[幕NNN]]` 又沒人解析了（那正是它誕生的理由）；後者誠實說出**計畫軌有幾條
    程式根本看不到**——`status_prose_rows` ＝狀態表列的伏筆名在全書任何一幕的
    「伏筆」欄都沒有 `埋|收[[伏筆:x]]` 標記。抉擇 2 B 決定不逼作者替這些「刻意不立
    token」的線補標記，於是 G5 的兩軌 diff 只覆蓋有標記的那半——**那就要說出來**，
    不能讓一份「53 列」的報表看起來像計畫軌整條可解析。
    """

    arcs: int = 0
    skeletons: int = 0
    beats: int = 0
    refs: int = 0
    marks: int = 0
    mark_names: int = 0
    status_rows: int = 0
    status_prose_rows: int = 0
    promise_sections: int = 0
    exclusions: int = 0
    object_files: int = 0
    notes: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    def render(self) -> str:
        return (
            f"檢查範圍：{self.arcs} 支 arc／{self.beats} 幕／{self.refs} 條前因／"
            f"{self.marks} 個伏筆標記（{self.mark_names} 名）／"
            f"{self.status_rows} 列狀態表"
            f"（其中 {self.status_prose_rows} 列的伏筆名全書無標記·不入機械 diff）／"
            f"{self.promise_sections} 個承諾區／{self.exclusions} 條排除線／"
            f"{self.object_files} 支物件檔；跳過 {self.skeletons} 支骨架"
        )


def _base_name(name: str) -> str | None:
    m = _TRAILING_PAREN_RE.match(name)
    return m.group(1).strip() if m else None


def _check_spine(book: Path, arcs: list[ArcStructure], problems: list[str]) -> None:
    """spine 涵蓋且唯一（V4／V7）。

    `全書順序：` 是四支工具共用的定序來源，卻**零守衛**。漏列一個已拆的 arc，
    `beat-metrics` 2026-07-27 前會靜默退回檔名排序（其餘三支硬報錯）——同一個壞法
    看你先跑哪支工具決定你會不會發現。
    """
    index = book / "story" / "幕綱" / "_index.md"
    where = "幕綱/_index.md"
    if not index.is_file():
        problems.append(f"{where}：不存在——「全書順序：」是四支工具共用的定序來源")
        return
    text = read_text(index)
    try:
        spine = parse_spine(text)
    except ScanError as e:
        problems.append(f"{where}：{e}")
        return

    # `parse_spine` 會靜默去重（定序只需要第一次出現），重複本身要另外報。
    for raw in text.splitlines():
        m = _SPINE_RE.search(raw)
        if not m:
            continue
        toks = _ARC_TOKEN_RE.findall(m.group(1))
        dups = sorted({t for t in toks if toks.count(t) > 1})
        for d in dups:
            problems.append(f"{where}：「全書順序」重複列出 {d}（{toks.count(d)} 次）")
        break

    if SKELETON_MARK in text:
        return  # 骨架的 spine 寫的是 `arc01 → arc02 → …`，不必涵蓋不存在的檔

    # 比對的是**磁碟上有哪些 arc 檔**，不是「有內容的那幾支」——spine 的職責是替
    # 存在的檔定序，一支還沒拆幕的骨架仍然要排進全書順序裡。
    present = {a.arc for a in arcs}
    for a in sorted(present - set(spine)):
        problems.append(f"{where}：「全書順序」未涵蓋 {a}（該 arc 已拆出幕號）")
    for a in sorted(set(spine) - present):
        problems.append(f"{where}：「全書順序」列了 {a}，但沒有對應的 {a}.md")


def lint_report(book: Path) -> tuple[list[str], LintStats]:
    """驗一本書的幕綱。回 (問題清單, 覆蓋率統計)。

    問題字串**一律以位置起頭**（`arcNN.md …`／`幕綱/_index.md …`），下游靠開頭
    分類（同 `fact_projection/cli.py:_is_object_problem` 的教訓：用 `in` 比對會把
    修法提示裡的字樣一起撈進來）。
    """
    problems: list[str] = []
    stats = LintStats()

    everything = parse_book(book)
    arcs = [a for a in everything if not a.skeleton]
    stats.arcs = len(arcs)
    stats.skeletons = len(everything) - len(arcs)

    # ---- 幕號唯一（全書）＋在預配號段內
    seen: dict[int, tuple[str, int]] = {}
    for a in arcs:
        m = _ARC_NUM_RE.match(a.arc)
        lo, hi = (
            ((int(m.group(1)) - 1) * BLOCK + 1, int(m.group(1)) * BLOCK) if m else (None, None)
        )
        for b in a.beats:
            stats.beats += 1
            if b.number in seen:
                prev_arc, prev_line = seen[b.number]
                problems.append(
                    f"{a.arc}.md 第 {b.lineno} 行：幕{b.number:03d} 與 "
                    f"{prev_arc}.md 第 {prev_line} 行重複——幕號是穩定 ID，"
                    f"`[[幕NNN]]`／章節錨點都引用它，撞號會讓引用指到兩個地方"
                )
            else:
                seen[b.number] = (a.arc, b.lineno)
            if lo is not None and not (lo <= b.number <= hi):
                problems.append(
                    f"{a.arc}.md 第 {b.lineno} 行：幕{b.number:03d} 不在 {a.arc} 的"
                    f"預配號段 幕{lo:03d}–幕{hi:03d} 內（`幕綱.schema.md`「幕號配號規則」）"
                )

    # ---- 八欄完整
    for a in arcs:
        for b in a.beats:
            missing = [f for f in FIELDS if f not in b.fields]
            if missing:
                problems.append(
                    f"{a.arc}.md 第 {b.lineno} 行：幕{b.number:03d} 缺欄位 "
                    f"{'、'.join(missing)}（schema 定「固定欄位（八項）」）"
                )
            for f in FIELDS:
                if f in OPTIONAL_EMPTY or f not in b.fields:
                    continue
                if b.fields[f].strip() in EMPTY_VALUES:
                    problems.append(
                        f"{a.arc}.md 第 {b.lineno} 行：幕{b.number:03d} 的「{f}」欄留白"
                        f"（只有「前因」「伏筆」兩欄可以填「—」）"
                    )

    # ---- 前因目標存在（V3：schema／skill 稱機械事實，2026-07-27 前無工具）
    defined = set(seen)
    for a in arcs:
        for r in a.refs:
            stats.refs += 1
            if r.target not in defined:
                problems.append(
                    f"{a.arc}.md 第 {r.lineno} 行：幕{r.beat:03d} 的前因 "
                    f"[[幕{r.target:03d}]] 指向不存在的幕（全書找不到 `## 幕{r.target}`）"
                )

    # ---- spine（傳全部 arc 檔，含骨架：見 `_check_spine` 的 `present`）
    _check_spine(book, everything, problems)

    # ---- 承諾區存在（`幕綱.schema.md`「分區是硬規定」）
    for a in arcs:
        if a.has_promise_section:
            stats.promise_sections += 1
            stats.exclusions += len(a.exclusions)
        else:
            problems.append(
                f"{a.arc}.md：缺「## 本 arc 承諾」分區"
                f"（`幕綱.schema.md`「分區是硬規定」；下游 write／beat-test 以它為準，"
                f"排除線也住這裡）"
            )

    # ---- 伏筆名：標記 vs 狀態表的近似名（V10）
    #
    # 報告 §3.1 原訂「狀態表名字 ∈（標記名 ∪ 續行名）」。**抉擇 2 B 之後那條不可實作**
    # ——續行刻意不立 token，「續行名」機器不可知，照原樣做會把幾十列合法續行全報成
    # 問題。改成近似名偵測（同 `object-lint` 的補償機制）：它正好抓到實測那兩個括號
    # 變體，又不冤枉續行。續行改為在覆蓋率行誠實計數。
    mark_names: dict[str, tuple[str, int]] = {}
    for a in arcs:
        for mk in a.marks:
            stats.marks += 1
            mark_names.setdefault(mk.name, (a.arc, mk.lineno))
    stats.mark_names = len(mark_names)

    known = dict(mark_names)
    for a in arcs:
        for row in a.rows:
            known.setdefault(row.name, (a.arc, row.lineno))
    for a in arcs:
        for row in a.rows:
            stats.status_rows += 1
            if row.name not in mark_names:
                stats.status_prose_rows += 1
            base = _base_name(row.name)
            if base and base in known and base != row.name:
                problems.append(
                    f"{a.arc}.md 第 {row.lineno} 行：狀態表「{row.name}」與"
                    f"〔{base}〕疑似同一條伏筆的兩個名字（只差尾巴的括註）。"
                    f"伏筆名是 ID，同一件事要沿用同一個名"
                )

    # ---- 目的地存在性（E1 新推論：遷移承諾的終點要有守衛）
    #
    # schema 三處＋`beat-sheet` 一處命令「設計註落檔時搬進 story/參照/裁決流.md」，
    # 但**沒有人驗過那支檔在不在**。實測一世之尊：arc11 有 6,050 B 的設計註、
    # 全書沒有裁決流——搬移工作流是斷的，於是「為什麼」只好滲進八欄，行動欄從
    # 76 字/幕 長到 513 字/幕。箭頭指向空氣，而箭頭本身格式完全合法。
    with_notes = [a for a in arcs if a.design_note_lines]
    if with_notes:
        ref = book / "story" / "參照"
        if not any((ref / n).is_file() for n in DECISION_LOG):
            listed = "、".join(f"{a.arc}.md（{a.design_note_lines} 行）" for a in with_notes)
            problems.append(
                f"story/參照/：{listed}有「## 設計註」，但搬移目的地 "
                f"`裁決流.md` 不存在——`幕綱.schema.md`「設計註要搬走」指定的"
                f"終點在這本書裡沒有落地，設計註無處可搬只會繼續滲進八欄"
            )

    # ---- 提示（不計入問題數、不影響 exit code）
    objects = book / "story" / "物件"
    registry: set[str] = set()
    if objects.is_dir():
        registry = {p.stem for p in objects.glob("*.md") if not p.stem.startswith(("_", "."))}
    stats.object_files = len(registry)
    unregistered = sorted(n for n in mark_names if n not in registry)
    if unregistered:
        stats.hints.append(
            f"{len(unregistered)}/{len(mark_names)} 個伏筆名沒有 `story/物件/<名>.md`："
            f"{'、'.join(f'〔{n}〕' for n in unregistered[:5])}"
            f"{'…' if len(unregistered) > 5 else ''}"
            f"——沒有物件檔的 ID 是合法的（`物件.schema.md`「開不開檔是內容測試」），"
            f"故不計入問題；但 registry 比對是 C3 的另一半，要開檔就趁現在"
        )

    hooks = sum(len(a.tail_hook_beats) for a in arcs)
    if hooks:
        stats.hints.append(
            f"{hooks}/{stats.beats} 幕有 `幕尾鉤` 欄，而 `幕綱.schema.md` 只定義八欄"
            f"——本輪刻意不裁它該不該升格成正式欄位（見 `docs/重構/功能報告/02-幕綱.md` §八）"
        )

    unknown = [(a.arc, ln, t) for a in arcs for ln, t in a.unknown_sections]
    if unknown:
        stats.hints.append(
            f"{len(unknown)} 個 schema 未定義的 `##` 分區（與 `## 幕NNN` 同層）："
            + "、".join(f"{arc}.md:{ln}「{t[:24]}」" for arc, ln, t in unknown[:3])
            + ("…" if len(unknown) > 3 else "")
            + "——分區只有承諾／幕／伏筆狀態／設計註四種"
        )

    no_status = [a.arc for a in arcs if not a.has_status_table]
    if no_status:
        stats.notes.append(
            f"{len(no_status)} 支 arc 沒有「## 本 arc 伏筆狀態」表（選用分區）："
            + "、".join(no_status)
        )

    return problems, stats


def lint(book: Path) -> list[str]:
    return lint_report(book)[0]
