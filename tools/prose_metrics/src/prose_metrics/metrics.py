from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class MetricsError(Exception):
    """找不到章節、或章節無法對映到 arc。"""


class LayerMissing(MetricsError):
    """**這本書還沒有正文層**——與「這本書的格式壞了」是兩件事（功能 14，抉擇 6 A）。

    契約：**exit 2，而且照樣印覆蓋率行**（`共同約定.md`「輸出與 exit 契約」）。
    6 本書裡有 3 本長期處在這個狀態，不分開的話 CI 會永遠紅。

    **它是 `MetricsError` 的子類**（同 `beat_metrics.LayerMissing ⊂ ScanError`）：
    既有的 `except MetricsError` 照舊接得住，只有想分辨的地方才要多接一層。
    """


# 刻意**不內建任何文類詞表**（武打詞、修煉詞…）。那會讓工具只對武俠有效，
# 且把「這個文類本來就這樣」誤判成退化。以下全部是文類無關的普世量，
# 唯一的「詞彙」是從該書自己的 設定/角色/ 檔名推導出來的——書自己定義的，不是我們塞的。
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING_RE = re.compile(r"^#.*$", re.MULTILINE)
_OLD_META_RE = re.compile(r"^-\s*(對應幕|所屬\s*arc|POV|基調|風格|狀態)[：:].*$", re.MULTILINE)
_QUOTE_CHARS = "「“"


@dataclass(frozen=True)
class Chapter:
    label: str
    group: str  # arc（或對照語料的卷）
    path: Path


@dataclass(frozen=True)
class Metrics:
    label: str
    group: str
    chars: int
    quotes: int
    paragraphs: int
    cast: int

    @property
    def quote_density(self) -> float:
        """每千字對白引號數——比絕對數耐得住篇幅變化。"""
        return self.quotes * 1000 / self.chars if self.chars else 0.0

    @property
    def avg_paragraph(self) -> float:
        return self.chars / self.paragraphs if self.paragraphs else 0.0

    @property
    def solo(self) -> bool:
        """全章只提到 ≤1 個已知角色＝主角一個人的獨白章。"""
        return self.cast <= 1


def strip_scaffolding(text: str) -> str:
    """去掉標題、幕錨點註解、舊版內嵌 metadata——只留讀者真正讀到的散文。"""
    text = _HTML_COMMENT_RE.sub("", text)
    text = _OLD_META_RE.sub("", text)
    text = _HEADING_RE.sub("", text)
    return text


def paragraphs(prose: str) -> list[str]:
    """段落＝去鷹架後的非空行。段是本系統的分析單位（見 exposition.py）。"""
    return [ln for ln in (l.strip() for l in prose.splitlines()) if ln]


def chapter_metrics(ch: Chapter, vocab: list[str]) -> Metrics:
    raw = ch.path.read_text(encoding="utf-8", errors="replace")
    prose = strip_scaffolding(raw)
    paragraphs_ = paragraphs(prose)
    chars = sum(len(p) for p in paragraphs_)
    return Metrics(
        label=ch.label,
        group=ch.group,
        chars=chars,
        quotes=sum(prose.count(q) for q in _QUOTE_CHARS),
        paragraphs=len(paragraphs_),
        cast=sum(1 for name in vocab if name in prose),
    )


# ---------------------------------------------------------------- 語料載入

def load_vocab(book: Path) -> list[str]:
    """角色詞彙表＝該書 設定/角色/ 的源檔檔名（源是唯一真實來源，檔名即權威名）。"""
    d = book / "story" / "設定" / "角色"
    if not d.is_dir():
        return []
    return sorted(
        p.stem
        for p in d.glob("*.md")
        if not p.name.endswith(".ai.md") and not p.name.startswith("_")
    )


_ARC_FM_RE = re.compile(r"^所屬arc:\s*(\S+)", re.MULTILINE)
_ARC_OLD_RE = re.compile(r"^-\s*所屬\s*arc[：:]\s*(\S+)", re.MULTILINE)


def _arc_of(md: Path) -> str:
    """章→arc。新版讀 chNNNN.ai.md front-matter，舊版讀 .md 內嵌 bullet。"""
    ai = md.parent / f"{md.stem}.ai.md"
    if ai.exists():
        m = _ARC_FM_RE.search(ai.read_text(encoding="utf-8"))
        if m:
            return m.group(1).strip()
    m = _ARC_OLD_RE.search(md.read_text(encoding="utf-8", errors="replace"))
    return m.group(1).strip() if m else "（未標 arc）"


def load_book_chapters(book: Path) -> list[Chapter]:
    d = book / "chapters"
    if not d.is_dir():
        raise LayerMissing(f"找不到 chapters/：{d}")
    chapters = [
        Chapter(label=p.stem, group=_arc_of(p), path=p)
        for p in sorted(d.glob("ch*.md"))
        if not p.name.endswith(".ai.md")
    ]
    if not chapters:
        raise LayerMissing(f"{d} 下沒有 chNNNN.md")
    return chapters


_CJK_DIGITS = {c: i for i, c in enumerate("〇一二三四五六七八九", start=0)}


def group_sort_key(name: str) -> tuple[int, str]:
    """中文數字不能用字典序排（`三` U+4E09 < `二` U+4E8C，卷三會排到卷二前面）。

    抽出中文／阿拉伯數字當主鍵；抽不到就退回字典序（次鍵）。
    """
    m = re.search(r"(\d+)", name)
    if m:
        return (int(m.group(1)), name)
    total, seen = 0, False
    for ch in name:
        if ch == "十":
            total = (total or 1) * 10
            seen = True
        elif ch in _CJK_DIGITS:
            total += _CJK_DIGITS[ch]
            seen = True
    return (total, name) if seen else (10**9, name)


def load_plain_chapters(root: Path) -> list[Chapter]:
    """對照語料：子目錄即分組（如原著的 卷一／卷二／卷三），檔案排序即章序。"""
    if not root.is_dir():
        raise MetricsError(f"找不到目錄：{root}")
    chapters: list[Chapter] = []
    subdirs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: group_sort_key(p.name))
    for sub in subdirs or [root]:
        for p in sorted(sub.iterdir()):
            if p.suffix.lower() in (".txt", ".md") and p.is_file():
                chapters.append(
                    Chapter(label=p.stem[:14], group=sub.name if subdirs else root.name, path=p)
                )
    if not chapters:
        raise MetricsError(f"{root} 下沒有 .txt/.md 章節檔")
    return chapters
