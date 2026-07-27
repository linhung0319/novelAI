from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .core import AI_SUFFIX
from .validate import SETTINGS_KINDS, enum_for, stray_sections

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
# 事實行量的是**內容欄**（信封第四欄），與 `fact-lint` 同一把尺，只是門檻更早：
# 哨兵 120（≈1.6× 健康均值）先示警，`fact-lint` 200 才擋。
FACT_LINE_CHARS = 120
FACT_PAREN_RATIO = 0.40  # 括號內註解佔比（夾帶設計註的信號）
FACT_PAREN_MIN_CHARS = 60

_ARC_RE = re.compile(r"^arc[0-9A-Za-z]+$")
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
                hint = (
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
    for kind in SETTINGS_KINDS:
        d = book / "story" / "設定" / kind
        if not d.is_dir():
            continue
        for p in sorted(d.glob(f"*{AI_SUFFIX}")):
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
                        hint="正文釘死的事實（錨）屬該章 chNNNN.ai.md 的「## 本章事實」；下游硬約束與揭示層級屬 story/物件/<名>.md；裁決理由屬 裁決流.co.md。衍生檔只留 schema 定義的節",
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
    book: Path, limit: int = LINE_CHARS, rollup_limit: int = ROLLUP_LINE_CHARS
) -> list[Finding]:
    """單行過長＝狀態格／表格 cell 被當事件日誌用。

    掃兩處，門檻不同：
    - `story/參照/` 的綜合檔（就緒儀表／結構）→ `limit`。參照值：一世之尊
      就緒儀表最長單一 cell 約 10,000 字元（≈24KB）。
    - 設定層 rollup（`_index.ai.md`／`_總覽.ai.md`）→ `rollup_limit`。schema 說
      那一欄是「一行需求」，實測被寫成 800–1000 字元的整段補厚紀錄，等於讓
      rollup 變成第二份真相。

    事實流／裁決流是 append log，有投影工具、且天生一行一筆——不受此限。
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
        if d.is_dir():
            targets += [(p, rollup_limit) for p in sorted(d.glob(f"_*{AI_SUFFIX}"))]

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
                    hint="狀態格／rollup 一列只報摘要；沿革與裁決記錄屬 裁決流.md，不該住在表格 cell 裡",
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
                    hint="伏筆埋／收屬幕綱、裁決理由屬 裁決流.co.md、"
                    "下游排除線屬 story/物件/<實體>.md 的「## 不得寫成什麼」",
                )
            )
    return out


def run(book: Path) -> list[Finding]:
    return (
        beat_sheet_density(book)
        + oversized_sources(book)
        + unsliceable_derived(book)
        + long_lines(book)
        + bloated_fact_lines(book)
    )
