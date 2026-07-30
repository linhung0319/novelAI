"""幕綱八欄解析（`結構定義/幕綱.schema.md`「固定欄位（八項）」）。

**為什麼自帶解析器、不與 `foreshadow_project` 共用**：本 repo 的 tools/ 慣例是各套件
零依賴、小 regex 各自持有（`_BEAT_HEAD_RE` 今天同時存在於 `foreshadow_project/scan.py`
與 `derived_sync/sentinel.py`）。`foreshadow_project` 只認「伏筆」一欄——它刻意不解析
其餘七欄，因為多解析一欄就多一種誤配對的來源。本檔要的是全八欄，職責不同。

**只讀八欄，不讀檔尾設計註**——這正是 `幕綱.schema.md`「設計註只讀不抄」的機械版：
`write` 抄的是欄位，所以量的也只能是欄位。把設計註算進來會讓「把治理文字搬到檔尾」
這個正確動作看起來像沒有改善。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class ScanError(Exception):
    """幕綱檔無法定位或解析。"""


class LayerMissing(ScanError):
    """**這本書還沒有這一層**——與「這本書的格式壞了」是兩件事。

    **2026-07-28（功能 14，抉擇 6 A）新增。** 在此之前兩者共用 `ScanError` → exit 1，
    而 6 本書裡有 **3 本**長期處在「還沒到那一層」（只有 `raw/`）：實測
    `beat-lint --book gothic_witch` 印**一行**「掃描錯誤：找不到幕綱目錄」、
    **連覆蓋率行都不印**、exit 1——與一支格式真的壞掉的書**完全不可分辨**。

    它是 CI 的必要條件（抉擇 2 A）：不分開的話那 3 本純 raw 書會讓 CI 永遠紅。

    契約（`共同約定.md`「輸出與 exit 契約」）：**exit 2，而且照樣印覆蓋率行**
    （「掃了 0 支」）——`設計原則.md` E2「0 也印」在錯誤路徑上一樣成立。
    """


FIELDS = ("角色", "時空", "行動", "衝突", "結果", "前因", "伏筆", "結構階段")

# 八欄裡有兩欄是**結構化連結欄**，不是散文：`前因` 只寫 `[[幕NNN]]`、`伏筆` 只寫
# `埋/收[[伏筆:x]]` 與 `arcNN（未拆）`／「見伏筆狀態表」這類指標（`幕綱.schema.md`
# 「連結規範」「本 arc 伏筆狀態」）。把它們算進母題重複與元管理掃描會製造大量假陽性：
# 實測未排除時「見伏筆狀態」「伏筆狀態表」佔滿每個 arc 的重複前三名，而 `arcNN（未拆）`
# 讓連 arc01 都被判成分區衛生違規。**指標欄的重複是格式，不是母題。**
PROSE_FIELDS = ("角色", "時空", "行動", "衝突", "結果", "結構階段")

# 母題重複再少一欄：`角色` 是**名單**，不是散文。主角每一幕都要列，「孟奇（真定）」
# 與「（心裡·不在場：…）」這類括註格式因此在每個 arc 都會重複——那是 schema 要求的
# 樣板，不是母題在迴圈。實測未排除時 arc11 的重複前五名有兩名是角色欄樣板
# （「心裡不在場」×5、「孟奇真定妙音」×5），排除後 arc01↔arc11 的分離從 8 倍升到 11 倍。
MOTIF_FIELDS = ("時空", "行動", "衝突", "結果", "結構階段")

# Windows 上的編輯器（含 PowerShell `Set-Content -Encoding utf8`）常寫出帶 BOM 的
# UTF-8。BOM 會黏在第一行行首，讓開頭的 `# arcNN`／`## 幕001` 認不出來而被靜默跳過
# ——**少掃一整支 arc 比報錯還難查**，而本套件的 `beat-lint` 存在的理由正是消滅這類
# 靜默漏掉。`utf-8-sig` 有 BOM 就吃掉、沒有也照常運作。
# （理由與 `fact_projection/sources.py:_ENCODING` 同源；`derived_sync` 刻意不跟進，
#  它讀檔是為了算 hash，換編碼會讓既有 `generated-from` 全數失準。）
_ENCODING = "utf-8-sig"


def read_text(path: Path) -> str:
    """本套件讀幕綱檔的唯一入口（見 `_ENCODING` 的理由）。"""
    return path.read_text(encoding=_ENCODING)


_BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)\s*[·・]?\s*(.*)$")
# 全形／半形冒號都收：schema 寫全形，實檔兩種都出現過，錯字不該靜默漏掉。
_FIELD_RE = re.compile(rf"^-\s*({'|'.join(FIELDS)})\s*[：:]\s*(.*)$")
_ARC_FILE_RE = re.compile(r"^arc[0-9A-Za-z]+$")


@dataclass
class Beat:
    number: int
    title: str
    arc: str
    lineno: int
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def prose(self) -> str:
        """六個散文欄併成一串——元管理字樣掃描以此為母體（見 `PROSE_FIELDS`）。"""
        return "".join(self.fields.get(k, "") for k in PROSE_FIELDS)

    @property
    def motif_body(self) -> str:
        """母題重複的母體：再去掉名單型的 `角色` 欄（見 `MOTIF_FIELDS`）。"""
        return "".join(self.fields.get(k, "") for k in MOTIF_FIELDS)


@dataclass
class ArcBeats:
    arc: str
    path: Path
    beats: list[Beat] = field(default_factory=list)


def scan_arc(path: Path, arc: str) -> ArcBeats:
    """掃一個 arc 幕綱的八欄。

    續行（欄位值換行續寫）併回該欄；`##` 之後、第一個欄位之前的散文（arc 檔頭、
    幕註）一律丟棄——它們不是欄位，不該進統計。
    """
    out = ArcBeats(arc=arc, path=path)
    current: Beat | None = None
    current_field: str | None = None
    for i, raw in enumerate(read_text(path).splitlines(), start=1):
        if raw.startswith("##"):
            m = _BEAT_HEAD_RE.match(raw)
            if m:
                current = Beat(
                    number=int(m.group(1)), title=m.group(2).strip(), arc=arc, lineno=i
                )
                out.beats.append(current)
            else:
                current = None  # 「本 arc 伏筆狀態」等非幕小節
            current_field = None
            continue

        if current is None:
            continue

        stripped = raw.strip()
        m = _FIELD_RE.match(stripped)
        if m:
            current_field = m.group(1)
            current.fields[current_field] = m.group(2).strip()
        elif current_field and stripped and not stripped.startswith(("-", "|", ">", "（", "(")):
            # 續行：欄位值被換行斷開時接回去。以 `-` 開頭的是下一個 bullet，
            # 以 `（` 開頭的是幕註（schema：幕註不是欄位），都不接。
            current.fields[current_field] += stripped
        else:
            current_field = None
    return out


def load_book(book: Path) -> list[ArcBeats]:
    """依 `幕綱/_順序.md`「全書順序」定序——與 foreshadow_project 同源的紀律：
    **判先後不能比幕號大小**（arc 會亂序下沉，幕號不代表全書順序）。
    """
    d = book / "story" / "幕綱"
    if not d.is_dir():
        raise LayerMissing(f"找不到幕綱目錄：{d}")
    files = {p.stem: p for p in sorted(d.glob("*.md")) if _ARC_FILE_RE.match(p.stem)}
    if not files:
        raise LayerMissing(f"{d} 下沒有 arcNN.md")

    order = _spine(spine_path(book), book)
    ranked = sorted(files, key=lambda a: (order.get(a, len(order)), a))
    return [scan_arc(files[a], a) for a in ranked]


# spine 的落點（2026-07-28 功能 12 抉擇 2 A；**回退 2026-07-30 移除**）。
#
# `全書順序：` 是作者的創作決定（哪一段先發生），沒有任何檔算得出來——它是 A1 源，
# 而它原本住在一支被 `beat-lint` 當「視圖 ≡ 資料夾」驗的索引檔裡。一支檔同時裝
# 「權威在自己身上的源」與「權威在別處的視圖」＝六問 Q0 的違反，所以 12 把它搬進
# 同層的 `_順序.md`。
#
# **舊落點 `_index.md` 的回退（驗證輪階段 1c）移除。** 實測活用戶**只有 `一世之尊`**
# ——`書本模板`／`驗證範例` 早就是 `_順序.md`，`harry_potter`／`gothic_witch`／
# `芯片巫師` 沒有幕綱層。四份回退實作服務一本刻意不遷移的病例書。
#
# **它換成墓碑，不是換成靜默**：檔在就報「舊落點還在、2026-07-30 起不再讀」，
# 並指出 `git mv` 那一行過去即可。依 `設計原則.md` A5，撤銷一個落點的身分要從
# 機制看得出來——不讀又不報，會讓「這本書沒有 spine」與「這本書的 spine 住舊落點」
# 變成同一句話。
#
# **回退活著的時候，這件事只有 1/4 成立**（功能 14 的 V9）：12 承諾四支工具都要讓
# 回退可見，而只有 `beat-lint` 有 `spine_legacy` 欄。現在四支都印，因為墓碑就是輸出。
SPINE_FILES = ("_順序.md",)
RETIRED_SPINE_FILES = ("_index.md",)


def spine_path(book: Path) -> Path:
    """回 spine 檔的落點。**唯一落點**——不在時照樣回它，讓錯誤訊息指向該建的那支。"""
    return book / "story" / "幕綱" / SPINE_FILES[0]


def retired_spine_files(book: Path) -> list[Path]:
    """還留在已廢除落點的 spine（`_index.md`）。**檔在就要說出來**（A5）。"""
    d = book / "story" / "幕綱"
    return [p for n in RETIRED_SPINE_FILES if (p := d / n).is_file()]


_SPINE_RE = re.compile(r"全書順序：(.+)$")
_ARC_TOKEN_RE = re.compile(r"arc[0-9A-Za-z]+")


def parse_spine(text: str) -> dict[str, int]:
    """`幕綱/_順序.md` 的「全書順序」→ {arc: 排名}。

    **這份解析的唯一真相在 `tools/fact_projection/src/fact_projection/fold.py:parse_spine`**；
    工具間零相依（所有 tools/*/pyproject.toml 皆 dependencies = []），故複製最小片段。

    **2026-07-27（功能 02 重構·V4）改成硬報錯。** 舊版讀不到就回 `{}` 退檔名排序，
    理由是「本工具全部是逐 arc 統計，定序只影響誰是前段基準」——那個理由**本身是錯的**：
    定序錯了，「相對本書前段」的基準就是拿錯誤的前段算的，可疑點排序全歪，**而它印
    exit 0**。同一個壞法，`foreshadow_project`／`fact_projection`／`decision_projection`
    三支全部 raise，只有本支靜默退化：**同一份資料，看你先跑哪支工具決定你會不會發現**
    （`設計原則.md` E2 第五格·假陰性）。實測 `驗證範例` 的 `_index.md` 就缺這一行。
    """
    for raw in text.splitlines():
        m = _SPINE_RE.search(raw)
        if not m:
            continue
        arcs: list[str] = []
        for tok in _ARC_TOKEN_RE.findall(m.group(1)):
            if tok not in arcs:
                arcs.append(tok)
        if arcs:
            return {a: r for r, a in enumerate(arcs)}
    raise ScanError("幕綱順序檔找不到可解析的『全書順序：』arc 序列")


def _spine(index: Path, book: Path | None = None) -> dict[str, int]:
    if not index.is_file():
        extra = ""
        if book is not None and (retired := retired_spine_files(book)):
            # **墓碑**：舊落點還在時要說出來，否則「這本書沒有 spine」與
            # 「這本書的 spine 住在一個已經不讀的落點」會是同一句錯誤訊息。
            extra = (
                f"。舊落點 `{retired[0].name}` 還在，但**2026-07-30 起不再讀它**"
                f"——`git mv` 那一行過去即可"
            )
        raise ScanError(
            f"找不到幕綱順序檔：{index}"
            f"（「全書順序：」是四支工具共用的定序來源）{extra}"
        )
    return parse_spine(read_text(index))


_POV_RE = re.compile(r"^視角結構:.*?POV\s*[:：]\s*([^,，}\s]+)", re.MULTILINE)


def load_pov(book: Path) -> str | None:
    """主角＝`00-摘要.ai.md` front-matter `視角結構.POV`。

    **讀不到就回 None、不猜**：純內在幕比例是「主角獨處」的比例，猜錯主角會讓
    整項數字失真且無從察覺——報「不適用」比報一個錯的數字誠實。
    """
    p = book / "story" / "00-摘要.ai.md"
    if not p.is_file():
        return None
    m = _POV_RE.search(read_text(p))
    return m.group(1).strip() if m else None
