from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .core import AI_SUFFIX

# 門檻皆為**建議值**（advisory），不是門檻式 pass/fail——呼應「AI 是審稿員不是門檻」。
# 取值依據見各函式 docstring，全部可由 CLI 覆寫。
BEAT_BYTES_PER_BEAT = 2500  # 幕綱：每幕位元組
SOURCE_BYTES = 25000  # 源檔：單檔絕對上限（約 8000 漢字）
LINE_CHARS = 2000  # 綜合檔：單行（單一表格 cell）字元數

_ARC_RE = re.compile(r"^arc[0-9A-Za-z]+$")
_BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)")


@dataclass(frozen=True)
class Finding:
    kind: str
    path: Path
    detail: str
    hint: str


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
                    hint="設計理由（母題論證／判例／本輪拍板）該在檔尾設計註或決策日誌，不在幕的欄位裡",
                )
            )
    return out


def oversized_sources(book: Path, limit: int = SOURCE_BYTES) -> list[Finding]:
    """人管·源靠「一實體一檔、檔名即選擇器」控制大小；單檔過大＝該拆檔。

    **用絕對門檻，不用「同層中位數的 N 倍」**：承重角色的設定檔本來就該比路人厚，
    中位數會被一堆小角色拉低，於是主角每次都被報——那是雜訊，不是缺陷。

    刻意**不建議「只讀一部分」**——那會把自由格式的源檔逼成有 schema 的東西。
    """
    out: list[Finding] = []
    for kind in ("角色", "世界觀"):
        d = book / "story" / "設定" / kind
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            if p.name.endswith(AI_SUFFIX) or p.name.startswith("_"):
                continue
            size = len(p.read_text(encoding="utf-8").encode("utf-8"))
            if size > limit:
                out.append(
                    Finding(
                        kind="源檔肥大",
                        path=p,
                        detail=f"{size} B（建議 ≤{limit}）",
                        hint="考慮拆成多支源檔（檔名即選擇器），別改成「只讀一部分」",
                    )
                )
    return out


def long_lines(book: Path, limit: int = LINE_CHARS) -> list[Finding]:
    """綜合檔（就緒儀表／結構）的單行過長＝狀態格被當事件日誌用。

    參照值：一世之尊 就緒儀表最長單一 cell 約 10,000 字元（≈24KB）。
    """
    out: list[Finding] = []
    d = book / "story" / "參照"
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.md")):
        if p.name.endswith(AI_SUFFIX):
            continue
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
                    hint="狀態格只報現況；沿革／裁決記錄屬 append log，不該住在狀態表的 cell 裡",
                )
            )
    return out


def run(book: Path) -> list[Finding]:
    return beat_sheet_density(book) + oversized_sources(book) + long_lines(book)
