"""事件從哪裡讀進來。

事實軸按「**可不可重生**」拆成兩個落點（見 `結構定義/事實流.schema.md`）：

- `狀態`／`錨` ＝ 該章正文的函數 → 住 `chapters/chNNNN.ai.md` 的 `## 本章事實`
  區塊，隨該章 `.ai.md` 一起走 `derived_sync` 的 hash 偵測。作者改了正文，
  `derived-sync check` 就報 stale，重生即修正——這是 append log 做不到的。
- `約束` ＝ 作者拍板的意圖（正文裡沒有這句話，重讀一萬遍也生不出來）
  → 住 `story/參照/約束.md`，維持 append log 語意。

fold 本身（slot key、as-of、`（解除）`）三類共用一套，逐字不變；本模組只換 input。
"""

from __future__ import annotations

from pathlib import Path

from .fold import KIND_CONSTRAINT, Event, FoldError, parse_events

CHAPTER_SECTION = "本章事實"
CONSTRAINT_LOG = "約束.md"

# Windows 上的編輯器（含 PowerShell `Set-Content -Encoding utf8`）常寫出帶 BOM 的
# UTF-8。BOM 會黏在第一行行首，讓 `- 幕001…` 的事件行認不出來而被靜默跳過——
# 事實少一筆比報錯還難查。`utf-8-sig` 有 BOM 就吃掉、沒有也照常運作。
# （`derived_sync` 那邊刻意**不**跟進：它讀檔是為了算 hash，換編碼會讓既有
#  `generated-from` 全數失準、整書誤報 stale。）
_ENCODING = "utf-8-sig"

# 2026-07-26 前的單檔 append log。既有書（一世之尊）不遷移，工具照樣讀得動。
LEGACY_STREAM_NAMES = ("事實流.md", "狀態事件流.md")


def resolve_legacy_stream(book: Path) -> Path | None:
    """找舊的單檔事實流；沒有就回 None（＝這本書走新格式）。"""
    ref = book / "story" / "參照"
    for name in LEGACY_STREAM_NAMES:
        p = ref / name
        if p.is_file():
            return p
    return None


def section_lines(text: str, title: str) -> str:
    """抽出 `## <title>` 區塊，**保留原行號**（區塊外的行換成空行）。

    行號要對得上原檔，報錯訊息才指得到人看得懂的位置。
    """
    out: list[str] = []
    inside = False
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = raw.strip()
        if stripped.startswith("## "):
            inside = stripped[3:].strip().startswith(title)
            out.append("")  # 標題行本身不是事件
            continue
        out.append(raw if inside else "")
    return "\n".join(out)


def _chapter_origin(p: Path) -> str:
    return p.name[: -len(".ai.md")]


def collect_events(
    book: Path, errors: list[str] | None = None
) -> tuple[list[Event], str]:
    """收齊全書事件，回傳 (events, mode)；mode ∈ {"legacy", "chapters"}。

    `errors` 傳 list ＝ 收集模式（lint 用），None ＝ 嚴格模式（投影用）。
    `order` 依「章序 → 約束 log」遞增指派，故跨檔的同位置 tiebreak 是穩定的。
    """
    legacy = resolve_legacy_stream(book)
    if legacy is not None:
        # 舊格式只有一支檔，標來源等於每行都印同一個檔名——留空，別加雜訊。
        return parse_events(
            legacy.read_text(encoding=_ENCODING), errors=errors
        ), "legacy"

    events: list[Event] = []
    chapters = book / "chapters"
    if chapters.is_dir():
        for p in sorted(chapters.glob("ch*.ai.md")):
            body = section_lines(p.read_text(encoding=_ENCODING), CHAPTER_SECTION)
            events += parse_events(
                body,
                origin=_chapter_origin(p),
                start_order=len(events),
                errors=errors,
            )

    log = book / "story" / "參照" / CONSTRAINT_LOG
    if log.is_file():
        events += parse_events(
            log.read_text(encoding=_ENCODING),
            origin=CONSTRAINT_LOG,
            start_order=len(events),
            errors=errors,
        )
    elif not events and not chapters.is_dir():
        raise FileNotFoundError(
            f"{book} 下既無 chapters/ 也無 story/參照/{CONSTRAINT_LOG}"
            f"（舊格式書則需 story/參照/{' 或 '.join(LEGACY_STREAM_NAMES)}）"
        )
    return events, "chapters"


def check_kind_placement(events: list[Event]) -> list[str]:
    """類型有沒有住錯地方——只有 lint 做，投影不做。

    住錯地方不是格式壞，是**可重生性**錯：約束放進會被重生的章 delta，下次
    重生就沒了；狀態／錨放進 append log，作者改正文時就沒人管得了。
    """
    problems: list[str] = []
    for e in events:
        if e.origin == CONSTRAINT_LOG and e.kind != KIND_CONSTRAINT:
            problems.append(
                f"{e.origin} 第 {e.lineno} 行是 `{e.kind}`：{CONSTRAINT_LOG} 只住"
                f"`約束`。狀態／錨屬該章 chNNNN.ai.md 的「## {CHAPTER_SECTION}」"
                "（它們是正文的函數，要能隨正文重生）"
            )
        elif e.origin != CONSTRAINT_LOG and e.kind == KIND_CONSTRAINT:
            problems.append(
                f"{e.origin} 第 {e.lineno} 行是 `約束`：章 delta 會被重生，約束"
                f"寫在這裡下次重生就沒了。約束屬 story/參照/{CONSTRAINT_LOG}"
            )
    return problems


def lint(book: Path) -> list[str]:
    """回傳全部問題（格式壞行＋類型住錯地方）；空 list ＝ 乾淨。"""
    errors: list[str] = []
    try:
        events, _mode = collect_events(book, errors=errors)
    except FileNotFoundError as e:
        return [str(e)]
    except FoldError as e:  # collect 模式理論上不該走到，保險
        return [str(e)]
    return errors + check_kind_placement(events)
