"""物件軸：`story/物件/<名>.md`——一物件一檔，**檔名即 ID、目錄即 registry**。

見 `結構定義/物件.schema.md`。物件 ＝「具名 ＋ 隨劇情推進會變狀態」的東西（伏筆、
道具、角色、關係、組織、地點、設定規則）。2026-07-27 建軸，把原本散在五處的同一個
抽象收成一個：

| 原本住哪 | 病徵 | 現在 |
|---|---|---|
| `story/參照/約束.co.md`（5 欄表） | 實體欄是自由字串，同一個人可以有兩個名字 | 本檔「## 不得寫成什麼」（4 欄，實體＝檔名） |
| 設定層 `.ai.md` 的 🧊 標記（三種語法） | 不可重生的裁決住在會被重生的檔裡 | 本檔 front-matter 的 `揭示層級` |
| 設定層 `.ai.md` 的枚舉外節（實測 13 支檔 70 行） | 下次重生就消失 | 本檔的三個節 |

**它是 A1 源檔**——沒有任何 inbound 重算規則，所以人與 AI 混寫安全，作者的手改不會
被覆蓋。代價是它得自己守格式（E1），那就是本模組。

**邊界（不吸收別條軸）**：
- 埋／收在哪一幕仍然只有幕綱說得準（`幕綱.schema.md`「伏筆不另立登記簿」）。本檔的
  `揭示層級` 只放一個**指向**那個收點的指標，不複述時機。
- 狀態怎麼變仍然住章 delta（`chNNNN.ai.md` 的「## 本章事實」）。本檔寫的是「這東西
  是什麼、為什麼存在、不得寫成什麼」——**不隨劇情變的那一半**。

**沒有物件檔的 ID 是合法的**（G4／抉擇 3）：判準是內容測試——寫得出「不得寫成什麼」
或「為什麼這樣定」才開檔，只有狀態沒有故事的東西只以 delta 存在。所以本模組**不**
要求每個被引用的名字都有檔；它守的是**已經開了檔的那些**，外加一個「這名字看起來
跟某支物件檔是同一件事，但字不一樣」的近似名警報（那才是實測會出事的地方）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .constraints import (
    CONSTRAINT_SECTION,
    Constraint,
    check_duplicates,
    parse_constraints,
)
from .fold import FoldError
from .marks import BEAT_HEAD_RE, MARK_RE, REVEAL_TARGET_RE

OBJECT_DIRNAME = "物件"

# 封閉八型（七型為作者 2026-07-27 拍板；第八型 `方針` 同日經**停下來問作者**後新增，
# 那正是「要第八型＝停下來問作者」這條規則第一次被執行）。多值以 `、` 分隔，
# **第一個是主型別**（實測需求：`小玉佛來歷` 同時是伏筆與道具，分子目錄會逼它選邊站）。
KINDS = ("伏筆", "道具", "角色", "關係", "組織", "地點", "設定規則", "方針")

# `方針` ＝ 射程全書、不綁任何實體的作者通則（「這本書不寫感情線」）。它與其餘
# 七型不同：那七型都是「具名 ＋ 隨劇情推進會變狀態」的東西（G1），而方針**自己
# 就是規則**、沒有狀態。它進物件軸是為了拿到約束表與 `fact-project` 的載入路徑
# （F2 新判準：射程綁全書 → 需要一個每次都會被無條件載入的落點）。
# **綁定檔名 `全書`**：這一型只有一個合法住址，否則「方針」會變成第二個約束軸。
POLICY_KIND = "方針"
POLICY_NAME = "全書"

KEY_KIND = "型別"
KEY_REVEAL = "揭示層級"
FRONTMATTER_KEYS = (KEY_KIND, KEY_REVEAL)

SECTION_WHAT = "是什麼"
SECTION_WHY = "為什麼存在"
SECTIONS = (SECTION_WHAT, SECTION_WHY, CONSTRAINT_SECTION)

# 揭示層級的**唯一**語法。2026-07-27 前有三種 schema 授權的寫法而工具只認一種，
# 實測 92 次出現、91 次隱形，且 `foreshadow-project` 大方印「0 條為可疑點」。
REVEAL_PUBLIC = "公開"
_REVEAL_UNDERWATER = re.compile(r"^水下\s*[｜|]\s*(.+)$")
_REVEAL_TARGET = REVEAL_TARGET_RE  # 標記語法只寫一次，見 `marks.py`
_CROSS_BOOK = "跨集留白"

# 檔名即 ID，所以檔名裡不能有那些會讓 ID 失去唯一性或無法被引用的字。
_BAD_NAME_CHARS = "〔〕[]｜|:：/\\*?\"<>"

_FM_FENCE = "---"
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")

_ENCODING = "utf-8-sig"


@dataclass(frozen=True)
class ObjectFile:
    name: str  # 檔名 stem ＝ ID
    path: Path
    kinds: tuple[str, ...]  # 第一個是主型別
    reveal_raw: str  # `揭示層級` 原文（未填＝公開）
    reveal_target: str | None  # 指向的伏筆名；公開／跨集留白為 None
    cross_book: bool
    sections: dict[str, str]  # 節名 → 內容（原文）
    constraints: tuple[Constraint, ...] = field(default=())

    @property
    def origin(self) -> str:
        return f"{OBJECT_DIRNAME}/{self.path.name}"

    @property
    def underwater(self) -> bool:
        return self.reveal_raw != REVEAL_PUBLIC


def objects_dir(book: Path) -> Path:
    return book / "story" / OBJECT_DIRNAME


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """回 (front-matter 鍵值, 本體)。沒有 front-matter 就回 ({}, 全文)。

    刻意只做「一層 `鍵: 值`」——物件檔的 front-matter 只有兩個鍵，引入 YAML
    相依（或自己寫一個半套 YAML）換來的只有更多出錯的方式。
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != _FM_FENCE:
        return {}, text
    fm: dict[str, str] = {}
    for i, raw in enumerate(lines[1:], start=1):
        if raw.strip() == _FM_FENCE:
            return fm, "\n".join(lines[i + 1 :])
        key, sep, value = raw.partition(":")
        if sep:
            fm[key.strip()] = value.split("#", 1)[0].strip().strip('"').strip("'")
    return fm, text  # 沒有收尾的 fence＝格式壞，交給 check_objects 報


def _split_sections(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    title = ""
    buf: list[str] = []
    for raw in body.splitlines():
        m = _H2_RE.match(raw)
        if m:
            if title:
                out[title] = "\n".join(buf).strip()
            title, buf = m.group(1).strip(), []
            continue
        if title:
            buf.append(raw)
    if title:
        out[title] = "\n".join(buf).strip()
    return out


def _parse_reveal(raw: str) -> tuple[str | None, bool, str | None]:
    """`揭示層級` → (指向的伏筆名, 是否跨集留白, 格式錯訊息)。"""
    s = raw.strip()
    if not s or s == REVEAL_PUBLIC:
        return None, False, None
    m = _REVEAL_UNDERWATER.match(s)
    if not m:
        return (
            None,
            False,
            f"「{KEY_REVEAL}」語法只有三種：`{REVEAL_PUBLIC}`／"
            f"`水下｜揭示於 收[[伏筆:X]]`／`水下｜{_CROSS_BOOK}`，得到 {raw!r}",
        )
    tail = m.group(1).strip()
    if _CROSS_BOOK in tail:
        return None, True, None
    t = _REVEAL_TARGET.match(tail)
    if t:
        return t.group(1).strip(), False, None
    return (
        None,
        False,
        f"「{KEY_REVEAL}」的水下層必須二選一：指向一個收點"
        f"（`水下｜揭示於 收[[伏筆:X]]`）或明標 `水下｜{_CROSS_BOOK}`，得到 {raw!r}。"
        "揭示時機的唯一真實來源是幕綱的收點，這裡只放指標、不用散文複述",
    )


def load_objects(
    book: Path, errors: list[str] | None = None
) -> list[ObjectFile]:
    """讀 `story/物件/*.md`。目錄不存在就回空——一本書可以還沒有任何物件。

    `errors` 為 None ＝嚴格模式（投影走這條，約束缺一條比報錯危險）；傳 list ＝
    收集模式，讓 lint 一次報完全部。
    """
    d = objects_dir(book)
    if not d.is_dir():
        return []
    out: list[ObjectFile] = []
    for p in sorted(d.glob("*.md")):
        stem = p.name[: -len(".md")]
        if stem.startswith("_") or stem.startswith("."):
            continue  # 保留給日後的說明檔／rollup，不當成物件
        text = p.read_text(encoding=_ENCODING)
        fm, body = _split_frontmatter(text)
        sections = _split_sections(body)
        kinds = tuple(
            k.strip() for k in re.split(r"[、,，]", fm.get(KEY_KIND, "")) if k.strip()
        )
        reveal_raw = fm.get(KEY_REVEAL, "").strip() or REVEAL_PUBLIC
        target, cross, bad = _parse_reveal(reveal_raw)
        origin = f"{OBJECT_DIRNAME}/{p.name}"
        if bad:
            if errors is None:
                raise FoldError(f"{origin}：{bad}")
            errors.append(f"{origin}：{bad}")
        cons: tuple[Constraint, ...] = ()
        if sections.get(CONSTRAINT_SECTION):
            rows = parse_constraints(
                sections[CONSTRAINT_SECTION],
                entity=stem,
                origin=origin,
                errors=errors,
            )
            if errors is not None:
                errors += check_duplicates(rows, origin=origin)
            cons = tuple(rows)
        out.append(
            ObjectFile(
                name=stem,
                path=p,
                kinds=kinds,
                reveal_raw=reveal_raw,
                reveal_target=target,
                cross_book=cross,
                sections=sections,
                constraints=cons,
            )
        )
    return out


def collect_object_constraints(
    book: Path, errors: list[str] | None = None
) -> list[Constraint]:
    return [c for o in load_objects(book, errors=errors) for c in o.constraints]


# ------------------------------------------------------------------ 檢查器


def check_objects(objs: list[ObjectFile]) -> list[str]:
    """物件檔自己的格式：檔名、型別枚舉、節枚舉、內容測試。

    `揭示層級` 的**語法**在 `load_objects` 就報了（解析不了就沒有值可用）；它
    **指向的收點存不存在**要幕綱才判得出來，走 `check_reveal_targets`。
    """
    problems: list[str] = []
    for o in objs:
        bad = [c for c in _BAD_NAME_CHARS if c in o.name]
        if bad:
            problems.append(
                f"{o.origin}：檔名含 {''.join(bad)}——檔名就是這個物件的 ID"
                "（會被 delta 的命題名、幕綱的伏筆名、約束的實體引用），"
                "不能含這些字"
            )
        if not o.kinds:
            problems.append(
                f"{o.origin}：front-matter 缺 `{KEY_KIND}`"
                f"（封閉八型：{'／'.join(KINDS)}；多型以 `、` 分隔，第一個是主型別）"
            )
        for k in o.kinds:
            if k not in KINDS:
                problems.append(
                    f"{o.origin}：`{KEY_KIND}` 有 `{k}`，不在封閉枚舉內"
                    f"（{'／'.join(KINDS)}）。真的需要第九型＝停下來問作者，"
                    "別自己加一個（投影按型別 fold 要靠這個枚舉）"
                )
        # `方針` ⇔ 檔名 `全書` 雙向綁定。方針射程＝全書、不綁實體，所以它只有一個
        # 合法住址；沒有這條，「方針」會退化成第二個約束軸（誰都能開一支方針檔，
        # 而 `--for-beat` 只無條件載入 `全書` 那一支，其餘會靜默不被載入）。
        if POLICY_KIND in o.kinds and o.name != POLICY_NAME:
            problems.append(
                f"{o.origin}：`{KEY_KIND}` 是 `{POLICY_KIND}`，但檔名不是 "
                f"`{POLICY_NAME}.md`——書級方針射程＝全書、不綁任何實體，"
                f"只有 `{OBJECT_DIRNAME}/{POLICY_NAME}.md` 這一個落點"
                f"（`fact-project --for-beat` 也只無條件印那一支）。"
                f"綁單一實體的排除線該寫進該實體自己的物件檔"
            )
        if o.name == POLICY_NAME and POLICY_KIND not in o.kinds:
            problems.append(
                f"{o.origin}：檔名是 `{POLICY_NAME}` 但 `{KEY_KIND}` 沒有 "
                f"`{POLICY_KIND}`——這支檔是書級方針的保留落點"
            )
        # 方針不是「具名＋隨劇情推進會變狀態」的東西（G1），沒有「何時向讀者揭」
        # 可言；容忍它會讓 `foreshadow-project` 去解析一個永遠不會有收點的指標。
        if POLICY_KIND in o.kinds and o.underwater:
            problems.append(
                f"{o.origin}：方針檔不得有 `{KEY_REVEAL}`——"
                f"方針是作者的創作通則，不是會被揭示的故事內容"
            )
        stray = [s for s in o.sections if s not in SECTIONS]
        if stray:
            problems.append(
                f"{o.origin}：{len(stray)} 個枚舉外的節：{'、'.join(stray[:4])}"
                f"{'…' if len(stray) > 4 else ''}"
                f"（物件檔只有 {'／'.join(SECTIONS)} 三節；狀態變化屬該章 delta、"
                "埋／收屬幕綱、裁決理由屬 story/參照/裁決流.md）"
            )
        # 抉擇 3 B 的內容測試，可執行化：兩節都空＝這個物件沒有故事可寫，
        # 它不該有檔（G4）——只有狀態沒有故事的東西只以 delta 存在就好。
        if not o.sections.get(SECTION_WHY) and not o.sections.get(CONSTRAINT_SECTION):
            problems.append(
                f"{o.origin}：`{SECTION_WHY}` 與 `{CONSTRAINT_SECTION}` 兩節都空"
                "——這兩節都寫不出來的物件不必開檔（G4），讓它只以 delta 存在即可。"
                "刪掉這支檔，或把作者拍板的理由／排除線寫進去"
            )
    return problems


def planted_and_paid(book: Path) -> tuple[set[str], set[str]]:
    """掃幕綱的 `埋`／`收[[伏筆:X]]`，回 (埋過的名字, 收過的名字)。

    定序與配對是 `foreshadow-project` 的工作；這裡只要「這個名字在幕綱存在嗎」。
    """
    planted: set[str] = set()
    paid: set[str] = set()
    d = book / "story" / "幕綱"
    if not d.is_dir():
        return planted, paid
    for p in sorted(d.glob("*.md")):
        for kind, name in MARK_RE.findall(p.read_text(encoding=_ENCODING)):
            (planted if kind == "埋" else paid).add(name.strip())
    return planted, paid


_SPINE_RE = re.compile(r"全書順序：(.+)$")
_ARC_TOKEN_RE = re.compile(r"arc[0-9A-Za-z]+")
# **與 `beats` 是同一把尺**（2026-07-28 功能 14，抉擇 1 D：同套件內的複製沒有
# 政策在支持它）。這裡只要「這支檔有沒有幕標題」，所以用 `search`。
_BEAT_HEAD_RE = re.compile(BEAT_HEAD_RE.pattern, re.M)


def unbuilt_arcs(book: Path) -> list[str]:
    """在「全書順序」裡、但還沒拆出幕號的 arc。

    它是「揭示點待落幕」這個**資訊**判定的依據：指向的名字在幕綱找不到，但還有
    arc 沒拆，那個名字很可能就在那裡面。沒有任何未拆 arc 可解釋時才是可疑點
    （`世界觀.schema.md` 檢查點的原文條件）。
    """
    d = book / "story" / "幕綱"
    index = d / "_index.md"
    if not index.is_file():
        return []
    arcs: list[str] = []
    for raw in index.read_text(encoding=_ENCODING).splitlines():
        m = _SPINE_RE.search(raw)
        if m:
            for tok in _ARC_TOKEN_RE.findall(m.group(1)):
                if tok not in arcs:
                    arcs.append(tok)
            break
    out: list[str] = []
    for arc in arcs:
        p = d / f"{arc}.md"
        if not p.is_file() or not _BEAT_HEAD_RE.search(p.read_text(encoding=_ENCODING)):
            out.append(arc)
    return out


def check_reveal_targets(
    book: Path, objs: list[ObjectFile], notes: list[str] | None = None
) -> list[str]:
    """`揭示層級` 指向的收點，幕綱裡找得到嗎？

    **揭示點還不存在是合法狀態**（`共同約定.md` 六）。三種結果，比照
    `世界觀.schema.md` 檢查點的原文：

    - 幕綱有收點 → 資訊（揭示於哪一幕由 `foreshadow-project` 算）。
    - 找不到收點，但該伏筆已埋、或還有 arc 沒拆 → **「揭示點待落幕」，資訊、非可疑點**。
    - 找不到、且沒有未拆 arc 可解釋 → 可疑點（疑似手誤，或那條伏筆已被刪）。
    """
    planted, paid = planted_and_paid(book)
    pending = unbuilt_arcs(book)
    problems: list[str] = []
    for o in objs:
        if o.reveal_target is None:
            continue
        t = o.reveal_target
        if t in paid:
            if notes is not None:
                notes.append(f"{o.origin}：揭示層級 → 收[[伏筆:{t}]]（幕綱有收點）")
        elif t in planted or pending:
            if notes is not None:
                why = "該伏筆已埋、尚無收點" if t in planted else f"{'、'.join(pending)} 尚未拆幕"
                notes.append(
                    f"{o.origin}：揭示層級 → 收[[伏筆:{t}]] 揭示點待落幕（{why}）"
                )
        else:
            problems.append(
                f"{o.origin}：`{KEY_REVEAL}` 指向 收[[伏筆:{t}]]，"
                "但全書幕綱既無這條伏筆的埋也無收，也沒有未拆的 arc 可以解釋"
                "——名字是不是打錯了，或那條伏筆已被刪？"
            )
    return problems


def check_near_miss(objs: list[ObjectFile], referenced: dict[str, list[str]]) -> list[str]:
    """引用到的名字與物件檔名**互為子串但不相等** → 疑似同一物件的兩個名字。

    這是 V7 的實測病徵：`呆底下另有東西` 與 `呆底下另有東西（真慧）` 在同一本書裡
    並存，而 `知識前沿` 的命題名比對就掛在這個命名空間上——一個括號註解就能讓比對
    失準。名字不必有物件檔（G4），但**有了物件檔就不該再有變體**。
    """
    names = {o.name for o in objs}
    problems: list[str] = []
    for ref, wheres in sorted(referenced.items()):
        if ref in names:
            continue
        for n in sorted(names):
            if len(ref) < 2 or len(n) < 2:
                continue
            if ref in n or n in ref:
                problems.append(
                    f"引用名〔{ref}〕（{'、'.join(wheres[:3])}"
                    f"{'…' if len(wheres) > 3 else ''}）與物件檔〔{n}〕"
                    "疑似同一件事的兩個名字——物件檔名就是 ID，"
                    "引用一律用它的原字（同一件事兩個名字會讓它分裂成兩筆並存）"
                )
                break
    return problems


# 抉擇 3：引用次數只當**提示**，不設門檻、不強制。判準是內容測試（見 check_objects）。
OPEN_FILE_HINT = 3


def suggest_objects(
    objs: list[ObjectFile], referenced: dict[str, list[str]]
) -> list[str]:
    """被引用夠多次卻還沒有物件檔的名字，印一行問句。**不是門檻。**"""
    names = {o.name for o in objs}
    out: list[str] = []
    for ref, wheres in sorted(referenced.items()):
        if ref in names or len(wheres) < OPEN_FILE_HINT:
            continue
        out.append(
            f"〔{ref}〕被引用 {len(wheres)} 次卻沒有物件檔——"
            "要不要開一支？（判準是內容測試：寫得出「不得寫成什麼」或"
            "「為什麼這樣定」就開，寫不出就別開）"
        )
    return out
