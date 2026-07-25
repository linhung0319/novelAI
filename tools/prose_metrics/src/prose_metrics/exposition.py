"""解說段偵測（診斷01 R4）。

病徵不是句級的頓悟宣布句，而是**段落級的解說結構**——整段的工作是解說剛才那一手
的用意，或把推理過程結算成條列。所以分析單位是**段**，命中規則是「回指 ＋ 功能宣告」
的**結構共現**，不是任一詞出現。

實測三組語料（候選/千字）：

                    段級（本檔主訊號）   句級（舊詞表）
    known-good 原著 501 章    0.007            0.002
    known-bad  生成  93 章    0.352 （50 倍）  0.000
    對照 芯片巫師    23 章    0.049            0.016

**舊的句級詞表對本病徵是反相關的**——它在健康語料上比在病態語料上響得更多（生成版
整整 93 章一條都沒有）。句級掃描仍留在這裡，只是為了把它從「LLM 讀全文」搬進程式，
它是低產出區塊，別當主訊號用。`test_exposition.py` 把這個方向釘死，就是為了防止日後
有人再把它升回主力。

⚠️ 限制：M1/M2 是在**第一人稱** known-bad 語料上調出來的。標記本身與人稱無關
（這一手／這一下／盤算／得出結論 在第三人稱同樣成立），但「第三人稱下召回率多少」
目前無語料可驗——唯一的第三人稱語料是 known-good，它本來就幾乎不犯這個病。
要等新書實驗才能收斂。
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from .drift import BASELINE_FRACTION, MIN_GROUPS, Finding
from .metrics import Chapter, paragraphs, strip_scaffolding

# 報出漂移的雙條件，沿用 drift.py 獨白章佔比的寫法。樓地板存在的唯一理由是
# 基準可能為 0（原著卷一＝0.000，倍率無意義）；候選清單本身無門檻、純 advisory。
EXPO_RATIO = 2.0  # 相對本書前段基準的倍率
EXPO_FLOOR = 0.05  # 候選/千字，低於此不談漂移

MIN_PARAGRAPH = 15  # 短促句不是解說段

# 對白跨距。**三種引號都要**：原著用彎引號、芯片巫師用【】、生成版用「」。
# 只寫「」的話 known-good 會多出十幾條誤報——這是三組語料回歸抓到的第一個 bug。
# 門檻 6 字：短引號多半是引用詞（「想不起事」），不是有人在說話。
_DIALOGUE = re.compile(r"[「“【][^」”】]{6,}[」”】]")

# M1 自指回述＋功能宣告：指向自己剛才言行的指示語，緊接判斷／目的語。
# 長的替代項要排在短的前面（Python 的 | 取第一個成功的分支）。
_BACK = r"(?:這|那)(?:句話|一句|句|話|一手|一下|一問|一答|番話|一著|一招|麼一說|麼一來)"
_DECL = r"(?:是|就是|等於|意味|為的|目的|作用|留的|好處|意思)"
_M1 = re.compile(_BACK + r"[，、]?.{0,6}?" + _DECL)

# M2 元認知結算：把推理過程當帳目結算的措辭。
_M2 = re.compile(
    r"(?:[先再又]算[^。，]{0,10}|算了一[遍筆下]|算一[算遍筆]|盤算|捋了?一遍|推了?一遍"
    r"|擺清楚|理清楚|得出[^。]{0,10}結論|過了一遍|算一筆帳)"
)

# 句級反射式收尾詞表（低產出，見檔頭）。頓悟動詞必須是**認知**動詞——裸的「他終於」
# 會誤中「他終於轉過頭」這種物理動作。
_REFLEX = re.compile(
    r"(?:(?:他|她|它)(?:懂了|明白了|忽然明白|這才(?:想起|明白|懂|發現)"
    r"|終於(?:明白|懂了|想通|想起))|原來如此|這(?:意味著|說明|代表)"
    r"|(?:他|她)(?:心裡)?很清楚)"
)

# 切到**小句**而非句子：禁的是收尾用法，而「他終於明白了，於是抬手推開門」整句
# 以句號結尾，只切句子的話這個宣布句會被當成收尾。小句才切得出「它在不在最後」。
_CLAUSE_SPLIT = re.compile(r"[。！？…；，、]")

_KIND_M1 = "自指回述"
_KIND_M2 = "元認知結算"


@dataclass(frozen=True)
class Candidate:
    label: str
    group: str
    index: int  # 段序（第幾個非空行）
    kinds: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class ChapterExposition:
    label: str
    group: str
    chars: int
    paragraph: tuple[Candidate, ...]  # 段級（主訊號）
    sentence: tuple[Candidate, ...]  # 句級（低產出）


@dataclass(frozen=True)
class ExpoStat:
    group: str
    chapters: int
    chars: int
    paragraph_hits: int
    sentence_hits: int

    @property
    def density(self) -> float:
        """段級候選／千字。用密度而非絕對數，否則篇幅腰斬會把病徵一起藏起來。"""
        return self.paragraph_hits * 1000 / self.chars if self.chars else 0.0


def _last_clause(para: str) -> str:
    parts = [s for s in _CLAUSE_SPLIT.split(para.rstrip("。！？…")) if s.strip()]
    return parts[-1] if parts else ""


def scan_chapter(ch: Chapter) -> ChapterExposition:
    prose = strip_scaffolding(ch.path.read_text(encoding="utf-8", errors="replace"))
    paras = paragraphs(prose)
    para_hits: list[Candidate] = []
    sent_hits: list[Candidate] = []
    for i, p in enumerate(paras):
        if _DIALOGUE.search(p):
            continue  # 有人在說話的段落不是解說段
        if len(p) >= MIN_PARAGRAPH:
            kinds = tuple(
                k for k, rx in ((_KIND_M1, _M1), (_KIND_M2, _M2)) if rx.search(p)
            )
            if kinds:
                para_hits.append(Candidate(ch.label, ch.group, i, kinds, p))
        # 句級只認「落在段落最後一句」——禁的是收尾用法，不是這些字永不出現。
        if len(p) >= 10 and _REFLEX.search(_last_clause(p)):
            sent_hits.append(Candidate(ch.label, ch.group, i, ("反射式收尾",), p))
    return ChapterExposition(
        label=ch.label,
        group=ch.group,
        chars=sum(len(p) for p in paras),
        paragraph=tuple(para_hits),
        sentence=tuple(sent_hits),
    )


def summarize_exposition(rows: list[ChapterExposition]) -> list[ExpoStat]:
    order: list[str] = []
    buckets: dict[str, list[ChapterExposition]] = {}
    for r in rows:
        if r.group not in buckets:
            buckets[r.group] = []
            order.append(r.group)
        buckets[r.group].append(r)
    return [
        ExpoStat(
            group=g,
            chapters=len(rs),
            chars=sum(r.chars for r in rs),
            paragraph_hits=sum(len(r.paragraph) for r in rs),
            sentence_hits=sum(len(r.sentence) for r in rs),
        )
        for g in order
        for rs in [buckets[g]]
    ]


def detect_exposition(
    stats: list[ExpoStat],
    ratio: float = EXPO_RATIO,
    floor: float = EXPO_FLOOR,
) -> tuple[list[Finding], float | None]:
    """回傳 (可疑點, 基準密度)。分組太少就不談漂移——沒有基準可言。"""
    if len(stats) < MIN_GROUPS:
        return [], None
    n = max(1, int(len(stats) * BASELINE_FRACTION))
    base = statistics.mean(s.density for s in stats[:n])
    findings = [
        Finding(
            group=s.group,
            metric="解說密度",
            detail=(
                f"{s.density:.2f} 候選/千字，為基準 {base:.2f} 的 "
                f"{s.density / base:.1f} 倍" if base > 0 else
                f"{s.density:.2f} 候選/千字（基準 0.00）"
            ),
        )
        for s in stats[n:]
        if s.density >= floor and s.density >= base * ratio
    ]
    return findings, base
