""".ai.md 的格式閘門。

`.md` 與 `.ai.md` 的差別在於**程式怎麼讀它**：`.md` 不保證格式（人一改就可能
破掉，所以程式只能整檔讀）；`.ai.md` 保證格式，因此程式可以切片、可以解析欄位。

在本模組之前，那個「保證」沒有任何東西在守——`check` 只驗新鮮度（hash 對不對），
不驗格式。作者若在 `.ai.md` 手改而破了格式，或某輪 skill 開了 schema 沒有的節，
要到下游解析炸掉才會發現。

與 `fact-lint` 分工：本模組管 `.ai.md` 的**結構**（front-matter、節枚舉），
`fact-lint` 管**事實信封行**的格式。各自擁有自己那份格式的唯一真相，不建立
跨 uv 專案的相依。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .core import AI_SUFFIX, _is_declarative, _split_frontmatter

_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):")

# 各 schema 定義的封閉節枚舉。節名取 `##` 標題的**開頭**比對（容許作者在標題後
# 加註記，如「## 待裁決回饋（2 筆）」）。找不到對應枚舉的 `.ai.md` 只查 front-matter。
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
    # 結構定義/章節.schema.md
    "章節": ("本章事實", "待裁決回饋"),
    "章節/_index": ("章節索引", "章末狀態快照"),
}

SETTINGS_KINDS = ("角色", "世界觀", "風格")

REQUIRED_KEYS = ("generated-from", "generated-at")


def enum_for(kind: str, stem: str) -> tuple[str, ...] | None:
    """(產物類別, 去掉 .ai.md 的檔名) → 該檔允許的 `##` 節；無定義回 None。"""
    if stem.startswith("_"):
        return DERIVED_SECTIONS.get(f"{kind}/{stem}")
    return DERIVED_SECTIONS.get(kind)


def stray_sections(text: str, allowed: tuple[str, ...]) -> list[str]:
    stray: list[str] = []
    for ln in text.splitlines():
        m = _H2_RE.match(ln)
        if not m:
            continue
        title = m.group(1).strip()
        if not any(title.startswith(a) for a in allowed):
            stray.append(title)
    return stray


def classify(book: Path, p: Path) -> str | None:
    """這支 `.ai.md` 屬哪個產物類別（決定套哪份節枚舉）。"""
    try:
        rel = p.relative_to(book).parts
    except ValueError:
        return None
    if rel[:1] == ("chapters",):
        return "章節"
    if rel[:2] == ("story", "設定") and len(rel) >= 3 and rel[2] in SETTINGS_KINDS:
        return rel[2]
    return None


@dataclass(frozen=True)
class Problem:
    path: Path
    detail: str
    hint: str


def validate_file(book: Path, p: Path) -> list[Problem]:
    """驗這支 `.ai.md` 的形狀。

    **分工**：`check` 問「產出了沒、過期沒」，`validate` 問「產出的東西形狀對不對」。
    因此完全沒有 front-matter 的檔（書本模板的「尚未產出」骨架、尚未封章的新檔）
    在這裡靜默跳過——那個狀態 `check` 已經報成 `unstamped` 了，重複報是雜訊。
    """
    text = p.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    out: list[Problem] = []

    if fm is not None and not _is_declarative(p):
        keys = {m.group(1) for ln in fm if (m := _KEY_RE.match(ln.strip()))}
        missing = [k for k in REQUIRED_KEYS if k not in keys]
        if missing:
            out.append(
                Problem(
                    p,
                    f"front-matter 缺 {'、'.join(missing)}",
                    "重生後跑 `derived-sync stamp <該檔>` 封章，別手填",
                )
            )

    kind = classify(book, p)
    allowed = enum_for(kind, p.name[: -len(AI_SUFFIX)]) if kind else None
    if allowed:
        stray = stray_sections(body, allowed)
        if stray:
            shown = "、".join(stray[:4]) + ("…" if len(stray) > 4 else "")
            out.append(
                Problem(
                    p,
                    f"{len(stray)} 個枚舉外的節：{shown}",
                    f"{kind} 衍生檔只留 schema 定義的節（{'／'.join(allowed)}）；"
                    "正文釘死的事實屬該章「## 本章事實」、下游硬約束屬 約束.md、"
                    "裁決理由屬 裁決流.md",
                )
            )
    return out


def validate_book(book: Path) -> list[Problem]:
    out: list[Problem] = []
    for p in sorted(book.rglob(f"*{AI_SUFFIX}")):
        out += validate_file(book, p)
    return out
