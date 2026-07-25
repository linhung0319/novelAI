"""行文節奏偵測（診斷03 P8）。

`exposition.py` 抓「解說」，`drift.py` 抓「退化」，本檔抓**碎**——句與句、段與段
之間的節奏。它是 `技巧知識庫/字詞句法與抗生硬.md`（M1–M7，防「硬」）對稱的另一半：
那把尺全部十條病徵都是「太長、太抽象、太譯腔」型，總開關寫的是「更具體、更短、
更主動、更口語」，**沒有一條抓太碎**。

三項簽名，本檔實測全語料（每千漢字；回聲報佔 ≤12字非對白段的比例）：

                            破折號密度   顛簸指數   回聲佔比   分段
    known-good 六本語料       0.00–0.38  0.08–0.23  0.0–0.6%   8
    known-bad  生成一世之尊    6.42–9.76  1.87–3.51  0.0–9.1%  11 arc
    對照       生成芯片巫師    8.61–9.81  1.66–2.40  0.0–6.5%   3 arc

**芯片巫師是另一本書、另一份風格檔、另一個文類，簽名一模一樣。** 跨書恆定的東西
不可能由某一本書的風格檔造成——這是 LLM 的預設行文習性，而系統裡沒有任何一層在壓。
六本橫跨蒸汽克蘇魯／仙俠文言／系統流／都市恐怖的書在這三項上落在同一窄帶，
證明「與風格無關的行文地板」確實存在且可測。**兩組之間沒有任何重疊區**：最壞的
known-good（破折號 0.38）與最好的生成分段（6.42）之間差 17 倍。

診斷03 §1.1 的表是抽樣（原著取 30 章區間、生成取 10 章區間）算的，數量級與方向
一致，逐項略有出入；本檔的數字是**全語料 ＋ 修正後定義**（見 `_is_beat` 與
`_ECHO_EXEMPT_END` 兩處的實測理由），以本檔為準。

⚠️ **短本身無罪**。《極道天魔》的斷片段密度高於生成版（4.42 vs 2.2–3.7/千字）、
≥40字句字數佔比僅 13.5%，它比生成版更短更碎，而它在 known-good 名單裡——它的短行
每一行都有主謂、都在推進事件，且通篇維持同一速度。判準因此不是「句子要長」，
是這三條：**不要無資訊的重拍、不要高頻煞車、不要把逗號升級成句號**。
`test_rhythm.py` 把極道釘死成回歸案例，就是為了防止日後有人把本檔誤讀成「寫長一點」。
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from .drift import Finding
from .metrics import Chapter, paragraphs, strip_scaffolding

# 這三項用**絕對**門檻，是本檔與 drift.py 最大的不同。drift.py 的判準刻意相對本書
# 前段（篇幅／對白密度是文類相依的，武俠和推理的對白密度本來就不同），但上表證明
# 這三項跨文類收斂，且 known-good 與生成書之間**沒有任何重疊區**，絕對門檻成立且
# 不誤報。兩套判準並存，互不取代。
#
# 取值＝「剛好高於六本語料的 max，留約三成餘裕」（作者 2026-07-25 拍板）。六本全清
# 可當回歸測試釘死，而離最近的生成分段仍有數倍距離：
#                     六本 max    生成 min    門檻    上下餘裕
#     破折號密度        0.38        6.42       0.50    1.3× / 12.8×
#     顛簸指數          0.23        1.66       0.30    1.3× /  5.5×
#     回聲斷片佔比      0.6%        （見下）    1.5%    2.5× /  ——
#
# 回聲是三項裡唯一「單一分段可能合法為 0」的：生成書也有 0.0% 的 arc（一世之尊
# arc07、芯片巫師 arc01），因為它量的是**局部習慣**而非全書體質。那兩個 arc 仍被
# 另外兩項報出來——三項是互補的，不是三次量同一件事。
DASH_CAP = 0.5  # 每千漢字
JOLT_CAP = 0.3  # 每千漢字
ECHO_CAP = 0.015  # 佔 ≤12字非對白段的比例

# 回聲**佔比**的分母是「≤12字非對白段」，短段本來就少的書分母極小，一兩條就能
# 衝破門檻。樣本不足時不報（密度值仍照印，供人看）。
MIN_ECHO_SAMPLE = 20

_CJK = re.compile(r"[一-鿿]")

# 破折號：**連續出現算一次**（`——` 記 1，不記 2）。單個 `-` 不算，那是連字號。
_DASH = re.compile(r"[—─―]+|-{2,}")

# 對白段＝**以引號起首**者。這刻意不同於 `exposition._DIALOGUE`（全段任意位置、
# 需 ≥6 字）：那裡問的是「這段裡有沒有人在說話」，這裡問的是「這個短段是不是一句
# 台詞」——台詞短是正常的，不該算進顛簸與回聲。兩個定義服務不同病徵，各自保留。
_DIALOGUE_START = ("「", "“", '"', "『")

# 冒號結尾的短段＝對白引語（`克萊恩冷笑道：`／`陳丹朱苦笑一聲：`），是網文把說話人
# 單獨排一行的版式，不是獨立節拍。附錄 A 的定義只排除「以引號起首」，漏掉了這一半：
# 實測詭秘之主的顛簸指數 0.31→0.08，全部差額都是這個形狀。句法上它也不是一個完整
# 節拍——冒號代表「內容在下一段」，它自己沒說完。
_LEAD_IN = ("：", ":")

# 句切：句末標點之後斷開，但收尾引號要跟著上一句走（「他說。」不切成兩句）。
_SENT_SPLIT = re.compile(r'(?<=[。！？…])(?![」』”"])')

# 分句切：碎不碎的顆粒度就落在這一級——原著的「碎嘴感」住在分句層（平均 8.6 字、
# 每句串約 4 個的流水句），生成版把同樣的讀感實現在段落層。
_CLAUSE_SPLIT = re.compile(r"[，。！？；、…—]+")

# 回聲斷片的詞塊切法（附錄 A）。比 _CLAUSE_SPLIT 多吃空白，少吃分號。
_ECHO_CHUNK = re.compile(r"[。，！？、…—\s]+")

# 感嘆／提問結尾的短段**不算回聲**。附錄 A 的字面定義沒有這條，而實測顯示少了它
# 指標就廢掉：六本語料的命中幾乎全是擬聲與驚呼（`轟隆！`／`穿越了！`／`該怎么辦？`），
# 那些字詞當然會在前文出現——打鬥場面本來就連著響。加上這條之後：
#
#              六本語料        生成一世之尊   生成芯片巫師
#     字面定義   0.3–1.7%          2.7%          4.5%   ← 分離度 1.6 倍，指標不可用
#     加本條     0.0–0.6%          2.6%          4.5%   ← 分離度 4.3 倍
#
# 理由不是為了讓數字好看：`！`／`？` 帶的是新的**語氣行為**（擬聲、驚呼、自問），
# 病徵是**平述句的重述**——把剛說過的名詞加個句號再說一次（`真定。`／`玄悲。`／
# `薑湯。二少爺。老奴。`），沒有語氣、沒有新資訊，純粹是一次煞車。
_ECHO_EXEMPT_END = ("！", "？", "!", "?")

JOLT_SHORT = 8  # 顛簸：多短算「斷片段」
JOLT_LONG = 60  # 顛簸：鄰段多長算「長段」
ECHO_SHORT = 12  # 回聲：多短算「候選短段」
ECHO_LOOKBACK = 3  # 回聲：往前看幾段
LONG_SENT = 40  # 輔助量：多長算「長句」


@dataclass(frozen=True)
class ChapterRhythm:
    label: str
    group: str
    cjk: int
    paras: int
    dashes: int
    jolts: int
    echoes: int
    short_paras: int  # ≤12字非對白段（回聲佔比的分母）
    sent_lens: tuple[int, ...]
    clause_lens: tuple[int, ...]
    commas: int
    periods: int


@dataclass(frozen=True)
class RhythmStat:
    group: str
    chapters: int
    cjk: int
    paras: int
    dashes: int
    jolts: int
    echoes: int
    short_paras: int
    sent_lens: tuple[int, ...]
    clause_lens: tuple[int, ...]
    commas: int
    periods: int

    def _per_k(self, n: int) -> float:
        return n * 1000 / self.cjk if self.cjk else 0.0

    # ---- 三項門檻量
    @property
    def dash_density(self) -> float:
        return self._per_k(self.dashes)

    @property
    def jolt_index(self) -> float:
        return self._per_k(self.jolts)

    @property
    def echo_density(self) -> float:
        return self._per_k(self.echoes)

    @property
    def echo_share(self) -> float:
        """佔 ≤12字非對白段的比例。比密度穩，不受篇幅與段落風格影響。"""
        return self.echoes / self.short_paras if self.short_paras else 0.0

    # ---- 輔助量（供對照 `可用句式` 宣告，非門檻）
    @property
    def sent_median(self) -> float:
        return statistics.median(self.sent_lens) if self.sent_lens else 0.0

    @property
    def long_sent_share(self) -> float:
        """字數落在 ≥40 字句的比例——問的是「多少字活在長句裡」，不是「多少句是長句」。"""
        total = sum(self.sent_lens)
        return sum(n for n in self.sent_lens if n >= LONG_SENT) / total if total else 0.0

    @property
    def comma_period(self) -> float:
        return self.commas / self.periods if self.periods else 0.0

    @property
    def clause_mean(self) -> float:
        return statistics.mean(self.clause_lens) if self.clause_lens else 0.0

    @property
    def sent_per_para(self) -> float:
        """句/段。**顛簸指數的機制解釋**，本輪從語料反推出來、診斷03 未載。

        六本語料 0.96–1.22（＝一句一段是常態，段落就是句子），兩本生成書 1.69／2.13，
        無重疊。生成版的形狀因此是：**多句擠成的密集長段 ＋ 夾在中間的斷片段**，
        長短在段落級高頻擺盪；語料則通篇同一顆粒度，沒有可擺盪的空間。

        列為輔助量而非門檻：它是機制而非病徵本身（顛簸指數已經在量病徵），
        且一句一段是網文排版慣例，文學向的書未必要跟。
        """
        return len(self.sent_lens) / self.paras if self.paras else 0.0


def cjk_len(s: str) -> int:
    return len(_CJK.findall(s))


def _is_dialogue(para: str) -> bool:
    return para.startswith(_DIALOGUE_START)


def _is_beat(para: str, n_cjk: int, cap: int) -> bool:
    """這個段落算不算一個「短的散文節拍」——顛簸與回聲共用的候選閘。

    三個排除：對白段（台詞短是正常的）、對白引語（見 `_LEAD_IN`）、
    以及**漢字數 0 的段**（`……` 分隔行、`PS：求收藏` 作者按語、純數字標題）——
    那些不是斷片段，是排版。實測從紅月開始的顛簸指數 0.36→0.15，差額全是這一類。
    """
    return (
        1 <= n_cjk <= cap
        and not _is_dialogue(para)
        and not para.rstrip().endswith(_LEAD_IN)
    )


def _echo_hit(para: str, prev: str) -> bool:
    """整段每一個詞塊都在前幾段裡逐字出現過＝把剛說過的話複製成一個重拍。

    典型長相：`薑湯。二少爺。老奴。`／`別惹眼。別耍性子。安安分分。`——六本語料
    近乎不存在（≤0.6%），是純 LLM 產物。
    """
    if para.rstrip().endswith(_ECHO_EXEMPT_END):
        return False
    chunks = [c for c in (_cjk_only(x) for x in _ECHO_CHUNK.split(para)) if c]
    if not chunks:
        return False
    return all(len(c) >= 2 and c in prev for c in chunks)


def _cjk_only(s: str) -> str:
    return "".join(_CJK.findall(s))


def scan_rhythm(ch: Chapter, drop_title: bool = False) -> ChapterRhythm:
    """掃一章。

    `drop_title`：純文字語料（`examples/<書>/*.txt`）的首行是章名、沒有 `#`，
    `strip_scaffolding` 去不掉，會被當成一個 6–10 字的斷片段直接污染顛簸與回聲。
    書資料夾的 `chNNNN.md` 標題有 `#`，已被去掉，故不需要。
    """
    prose = strip_scaffolding(ch.path.read_text(encoding="utf-8", errors="replace"))
    paras = paragraphs(prose)
    if drop_title and paras:
        paras = paras[1:]

    lens = [cjk_len(p) for p in paras]

    jolts = 0
    echoes = 0
    short_paras = 0
    for i, p in enumerate(paras):
        if _is_beat(p, lens[i], JOLT_SHORT) and (
            (i > 0 and lens[i - 1] >= JOLT_LONG)
            or (i + 1 < len(paras) and lens[i + 1] >= JOLT_LONG)
        ):
            jolts += 1
        if _is_beat(p, lens[i], ECHO_SHORT):
            short_paras += 1
            prev = _cjk_only("".join(paras[max(0, i - ECHO_LOOKBACK) : i]))
            if prev and _echo_hit(p, prev):
                echoes += 1

    sent_lens: list[int] = []
    clause_lens: list[int] = []
    for p in paras:
        sent_lens += [n for n in (cjk_len(s) for s in _SENT_SPLIT.split(p)) if n]
        clause_lens += [n for n in (cjk_len(c) for c in _CLAUSE_SPLIT.split(p)) if n]

    body = "".join(paras)
    return ChapterRhythm(
        label=ch.label,
        group=ch.group,
        cjk=sum(lens),
        paras=len(paras),
        dashes=len(_DASH.findall(body)),
        jolts=jolts,
        echoes=echoes,
        short_paras=short_paras,
        sent_lens=tuple(sent_lens),
        clause_lens=tuple(clause_lens),
        commas=body.count("，"),
        periods=body.count("。"),
    )


def combine(rows: list[ChapterRhythm], group: str) -> RhythmStat:
    return RhythmStat(
        group=group,
        chapters=len(rows),
        cjk=sum(r.cjk for r in rows),
        paras=sum(r.paras for r in rows),
        dashes=sum(r.dashes for r in rows),
        jolts=sum(r.jolts for r in rows),
        echoes=sum(r.echoes for r in rows),
        short_paras=sum(r.short_paras for r in rows),
        sent_lens=tuple(n for r in rows for n in r.sent_lens),
        clause_lens=tuple(n for r in rows for n in r.clause_lens),
        commas=sum(r.commas for r in rows),
        periods=sum(r.periods for r in rows),
    )


def summarize_rhythm(rows: list[ChapterRhythm]) -> list[RhythmStat]:
    order: list[str] = []
    buckets: dict[str, list[ChapterRhythm]] = {}
    for r in rows:
        if r.group not in buckets:
            buckets[r.group] = []
            order.append(r.group)
        buckets[r.group].append(r)
    return [combine(buckets[g], g) for g in order]


def detect_rhythm(
    stats: list[RhythmStat],
    dash_cap: float = DASH_CAP,
    jolt_cap: float = JOLT_CAP,
    echo_cap: float = ECHO_CAP,
) -> list[Finding]:
    """絕對門檻，不需要基準分組——這正是它與 `drift.detect` 的分工。

    **advisory**：命中＝候選，交作者判斷，不是 pass/fail。刻意的全短風格
    （極道天魔型）三項簽名全清，不會被這裡報出來。
    """
    findings: list[Finding] = []
    for s in stats:
        if s.dash_density > dash_cap:
            findings.append(
                Finding(
                    group=s.group,
                    metric="破折號密度",
                    detail=(
                        f"{s.dash_density:.2f}/千漢字（上限 {dash_cap}，語料 0.00–0.38）"
                        f"——重拍裝置是稀缺資源，約每 {1000 / s.dash_density:.0f} 字一個"
                    ),
                )
            )
        if s.jolt_index > jolt_cap:
            findings.append(
                Finding(
                    group=s.group,
                    metric="顛簸指數",
                    detail=(
                        f"{s.jolt_index:.2f}/千漢字（上限 {jolt_cap}，語料 0.08–0.23）"
                        f"——{s.jolts} 個 ≤{JOLT_SHORT}字斷片段緊鄰 ≥{JOLT_LONG}字長段，"
                        "每一個都是一次完全煞車"
                    ),
                )
            )
        if s.short_paras >= MIN_ECHO_SAMPLE and s.echo_share > echo_cap:
            findings.append(
                Finding(
                    group=s.group,
                    metric="回聲斷片",
                    detail=(
                        f"{s.echo_share:.1%}（{s.echoes}/{s.short_paras} 個 ≤{ECHO_SHORT}字"
                        f"非對白段；上限 {echo_cap:.1%}，語料 0.0–0.6%）"
                        "——把上一段剛說過的話逐字複製成獨立短段當重拍，無新資訊"
                    ),
                )
            )
    return findings
