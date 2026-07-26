from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .core import AI_SUFFIX

# 門檻皆為**建議值**（advisory），不是門檻式 pass/fail——呼應「AI 是審稿員不是門檻」。
# 取值依據見各函式 docstring，全部可由 CLI 覆寫。
#
# 哨兵量的是**「必須整檔讀的東西有多大」**，不是「檔多大」（`共同約定.md` 零）：
# 有投影工具可切片的 append log（事實流／裁決流）不受大小規範；沒有工具切得動
# 的（源檔、`.ai.md`）才受。
BEAT_BYTES_PER_BEAT = 2500  # 幕綱：每幕位元組
SOURCE_BYTES = 25000  # 源：單檔（或單一角色目錄總和）絕對上限（約 8000 漢字）
DERIVED_BYTES = 12000  # 衍生 `.ai.md`：無切片工具，且應是源的壓縮，故更嚴（約 4000 漢字）
LINE_CHARS = 2000  # 綜合檔單行（單一表格 cell）字元數
ROLLUP_LINE_CHARS = 400  # rollup 一列＝一行摘要，比綜合檔嚴得多（schema 說「一行需求」）

_ARC_RE = re.compile(r"^arc[0-9A-Za-z]+$")
_BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")

SETTINGS_KINDS = ("角色", "世界觀", "風格")

# 各 schema 定義的封閉節枚舉。節名取 `##` 標題的**開頭**比對（容許作者在標題後
# 加註記，如「## 待裁決回饋（2 筆）」）。找不到對應枚舉的 `.ai.md` 只查大小。
DERIVED_SECTIONS: dict[str, tuple[str, ...]] = {
    # 結構定義/角色.schema.md
    "角色": ("需求四象限", "預期弧線", "馬斯洛層次", "對衝關係", "🧊 水下", "待裁決回饋"),
    "角色/_index": ("角色清單", "待裁決回饋"),
    # 結構定義/世界觀.schema.md
    "世界觀": ("限制與代價", "影響力", "自洽 / 升格哨兵", "自洽／升格哨兵", "待裁決回饋"),
    "世界觀/_總覽": (
        "一句話定位",
        "核心規則索引",
        "背景維度盤點",
        "待確認／潛在矛盾",
        "升格哨兵彙總",
        "素材出處",
        "待裁決回饋",
    ),
}


@dataclass(frozen=True)
class Finding:
    kind: str
    path: Path
    detail: str
    hint: str


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


def _section_enum_for(path: Path, kind: str) -> tuple[str, ...] | None:
    stem = path.name[: -len(AI_SUFFIX)]
    if stem.startswith("_"):
        return DERIVED_SECTIONS.get(f"{kind}/{stem}")
    return DERIVED_SECTIONS.get(kind)


def _stray_sections(text: str, allowed: tuple[str, ...]) -> list[str]:
    stray: list[str] = []
    for ln in text.splitlines():
        m = _H2_RE.match(ln)
        if not m:
            continue
        title = m.group(1).strip()
        if not any(title.startswith(a) for a in allowed):
            stray.append(title)
    return stray


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
            allowed = _section_enum_for(p, kind)
            stray = _stray_sections(text, allowed) if allowed else []
            if stray:
                shown = "、".join(stray[:4]) + ("…" if len(stray) > 4 else "")
                out.append(
                    Finding(
                        kind="衍生檔不可切片",
                        path=p,
                        detail=f"{size} B，{len(stray)} 個枚舉外的節：{shown}",
                        hint="正文釘死的事實／下游硬約束屬 事實流.md（錨／約束）；裁決理由屬 裁決流.md。衍生檔只留 schema 定義的節",
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
        targets += [
            (p, limit)
            for p in sorted(ref.glob("*.md"))
            if not p.name.endswith(AI_SUFFIX)
            and p.stem not in ("事實流", "狀態事件流", "裁決流")
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


def run(book: Path) -> list[Finding]:
    return (
        beat_sheet_density(book)
        + oversized_sources(book)
        + unsliceable_derived(book)
        + long_lines(book)
    )
