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

# `.ai.md` 檔末的自由 blockquote 裁決日誌——三支 schema 明文禁止、零守衛。
# 門檻取自診斷輪的量法（`功能報告/04-裁決與回饋.md` §〇）：只算 >40 字元的行，
# 一兩句短註解不計。
BLOCKQUOTE_CHARS = 40

# 各 schema 定義的封閉節枚舉。節名取 `##` 標題的**開頭**比對（容許作者在標題後
# 加註記，如「## 待裁決回饋（2 筆）」）。找不到對應枚舉的 `.ai.md` 只查 front-matter。
# 2026-07-27（功能 04）**五處移除 `待裁決回饋`**：那一節沒有 inbound 重算規則
# ＝依 A1 它是源，卻住在依 A2 必被覆蓋的容器裡（A3 說這種衝突必須解掉）。實測
# 30 支 `.ai.md` 帶這個節、其中 0 列真的待裁決、7 列是結案未刪的，而「重生把它
# 吃掉」與「它被正常消化」在檔案系統上留下的痕跡**完全相同**。它現在住
# `story/參照/待裁決.md`（四欄、無狀態欄、集中一支，由 `decision-lint` 守）。
# 既有書那些節現在會被報成枚舉外——**那是預期的**（同移除 `🧊 水下` 時）。
DERIVED_SECTIONS: dict[str, tuple[str, ...]] = {
    # 結構定義/角色.schema.md
    # 2026-07-27 移除 `🧊 水下`：揭示層級是**作者拍板何時揭**（不可重生的新資訊），
    # 住在會被重生的 `.ai.md` 裡下次重生就沒了。它現在住 `story/物件/<名>.md` 的
    # `揭示層級` 欄，由 `object-lint` 守。
    "角色": ("需求四象限", "預期弧線", "馬斯洛層次", "對衝關係"),
    "角色/_index": ("角色清單",),
    # 結構定義/世界觀.schema.md
    # 2026-07-27（功能 05）`自洽 / 升格哨兵` 改名 `自洽`：硬約束逐條搬去
    # `story/物件/<名>.md` 的「## 不得寫成什麼」（觸發者＝worldbuild Phase 2 步驟 7），
    # 這一節只留自洽分析。**既有書不必改名**——比對用 startswith，舊的
    # 「## 自洽 / 升格哨兵」仍然通過。front-matter 那四個宣告欄的收斂由
    # `world-lint` 守（本模組只管所有 `.ai.md` 共通的結構）。
    "世界觀": ("限制與代價", "影響力", "自洽"),
    "世界觀/_總覽": (
        "一句話定位",
        "核心規則索引",
        "背景維度盤點",
        "待確認／潛在矛盾",
        "升格哨兵彙總",
        "素材出處",
    ),
    # 結構定義/章節.schema.md
    "章節": ("本章事實",),
    # 2026-07-27 移除 `章末狀態快照`：它是僵屍規格——schema 定義了、本枚舉允許了、
    # 但**沒有任何工具產生它**，實書裡只剩兩行引用已改名工具（`state-project`）的殘骸。
    # 要人眼可讀的章末切片就跑 `fact-project --as-of`，不落檔。
    "章節/_index": ("章節索引",),
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


def decision_blockquotes(text: str, limit: int = BLOCKQUOTE_CHARS) -> list[tuple[int, int]]:
    """`.ai.md` 裡的裁決日誌 blockquote，回傳 [(行號, 字元數)]。

    **只算第一個 `##` 之後的**——這是位置判準，不是分類判準。理由是分類判準在
    這裡做不到：「這段 blockquote 是裁決日誌還是檔頭說明」需要讀懂中文語意，
    而那正是 `prose-metrics` 的「偏網文關鍵詞」被駁回的形狀（見
    `docs/重構/02-待用構想.md`）。位置可以機械判，而且它與 schema 的用字一致
    ——三處禁令講的都是「**檔末**的自由 blockquote」。

    實測一世之尊：全檔掃是 232 行／52,745 字元，其中 42 行落在第一個 `##`
    之前，逐一看過都是檔案狀態說明（「⚠️ 本檔由 write 重生…」「甲批機械可見度
    檔…」）——那是合法的頭註。第一個 `##` 之後的 190 行／46,245 字元才是那份
    無天花板的 append log。
    """
    out: list[tuple[int, int]] = []
    seen_section = False
    for i, raw in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        s = raw.strip()
        if _H2_RE.match(s):
            seen_section = True
            continue
        if seen_section and s.startswith(">") and len(s) > limit:
            out.append((i, len(s)))
    return out


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


@dataclass
class ValidateStats:
    """**我在這本書上檢查了幾支。**

    `設計原則.md` E2 的可執行推論。這支工具原本只印「所有 .ai.md 格式合規」——
    而它對**沒有節枚舉的產物**（風格／摘要，`DERIVED_SECTIONS` 裡根本沒有它們）
    只驗 front-matter，節枚舉是空頭承諾。不把 `enumerated`／`fm_only` 分開印，
    那個缺口就永遠看不出來（→ 功能 07／08）。**0 也印。**
    """

    files: int = 0
    enumerated: int = 0
    fm_only: int = 0
    declarative: int = 0
    skeleton: int = 0
    sections: int = 0
    blockquote_files: int = 0
    blockquote_lines: int = 0

    def render(self) -> str:
        return (
            f"檢查範圍：{self.files} 支 .ai.md"
            f"（{self.enumerated} 支套節枚舉／{self.fm_only} 支只驗 front-matter"
            f"·**節枚舉對它們是空頭承諾**／{self.declarative} 支宣告式）；"
            f"其中 {self.skeleton} 支尚未封章的骨架跳過 front-matter 與 blockquote 檢查；"
            f"比對了 {self.sections} 個 `##` 節；"
            f"掃了裁決 blockquote，{self.blockquote_files} 支檔命中"
            f"（{self.blockquote_lines} 行）"
        )


def validate_file(
    book: Path, p: Path, stats: ValidateStats | None = None
) -> list[Problem]:
    """驗這支 `.ai.md` 的形狀。

    **分工**：`check` 問「產出了沒、過期沒」，`validate` 問「產出的東西形狀對不對」。
    因此完全沒有 front-matter 的檔（書本模板的「尚未產出」骨架、尚未封章的新檔）
    在這裡靜默跳過——那個狀態 `check` 已經報成 `unstamped` 了，重複報是雜訊。
    骨架跳過幾支要印在覆蓋率行，否則就是另一個報平安的守衛。
    """
    text = p.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    out: list[Problem] = []
    st = stats if stats is not None else ValidateStats()
    st.files += 1
    if _is_declarative(p):
        st.declarative += 1
    elif fm is None:
        st.skeleton += 1
    st.sections += sum(1 for ln in body.splitlines() if _H2_RE.match(ln))

    # 裁決日誌 blockquote（T1）。骨架與宣告式豁免：模板的「⚠️ 尚未產出」頭註
    # 本來就是長 blockquote，而它不是任何人的 append log。
    if fm is not None and not _is_declarative(p):
        bq = decision_blockquotes(text)
        if bq:
            st.blockquote_files += 1
            st.blockquote_lines += len(bq)

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
    if not _is_declarative(p):
        if allowed:
            st.enumerated += 1
        else:
            st.fm_only += 1
    if allowed:
        stray = stray_sections(body, allowed)
        if stray:
            shown = "、".join(stray[:4]) + ("…" if len(stray) > 4 else "")
            out.append(
                Problem(
                    p,
                    f"{len(stray)} 個枚舉外的節：{shown}",
                    f"{kind} 衍生檔只留 schema 定義的節（{'／'.join(allowed)}）；"
                    "正文釘死的事實屬該章「## 本章事實」、"
                    "下游硬約束與揭示層級屬 story/物件/<名>.md、"
                    "待裁決回饋屬 story/參照/待裁決.md、"
                    "裁決理由屬 story/參照/裁決流.md",
                )
            )
    return out


def validate_report(book: Path) -> tuple[list[Problem], ValidateStats]:
    """驗全書，回傳 (問題清單, 覆蓋率)。

    裁決 blockquote **聚合成整本一行**（03 重構輪拍板的判準：同一種病散在幾十支
    檔、而且病因與修法完全相同時聚合）。實測一世之尊 29 支檔命中——逐支報就是
    29 行同型雜訊，會把真正該看的枚舉外節淹掉。
    """
    stats = ValidateStats()
    out: list[Problem] = []
    worst: tuple[int, Path, int] = (0, book, 0)
    total_chars = 0
    for p in sorted(book.rglob(f"*{AI_SUFFIX}")):
        out += validate_file(book, p, stats)
        text = p.read_text(encoding="utf-8")
        fm, _ = _split_frontmatter(text)
        if fm is None or _is_declarative(p):
            continue
        for lineno, chars in decision_blockquotes(text):
            total_chars += chars
            if chars > worst[0]:
                worst = (chars, p, lineno)
    if stats.blockquote_files:
        rel = worst[1].relative_to(book) if worst[1].is_relative_to(book) else worst[1]
        out.append(
            Problem(
                book,
                f"{stats.blockquote_files} 支 .ai.md 有裁決日誌 blockquote："
                f"{stats.blockquote_lines} 行、合計 {total_chars} 字元"
                f"（最長 {worst[0]} 字元：{rel}:{worst[2]}）",
                "三處 schema 明文禁止（待裁決.schema.md／裁決流.schema.md／"
                "共同約定.md 零）：理由寫多長都行，寫在 story/參照/裁決流.md，"
                "那裡有投影工具、不會擠進 write 的 context。"
                "只算第一個 `##` 之後的行，檔頭說明不計",
            )
        )
    return out, stats


def validate_book(book: Path) -> list[Problem]:
    return validate_report(book)[0]
