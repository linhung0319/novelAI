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

from .refs import MISSING_HINT, format_missing, scan_md_refs
from .scan import (
    SPINE_FILES,
    ScanError,
    parse_spine,
    read_text,
    retired_spine_files,
    spine_path,
)
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
# 2026-07-27（功能 04）`.co.md` 這個檔類廢除，正名 `裁決流.md`。
# **舊名 2026-07-30（驗證輪階段 1c）從這個 tuple 移除**：實測 0 本書有 `.co.md`
# 任何檔，而「目的地存在性」認舊名等於讓一支拿不到 `decision-lint` 的檔冒充目的地
# ——E1 要的是「目的地存在」，不是「有個叫這名字的檔存在」。
DECISION_LOG = ("裁決流.md",)

# 測試執行紀錄（2026-07-28 功能 10 抉擇 3 A）。落點＝arc 檔**檔頭**的一行
# `beat-test: 2026-07-24·0高3中3低`，解析在 `structure.parse_arc`。
#
# **選填——缺席合法、不計入問題數**：沒測過是一種真實狀態，把它報成問題等於把一個
# 明訂非門檻的東西變成門檻。缺幾支由覆蓋率行說，**0 也印**。
# **判準是結構判準**：日期 ＋ `N高N中N低` 的阿拉伯數字，**不驗測試結果好不好**
# （中文數字不認，同 `style-lint` 第 4 項與 `summary-lint` 第 7 項的紀律）。
# **消費者在誕生當天就指得出行號**（E1）：`write/SKILL.md` 步驟 2 的就緒提醒、
# `readiness` 第 3 節；寫它的是 `beat-test` 的收尾。在此之前這件事有三份手抄、
# 零比對、零格式（就緒儀表狀態格／幕綱檔頭散文／測試報告不落檔）。
TEST_RECORD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*[·・]\s*(\d+)高(\d+)中(\d+)低$")

# ---- 幕綱索引 `story/幕綱/_index.md`（2026-07-28 功能 12 補上三項守衛）
#
# **這支檔在功能 12 之前是全書「壞了永遠不會發現」最集中的一格**：9 項裡 6 項在它
# 身上。它是四支工具共用 spine 的家、28,013 B、5 天長 8.8×，而**它在整套工具鏈裡
# 不存在**——`.md` 讓 `check`／`validate` 的 `rglob("*.ai.md")` 掃不到；`sentinel`
# 四支手寫路徑清單沒有一支含它（功能 12 已補，見 `sentinel._beat_index`）；
# `beat-lint` 只讀 `全書順序：` 那一行，其餘 11,647 字元不看。
BEAT_INDEX_NAME = "_index.md"
BEAT_DIR_LABEL = "幕綱"
# 這三支解析索引列／幕號區間／選用公式行的 regex **2026-07-30 移除**（驗證輪階段
# 1c／1d）：`_index.md` 廢除之後，本 lint 只驗它在不在，不再解析它的任何一行。
# 那份「視圖 ≡ 資料夾」的重算仍然活著——它在 `beat-lint --emit` 裡，而那才是
# 功能 12 給它的家（抉擇 4 C：誰重算誰印，同一行程式，結構上不可能漂）。

# 檔內書內路徑的目的地存在性（`設計原則.md` E1「目的地承諾」推論）。
# **這四個常數是 `outline.py` 第 9 項的最小複製**（套件內同層，但兩支 lint 的射程
# 不同：那一支掃 `story/大綱/`，這一支掃 `story/幕綱/`）。射程刻意窄的理由見
# `_check_destinations`。
# （四個常數 2026-07-28 搬進 `refs.py`——見上）


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
    test_records: int = 0
    test_records_bad: int = 0
    # 幕綱索引 `_index.md`（2026-07-28 功能 12 廢除）。**2026-07-30 起只剩一個
    # 布林**：本項從「照舊比對」改成存在性檢查，那七個計數欄隨之消失——它們量的是
    # 「一支已廢除的檔跟資料夾對不對得上」，而那個問題不該再被問（見 `_check_index`）。
    # **0 也印**：覆蓋率行印「已廢除的 `_index.md`：已不在」，不是不印。
    index_retired: bool = False
    path_refs: int = 0
    path_missing: int = 0
    # spine 讀到哪一支檔（2026-07-28 功能 12 抉擇 2 A）。**要印出來**：
    # 落點本身是一個要被看見的狀態，不是一句半真的相容承諾（功能 10／11 的教訓）。
    # `spine_legacy` 2026-07-30 起的語意變了——它不再是「這次走了回退」，
    # 而是「**舊落點的檔還在，而工具已經不讀它了**」（墓碑）。**0 也印。**
    spine_file: str = ""
    spine_legacy: bool = False
    notes: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    def render(self) -> str:
        spine = (
            f"spine 讀自 `{self.spine_file}`"
            if self.spine_file
            else f"spine **找不到**（新落點 `{SPINE_FILES[0]}` 不在）"
        ) + (
            "（**舊落點 `_index.md` 仍在·2026-07-30 起不讀**）"
            if self.spine_legacy
            else "（舊落點已不在）"
        )
        return (
            f"檢查範圍：{self.arcs} 支 arc／{self.beats} 幕／{self.refs} 條前因／"
            f"{self.marks} 個伏筆標記（{self.mark_names} 名）／"
            f"{self.status_rows} 列狀態表"
            f"（其中 {self.status_prose_rows} 列的伏筆名全書無標記·不入機械 diff）／"
            f"{self.promise_sections} 個承諾區／{self.exclusions} 條排除線／"
            f"{self.object_files} 支物件檔；"
            f"已廢除的 `{BEAT_INDEX_NAME}`："
            + ("**仍在**" if self.index_retired else "已不在")
            + "；"
            f"{self.path_refs} 筆檔內書內路徑（**目的地不存在 {self.path_missing}**）；"
            f"{spine}；"
            f"{self.test_records}/{self.arcs} 支 arc 有 `beat-test` 紀錄"
            f"（**格式不合 {self.test_records_bad} 支**·缺紀錄不計入問題數）；"
            f"跳過 {self.skeletons} 支骨架"
        )


def _base_name(name: str) -> str | None:
    m = _TRAILING_PAREN_RE.match(name)
    return m.group(1).strip() if m else None


def _check_spine(
    book: Path, arcs: list[ArcStructure], stats: LintStats, problems: list[str]
) -> None:
    """spine 涵蓋且唯一（V4／V7），落點是 `_順序.md`（2026-07-28 功能 12 抉擇 2 A）。

    `全書順序：` 是四支工具共用的定序來源，卻**零守衛**。漏列一個已拆的 arc，
    `beat-metrics` 2026-07-27 前會靜默退回檔名排序（其餘三支硬報錯）——同一個壞法
    看你先跑哪支工具決定你會不會發現。

    **2026-07-28 搬家的理由**：它是本功能唯一「機械來源答不出來」的那一格（133 字元
    ／1.1%）——arc 的故事順序是作者的創作決定，A1 源。而它原本住在一支被本 lint 當
    「視圖 ≡ 資料夾」驗的索引檔裡：**同一支檔裡一半是源、一半是視圖**（六問 Q0）。
    `設計原則.md` A1 同輪補的那句就是這件事——有 lint 在驗它 ≡ 別的檔，那條 lint
    就是一條只報錯不產生的 inbound 規則。

    **已駁回「證明它 ≡ 檔名排序後刪掉」**（抉擇 2 C）：實測 10/10 個實例相同，但它
    省下的是 133 字元，賭上的是系統宣稱了三個月的「arc 可亂序」自由度。見
    `docs/重構/02-待用構想.md`。

    **回退 2026-07-30（驗證輪階段 1c）移除，改成墓碑。** 2026-07-28～30 之間
    `_index.md` 仍讀得到，而那正是「別讓它一直是提醒」的下場——提醒發了兩天，
    唯一走回退的書一個字沒動，四份回退實作照樣活著。實測活用戶只有 `一世之尊`。
    現在舊落點**不讀**，但**報**：墓碑那一格 0 也印，所以「已遷移」與「這支守衛
    被關掉了」在輸出上分得開。
    """
    index = spine_path(book)
    where = f"幕綱/{index.name}"
    # **只有真的讀到才記「讀自」**：舊版無條件寫檔名，於是新落點不存在時覆蓋率行
    # 印「spine 讀自 `_順序.md`」而同一次輸出裡報「`_順序.md`：不存在」——
    # 兩句話互相打臉，而其中一句是假的。
    stats.spine_file = index.name if index.is_file() else ""
    retired = retired_spine_files(book)
    stats.spine_legacy = bool(retired)
    if not index.is_file():
        detail = (
            f"幕綱/{SPINE_FILES[0]}：不存在"
            f"——「全書順序：」是四支工具共用的定序來源（`幕綱.schema.md`「順序檔」）"
        )
        if retired:
            detail += (
                f"。**舊落點 `{retired[0].name}` 還在，但 2026-07-30 起四支工具都不讀它**"
                f"——`全書順序：` 是 A1 源（arc 的故事順序是創作決定，沒有任何檔算得出來），"
                f"而 `{retired[0].name}` 是一支被驗成「視圖 ≡ 資料夾」的索引，"
                f"兩者同居一檔是六問 Q0 的違反。"
                f"`git mv` 那一行過去即可（三行以內），這本書就會重新跑得動"
            )
        problems.append(detail)
        return
    if retired:
        problems.append(
            f"幕綱/{retired[0].name}：舊落點還在（`全書順序：` 已於 2026-07-28 搬到 "
            f"`{SPINE_FILES[0]}`，本書兩支都有）——**工具只讀新的**，"
            f"舊的那一行不再有任何效力，刪掉以免兩份定序漂移"
        )
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


def _check_index(
    book: Path, arcs: list[ArcStructure], stats: LintStats, problems: list[str]
) -> None:
    """幕綱索引 `_index.md` ＝**已廢除的 rollup**：只驗它在不在，不再照舊比對。

    **2026-07-30（驗證輪階段 1c／1d）從「相容模式」改成存在性檢查。**

    功能 12（2026-07-28）廢除五支 rollup，而 `derived_sync.ABOLISHED_ROLLUPS` 的射程
    只到 `.ai.md`（`check_book` 的 `rglob("*.ai.md")` 在定義上看不到 `.md`）。
    那兩支 `.md`（`幕綱/_index.md`、`大綱/_index.md`）當時交給本 lint 與 `outline-lint`
    的殘留偵測，**而實作出來的是「照舊比對」**——`功能報告/15` 明文交回這一筆。

    **照舊比對的實際後果**：工具對一支已廢除的檔報「你的視圖跟資料夾不一致」，
    於是作者去**把它修好**——而修好一支已廢除的檔，就等於讓它永久合法
    （`設計原則.md` **A5**：撤銷一支檔的身分必須從機制看得出來）。
    這與 `ABOLISHED_ROLLUPS` 檔頭記的是同一句話，只是那裡守住了 `.ai.md`、
    這裡漏了 `.md`。

    所以現在：**檔在 → 報「已廢除，改跑 `beat-lint --emit`」；檔不在 → 什麼都不報**
    （那是新書的正常狀態）。覆蓋率行照印墓碑那一格，**0 也印**。
    """
    index = book / "story" / BEAT_DIR_LABEL / BEAT_INDEX_NAME
    where = f"{BEAT_DIR_LABEL}/{BEAT_INDEX_NAME}"
    if not index.is_file():
        return
    stats.index_retired = True
    problems.append(
        f"{where}：**已廢除的 rollup 還在**（2026-07-28 功能 12 廢除五支 rollup）"
        f"——全書視圖改跑 `beat-lint --emit`（同一份重算，不落檔），"
        f"故事順序改住同層 `{SPINE_FILES[0]}` 的 `全書順序：`，"
        f"選用結構公式的權威在大綱的 `## 選用結構公式`（`outline-lint` 第 12 項守）。"
        f"**2026-07-30 起工具不再讀它的任何一行**——在此之前本項是「照舊比對」，"
        f"而那會叫人去把一支已廢除的檔修好，修好就永久合法了（`設計原則.md` A5）"
    )


def _check_destinations(book: Path, stats: LintStats, problems: list[str]) -> None:
    """檔內指名的書內路徑存在（`設計原則.md` E1「目的地承諾」推論）。

    **第 7 個實例**（前六：幕綱設計註→裁決流／`derived-sync` 的 `missing_destinations`
    ／`decision-lint` 兩處／`ch-lint` 的 `風格` 欄／`summary-lint` 的幕號·arc 引用／
    `outline-lint` 第 9 項）。射程＝`story/幕綱/*.md`，**含 `_index.md`**——那正是
    這一項要抓的地方：實測一世之尊 `幕綱/_index.md` 有 **4 處**引用 `參照/結構.md`，
    而那支檔 2026-07-28（功能 11）已廢除。檔頭甚至逐字寫著「arc 概覽同步自
    `參照/結構.md`」——**一支檔宣告自己的來源是系統剛剛刪掉的檔，零守衛。**

    **射程刻意窄**（同 `outline-lint` 第 9 項）：只認反引號裡、以書內資料夾開頭的
    `.md`。schema 檔、`技巧知識庫/`、佔位寫法（`arcNN.md`）、範圍寫法都不是「指名
    一個檔」——不排除的話，一支完全合法的幕綱會因為引用了自己的 schema 而被報。
    """
    d = book / "story" / BEAT_DIR_LABEL
    if not d.is_dir():
        return
    items = [(f"{BEAT_DIR_LABEL}/{p.name}", read_text(p)) for p in sorted(d.glob("*.md"))]
    checked, missing = scan_md_refs(items, book)
    stats.path_refs += checked
    if not missing:
        return
    stats.path_missing = len(missing)
    shown = format_missing(missing)
    problems.append(
        f"{BEAT_DIR_LABEL}/：{len(missing)} 個檔內指名的路徑不存在：{shown}——{MISSING_HINT}"
    )


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
    _check_spine(book, everything, stats, problems)

    # ---- 幕綱索引的視圖 ＋ 選用公式指路（2026-07-28 功能 12）。**傳全部 arc 檔，
    # 含骨架**（同 `_check_spine`）：視圖 ≡ 資料夾，而骨架也在資料夾裡。
    _check_index(book, everything, stats, problems)

    # ---- 檔內書內路徑的目的地存在性（2026-07-28 功能 12）
    _check_destinations(book, stats, problems)

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

    # ---- 測試執行紀錄的形狀（2026-07-28 功能 10 抉擇 3 A）。**有寫才驗。**
    for a in arcs:
        if a.beat_test is None:
            continue
        value, lineno = a.beat_test
        stats.test_records += 1
        if not TEST_RECORD_RE.match(value):
            stats.test_records_bad += 1
            problems.append(
                f"{a.arc}.md 第 {lineno} 行：`beat-test: {value}` 不合形狀"
                f"——`YYYY-MM-DD·N高N中N低`（阿拉伯數字，中文數字不算）。"
                f"由 `beat-test` 收尾時寫，`write` 的就緒提醒與 `readiness` 讀它"
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
