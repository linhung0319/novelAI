"""裁決軸與待裁決軸的格式閘門（`decision-lint`）。

**為什麼這支工具存在。** `裁決流.schema.md` 宣告了七欄固定格式、三種射程寫法、
三種狀態值、append-only、「一項裁決一列」——**一條都沒有 lint 在守**
（`設計原則.md` E1：填不出檢查器就不准在 schema 裡宣稱那個格式）。而
`共同約定.md` 同時宣稱 `.co.md` 是「嚴格（有檢查器）」，那是口頭承諾。

`decision-project` 是**查詢器不是閘門**：不查的時候格式錯不會被發現，而
`write` 依設計不查（理由不進正文的 context），所以最常跑的 skill 永遠不會撞到。

**這支工具同時是 `.co.md` 這個檔類得以廢除的條件**（`設計原則.md` A4）：檔的
第二個位元「程式會不會解析它」由有沒有檢查器承擔，不由副檔名承擔。

**守的是「人破結構」那一側**（B1），與 `beat-lint`／`derived-sync validate` 同類。
內容好壞不歸它——裁決得對不對是作者的事。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .parse import (
    COLUMNS,
    PENDING_COLUMNS,
    SCOPE_ALL,
    SCOPE_ROUND,
    STATUS_PROMOTED,
    STATUSES,
    Decision,
    ParseError,
    Pending,
    parse_decisions,
    parse_pending,
)

# 「一項裁決一列」的可執行形式。把一輪 session 的全部決定併成一列長文會讓
# `--target` 過濾失效，而「併成一列」在檔案上的樣子就是這一欄變長。
# **`理由` 欄刻意不設上限**——那一欄就是拿來寫長的，設了上限等於把人趕回去
# 寫 blockquote，那正是本輪要修的病。
RULING_CHARS = 200
FINDING_CHARS = 200

_SCOPE_UNTIL_RE = re.compile(r"^至\s*arc[0-9A-Za-z]+$")
# 「已升為通則」的理由欄該是一句指過去，指向 `結構定義/` 或 `技巧知識庫/` 的某支檔。
_PROMOTED_REF_RE = re.compile(r"(結構定義/[^\s`）)]+\.md|技巧知識庫/[^\s`）)]+\.md)")


@dataclass
class LintStats:
    """**我在這本書上掃了幾列。**（`設計原則.md` E2 的可執行推論）

    `待裁決 N 列／裁決 M 列` 並排印是刻意的：歷史重放顯示某個 commit 有 5 列
    回饋離開佇列、裁決流 +0 列、blockquote +4,903 字元。**「N 在掉而 M 恆為 0」
    就是那個病徵。** 這是「回饋列離開 ⇄ 裁決軸 append 必須是同一個原子動作」
    改寫不成之後的替代品——它讓病徵可見，**不等於守住了那條斷言**（跨時間，
    系統沒有「上一版」→ 功能 14）。**0 也印。**
    """

    stream_exists: bool = False
    pending_exists: bool = False
    decisions: int = 0
    pending: int = 0
    targets: int = 0
    bad_targets: int = 0
    promoted: int = 0
    retired_names: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        s = "有" if self.stream_exists else "**無**"
        q = "有" if self.pending_exists else "無"
        # 舊名那一格 **0 也印**（E2）：「已不在」與「這支閘門沒在看」在輸出上必須
        # 分得開，否則墓碑守衛被關掉的那天，輸出跟今天一模一樣。
        retired = (
            f"**{'、'.join(self.retired_names)} 仍在**" if self.retired_names else "已不在"
        )
        return (
            f"檢查範圍：裁決流（{s}）{self.decisions} 列／"
            f"待裁決（{q}）{self.pending} 列；"
            f"標的 {self.targets} 個（{self.bad_targets} 個在書內找不到）；"
            f"`已升為通則` {self.promoted} 列；舊名 `裁決流.co.md`：{retired}"
        )


def _package_root(book: Path) -> Path | None:
    """從書資料夾向上找「同時含 `結構定義/` 與 `技巧知識庫/` 的目錄」。

    這是 `共同約定.md` 一「資源定位」明訂的找法——**不得寫死絕對路徑**。
    找不到就回 None，此時「已升為通則指向的檔存在嗎」這一項**跳過而不是誤報**
    （書被單獨複製出來跑是合法情境）。
    """
    for d in [book.resolve(), *book.resolve().parents]:
        if (d / "結構定義").is_dir() and (d / "技巧知識庫").is_dir():
            return d
    return None


def _target_exists(book: Path, target: str) -> bool:
    if target.strip() == SCOPE_ALL:
        return True
    p = book / "story" / target.strip()
    return p.exists() or p.with_suffix("").is_dir()


def _check_decisions(
    book: Path, rows: list[Decision], problems: list[str], stats: LintStats
) -> None:
    root = _package_root(book)
    if root is None and any(d.status == STATUS_PROMOTED for d in rows):
        stats.notes.append(
            "找不到套件根（同時含 `結構定義/` 與 `技巧知識庫/` 的目錄），"
            "故 `已升為通則` 指向的檔存不存在**這一項跳過**——不是通過"
        )
    for d in rows:
        where = f"裁決流.md 第 {d.lineno} 行"
        # 日期／欄數／狀態枚舉已由 parse_decisions 當場炸；這裡驗它沒驗的。
        scope = d.scope.strip()
        if scope not in (SCOPE_ALL, SCOPE_ROUND) and not _SCOPE_UNTIL_RE.match(scope):
            problems.append(
                f"{where}：射程 {scope!r} 不是 `全書`／`至arcNN`／`本輪` 三者之一"
                f"——**`decision-project` 從不驗這一欄**，寫錯它只會在 `--as-of` 時"
                f"靜默當成「判不了」，於是一條早該過期的裁決永遠回「生效中」"
            )
        if len(d.ruling) > RULING_CHARS:
            problems.append(
                f"{where}：`裁決` 欄 {len(d.ruling)} 字（上限 {RULING_CHARS}）"
                f"——「一項裁決一列」，別把一輪 session 的全部決定併成一列長文"
                f"（那會讓 --target 過濾失效）。理由寫多長都行，那是 `理由` 欄的事"
            )
        if not _target_exists(book, d.target):
            stats.bad_targets += 1
            problems.append(
                f"{where}：標的 `{d.target}` 在書內找不到（檔案改名或已移除？）"
                f"——append-only 不刪列，但壞標的會讓 `--target` 再也命中不到它"
            )
        if d.status == STATUS_PROMOTED:
            stats.promoted += 1
            m = _PROMOTED_REF_RE.search(d.rationale)
            if not m:
                problems.append(
                    f"{where}：狀態是 `已升為通則`，但理由欄沒有指向 `結構定義/` 或"
                    f"`技巧知識庫/` 的檔——schema 要求「理由欄改成一句指過去」，"
                    f"不留第二份"
                )
            elif root is not None and not (root / m.group(1)).is_file():
                problems.append(
                    f"{where}：`已升為通則` 指向的 `{m.group(1)}` 不存在"
                    f"（E1 目的地存在性：箭頭指向空氣，而箭頭本身格式完全合法）"
                )


def _check_pending(
    book: Path, rows: list[Pending], problems: list[str], stats: LintStats
) -> None:
    for q in rows:
        where = f"待裁決.md 第 {q.lineno} 行"
        if len(q.finding) > FINDING_CHARS:
            problems.append(
                f"{where}：`發現` 欄 {len(q.finding)} 字（上限 {FINDING_CHARS}）"
                f"——一句話講清楚問題是什麼就好；論證屬裁決流的 `理由` 欄"
            )
        if not _target_exists(book, q.target):
            stats.bad_targets += 1
            problems.append(
                f"{where}：標的 `{q.target}` 在書內找不到（檔案改名或已移除？）"
                f"——這一欄是選擇器，路徑寫錯這筆回饋就再也查不到"
            )


def lint_report(book: Path) -> tuple[list[str], LintStats]:
    """驗一本書的兩支檔。回 (問題清單, 覆蓋率統計)。

    問題字串**一律以位置起頭**（`裁決流.md 第 N 行 …`），下游靠開頭分類。
    """
    from .cli import resolve_pending, resolve_stream, retired_stream_files

    problems: list[str] = []
    stats = LintStats()

    try:
        stream_path = resolve_stream(book)
    except FileNotFoundError:
        stream_path = None

    # 舊名 `裁決流.co.md`（2026-07-27 功能 04 廢除該檔類，2026-07-30 移除讀取路徑）。
    # **這一格是「移除讀取路徑」的另一半**：拿掉相容分支而不補墓碑，等於把
    # 「這本書沒有裁決流」與「這本書的裁決流叫舊名、而且從此沒有任何工具讀它」
    # 壓成同一句「無」——那是 `設計原則.md` A5 要擋的「撤銷看不出來」。
    retired = retired_stream_files(book)
    stats.retired_names = [p.name for p in retired]
    for p in retired:
        problems.append(
            f"story/參照/{p.name}：**舊名 2026-07-30 起不再支援**"
            f"（`.co.md` 這個檔類已於 2026-07-27 功能 04 廢除）。"
            f"在此之前它是一句半真的相容承諾——`decision-project` 的查詢吃得動，"
            f"而本閘門與 `derived-sync` 的掃描起點吃不動，"
            f"於是這本書拿得到查詢、拿不到守衛。"
            f"改名成 `裁決流.md` 即可，內容格式不變"
        )

    pending_path = resolve_pending(book)
    stats.stream_exists = stream_path is not None
    stats.pending_exists = pending_path is not None

    decisions: list[Decision] = []
    pending: list[Pending] = []

    if stream_path is not None:
        try:
            decisions = parse_decisions(stream_path.read_text(encoding="utf-8"))
        except ParseError as e:
            problems.append(f"裁決流.md 解析失敗：{e}（表頭七欄 {list(COLUMNS)}）")
    if pending_path is not None:
        try:
            pending = parse_pending(pending_path.read_text(encoding="utf-8"))
        except ParseError as e:
            problems.append(
                f"待裁決.md 解析失敗：{e}"
                f"（表頭**恰四欄** {list(PENDING_COLUMNS)}——"
                f"**不得有 `狀態` 欄**：這張表只住待裁決的，狀態是恆真的。"
                f"實測舊設計那個只允許一個值的狀態欄，7 列平均 171 字元、"
                f"最長 440、佔整列 61%，人的裁決被塞進 AI 那一筆的最後一格）"
            )

    stats.decisions = len(decisions)
    stats.pending = len(pending)
    stats.targets = len({d.target for d in decisions} | {q.target for q in pending})

    _check_decisions(book, decisions, problems, stats)
    _check_pending(book, pending, problems, stats)

    # 目的地存在性（E1）：結案時理由要 append 進裁決流，那支檔得在。
    if pending and stream_path is None:
        problems.append(
            f"story/參照/：有 {len(pending)} 列待裁決，但 `裁決流.md` 不存在"
            f"——結案時「理由」無處可去。實測那個下場是理由改落 `.ai.md` 的"
            f"blockquote（一世之尊累積到 29 支檔／190 行／46,245 字元而無人察覺）。"
            f"照 `書本模板/story/參照/裁決流.md` 的骨架先建一支"
        )

    if not stats.stream_exists and not stats.pending_exists:
        stats.notes.append(
            "這本書還沒有裁決軸（兩支檔都不存在）——那是合法狀態，"
            "第一次有作者拍板時再照 `書本模板/story/參照/` 的骨架建"
        )
    # 兩軸不對帳（T5 改寫不成）時至少把病徵並排印出來。
    if stats.pending and not stats.decisions and stats.stream_exists:
        stats.notes.append(
            f"{stats.pending} 列待裁決、0 列裁決——若佇列有在被消化，"
            f"裁決流卻始終是 0，代表理由落到了別的地方（實測那個別的地方是 "
            f"`.ai.md` 的 blockquote）。**這不是問題、不計入問題數**，"
            f"跨時間對帳在現行架構裡不可檢查（→ 功能 14）"
        )

    return problems, stats
