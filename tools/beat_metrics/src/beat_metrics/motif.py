"""母題語彙自我複製與行動欄膨脹（診斷01 P10 / R1 漂移）。

P10 的病徵是「『那顆子』『那道門』『手上的髒』『付利息』反覆迴圈」。診斷01 把它
歸在階段三、猜它是正文層的用詞問題——**實測證明那個歸屬是錯的**。

已測過但不成立：正文層的重複率
------------------------------
**用等長視窗量**（連續 3000 漢字一格，消掉章長差異；5-gram 重複率）：

                            重複率中位
    known-good 六本語料        4.3 – 15.8‰
    生成一世之尊 ch1–10        4.3‰
    生成一世之尊 末 15 章     13.3‰   ← 落在 known-good 帶的中段
    生成芯片巫師              13.7‰

**兩群完全重疊、分不開。** 任何抓得到生成書的門檻都會先誤傷《我有一個修仙世界》
（15.8‰）——與 `prose_metrics/rhythm.py` 檔頭「長句佔比不成立」同一形狀。

⚠️ **不要用不等長的樣本重測這一項**（第一輪踩過）：逐章量會得到「末 15 章 0.00%、
比每一本好書都更不重複」的假象——那是後段章只剩約 1050 字、重複短語達不到門檻造成的
長度假象，不是真的更不重複。**結論一樣是「不成立」，但理由是「重疊」不是「更低」。**
**不要再回頭做正文層 P10 偵測器。**

成立的是幕綱層
--------------
同一個 5-gram 重複率改掃**幕綱的散文欄**（`scan.MOTIF_FIELDS`），乾淨分離 11 倍：

            arc01  arc05  arc08  arc10  arc11
    重複率    4.6‰  51.2‰  47.3‰  62.6‰   87.7‰   ← arc11 為 2026-07-26 遷移前
    行動均長  76 字  163    448    311    355

診斷01 自己寫的「P10＝R9 下滲」是對的：母題語彙在幕綱層被宣告、在每一幕被複述，
`write` 抄的是欄位，於是複述被原樣散文化進正文。**病灶在上游，量就要量在上游。**

⚠️ **三個欄位不算進來**（實測逐一踩過）：`前因`／`伏筆` 是結構化連結欄（「見伏筆狀態表」
之類的指標會佔滿重複前三名，把真正的母題擠出榜外）；`角色` 是名單（主角每幕都要列，
「孟奇（真定）」與「（心裡·不在場：…）」是 schema 要求的樣板）。**判準是「這一欄重複
是格式還是內容」**——格式重複進榜就是雜訊。理由見 `scan.PROSE_FIELDS` 與 `MOTIF_FIELDS`。

判準是相對的，不是絕對的
------------------------
比照 `prose_metrics/drift.py`：拿**這本書自己的前段**當基準。絕對值是書/文類相依的
（母題重的書本來就會複述得多），但「這本書的行動欄長了 4.7 倍、重複率漲了 12 倍」
與文類無關。故本檔不內建任何門檻詞表，只比本書自己。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .scan import ArcBeats

NGRAM = 5
BASELINE_ARCS = 2  # 前幾個 arc 當基準
RISE = 3.0  # 超過基準幾倍算可疑點
MIN_CHARS = 500  # 八欄太短時比值不穩，不談漂移

_CJK_RE = re.compile(r"[一-鿿]+")


@dataclass(frozen=True)
class ArcMotif:
    arc: str
    beats: int
    chars: int
    repeat_rate: float  # 每千漢字的重複 n-gram 數
    action_mean: float
    hot: tuple[tuple[int, str], ...]  # (次數, 詞) 前幾名，供人眼看是哪個母題在迴圈


@dataclass(frozen=True)
class Finding:
    arc: str
    metric: str
    detail: str


def _cjk(text: str) -> str:
    return "".join(_CJK_RE.findall(text))


def measure(arc: ArcBeats, action_mean: float, top: int = 3) -> ArcMotif:
    body = _cjk("".join(b.motif_body for b in arc.beats))
    grams: dict[str, int] = {}
    for i in range(len(body) - NGRAM + 1):
        g = body[i : i + NGRAM]
        grams[g] = grams.get(g, 0) + 1
    dup = sum(c - 1 for c in grams.values() if c > 1)
    hot = sorted(((c, g) for g, c in grams.items() if c >= 4), reverse=True)[:top]
    return ArcMotif(
        arc=arc.arc,
        beats=len(arc.beats),
        chars=len(body),
        repeat_rate=dup * 1000 / len(body) if len(body) else 0.0,
        action_mean=action_mean,
        hot=tuple(hot),
    )


def detect(
    stats: list[ArcMotif], baseline: int = BASELINE_ARCS, rise: float = RISE
) -> tuple[list[Finding], ArcMotif | None]:
    """相對本書前段偵測。前段本身不參與判定（它就是尺）。"""
    usable = [s for s in stats if s.chars >= MIN_CHARS]
    if len(usable) < baseline + 1:
        return [], None
    base_rows = usable[:baseline]
    base = ArcMotif(
        arc=f"（基準＝前 {baseline} 個 arc）",
        beats=sum(s.beats for s in base_rows),
        chars=sum(s.chars for s in base_rows),
        repeat_rate=sum(s.repeat_rate for s in base_rows) / baseline,
        action_mean=sum(s.action_mean for s in base_rows) / baseline,
        hot=(),
    )
    out: list[Finding] = []
    for s in usable[baseline:]:
        for metric, cur, ref, unit in (
            ("母題重複率", s.repeat_rate, base.repeat_rate, "‰"),
            ("行動欄長度", s.action_mean, base.action_mean, "字/幕"),
        ):
            if ref > 0 and cur > ref * rise:
                out.append(
                    Finding(
                        arc=s.arc,
                        metric=metric,
                        detail=f"{cur:.1f}{unit}，為基準 {ref:.1f} 的 {cur / ref:.1f} 倍",
                    )
                )
    return out, base
