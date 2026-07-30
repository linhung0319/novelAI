"""**「這本書有哪些受管檔」的唯一真相。**

**為什麼要有這支檔（2026-07-28 功能 14）。** 在它之前，這個答案散在
`sentinel.py` 五支掃描器裡**各自手寫的路徑清單**，而那個形狀被**十次診斷各自報過
一次**「第 N 次手寫路徑清單漏檔」，**每一次的處置都是「各補各的、根因不修」**：

| 第幾次 | 誰補的 | 漏的是什麼 | 靜音了多少 |
|---|---|---|---|
| 1–2 | 功能 03 | `chapters/` | `_index.ai.md` 50,782 B ＝門檻的 4.2×、單行 2,235 字元 |
| 3–5 | 功能 05 | 設定層非 rollup 的衍生檔與源檔 | 單行 1,155／1,072 字元 |
| 6 | 功能 08 | `story/00-摘要.{md,ai.md}` | 源 15,656 B、衍生 10,530 B ＝門檻的 87.8% |
| 7 | 功能 09 | **整個大綱軸** | 6/12 支超過 25,000 B（最大 44,307） |
| 8 | 功能 10 | `story/參照/` | **292,591 B，全書最大的一支檔** |
| 9 | 功能 12 | `story/幕綱/_index.md` | 28,013 B、9 行超過 400、最長 1,949 |

**第九次的性質變了**：漏的檔**就在 `beat_sheet_density` 每次都會 `glob` 進去的那個
資料夾裡**，而且有一支**綠色的測試**（`test_non_arc_files_in_beat_dir_ignored`）把
「一支 50,000 漢字的 `_index.md` 什麼都不會觸發」釘成了預期行為。也就是說手寫清單的
失效模式已經從「遺漏」升級成「**即使人在現場、即使有一支綠色的測試，也會漏**」。

**根因有兩半，本檔只是其中一半**：
1. **清單散成五份** → 收成這一份；
2. **哨兵是全系統唯一沒有覆蓋率行的守衛** → `SentinelStats`（見 `sentinel.py`）。
   **十次漏檔每一次都會被那一行當場抓到**（例：`story/大綱/` 不在名單時，那一行
   會印「大綱 0 支」）。**第 2 半才是決定性的**——一份清單仍然可能漏，但一個印
   「0 支」的覆蓋率行會讓漏變得看得見。

**豁免要寫成豁免哪一項檢查，不能豁免整支檔**（`設計原則.md` E2 第七形態），而且
**「刻意不受管」與「忘了加」在清單上要長得不一樣**（功能 13 為 `raw/` 立的先例）
——所以豁免的那幾軸在本表裡**有列**，帶 `exempt` 與理由，並且會印進覆蓋率行。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .core import AI_SUFFIX
from .validate import (
    SETTINGS_KINDS,
    SUMMARY_DERIVED,
    SUMMARY_DIR,
    SUMMARY_SOURCE,
)

# ---------------------------------------------------------------- 門檻
#
# 門檻皆為**建議值**（advisory），不是門檻式 pass/fail——呼應「AI 是審稿員不是門檻」。
# 取值依據見 `sentinel.py` 各函式 docstring；**本檔只負責「掃哪些檔」，不負責「多大算大」**。
# 取自實測分佈：健康的落在 1378–2211 B/幕（一世之尊 arc01–arc04、芯片巫師全三段、
# harry_potter），漂移的從 2872 起跳並一路升到 9113。2500 是這兩群之間的空隙。
BEAT_BYTES_PER_BEAT = 2500  # 幕綱：每幕位元組
# 源：單檔（或單一角色目錄總和）絕對上限（約 8000 漢字）。**用絕對門檻，不用
# 「同層中位數的 N 倍」**——承重角色的設定檔本來就該比路人厚，中位數會被一堆
# 小角色拉低，於是主角每次都被報。功能 09 複核：11 支 arcNN 的分佈是 4,848…
# 21,836／33,468…44,307，**21,836 → 33,468 之間有空隙，25,000 正好落在裡面**（n=11）。
SOURCE_BYTES = 25000
# 衍生 `.ai.md`：無切片工具，且應是源的壓縮，故更嚴（約 4000 漢字）。
DERIVED_BYTES = 12000
# 綜合檔單行（單一表格 cell）字元數。參照值：一世之尊就緒儀表最長單一 cell
# 約 10,000 字元（≈24KB）。
LINE_CHARS = 2000
# rollup 一列＝一行摘要，比綜合檔嚴得多（schema 說那一欄是「一行需求」，
# 實測被寫成 800–1000 字元的整段補厚紀錄）。
ROLLUP_LINE_CHARS = 400
# 設定層**非 rollup** 檔的單行（2026-07-27 功能 05 補上）。分析段落天生比 rollup 的
# 一列長（「限制與代價」那種一條就是一段），所以不套 400；但也不能沒有門檻——實測
# `江湖勢力.ai.md` 單行 1,155 字元（rollup 門檻的 2.9×）一聲沒吭地長了八次重生。
#
# **兩個門檻皆取自實測分佈的空隙，樣本 n=4（一世之尊四支世界觀主題），是暫定值**：
#   衍生最長行 671／690／1,072／1,155 → 800 落在 690 與 1,072 之間
#   源檔最長行 372／375／430／575     → 600 落在 430 與 575 之上的空隙
# 取法與 `BEAT_BYTES_PER_BEAT` 的 2,500 一致（「兩群之間的空隙」）。**第二本書有
# 設定層之後要重取**——n=4 的分佈不足以定一個跨書門檻，見 `世界觀.schema.md`。
SETTINGS_DERIVED_LINE_CHARS = 800
SETTINGS_SOURCE_LINE_CHARS = 600

# 有投影工具可切片的檔——**檔案大小**不受規範（行長仍受）。含各代舊檔名。
# 2026-07-30（驗證輪階段 1c）移除 `裁決流.co`：`.co.md` 這個檔類 2026-07-27 廢除，
# 而它的豁免活到今天；實測 0 本書有它。與 `sentinel.APPEND_LOG_STEMS` 一起收。
APPEND_LOG_STEMS = frozenset({"事實流", "狀態事件流", "裁決流"})

OUTLINE_FULL = ("story", "01-大綱.md")
OUTLINE_DIR = ("story", "大綱")
OUTLINE_INDEX = "_index.md"
OUTLINE_RETIRED = "_已併入"
BEAT_DIR = ("story", "幕綱")
# `_順序.md` 是活的（spine，A1 源）；`_index.md` 是 2026-07-28 功能 12 廢除的 rollup。
# **兩支都要量體積**（見 `beat_index`）——活的那一支才是新書會長大的那一支。
BEAT_SPINE = "_順序.md"
BEAT_INDEX = "_index.md"
REFERENCE_DIR = ("story", "參照")
CHAPTERS_DIR = "chapters"


def base_stem(p: Path) -> str:
    """去掉 `.ai.md` 或 `.md`，取實體名。`就緒儀表.ai.md` → `就緒儀表`。"""
    name = p.name
    if name.endswith(AI_SUFFIX):
        return name[: -len(AI_SUFFIX)]
    return p.stem


# ---------------------------------------------------------------- 軸的定義


@dataclass(frozen=True)
class Axis:
    """一個受管軸。`label` 會逐字出現在覆蓋率行上，所以它就是這一軸的名字。

    `exempt` 非空 ＝ **刻意不受這一項管**，而它**仍然要印**（帶理由）。空字串
    ＝正常受管。
    """

    label: str
    exempt: str = ""


# 體積（`oversized_sources`／`unsliceable_derived`）的軸
SIZE_AXES: tuple[Axis, ...] = (
    Axis("幕綱"),
    Axis("設定層源"),
    Axis("設定層衍生"),
    Axis("章衍生"),
    Axis("大綱"),
    Axis("參照"),
    Axis("摘要"),
    Axis("幕綱索引"),
    # **明文豁免，不是漏了加**（2026-07-28 功能 14 補上這一列；功能 14 診斷的 V14）。
    # 13 為 `raw/` 立這個先例時的理由逐字適用：「刻意不受管」與「忘了加」在清單上
    # 要長得不一樣。實測一世之尊 93 章正文源最大 15,363 B < `SOURCE_BYTES` 25,000
    # ——**補上去會報 0**，所以正解是寫明豁免。
    Axis("正文源", exempt="體積·實測 93 章最大 15,363 B < 25,000，補上去報 0"),
    # 功能 13 已拍板：raw 的豁免是「查詢入口」也是「體積」。
    # n=5 的資料夾總和分佈是 1,683／3,115／7,236／12,110／74,278 B，
    # **空隙寬到任何門檻值都是任意的**；真正的成本是「誰整批讀它」，
    # 已由 `共同約定.md` 八 的兩段式讀取契約解掉。
    Axis("raw", exempt="全部·功能 13 拍板，成本是「誰整批讀它」不是「檔多大」"),
)


def settings_dirs(book: Path) -> list[tuple[str, Path]]:
    """設定層的三個 kind 資料夾（存在的才回）。"""
    out = []
    for kind in SETTINGS_KINDS:
        d = book / "story" / "設定" / kind
        if d.is_dir():
            out.append((kind, d))
    return out


def summary_paths(book: Path) -> tuple[Path, Path]:
    """摘要軸的兩支檔。路徑常數的擁有者是 `validate.py`（那裡是格式的擁有者）。"""
    d = book.joinpath(*SUMMARY_DIR)
    return d / SUMMARY_SOURCE, d / SUMMARY_DERIVED


def outline_sources(book: Path) -> list[Path]:
    """全書版 ＋ **未退役的** scoped 大綱檔。

    `_已併入/` 是退役源的家（`設計原則.md` A5），**刻意不掃**：它已經不是權威、
    也不該再長，對它報「檔太大」只是雜訊。
    """
    out: list[Path] = []
    full = book.joinpath(*OUTLINE_FULL)
    if full.is_file():
        out.append(full)
    d = book.joinpath(*OUTLINE_DIR)
    if d.is_dir():
        out += [p for p in sorted(d.glob("*.md")) if not p.name.startswith("_")]
    return out


def outline_index(book: Path) -> Path | None:
    p = book.joinpath(*OUTLINE_DIR, OUTLINE_INDEX)
    return p if p.is_file() else None


def beat_arcs(book: Path, arc_re) -> list[Path]:
    """`story/幕綱/arcNN.md`（`_index.md`／`_順序.md` 不算——它們走 `beat_index`）。"""
    d = book.joinpath(*BEAT_DIR)
    if not d.is_dir():
        return []
    return [p for p in sorted(d.glob("*.md")) if arc_re.match(p.stem)]


def beat_index(book: Path) -> list[Path]:
    """`story/幕綱/` 底下**非 arc 檔**的那幾支：`_順序.md`（活的）＋`_index.md`（已廢除）。

    **2026-07-30（驗證輪階段 1c）從單支改成清單。** 在此之前它只認 `_index.md`，
    而 2026-07-28 功能 12 把 spine 搬進 `_順序.md` 之後，**活的那一支反而沒有任何
    體積哨兵**——這正是本函式當初補上時記的「第九次四份手寫路徑清單漏檔」，
    **在同一個資料夾裡復發了一次，只是換了檔名**。
    """
    d = book.joinpath(*BEAT_DIR)
    return [p for n in (BEAT_SPINE, BEAT_INDEX) if (p := d / n).is_file()]


def reference_sources(book: Path) -> list[Path]:
    """`story/參照/` 底下**非 append log** 的檔（就緒／結構／各代舊名）。"""
    d = book.joinpath(*REFERENCE_DIR)
    if not d.is_dir():
        return []
    return [p for p in sorted(d.glob("*.md")) if base_stem(p) not in APPEND_LOG_STEMS]


def reference_logs(book: Path) -> list[Path]:
    """`story/參照/` 底下的 append log（事實流／裁決流／各代舊名）。"""
    d = book.joinpath(*REFERENCE_DIR)
    if not d.is_dir():
        return []
    return [p for p in sorted(d.glob("*.md")) if base_stem(p) in APPEND_LOG_STEMS]


def chapter_sources(book: Path) -> list[Path]:
    """`chapters/chNNNN.md`。**體積刻意豁免**（見 `SIZE_AXES`），但要數得出來
    ——一個豁免要能回答「它豁免了幾支」，否則它與「掃描器根本走不進去」不可分辨。
    """
    d = book / CHAPTERS_DIR
    if not d.is_dir():
        return []
    return [
        p
        for p in sorted(d.glob("ch*.md"))
        if not p.name.endswith(AI_SUFFIX) and not p.name.startswith("_")
    ]


def chapter_derived(book: Path) -> list[Path]:
    d = book / CHAPTERS_DIR
    if not d.is_dir():
        return []
    return sorted(d.glob(f"*{AI_SUFFIX}"))


def raw_files(book: Path) -> list[Path]:
    """`raw/` 底下的檔。**全部豁免**（功能 13 拍板），這裡只負責數得出來。"""
    d = book / "raw"
    if not d.is_dir():
        return []
    return sorted(p for p in d.rglob("*.md") if p.is_file())
