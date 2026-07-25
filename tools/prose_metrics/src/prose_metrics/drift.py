from __future__ import annotations

import statistics
from dataclasses import dataclass

from .metrics import Metrics

# 判準是**相對**的：拿這本書自己的前段當基準。
# 絕對門檻是文類相依的（武俠和推理的對白密度本來就不同），但「這本書的章長腰斬了」
# 是普世的——R7 的原問題就是「第 84 章跟第 1 章讀起來還是同一本書嗎」。
DROP_RATIO = 0.65  # 掉到基準的這個比例以下即報
SOLO_RATIO = 0.34  # 獨白章佔比上限
BASELINE_FRACTION = 1 / 3  # 取前這麼多比例的分組當基準
MIN_GROUPS = 3  # 少於這麼多分組就不談漂移（沒有基準可言）


@dataclass(frozen=True)
class GroupStat:
    group: str
    chapters: int
    chars: float
    quote_density: float
    cast: float
    solo_share: float


@dataclass(frozen=True)
class Finding:
    group: str
    metric: str
    detail: str


def summarize(rows: list[Metrics]) -> list[GroupStat]:
    order: list[str] = []
    buckets: dict[str, list[Metrics]] = {}
    for m in rows:
        if m.group not in buckets:
            buckets[m.group] = []
            order.append(m.group)
        buckets[m.group].append(m)
    return [
        GroupStat(
            group=g,
            chapters=len(ms),
            chars=statistics.mean(m.chars for m in ms),
            quote_density=statistics.mean(m.quote_density for m in ms),
            cast=statistics.mean(m.cast for m in ms),
            solo_share=sum(1 for m in ms if m.solo) / len(ms),
        )
        for g in order
        for ms in [buckets[g]]
    ]


MIN_BASELINE_CAST = 1.0  # 基準的在場角色低於此值＝詞彙表沒覆蓋到，該指標不具意義


def detect(
    stats: list[GroupStat],
    drop: float = DROP_RATIO,
    solo_cap: float = SOLO_RATIO,
    cast_metrics: bool = True,
) -> tuple[list[Finding], GroupStat | None]:
    """回傳 (可疑點, 基準分組的合成值)。分組太少時不談漂移。

    **篇幅／對白密度不依賴詞彙表**（普世量，任何書都成立）；
    **在場角色／獨白章依賴該書的 設定/角色/ 覆蓋度**——詞彙表沒建或沒覆蓋到受測期間時，
    這兩項會系統性偏低，報出來全是假的，故基準過低時整組跳過。
    """
    if len(stats) < MIN_GROUPS:
        return [], None
    n = max(1, int(len(stats) * BASELINE_FRACTION))
    base_rows = stats[:n]
    base = GroupStat(
        group=f"基準（前 {n} 段：{'／'.join(s.group for s in base_rows)}）",
        chapters=sum(s.chapters for s in base_rows),
        chars=statistics.mean(s.chars for s in base_rows),
        quote_density=statistics.mean(s.quote_density for s in base_rows),
        cast=statistics.mean(s.cast for s in base_rows),
        solo_share=statistics.mean(s.solo_share for s in base_rows),
    )

    cast_meaningful = cast_metrics and base.cast >= MIN_BASELINE_CAST

    findings: list[Finding] = []
    for s in stats[n:]:
        checks = [
            ("篇幅", s.chars, base.chars, "字/章"),
            ("對白密度", s.quote_density, base.quote_density, "引號/千字"),
        ]
        if cast_meaningful:
            checks.append(("在場角色", s.cast, base.cast, "人/章"))
        for metric, cur, ref, unit in checks:
            if ref > 0 and cur < ref * drop:
                findings.append(
                    Finding(
                        group=s.group,
                        metric=metric,
                        detail=f"{cur:.1f} {unit}，為基準 {ref:.1f} 的 {cur / ref:.0%}",
                    )
                )
        # 獨白章要**同時**超過絕對上限與基準的 1.5 倍才報——只用絕對上限的話，
        # 基準本身就偏高的書會前後不一致（基準期不報、之後同樣數字卻報）。
        if (
            cast_meaningful
            and s.solo_share > solo_cap
            and s.solo_share > base.solo_share * 1.5
        ):
            findings.append(
                Finding(
                    group=s.group,
                    metric="獨白章佔比",
                    detail=(
                        f"{s.solo_share:.0%} 的章只提到 ≤1 個建檔角色"
                        f"（上限 {solo_cap:.0%}，基準 {base.solo_share:.0%}）"
                    ),
                )
            )
    return findings, base
