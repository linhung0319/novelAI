"""幕的可演性（`beat-test` 測試9 / 診斷02 R1-c）。

抓的是**空洞**，不是矛盾。系統其餘測試全是「反矛盾」（罰做錯）；本檔是唯一
「反空洞」（罰什麼都不做）的機械層——在一個只有負向約束的系統裡，最安全的產出
就是最空的產出（診斷01 §四）。

四個子項全部零語意判斷：
    (a) 行動欄禁止清單詞式命中   ← `幕綱.schema.md`「八欄只寫故事事實」四類
    (b) 純內在幕（角色欄只剩主角一人）
    (c) 連續段
    (d) 分區衛生：八欄裡的元管理字樣

**可疑點判在 (a)∧(b)，不判在 (b) 單獨**——建工具時實測改掉的一條
------------------------------------------------------------------
診斷02 §3 原訂「純內在幕 >1/3 即可疑」，並記 arc01＝0/9。實際掃出來 arc01 是
**2/9**：幕008（入定修行、化生真氣、察覺底子反常）與幕009（被什麼遠遠掃過又鬆開）
——主角確實獨處，但**行動欄有鏡頭拍得到的東西**，是健康的幕。診斷那個 0/9 是手數
的誤差，而它正是「(b) 單獨會誤傷」的證據。

一世之尊全 11 arc 實測（2026-07-26 遷移前，(a)∧(b)＝「獨處且行動欄只剩主題陳述」）：

                    arc01 02 03 04 05 06 07 08 09 10 11
    純內在幕          2  0  0  0  1  1  1  1  2  4  6
    空洞幕 (a)∧(b)    0  0  0  0  1  0  0  1  0  1  5

**(b) 單獨無法分離**（arc01 就有 2 幕，與 arc10 的 4、arc11 的 6 之間沒有乾淨的線）；
**合取之後前四個 arc 全清、arc11 燒到 45%＋兩段連續**。單獨的純內在幕仍照報，但只當
資訊列——一個人在場不是病，一個人在場**而且沒有東西可拍**才是。

門檻是「供排序」不是 pass/fail（`共同約定.md` 五：AI 是審稿員不是門檻）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .scan import ArcBeats, Beat

HOLLOW_SHARE_CAP = 1 / 3
RUN_CAP = 2

# 行動欄四類禁止內容的詞式（`幕綱.schema.md`「八欄只寫故事事實」）。
# 刻意**不含任何文類詞**——全是「元層級」用語，換一本書、換一個文類都一樣。
BANNED_ACTION = (
    "母題", "落地", "新軸", "那一階", "質地", "聲部", "兌現", "檔位",
    "本段", "收點", "讀者", "預演", "加重", "收束", "同源", "遞向",
    "結構功能", "斜升", "配重",
)

# 分區衛生：治理文字滲進八欄的簽名。八欄只寫故事事實，這些一律屬檔尾設計註。
META_MARKS = ("護欄", "排除線", "判例", "拍板", "射程", "降回閥", "本欄權威")

# arc 引用要看**引用的形狀**，不能光看 `arc\d`：`結果` 欄寫「接 arc02 輪回世界啟動」
# 是章末鉤的故事事實，`行動` 欄寫「與 arc09 刻意成對比」才是設計理由。實測裸 `arc\d`
# 會把 known-good 的 arc01／arc03 全報進去（arc01 幕009、arc03 五幕），分區衛生因此
# 失去鑑別力；改成比對式引用後 arc01–arc03 全清、arc11 仍中 4 幕。
_META_ARC_RE = re.compile(
    r"(刻意|比照|延續|同|守|見|照抄|對比|承)\s*arc\d|arc\d\s*(判例|檔頭|通則|那組|成對比)"
)

# 角色欄裡代表「不在場」的括註標記。**刻意不含「背景」**——背景僧眾是物理在場的，
# 可以被搭話，算得上一個可演的對手；把它當缺席會高估純內在幕。寧可少報。
ABSENT_MARKS = (
    "不出場", "不在場", "心裡", "暗處", "空缺", "聲音",
    "不照面", "未照面", "事後提起", "不揭", "尚未",
)

_PAREN_RE = re.compile(r"[（(][^（()）]*[)）]")
_LABEL_RE = re.compile(r"^[^：:]{0,8}[：:]")


@dataclass(frozen=True)
class BeatFlags:
    beat: int
    title: str
    solo: bool
    banned: tuple[str, ...]
    meta: tuple[str, ...]
    action_len: int

    @property
    def hollow(self) -> bool:
        """獨處**且**行動欄只剩主題陳述＝這一幕拍不出東西。見檔頭實測理由。"""
        return self.solo and bool(self.banned)


@dataclass(frozen=True)
class ArcPlayability:
    arc: str
    flags: list[BeatFlags]

    @property
    def total(self) -> int:
        return len(self.flags)

    @property
    def solo_beats(self) -> list[int]:
        return [f.beat for f in self.flags if f.solo]

    @property
    def hollow_beats(self) -> list[int]:
        return [f.beat for f in self.flags if f.hollow]

    @property
    def hollow_share(self) -> float:
        return len(self.hollow_beats) / self.total if self.total else 0.0

    @property
    def hollow_runs(self) -> list[list[int]]:
        """連續空洞幕（長度 ≥2）。單獨一幕的收點餘韻合法，連著才是病。"""
        return _runs([f.hollow for f in self.flags], [f.beat for f in self.flags])

    @property
    def solo_runs(self) -> list[list[int]]:
        return _runs([f.solo for f in self.flags], [f.beat for f in self.flags])

    @property
    def action_mean(self) -> float:
        return sum(f.action_len for f in self.flags) / self.total if self.total else 0.0

    @property
    def meta_beats(self) -> list[int]:
        return [f.beat for f in self.flags if f.meta]


def _runs(mask: list[bool], beats: list[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    cur: list[int] = []
    for hit, b in zip(mask, beats):
        if hit:
            cur.append(b)
        else:
            if len(cur) >= RUN_CAP:
                runs.append(cur)
            cur = []
    if len(cur) >= RUN_CAP:
        runs.append(cur)
    return runs


def _others(cast: str, pov: str | None) -> list[str]:
    """角色欄裡除主角以外、**在場且可演**的角色。

    括註有兩種，要分開處理——**用有沒有冒號來分**：

    - **別名／狀態註**（`孟奇（真定）`、`真應（被誤鎖定·不知情）`）：無冒號。整組丟掉，
      前面那個名字仍在場。
    - **具名群組**（`（背景：帶隊執事、水月庵隨行）`、`（暗處：無凈；背景：寺方）`）：有冒號。
      **逐子群判定並攤平**——群組內可能用 `；` 併寫在場與不在場兩組（實例：
      `（帶隊執事·因故不在場／被調開；背景：無退步步進逼）`），整組丟掉會把還在場的
      對手一起丟掉、把有戲的幕誤判成獨處幕。攤平（而非保留括號）是必要的，否則下面
      那一步的通用去括號會把剛留下來的內容再刪一次。
    """

    def _keep(group: str) -> str:
        inner = group[1:-1]
        if "：" not in inner and ":" not in inner:
            return ""  # 別名／狀態註
        kept = [s for s in re.split(r"[；;]", inner) if not any(k in s for k in ABSENT_MARKS)]
        return "、" + "、".join(kept) if kept else ""

    text = _PAREN_RE.sub(lambda m: _keep(m.group(0)), cast)
    segments = [s for s in re.split(r"[／/]", text) if not any(k in s for k in ABSENT_MARKS)]
    out: list[str] = []
    for seg in segments:
        seg = _PAREN_RE.sub("", seg)
        for tok in re.split(r"[、,，]", seg):
            tok = _LABEL_RE.sub("", tok.strip()).strip(" *〔〕[]　")
            if not tok:
                continue
            if pov and (tok == pov or tok in pov or pov in tok):
                continue
            out.append(tok)
    return out


def _flags(b: Beat, pov: str | None) -> BeatFlags:
    action = b.fields.get("行動", "")
    prose = b.prose
    return BeatFlags(
        beat=b.number,
        title=b.title,
        # 讀不到 POV 時一律不判 solo（`scan.load_pov` 的「不猜」紀律延伸到這裡）
        solo=bool(pov) and not _others(b.fields.get("角色", ""), pov),
        banned=tuple(w for w in BANNED_ACTION if w in action),
        meta=tuple(w for w in META_MARKS if w in prose)
        + (("arc比對",) if _META_ARC_RE.search(prose) else ()),
        action_len=len(action),
    )


def analyse(arc: ArcBeats, pov: str | None) -> ArcPlayability:
    return ArcPlayability(arc=arc.arc, flags=[_flags(b, pov) for b in arc.beats])
