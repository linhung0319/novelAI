from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .core import AI_SUFFIX
from .validate import (
    SETTINGS_KINDS,
    SUMMARY_DERIVED,
    SUMMARY_DIR,
    SUMMARY_KIND,
    SUMMARY_SOURCE,
    enum_for,
    stray_sections,
)

# 門檻皆為**建議值**（advisory），不是門檻式 pass/fail——呼應「AI 是審稿員不是門檻」。
# 取值依據見各函式 docstring，全部可由 CLI 覆寫。
#
# 哨兵量的是**「必須整檔讀的東西有多大」**，不是「檔多大」（`共同約定.md` 零）：
# 有投影工具可切片的檔（約束表／裁決流，以及舊格式的事實流）**檔案大小**不受規範。
#
# **但「有投影工具」不豁免行長**：投影的粒度**就是行**，一行不可再切。2026-07-27
# 前這裡曾整支檔豁免，於是實測 1,728 字的單一事件行一聲沒吭地長了 11 個 arc
# （見 `結構定義/事實流.schema.md`）。故行長改為一律受管，只是門檻不同。
BEAT_BYTES_PER_BEAT = 2500  # 幕綱：每幕位元組
SOURCE_BYTES = 25000  # 源：單檔（或單一角色目錄總和）絕對上限（約 8000 漢字）
DERIVED_BYTES = 12000  # 衍生 `.ai.md`：無切片工具，且應是源的壓縮，故更嚴（約 4000 漢字）
LINE_CHARS = 2000  # 綜合檔單行（單一表格 cell）字元數
ROLLUP_LINE_CHARS = 400  # rollup 一列＝一行摘要，比綜合檔嚴得多（schema 說「一行需求」）
# 設定層**非 rollup** 檔的單行（2026-07-27 功能 05 補上）。分析段落天生比 rollup 的
# 一列長（「限制與代價」那種一條就是一段），所以不套 400；但也不能沒有門檻——實測
# `江湖勢力.ai.md` 單行 1,155 字元（rollup 門檻的 2.9×）一聲沒吭地長了八次重生。
#
# **兩個門檻皆取自實測分佈的空隙，樣本 n=4（一世之尊四支世界觀主題），是暫定值**：
#   衍生最長行 671／690／1,072／1,155 → 800 落在 690 與 1,072 之間
#   源檔最長行 372／375／430／575     → 600 落在 430 與 575 之上的空隙
# 取法與 `beat_sheet_density` 的 2,500 一致（「兩群之間的空隙」）。**第二本書有設定層
# 之後要重取**——n=4 的分佈不足以定一個跨書門檻，見 `世界觀.schema.md`「單行長度」。
SETTINGS_DERIVED_LINE_CHARS = 800
SETTINGS_SOURCE_LINE_CHARS = 600
# 事實行量的是**內容欄**（信封第四欄），與 `fact-lint` 同一把尺，只是門檻更早：
# 哨兵 120（≈1.6× 健康均值）先示警，`fact-lint` 200 才擋。
FACT_LINE_CHARS = 120
FACT_PAREN_RATIO = 0.40  # 括號內註解佔比（夾帶設計註的信號）
FACT_PAREN_MIN_CHARS = 60

_ARC_RE = re.compile(r"^arc[0-9A-Za-z]+$")


def _summary_paths(book: Path) -> tuple[Path, Path]:
    """摘要軸的兩支檔。路徑的唯一真相在 `validate.py`（見那裡的 `SUMMARY_*`）。

    **2026-07-27（功能 08）補進本檔的三支目標集**。在此之前四支目標集
    **0/4** 含它，於是源 15,656 B（門檻的 62.6%）、衍生 10,530 B（門檻的
    **87.8%**）、源最長行 594、衍生最長行 626 **全部靜音**——而摘要的成長軸
    是**裁決輪次**（源 10.6×／衍生 15.5×），`共同約定.md` 甚至明文把它列進
    「本來就是單檔且有界」的豁免。

    **這是「四份手寫路徑清單漏檔」的第六次**（03 補 `chapters/`、05 補設定層
    衍生與源各一）。前五次漏的是資料夾，這次漏的是 `story/` 根目錄下的兩支檔
    ——形狀相同，根因相同：每支函式各自手寫路徑。**根因不在本輪修**，
    「這本書有哪些受管檔」的統一清單交功能 14。
    """
    d = book.joinpath(*SUMMARY_DIR)
    return d / SUMMARY_SOURCE, d / SUMMARY_DERIVED


# 大綱層（2026-07-28 功能 09 補上）。`_已併入/` 是退役源的家（`設計原則.md` A5），
# **刻意不掃**：它已經不是權威、也不該再長，對它報「檔太大」只是雜訊。
OUTLINE_FULL = ("story", "01-大綱.md")
OUTLINE_DIR = ("story", "大綱")
OUTLINE_INDEX = "_index.md"
OUTLINE_RETIRED = "_已併入"


def _outline_sources(book: Path) -> list[Path]:
    """全書版 ＋ 未退役的 scoped 大綱檔。

    **2026-07-28（功能 09）補進本檔的兩支目標集**。在此之前四支目標集 **0/4**
    含 `story/大綱/`，於是 **6/12 支檔超過 `SOURCE_BYTES`**（最大 44,307＝門檻的
    1.77×）、7 支檔有超過 600 字元的單行（最長 1,324）**全部靜音**——而同一次
    `check` 卻報了 32,650 B 的 `血刀頭陀.md`。

    **這是「四份手寫路徑清單漏檔」的第七次**（03 補 `chapters/`、05 補設定層衍生
    與源、08 補摘要兩支）。前幾次漏的是資料夾或根目錄下的兩支檔，**這次漏的是一整個
    產物軸**——而且是 repo 裡體積第三大的軸（302,669 B，僅次於幕綱與正文）。
    **根因不在本輪修**，「這本書有哪些受管檔」的統一清單交功能 14。
    """
    out: list[Path] = []
    full = book.joinpath(*OUTLINE_FULL)
    if full.is_file():
        out.append(full)
    d = book.joinpath(*OUTLINE_DIR)
    if d.is_dir():
        out += [p for p in sorted(d.glob("*.md")) if not p.name.startswith("_")]
    return out
_BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)")
_PAREN_RE = re.compile(r"（[^（）]*）")

# 節枚舉／`SETTINGS_KINDS` 的唯一真相在 `validate.py`（那裡是格式的擁有者）。
# 哨兵借用它判「衍生檔塞了不屬於它的東西」，兩份會漂移，故不另抄一份。

# 有投影工具可切片的檔——**檔案大小**不受規範（行長仍受，見上）。含各代舊檔名。
# `story/參照/` 底下那些「檔可以很大、但一行不可再切」的檔（有投影工具切它們）。
# 2026-07-27 移除 `約束`／`約束.co`：那個落點已廢除（約束搬進 story/物件/<名>.md 的
# 「## 不得寫成什麼」）。還留著那支檔的書由 `fact-lint` 報成落點錯，不是在這裡量行長。
APPEND_LOG_STEMS = frozenset({"事實流", "狀態事件流", "裁決流", "裁決流.co"})


@dataclass(frozen=True)
class Finding:
    kind: str
    path: Path
    detail: str
    hint: str


def _base_stem(p: Path) -> str:
    """去掉 `.ai.md` 或 `.md`，取實體名。`就緒儀表.ai.md` → `就緒儀表`。"""
    name = p.name
    if name.endswith(AI_SUFFIX):
        return name[: -len(AI_SUFFIX)]
    return p.stem


def _size(p: Path) -> int:
    return len(p.read_text(encoding="utf-8").encode("utf-8"))


def beat_sheet_density(book: Path, limit: int = BEAT_BYTES_PER_BEAT) -> list[Finding]:
    """幕綱該正比於幕數。明顯超出＝設計理由滲進了檔案。

    門檻取自實測分佈：健康的落在 1378–2211 B/幕（一世之尊 arc01–arc04、芯片巫師
    全三段、harry_potter），漂移的從 2872 起跳並一路升到 9113（一世之尊 arc05 之後）。
    2500 是這兩群之間的空隙。
    """
    out: list[Finding] = []
    d = book / "story" / "幕綱"
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.md")):
        if not _ARC_RE.match(p.stem):
            continue
        text = p.read_text(encoding="utf-8")
        beats = sum(1 for ln in text.splitlines() if _BEAT_HEAD_RE.match(ln))
        if beats == 0:
            continue
        per = len(text.encode("utf-8")) // beats
        if per > limit:
            out.append(
                Finding(
                    kind="幕綱肥大",
                    path=p,
                    detail=f"{per} B/幕（{beats} 幕，建議 ≤{limit}）",
                    hint="設計理由（母題論證／判例／本輪拍板）該搬進 story/參照/裁決流.md，不在幕的欄位、也不留在檔尾設計註",
                )
            )
    return out


def oversized_sources(book: Path, limit: int = SOURCE_BYTES) -> list[Finding]:
    """人管·源必須整檔讀，故單檔（或單一角色目錄）不該無限長。

    **用絕對門檻，不用「同層中位數的 N 倍」**：承重角色的設定檔本來就該比路人厚，
    中位數會被一堆小角色拉低，於是主角每次都被報——那是雜訊，不是缺陷。

    刻意**不建議「只讀一部分」**——那會把自由格式的源檔逼成有 schema 的東西；
    正解是升級成目錄形態（角色）或拆主題（世界觀）。
    """
    out: list[Finding] = []
    for kind in SETTINGS_KINDS:
        d = book / "story" / "設定" / kind
        if not d.is_dir():
            continue
        for entry in sorted(d.iterdir()):
            if entry.is_dir():
                # 目錄形態：切面總和過大＝這個角色本身該再拆，不是切面不夠
                facets = sorted(entry.glob("*.md"))
                size = sum(_size(f) for f in facets)
                hint = (
                    f"已是目錄形態（{len(facets)} 個切面）仍過大——"
                    "檢查是否有 AI 產物（裁決紀錄／正文既成事實）誤寫進源檔"
                )
            elif entry.suffix == ".md" and not entry.name.endswith(AI_SUFFIX) and not entry.name.startswith("_"):
                size = _size(entry)
                # **先搬後拆**（2026-07-27 功能 06 抉擇 4 B，作者拍板）。在此之前
                # 這一支只說「升級成目錄形態」，而實測 `血刀頭陀.md`（32,650 B）
                # 觸頂的直接原因不是角色太厚，是**寄居內容**：逐題問答 7 節 35.9%，
                # 加上帶日期的本輪拍板紀錄節共 **61.2%**——搬走之後剩 5,164 字元，
                # 遠低於門檻、**可能根本不需要拆**。照舊 hint 做等於把要搬走的東西
                # 分裝到五個切面檔。目錄形態那一支（見上）本來就是這個 hint，
                # 本輪把兩支對齊。
                hint = (
                    "**先問「是不是有寄居內容」再談拆**：共創逐題問答（Q1…Q9）、"
                    "本輪拍板紀錄、未用備案屬 story/參照/裁決流.md；正文釘死的事實屬"
                    "該章 chNNNN.ai.md 的「## 本章事實」；下游硬約束屬 "
                    "story/物件/<名>.md 的「## 不得寫成什麼」。搬完仍超標才拆——"
                    "角色＝升級成目錄形態（核心／來歷／能力／關係／水下，見 角色.schema.md）；"
                    "世界觀＝拆成更細的主題檔。別改成「只讀一部分」"
                )
            else:
                continue
            if size > limit:
                out.append(
                    Finding(
                        kind="源檔肥大",
                        path=entry,
                        detail=f"{size} B（建議 ≤{limit}）",
                        hint=hint,
                    )
                )
    # 摘要源（2026-07-27 功能 08 補上，見 `_summary_paths`）。**hint 與設定層不同**：
    # 摘要沒有目錄形態、也沒有「拆主題」可拆——它一本書就是一份，所以搬完仍超標
    # 時沒有第二步。實測它 51.4% 是裁決理由與已駁回方案、16.7% 是「臨場拍板」節
    # （而其中一大半寫著「已定案／已鎖定」），也就是說**搬走就夠了**。
    src, _ = _summary_paths(book)
    if src.is_file():
        size = _size(src)
        if size > limit:
            out.append(
                Finding(
                    kind="源檔肥大",
                    path=src,
                    detail=f"{size} B（建議 ≤{limit}）",
                    hint="摘要**沒有拆檔這條路**（一本書一份、無目錄形態、無主題可拆），"
                    "所以只有搬：**被捨棄的方案＋為什麼捨棄**屬 "
                    "story/參照/裁決流.md（`標的`＝00-摘要.md）、"
                    "真正未定的暫定屬 raw/、正文釘死的事實屬該章 chNNNN.ai.md 的"
                    "「## 本章事實」。摘要是**唯一每支 skill 都無條件整檔讀的源檔**，"
                    "所以它多一個字，全書每次落筆都多讀一個字",
                )
            )
    # 大綱（2026-07-28 功能 09 補上，見 `_outline_sources`）。**門檻沿用 `SOURCE_BYTES`，
    # 不新造**：實測一世之尊 11 支 arcNN 的分佈是 4,848／4,848／5,743／5,963／11,901／
    # 21,836／33,468／36,727／41,966／42,286／44,307——**21,836 → 33,468 之間有空隙，
    # 25,000 正好落在裡面**（取法同 05 的 800／600 與 `beat_sheet_density` 的 2,500）。
    # 樣本 n=11（比設定層那兩個門檻的 n=4 好，但仍是單書樣本）。
    #
    # **hint 與設定層／摘要都不同**：大綱沒有目錄形態、也沒有主題可拆，唯一的「拆」
    # 是把已收斂的卷併進 `01-大綱.md` 並 `git mv` 進 `_已併入/`（那是生命週期動作，
    # 不是切檔）。實測 arcNN 檔 **73% 不是連續敘述**——所以答案幾乎一定是搬，不是拆。
    for p in _outline_sources(book):
        size = _size(p)
        if size > limit:
            out.append(
                Finding(
                    kind="源檔肥大",
                    path=p,
                    detail=f"{size} B（建議 ≤{limit}）",
                    hint="大綱**沒有拆檔這條路**（一卷一份、無目錄形態、無主題可拆），"
                    "所以先搬：逐題發落紀錄／拍板來歷／護欄推導屬 "
                    "story/參照/裁決流.md（`標的`＝該大綱檔）；既成的伏筆埋設點與"
                    "回收點由 foreshadow-project --arc 回答，別在 "
                    "`## 本 arc 伏筆狀態` 抄第三份（那一節只寫意圖）；"
                    "「本 arc 不引爆哪條線」屬幕綱的 `## 本 arc 承諾`。"
                    "搬完仍超標，代表這一卷該收斂進 01-大綱.md 了"
                    "（併入的最後一步是 git mv 進 story/大綱/_已併入/）",
                )
            )
    return out


def _derived_targets(book: Path) -> list[tuple[Path, str]]:
    """所有受管的衍生 `.ai.md` ＋ 它套哪份節枚舉。

    **2026-07-27（功能 03）補上 `chapters/`。** 在此之前這裡只掃 `story/設定/<kind>`，
    於是 50,782 B 的 `chapters/_index.ai.md`（門檻的 4.2×）完全靜音，而
    `derived-sync check` 印「**0 個需處理**」——`設計原則.md` E2 最後一格（守衛回報
    正常的假陰性）。證據這不是刻意豁免：同檔的 `bloated_fact_lines` 早就在掃
    `chapters/ch*.ai.md`，**是三個目標集各自手寫路徑清單時漏了一個資料夾**
    （要不要有一份統一的「這本書有哪些受管檔」交功能 14）。
    """
    out: list[tuple[Path, str]] = []
    for kind in SETTINGS_KINDS:
        d = book / "story" / "設定" / kind
        if d.is_dir():
            out += [(p, kind) for p in sorted(d.glob(f"*{AI_SUFFIX}"))]
    chapters = book / "chapters"
    if chapters.is_dir():
        out += [(p, "章節") for p in sorted(chapters.glob(f"*{AI_SUFFIX}"))]
    # **2026-07-27（功能 08）補上摘要衍生檔**——第六次補同一個根因（見 `_summary_paths`）。
    # 實測 10,530 B ＝ `DERIVED_BYTES` 的 87.8%，而它還帶著 04 早就該搬走的
    # `## 待裁決回饋`（818 字元）：**兩個觸發都成立而兩個都靜音**。
    _, derived = _summary_paths(book)
    if derived.is_file():
        out.append((derived, SUMMARY_KIND))
    return out


def unsliceable_derived(book: Path, limit: int = DERIVED_BYTES) -> list[Finding]:
    """衍生 `.ai.md` 沒有任何切片工具，故不享有「可以很大」的豁免。

    見 `共同約定.md` 零的資格條款。兩個獨立觸發：

    1. **枚舉外的節**——內容找不到家而寄生在此。實測三種：「硬事實」「反派備註」
       「下游硬約束」（屬 `事實流.md` 的錨／約束），以及檔末的裁決 blockquote
       （屬 `裁決流.md`）。這一項不論大小都報，因為它是分類錯誤不是體積問題。
    2. **超過門檻**——衍生應是源的壓縮，比源檔門檻更嚴。
    """
    out: list[Finding] = []
    for p, kind in _derived_targets(book):
        text = p.read_text(encoding="utf-8")
        size = len(text.encode("utf-8"))
        allowed = enum_for(kind, p.name[: -len(AI_SUFFIX)])
        stray = stray_sections(text, allowed) if allowed else []
        if stray:
            shown = "、".join(stray[:4]) + ("…" if len(stray) > 4 else "")
            out.append(
                Finding(
                    kind="衍生檔不可切片",
                    path=p,
                    detail=f"{size} B，{len(stray)} 個枚舉外的節：{shown}",
                    hint="正文釘死的事實（錨）屬該章 chNNNN.ai.md 的「## 本章事實」；下游硬約束與揭示層級屬 story/物件/<名>.md；待裁決回饋屬 story/參照/待裁決.md；裁決理由屬 story/參照/裁決流.md。衍生檔只留 schema 定義的節",
                )
            )
        elif size > limit:
            out.append(
                Finding(
                    kind="衍生檔不可切片",
                    path=p,
                    detail=f"{size} B（建議 ≤{limit}）",
                    hint="衍生檔無切片工具、又該是源的壓縮；過大代表塞了不屬於它的東西（見 共同約定.md 零 資格條款）",
                )
            )
    return out


def long_lines(
    book: Path,
    limit: int = LINE_CHARS,
    rollup_limit: int = ROLLUP_LINE_CHARS,
    settings_derived_limit: int = SETTINGS_DERIVED_LINE_CHARS,
    settings_source_limit: int = SETTINGS_SOURCE_LINE_CHARS,
) -> list[Finding]:
    """單行過長＝狀態格／表格 cell 被當事件日誌用。

    掃五處，門檻不同：
    - `story/參照/` 的綜合檔（就緒儀表／結構）→ `limit`。參照值：一世之尊
      就緒儀表最長單一 cell 約 10,000 字元（≈24KB）。
    - 設定層 rollup（`_index.ai.md`／`_總覽.ai.md`）→ `rollup_limit`。schema 說
      那一欄是「一行需求」，實測被寫成 800–1000 字元的整段補厚紀錄，等於讓
      rollup 變成第二份真相。
    - **`chapters/_index.ai.md`（2026-07-27 功能 03 補上）** → 同 `rollup_limit`，
      與設定層 rollup 同一把尺。它是同一種病在另一支檔上復發：實測最長單行
      2,235 字元（門檻的 5.6×）、備註欄每列 196 B 長到 781 B，而三個目標集
      **恰好都不含 `chapters/`**，於是 `check` 印「0 個需處理」。
    - **設定層非 rollup 的衍生檔 `<實體>.ai.md`（2026-07-27 功能 05 補上）**
      → `settings_derived_limit`（800）。
    - **設定層的源檔 `<實體>.md`／`<名>/<切面>.md`（同輪補上）**
      → `settings_source_limit`（600）。源檔的行長不受「自由源不限單行長度」
      豁免的理由見下。
    - **`story/00-摘要.ai.md`／`00-摘要.md`（2026-07-27 功能 08 補上）**
      → 沿用上面兩級（800／600），**不新造第五級門檻**。

    事實流／裁決流是 append log，有投影工具、且天生一行一筆——不受此限。

    **為什麼後兩組在 2026-07-27 前完全靜音**：這是同一個根因的**第五次**——
    `sentinel.py` 四支函式各自手寫路徑清單，於是每加一種受管檔就漏一次
    （03 漏的是 `chapters/`）。證據這不是刻意豁免：同輪 `unsliceable_derived`
    早就在掃 `story/設定/<kind>/*.ai.md` 的**大小**，只有行長那一份漏了它。
    實測代價：`江湖勢力.ai.md` 1,155 字元、`修煉體系.ai.md` 1,072 字元的單行
    無人吭聲，而 `_總覽.ai.md`（同一個資料夾、只因檔名以 `_` 開頭）一直在報。
    要不要有一份統一的「這本書有哪些受管檔」交功能 14。

    **為什麼源檔也管行長**：`共同約定.md` 零 的表格寫「自由源·單行長度不限」，
    那條講的是**格式自由**（自由源沒有欄位，所以沒有「欄位溢位」）。但一個
    600 字元的 bullet 仍然是登記表被當 log 用的信號——實測 `修煉體系.md:124`
    是 759 字元的單行，內含三個日期的翻案沿革（「2026-07-22 作者明示當時不拍…
    2026-07-23 已依此形式拍下第一卷」）。那些沿革屬 `story/參照/裁決流.md`。
    門檻比衍生鬆（600 vs 800）是因為源檔是人寫的散文、本來就該更短。
    """
    out: list[Finding] = []
    targets: list[tuple[Path, int]] = []
    ref = book / "story" / "參照"
    if ref.is_dir():
        # 依 base stem 判斷，才能同時吃到新命名（就緒儀表.ai.md）與既有書的舊命名
        targets += [
            (p, limit)
            for p in sorted(ref.glob("*.md"))
            if _base_stem(p) not in APPEND_LOG_STEMS
        ]
    for kind in SETTINGS_KINDS:
        d = book / "story" / "設定" / kind
        if not d.is_dir():
            continue
        targets += [(p, rollup_limit) for p in sorted(d.glob(f"_*{AI_SUFFIX}"))]
        # 非 rollup 的衍生與源。**用 rglob 吃到角色的目錄形態**（`<名>/<切面>.md`）
        # ——單檔形態與目錄形態的行長是同一件事，不該因為源升級成目錄就靜音。
        for p in sorted(d.rglob("*.md")):
            if p.name.startswith("_"):
                continue
            if p.name.endswith(AI_SUFFIX):
                targets.append((p, settings_derived_limit))
            else:
                targets.append((p, settings_source_limit))
    chapters = book / "chapters"
    if chapters.is_dir():
        targets += [(p, rollup_limit) for p in sorted(chapters.glob(f"_*{AI_SUFFIX}"))]
    # **摘要兩支檔（2026-07-27 功能 08 補上）沿用設定層的兩級門檻**，不新造第五級：
    # 衍生是分析段落（同 `<主題>.ai.md` 的「限制與代價」，天生比 rollup 的一列長）、
    # 源是自由散文，性質與設定層那兩類相同。實測衍生最長行 626、源最長行 594
    # ——**兩者都只差門檻一點點**，那正是要它們進目標集的理由，不是放它們走的理由。
    # 另：`n=1` 的樣本不足以另立門檻（06 抉擇 5 A 已駁回「沒有空隙時硬定數字」）。
    summary_src, summary_derived = _summary_paths(book)
    if summary_derived.is_file():
        targets.append((summary_derived, settings_derived_limit))
    if summary_src.is_file():
        targets.append((summary_src, settings_source_limit))
    # **大綱層（2026-07-28 功能 09 補上）也沿用既有的兩級門檻，不新造第五級**：
    #   arcNN 與 01-大綱.md → 源那一級（600）。實測 11 支 arcNN 的最長行分佈是
    #     199／213／236／249／409｜723／728／924／1,035／1,072／1,324
    #     ——**空隙在 409 → 723**，設定層源那一級 600 正好落在裡面（n=11）。
    #   大綱/_index.md → rollup 那一級（400）。它是「視圖 ≡ 資料夾」形狀的索引，
    #     與 `chapters/_index.ai.md`／設定層 rollup 同類，只是它**不帶 `.ai.md`**
    #     （唯一一支這樣的 rollup → 形態交 12）。實測 11 列平均 823 字元、最長 1,828。
    #
    # **為什麼行長比檔案大小更該管**：實測 600 命中的那幾行有大半不是敘述段落，是
    # **逐題拍板紀錄與編號排除線被塞進單行**（arc07 那條 1,324 字元的最長行就是）
    # ——連續敘述天生一段一行，而一份沿革不該是一行。
    outline: set[Path] = set()
    for p in _outline_sources(book):
        targets.append((p, settings_source_limit))
        outline.add(p)
    outline_index = book.joinpath(*OUTLINE_DIR, OUTLINE_INDEX)
    if outline_index.is_file():
        targets.append((outline_index, rollup_limit))
        outline.add(outline_index)

    # 設定層非 rollup 檔的病徵不是「表格 cell」而是「一條分析／一個 bullet 長成
    # 一份沿革」，所以 hint 分開寫。**兩種 hint 都提 `story/參照/裁決流.md`**——
    # 那是 `missing_destinations` 的鉤子，把它拿掉等於讓這些筆數不再檢查目的地。
    settings_hint = (
        "一條分析／一個 bullet 不該裝一份沿革：拍板理由與翻案史屬 story/參照/裁決流.md、"
        "下游硬約束屬 story/物件/<名>.md 的「## 不得寫成什麼」。"
        "門檻取自 n=4 的實測空隙（衍生 800／源 600），是暫定值"
    )
    cell_hint = (
        "狀態格／rollup 一列只報摘要；沿革與裁決記錄屬 story/參照/裁決流.md，"
        "不該住在表格 cell 裡"
    )
    # 大綱層的病徵是**逐題拍板紀錄與編號排除線被塞進單行**，不是表格 cell、也不是
    # 「一條分析長成一份沿革」，而且門檻的樣本數不同（n=11 vs n=4）——所以 hint 分開寫。
    outline_hint = (
        "連續敘述天生一段一行，而**一份沿革不該是一行**：逐題發落紀錄（Q1…Qn）、"
        "本輪拍板來歷、護欄推導屬 story/參照/裁決流.md（`標的`＝該大綱檔）；"
        "編號排除線屬幕綱的 `## 本 arc 承諾`（射程天然綁 arc，"
        "`fact-project --for-beat` 會一起印）；卷級方向寫成 "
        "`## 卷級方向（卷X·本卷權威）` 一節、同卷其餘檔只指路。"
        "門檻取自 n=11 的實測空隙（409 → 723 之間取 600），沿用設定層源那一級"
    )
    settings_limits = {settings_derived_limit, settings_source_limit}
    for p, limit in targets:
        worst = 0
        worst_no = 0
        count = 0
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if len(ln) > limit:
                count += 1
                if len(ln) > worst:
                    worst, worst_no = len(ln), i
        if count:
            out.append(
                Finding(
                    kind="狀態格過長",
                    path=p,
                    detail=f"{count} 行超過 {limit} 字（最長 {worst} 字，第 {worst_no} 行）",
                    hint=(
                        outline_hint
                        if p in outline
                        else settings_hint
                        if limit in settings_limits
                        else cell_hint
                    ),
                )
            )
    return out


def _fact_lines(text: str) -> list[tuple[int, str]]:
    """`## 本章事實` 區塊裡的事件行。區塊外的一律不算（待裁決回饋也是 `- ` 開頭）。"""
    out: list[tuple[int, str]] = []
    inside = False
    for i, raw in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        s = raw.strip()
        if s.startswith("## "):
            inside = s[3:].strip().startswith("本章事實")
            continue
        if inside and s.startswith("- 幕"):
            out.append((i, s))
    return out


def bloated_fact_lines(
    book: Path,
    limit: int = FACT_LINE_CHARS,
    ratio: float = FACT_PAREN_RATIO,
) -> list[Finding]:
    """事實行只該寫「這一幕改變了什麼」——一行一筆 delta，不是一份前情提要。

    這是 2026-07-27 補上的哨兵。在它之前，事實／約束整支檔被豁免行長檢查（理由是
    「有投影工具」），但**投影的粒度就是行**：一行不可再切，所以有工具不構成豁免。

    實測一世之尊（93 章／11 arc，字元數）：事件**筆數**每 arc 都是 15–36 沒有成長，
    **內容欄**卻從 arc01–04 的平均 76 字脹到 arc09–11 的 194 字（最長 645），
    括號內註解佔比 36.1% → 51.9%，全程無人示警。

    兩個信號分別對應兩個成長機制：**內容長**＝重抄（fold 覆蓋逼出的前情提要效應）、
    **括號佔比**＝夾帶（伏筆狀態／裁決理由／排除線塞進唯一會被 write 讀到的欄位）。
    """
    # (路徑, 是否只認 `## 本章事實` 區塊)。章衍生檔一定要限定區塊——「## 待裁決
    # 回饋」底下也是 `- ` 開頭，全檔掃會誤報；參照/ 底下的檔沒有區塊標題，全檔掃。
    targets: list[tuple[Path, bool]] = []
    chapters = book / "chapters"
    if chapters.is_dir():
        targets += [(p, True) for p in sorted(chapters.glob("ch*" + AI_SUFFIX))]
    ref = book / "story" / "參照"
    if ref.is_dir():
        targets += [
            (p, False)
            for p in sorted(ref.glob("*.md"))
            if _base_stem(p) in APPEND_LOG_STEMS
        ]

    out: list[Finding] = []
    for p, sectioned in targets:
        text = p.read_text(encoding="utf-8")
        if sectioned:
            lines = _fact_lines(text)
        else:
            lines = [
                (i, ln.strip())
                for i, ln in enumerate(text.splitlines(), start=1)
                if ln.strip().startswith("- 幕")
            ]
        # 量的是**內容欄**（信封第四欄），與 fact-lint 同一把尺。第一個全形冒號
        # 是 token/內容的分隔（見 事實流.schema.md 信封格式）。
        bodies = [(i, ln.split("：", 1)[-1]) for i, ln in lines if "：" in ln]
        long_hits = [(i, b) for i, b in bodies if len(b) > limit]
        paren_hits = [
            (i, b)
            for i, b in bodies
            if len(b) >= FACT_PAREN_MIN_CHARS
            and sum(len(m) for m in _PAREN_RE.findall(b)) / len(b) > ratio
        ]
        if long_hits:
            worst_no, worst = max(long_hits, key=lambda t: len(t[1]))
            out.append(
                Finding(
                    kind="事實行肥大",
                    path=p,
                    detail=f"{len(long_hits)} 行的內容欄超過 {limit} 字"
                    f"（最長 {len(worst)} 字，第 {worst_no} 行）",
                    hint="delta 只寫這一幕改變了什麼；仍然成立的舊事不必重抄"
                    "（查得到：fact-project --history <實體>/<維度>）",
                )
            )
        if paren_hits:
            out.append(
                Finding(
                    kind="事實行夾帶",
                    path=p,
                    detail=f"{len(paren_hits)} 行的括號註解佔比超過 {ratio:.0%}"
                    f"（最早在第 {paren_hits[0][0]} 行）",
                    hint="伏筆埋／收屬幕綱、裁決理由屬 story/參照/裁決流.md、"
                    "下游排除線屬 story/物件/<實體>.md 的「## 不得寫成什麼」",
                )
            )
    return out


# 各 hint 指定的搬移目的地。舊名一併吃（既有書不必為改名動書內檔）。
DESTINATIONS: dict[str, tuple[str, ...]] = {
    "story/參照/裁決流.md": ("story/參照/裁決流.md", "story/參照/裁決流.co.md"),
    "story/參照/待裁決.md": ("story/參照/待裁決.md",),
    "story/物件/": ("story/物件",),
}


def missing_destinations(book: Path, findings: list[Finding]) -> list[Finding]:
    """**每一個「搬去 X」的建議，發建議前先檢查 X 在不在**（`設計原則.md` E1 新推論）。

    實測一世之尊：`derived-sync check` 的 229 行輸出裡有 37 行叫人把東西搬進
    `裁決流`，而那本書**沒有那支檔**。它不是假陰性（守衛確實在報），也不是單純的
    警報疲勞（建議本身沒錯）——**它是「報得沒錯但照做會失敗」**：箭頭指向空氣，
    而箭頭本身格式完全合法。三種都導致人不看，機制不同（→ 功能 14）。

    形狀複製自 `beat_metrics/lint.py` 的設計註目的地檢查（02 重構輪）。**工具間
    零相依（所有 tools/*/pyproject.toml 皆 dependencies = []），故複製而非 import**
    ——這是第 7 份同類複製（spine 4、伏筆 regex 3），該不該收斂交功能 14。

    **只在真的有內容要搬時才報**：沒有任何 hint 命中某個目的地，就不提它。
    一支乾淨的書不該因為「你沒有裁決流」而被念。
    """
    out: list[Finding] = []
    for label, candidates in DESTINATIONS.items():
        hits = [f for f in findings if label in f.hint]
        if not hits:
            continue
        if any((book / c).exists() for c in candidates):
            continue
        kinds = "、".join(sorted({f.kind for f in hits}))
        out.append(
            Finding(
                kind="目的地不存在",
                path=book / label,
                detail=f"{len(hits)} 筆建議要搬進 `{label}`，但這本書沒有它（{kinds}）",
                hint=f"照 `書本模板/{label}` 的骨架先建一支；"
                "搬移工作流是斷的時候，那些內容不會消失，只會繼續寄生在原地"
                "（實測：理由滲進幕綱八欄、行動欄從 76 字/幕 長到 513 字/幕）",
            )
        )
    return out


def run(book: Path) -> list[Finding]:
    findings = (
        beat_sheet_density(book)
        + oversized_sources(book)
        + unsliceable_derived(book)
        + long_lines(book)
        + bloated_fact_lines(book)
    )
    return findings + missing_destinations(book, findings)
