from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .book_layout import (
    APPEND_LOG_STEMS,
    BEAT_BYTES_PER_BEAT,
    DERIVED_BYTES,
    LINE_CHARS,
    OUTLINE_DIR,
    OUTLINE_INDEX,
    ROLLUP_LINE_CHARS,
    SETTINGS_DERIVED_LINE_CHARS,
    SETTINGS_SOURCE_LINE_CHARS,
    SIZE_AXES,
    SOURCE_BYTES,
    base_stem,
    beat_arcs,
    beat_index,
    chapter_derived,
    chapter_sources,
    outline_index,
    outline_sources,
    raw_files,
    reference_logs,
    reference_sources,
    settings_dirs,
    summary_paths,
)
from .core import AI_SUFFIX
from .md import BEAT_HEAD_RE
from .validate import SUMMARY_KIND, enum_for, stray_sections

# **門檻與路徑清單的擁有者是 `book_layout.py`**（2026-07-28 功能 14）。在此之前
# 五支掃描器各自手寫路徑，而那個形狀被十次診斷各自報過一次「第 N 次手寫路徑清單
# 漏檔」——**每一次的處置都是「各補各的、根因不修」**（明細見 `book_layout.py`）。
#
# 哨兵量的是**「必須整檔讀的東西有多大」**，不是「檔多大」（`共同約定.md` 零）：
# 有投影工具可切片的檔（約束表／裁決流，以及舊格式的事實流）**檔案大小**不受規範。
#
# **但「有投影工具」不豁免行長**：投影的粒度**就是行**，一行不可再切。2026-07-27
# 前這裡曾整支檔豁免，於是實測 1,728 字的單一事件行一聲沒吭地長了 11 個 arc
# （見 `結構定義/事實流.schema.md`）。故行長改為一律受管，只是門檻不同。
#
# 事實行量的是**內容欄**（信封第四欄），與 `fact-lint` 同一把尺，只是門檻更早：
# 哨兵 120（≈1.6× 健康均值）先示警，`fact-lint` 200 才擋。
FACT_LINE_CHARS = 120
FACT_PAREN_RATIO = 0.40  # 括號內註解佔比（夾帶設計註的信號）
FACT_PAREN_MIN_CHARS = 60

_ARC_RE = re.compile(r"^arc[0-9A-Za-z]+$")



# **十次「手寫路徑清單漏檔」的沿革搬進 `book_layout.py` 了**（2026-07-28 功能 14）。
# 本檔從此只回答「多大算大」，不回答「掃哪些檔」——後者的唯一真相在那支檔，
# 而**它印得出「我掃了幾支」**（`SentinelStats`）。那一行才是這十次漏檔的真正解藥：
# 一份清單仍然可能漏，但一個印「大綱 0 支」的覆蓋率行會讓漏變得看得見。


@dataclass
class SentinelStats:
    """**我在這本書上掃了幾支。**（`設計原則.md` E2 的可執行推論，**0 也印**。）

    **成長哨兵曾是全系統唯一沒有覆蓋率行的守衛**（功能 14 的 V3）：`_print_sentinel`
    在 0 筆時直接 `return`，而且它從不印「我掃了幾支檔」。實測射程——一世之尊 282 支
    `.md` 中 **184 支在射程內、98 支在射程外**，**644,577 B ＝全書 24.9% 完全靜音，
    而 `check` 的結語是「0 個需處理」**。

    **十次漏檔每一次都會被這一行當場抓到**：`story/大綱/` 不在名單時，這一行會印
    「大綱 0 支」；`story/幕綱/_index.md` 不在名單時，會印「幕綱索引 0 支」。

    **豁免的那幾軸也要印**（E2 第七形態＋功能 13 的先例）：「刻意不受管」與「忘了加」
    在清單上要長得不一樣，所以 `正文源`／`raw` 印的是「N 支·刻意豁免（理由）」。
    """

    size: dict[str, int] = field(default_factory=dict)
    lines_scanned: int = 0
    fact_files: int = 0
    fact_lines: int = 0
    destinations: int = 0
    destinations_missing: int = 0

    def count(self, label: str, n: int = 1) -> None:
        self.size[label] = self.size.get(label, 0) + n

    def render(self) -> str:
        cells = []
        for axis in SIZE_AXES:
            n = self.size.get(axis.label, 0)
            cells.append(
                f"{axis.label} {n}（**刻意豁免**：{axis.exempt}）"
                if axis.exempt
                else f"{axis.label} {n}"
            )
        return (
            "掃描範圍：體積 " + "／".join(cells) + "；"
            f"行長 {self.lines_scanned} 支；"
            f"事實行 {self.fact_files} 支檔·{self.fact_lines} 行；"
            f"搬移目的地 {self.destinations} 個（**{self.destinations_missing} 個不存在**）"
        )


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


def _size(p: Path) -> int:
    return len(p.read_text(encoding="utf-8").encode("utf-8"))


def beat_sheet_density(
    book: Path, limit: int = BEAT_BYTES_PER_BEAT, stats: SentinelStats | None = None
) -> list[Finding]:
    """幕綱該正比於幕數。明顯超出＝設計理由滲進了檔案。

    門檻取自實測分佈：健康的落在 1378–2211 B/幕（一世之尊 arc01–arc04、芯片巫師
    全三段、harry_potter），漂移的從 2872 起跳並一路升到 9113（一世之尊 arc05 之後）。
    2500 是這兩群之間的空隙。

    **`_ARC_RE` 濾掉 `_index.md` 是對的，但那不代表沒有人該量它**（2026-07-28
    功能 12）：這支函式量的是 B/幕，而索引檔沒有 `## 幕NNN`，除以零沒有意義。
    問題是**在功能 12 之前沒有第二支函式接手**——於是「幕綱資料夾裡一支 28,013 B
    的檔什麼都不會觸發」變成一條被 `test_non_arc_files_in_beat_dir_ignored`
    背書的行為。現在體積歸 `oversized_sources`、行長歸 `long_lines`，
    兩支都走 `_beat_index()`（見那裡的第九次漏檔紀錄）。
    """
    out: list[Finding] = []
    st = stats if stats is not None else SentinelStats()
    for p in beat_arcs(book, _ARC_RE):
        st.count("幕綱")
        text = p.read_text(encoding="utf-8")
        beats = sum(1 for ln in text.splitlines() if BEAT_HEAD_RE.match(ln))
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


def oversized_sources(
    book: Path, limit: int = SOURCE_BYTES, stats: SentinelStats | None = None
) -> list[Finding]:
    """人管·源必須整檔讀，故單檔（或單一角色目錄）不該無限長。

    **用絕對門檻，不用「同層中位數的 N 倍」**：承重角色的設定檔本來就該比路人厚，
    中位數會被一堆小角色拉低，於是主角每次都被報——那是雜訊，不是缺陷。

    刻意**不建議「只讀一部分」**——那會把自由格式的源檔逼成有 schema 的東西；
    正解是升級成目錄形態（角色）或拆主題（世界觀）。
    """
    out: list[Finding] = []
    st = stats if stats is not None else SentinelStats()
    # **豁免的兩軸也要數**（E2 第七形態＋功能 13 的先例）：一個豁免要能回答
    # 「它豁免了幾支」，否則它與「掃描器根本走不進去」不可分辨。
    st.count("正文源", len(chapter_sources(book)))
    st.count("raw", len(raw_files(book)))
    for _kind, d in settings_dirs(book):
        for entry in sorted(d.iterdir()):
            if entry.is_dir():
                # 目錄形態：切面總和過大＝這個角色本身該再拆，不是切面不夠
                st.count("設定層源")
                facets = sorted(entry.glob("*.md"))
                size = sum(_size(f) for f in facets)
                hint = (
                    f"已是目錄形態（{len(facets)} 個切面）仍過大——"
                    "檢查是否有 AI 產物（裁決紀錄／正文既成事實）誤寫進源檔"
                )
            elif entry.suffix == ".md" and not entry.name.endswith(AI_SUFFIX) and not entry.name.startswith("_"):
                st.count("設定層源")
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
    src, _ = summary_paths(book)
    if src.is_file():
        st.count("摘要")
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
    for p in outline_sources(book):
        st.count("大綱")
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
    # `story/參照/` 的非 append-log 檔（2026-07-28 功能 10 補上，見 `_reference_sources`）。
    # **hint 與前四類都不同**：這裡沒有「拆」也沒有「升級形態」可做——這個資料夾裝的
    # 是綜合檔，它變大**一定**是因為裝了別人的東西（實測 `就緒儀表.md` 53.8% 是拍板
    # 日誌、27.5% 是 `derived-sync check` 當場算得出來的東西、20.9% 是 transient TODO）。
    for p in reference_sources(book):
        st.count("參照")
        size = _size(p)
        if size > limit:
            out.append(
                Finding(
                    kind="源檔肥大",
                    path=p,
                    detail=f"{size} B（建議 ≤{limit}）",
                    hint="`story/參照/` 的綜合檔**沒有拆檔也沒有升級形態這條路**，"
                    "所以只有搬：作者拍板的理由與已駁回方案屬 "
                    "story/參照/裁決流.md（`標的`＝該綜合檔）；"
                    "「`derived-sync check` 全 fresh」「本輪動檔」「下一步」**直接刪**"
                    "（工具當場重算／transient TODO）；成熟度判斷屬 "
                    "story/參照/就緒.md 的五 token 狀態格，"
                    "而「哪個 arc 下沉到哪一層」「幾筆待裁決」一律跑 "
                    "`readiness`／`decision-project`，不落檔。"
                    "**搬之前先印保真率交作者確認**（見 `就緒.schema.md`）",
                )
            )
    # `story/幕綱/_index.md`（2026-07-28 功能 12 補上，見 `_beat_index`）。**hint 與前
    # 五類都不同**：這支檔一開始就只該裝「每支 arc 一列」，而實測 18 行裡 11 行是 arc
    # 概覽散文（平均 969 字元、最長 1,949），另有一行 652 字元的檔頭沿革與一行 310
    # 字元的選用結構公式複本——**三種東西，三個不同的家，一支檔**。
    bi = beat_index(book)
    if bi is not None:
        st.count("幕綱索引")
        size = _size(bi)
        if size > limit:
            out.append(
                Finding(
                    kind="源檔肥大",
                    path=bi,
                    detail=f"{size} B（建議 ≤{limit}）",
                    hint="幕綱索引**沒有拆檔也沒有升級形態這條路**——它是視圖，"
                    "一支 arc 一列就該是全部。變大一定是裝了別人的東西："
                    "arc 概覽散文的權威是 `story/幕綱/arcNN.md` 自己（全書視圖跑 "
                    "`beat-lint --emit`，別在這裡抄第二份）；選用結構公式屬大綱的 "
                    "`## 選用結構公式`（本檔只指路）；帶日期的沿革屬 "
                    "story/參照/裁決流.md（`標的`＝該索引檔），進度跑 `readiness`；"
                    "`全書順序：` 那一行屬同層的 `_順序.md`（A1 源，`beat-lint` 守）",
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
    for kind, d in settings_dirs(book):
        out += [(p, kind) for p in sorted(d.glob(f"*{AI_SUFFIX}"))]
    out += [(p, "章節") for p in chapter_derived(book)]
    # **2026-07-27（功能 08）補上摘要衍生檔**——第六次補同一個根因（見 `_summary_paths`）。
    # 實測 10,530 B ＝ `DERIVED_BYTES` 的 87.8%，而它還帶著 04 早就該搬走的
    # `## 待裁決回饋`（818 字元）：**兩個觸發都成立而兩個都靜音**。
    _, derived = summary_paths(book)
    if derived.is_file():
        out.append((derived, SUMMARY_KIND))
    return out


def unsliceable_derived(
    book: Path, limit: int = DERIVED_BYTES, stats: SentinelStats | None = None
) -> list[Finding]:
    """衍生 `.ai.md` 沒有任何切片工具，故不享有「可以很大」的豁免。

    見 `共同約定.md` 零的資格條款。兩個獨立觸發：

    1. **枚舉外的節**——內容找不到家而寄生在此。實測三種：「硬事實」「反派備註」
       「下游硬約束」（屬 `事實流.md` 的錨／約束），以及檔末的裁決 blockquote
       （屬 `裁決流.md`）。這一項不論大小都報，因為它是分類錯誤不是體積問題。
    2. **超過門檻**——衍生應是源的壓縮，比源檔門檻更嚴。
    """
    out: list[Finding] = []
    st = stats if stats is not None else SentinelStats()
    for p, kind in _derived_targets(book):
        st.count("章衍生" if kind == "章節" else "設定層衍生")
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
    stats: SentinelStats | None = None,
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
    - **`story/幕綱/_index.md`（2026-07-28 功能 12 補上，見 `_beat_index`）**
      → 同 `rollup_limit`（400），與 `大綱/_index.md` 同一把尺（兩支都是
      「視圖 ≡ 資料夾」形狀而不帶 `.ai.md` 的索引）。實測 9 行超過 400、
      最長 1,949——**第九次漏檔，而這次漏的檔就在既有函式已經走進去的資料夾裡**。

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
    # 依 base stem 判斷，才能同時吃到新命名（就緒儀表.ai.md）與既有書的舊命名
    targets += [(p, limit) for p in reference_sources(book)]
    for _kind, d in settings_dirs(book):
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
    targets += [
        (p, rollup_limit) for p in chapter_derived(book) if p.name.startswith("_")
    ]
    # **摘要兩支檔（2026-07-27 功能 08 補上）沿用設定層的兩級門檻**，不新造第五級：
    # 衍生是分析段落（同 `<主題>.ai.md` 的「限制與代價」，天生比 rollup 的一列長）、
    # 源是自由散文，性質與設定層那兩類相同。實測衍生最長行 626、源最長行 594
    # ——**兩者都只差門檻一點點**，那正是要它們進目標集的理由，不是放它們走的理由。
    # 另：`n=1` 的樣本不足以另立門檻（06 抉擇 5 A 已駁回「沒有空隙時硬定數字」）。
    summary_src, summary_derived = summary_paths(book)
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
    for p in outline_sources(book):
        targets.append((p, settings_source_limit))
        outline.add(p)
    oi = outline_index(book)
    if oi is not None:
        targets.append((oi, rollup_limit))
        outline.add(oi)
    # **幕綱索引（2026-07-28 功能 12 補上）套 rollup 那一級（400），不新造門檻**：
    # 它與 `大綱/_index.md` 是同一種檔（「視圖 ≡ 資料夾」形狀、不帶 `.ai.md`）。
    # 實測 18 行裝 11,780 字元（平均 654 字元/行）、9 行超過 400、最長 1,949。
    # **hint 要另立一個 set，不能靠 limit 判**——400 已經同時給設定層 rollup、
    # `chapters/_index.ai.md` 與 `大綱/_index.md` 用，limit 分不出病徵。
    beat_index_targets: set[Path] = set()
    bi = beat_index(book)
    if bi is not None:
        targets.append((bi, rollup_limit))
        beat_index_targets.add(bi)

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
    # 幕綱索引的病徵是**一列 arc 概覽長成整個 arc 的第三版改寫**（實測那 11 列對
    # 同名 `arcNN.md` 的 8-gram 保真率只有 4.2–35.8%——它不是摘要，是走樣的複本），
    # 不是「表格 cell 被當日誌用」也不是「一份沿革被塞進一行」，所以 hint 分開寫。
    beat_index_hint = (
        "索引的一列只寫「這個 arc 的幕號範圍與號段」，**不複述這個 arc 演了什麼**"
        "——那是 `story/幕綱/arcNN.md` 自己的內容，全書視圖跑 `beat-lint --emit`"
        "（實測這裡的 arc 概覽對同名 arc 檔的 8-gram 保真率只有 4.2–35.8%，"
        "它已經漂成第二份真相）。選用結構公式屬大綱的 `## 選用結構公式`（本檔只指路）；"
        "帶日期的沿革屬 story/參照/裁決流.md（`標的`＝該索引檔）"
    )
    settings_limits = {settings_derived_limit, settings_source_limit}
    st = stats if stats is not None else SentinelStats()
    st.lines_scanned += len(targets)
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
                        beat_index_hint
                        if p in beat_index_targets
                        else outline_hint
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
    stats: SentinelStats | None = None,
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
    targets: list[tuple[Path, bool]] = [
        (p, True) for p in chapter_derived(book) if p.name.startswith("ch")
    ]
    targets += [(p, False) for p in reference_logs(book)]

    out: list[Finding] = []
    st = stats if stats is not None else SentinelStats()
    st.fact_files += len(targets)
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
        st.fact_lines += len(lines)
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


def missing_destinations(
    book: Path, findings: list[Finding], stats: SentinelStats | None = None
) -> list[Finding]:
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
    st = stats if stats is not None else SentinelStats()
    st.destinations += len(DESTINATIONS)
    for label, candidates in DESTINATIONS.items():
        hits = [f for f in findings if label in f.hint]
        if not hits:
            continue
        if any((book / c).exists() for c in candidates):
            continue
        st.destinations_missing += 1
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


def run(book: Path) -> tuple[list[Finding], SentinelStats]:
    """回 (findings, 覆蓋率)。**兩個回傳值都要印**（`設計原則.md` E2）。

    在 2026-07-28（功能 14）之前這支只回 findings，而 `cli._print_sentinel` 在 0 筆
    時直接 `return`——於是「哨兵掃了 0 支檔」與「哨兵掃過而一切正常」印出來**完全
    相同**。十次「手寫路徑清單漏檔」每一次都落在前者。
    """
    stats = SentinelStats()
    findings = (
        beat_sheet_density(book, stats=stats)
        + oversized_sources(book, stats=stats)
        + unsliceable_derived(book, stats=stats)
        + long_lines(book, stats=stats)
        + bloated_fact_lines(book, stats=stats)
    )
    return findings + missing_destinations(book, findings, stats), stats
