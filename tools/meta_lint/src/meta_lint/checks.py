"""`meta-lint` 的九項。第 1–6 項是閘門（機械可判、有對錯），第 7–9 項是投影（只印）。

形狀照抄 `style-lint`：問題進問題數，提示不進。

**刻意不做的那一欄**：「這支 lint 守 schema 的哪幾條」——那是被駁回**六次**的形狀
（12 支 schema × ~10 條 ≈ 120 列會漂的對照表；前六次見 `docs/重構/02-待用構想.md`）。
**正解是方向反轉**：schema 那一側已經在寫「格式由 `X` 守」，第 3 項驗它指得到
——**驗既有的一句話，不新開一份表**。
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import repo as R


@dataclass(frozen=True)
class Problem:
    where: str
    detail: str
    hint: str

    def __str__(self) -> str:
        return f"{self.where}：{self.detail}"


@dataclass
class MetaStats:
    """**我在這個 repo 上檢查了幾筆。**（`設計原則.md` E2 的可執行推論，0 也印。）"""

    packages: int = 0
    commands: int = 0
    skills: int = 0
    schemas: int = 0
    workflows: int = 0
    cmd_without_trigger: int = 0
    tokens_checked: int = 0
    tokens_unknown: int = 0
    schema_guards: int = 0
    schema_guards_missing: int = 0
    schemas_without_checker: int = 0
    parallel_lists: int = 0
    cli_entries: int = 0
    cli_entries_without_stats: int = 0
    live_checked: int = 0
    live_skipped: bool = False
    notes: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    def render(self) -> str:
        live = "未接（`--no-live`）" if self.live_skipped else f"{self.live_checked} 次實跑"
        return (
            f"檢查範圍：{self.packages} 個套件／{self.commands} 個指令／"
            f"{self.skills} 支 SKILL.md／{self.schemas} 支 schema／"
            f"{self.workflows} 支 workflow；"
            f"指令觸發者：**{self.cmd_without_trigger} 個指令沒有任何觸發者**；"
            f"散文裡的指令 token {self.tokens_checked} 個"
            f"（**{self.tokens_unknown} 個 registry 查無**）；"
            f"schema 指名的守衛 {self.schema_guards} 處"
            f"（**{self.schema_guards_missing} 處指不到**"
            f"·**{self.schemas_without_checker} 支 schema 一個都指不出來**）；"
            f"平行清單 {self.parallel_lists} 份；"
            f"CLI 入口 {self.cli_entries} 個"
            f"（**{self.cli_entries_without_stats} 個路徑上沒有覆蓋率行**）；"
            f"輸出契約：{live}"
        )


# ============================================================ 第 1／2 項：指令 ↔ 觸發者
#
# **這兩項是本輪的重點**（作者拍板時特別交代）：工具鏈的真正呼叫者是 **AI 的 skill**，
# 不是 push——所以「每支指令有沒有觸發者」就是這套系統唯一的觸發模型本身，CI 只是後備。
#
# 它兌現的是 `設計原則.md` E1 的**後半句**：「每一條格式承諾都要指名一個檢查器**與
# 一個觸發時機**」。前十三輪執行的一律是前半句——十三支 lint，每一支都指得出來；
# **後半句十三輪零次執行**。


def check_triggers(repo: Path, stats: MetaStats) -> list[Problem]:
    """第 1 項：每支 `[project.scripts]` 至少被 1 支 SKILL.md **或 workflow** 指名。

    **「或 workflow」不是為了放水**：`meta-lint` 自己的觸發者就是
    `.github/workflows/tools.yml`（它不吃 `--book`，沒有任何一支 skill 該跑它）。
    E1 第五推論的字面是「哪支 `SKILL.md` 的第幾步**（或哪個自動化）**」。
    """
    cmds = R.commands(repo)
    stats.commands = len(cmds)
    texts = [(f"skills/{p.parent.name}", p.read_text(encoding="utf-8")) for p in R.skill_files(repo)]
    texts += [(f"workflows/{p.name}", p.read_text(encoding="utf-8")) for p in R.workflow_files(repo)]

    out: list[Problem] = []
    orphan: list[str] = []
    for cmd in sorted(cmds):
        if not any(cmd in t for _, t in texts):
            orphan.append(cmd)
    stats.cmd_without_trigger = len(orphan)
    if orphan:
        out.append(
            Problem(
                "指令 registry",
                f"{len(orphan)} 個指令沒有任何觸發者："
                + "、".join(f"`{c}`" for c in orphan),
                "**一支從不被呼叫的 lint 與一支不存在的 lint，在系統的行為上完全相同**"
                "——而前者更糟，因為 schema 裡寫著它（`設計原則.md` E1 第五推論）。"
                "把它掛進某支 SKILL.md 的落檔步驟，或掛進 `.github/workflows/tools.yml`；"
                "都掛不上就刪掉那個 entry point",
            )
        )
    return out


def check_named_commands(repo: Path, stats: MetaStats) -> list[Problem]:
    """第 2 項：每個 SKILL.md／schema 裡被反引號指名的指令 token 都是真實指令。

    反向的那一半。實測會抓到 `state-project`——`章節.schema.md` 明記它是僵屍殘骸，
    而**沒有任何東西驗過它還在不在**。
    """
    known = set(R.commands(repo))
    out: list[Problem] = []
    missing: dict[str, set[str]] = {}
    total = 0
    for p in R.skill_files(repo) + R.schema_files(repo):
        where = f"{p.parent.name}/{p.name}" if p.name == "SKILL.md" else p.name
        toks = R.command_tokens(p.read_text(encoding="utf-8"), known)
        total += len(toks)
        for t in sorted(toks - known):
            missing.setdefault(t, set()).add(where)
    stats.tokens_checked = total
    stats.tokens_unknown = len(missing)
    if missing:
        shown = "、".join(
            f"`{t}`（{'、'.join(sorted(w))}）" for t, w in sorted(missing.items())
        )
        out.append(
            Problem(
                "指令 registry",
                f"{len(missing)} 個被指名的指令不存在：{shown}",
                "箭頭指向空氣，而箭頭本身格式完全合法（E1 的目的地承諾推論）。"
                "改成實際的指令名，或把那一句連同它宣稱的動作一起刪掉",
            )
        )
    return out


# ============================================================ 第 3 項：schema 指名的守衛
#
# **它取代「schema ↔ lint 逐條對照表」**（被駁回六次的形狀）：schema 那一側已經在寫
# 「格式由 `X` 守」／「檢查器與觸發時機」，把那一句變成必填，這裡驗 `X` 指得到。

_GUARD_RE = re.compile(r"(?:格式(?:閘門)?[由：:]|誰守[：:]|由\s*)`([a-z][a-z0-9-]+(?:\s+[a-z-]+)?)`\s*守")
# **三種節名都算**。內容才是承諾，節名不是——六支 schema 用 `## 檢查點`（帶
# 「誰守／執行者」欄）、三支用 `## 檢查器與觸發時機`、一支用 `## 誰守它`。
# 逼它們改名是六個功能的事，而且改完什麼都沒多守到；**節名不一致印成提示、不擋**。
_GUARD_SECTION_RE = re.compile(r"^##+\s*(檢查器與觸發時機|誰守它|檢查點)")
_CANONICAL_SECTION = "檢查器與觸發時機"


def check_schema_guards(repo: Path, stats: MetaStats) -> list[Problem]:
    """第 3 項：schema 指名的守衛指得到。

    **兩個閘門**（都是 E1 的字面）：
    1. 「格式由 `X` 守」那一句裡的 `X` **存在**；
    2. 每支 schema **至少指得出一個存在的檢查器**——填不出來就不准在 schema 裡
       宣稱那個格式。

    **兩個提示**（只印、不擋）：沒有集中的守衛節／守衛節的名字不齊。節名不是承諾，
    內容才是；把節名做成閘門等於替另外六個功能的 schema 立一條 E1 沒有的規矩。
    """
    known = set(R.commands(repo))
    out: list[Problem] = []
    missing: dict[str, set[str]] = {}
    no_checker: list[str] = []
    no_section: list[str] = []
    off_name: list[str] = []
    total = 0
    for p in R.schema_files(repo):
        text = p.read_text(encoding="utf-8")
        hits = [
            m.group(1)
            for ln in text.splitlines()
            if (m := _GUARD_SECTION_RE.match(ln.strip()))
        ]
        if not hits:
            no_section.append(p.name)
        elif _CANONICAL_SECTION not in hits:
            off_name.append(f"{p.name}（`{hits[0]}`）")
        # **閘門驗的是 E1 的字面**：這支 schema 指不指得出一個**存在的**檢查器。
        # 「有沒有一節專門收它們」是整理問題，只印不擋——把它做成閘門等於替
        # 另外六個功能的 schema 立一條 E1 沒有的規矩。
        if not (R.command_tokens(text, known) & known):
            no_checker.append(p.name)
        for m in _GUARD_RE.finditer(text):
            cmd = m.group(1).split()[0]
            total += 1
            if cmd not in known:
                missing.setdefault(cmd, set()).add(p.name)
    stats.schema_guards = total
    stats.schema_guards_missing = len(missing)
    stats.schemas_without_checker = len(no_checker)
    if missing:
        shown = "、".join(
            f"`{c}`（{'、'.join(sorted(w))}）" for c, w in sorted(missing.items())
        )
        out.append(
            Problem(
                "結構定義/",
                f"{len(missing)} 個 schema 指名的守衛不存在：{shown}",
                "**沒有檢查器的保證只是口頭承諾**（E1）。指名一支真的存在的指令，"
                "或把那條格式承諾拿掉",
            )
        )
    if no_checker:
        out.append(
            Problem(
                "結構定義/",
                f"{len(no_checker)} 支 schema 一個檢查器都指不出來："
                + "、".join(f"`{n}`" for n in no_checker),
                "**沒有檢查器的保證只是口頭承諾**（E1）：每一條格式承諾都要指名一個"
                "檢查器與一個觸發時機，填不出來就不准在 schema 裡宣稱那個格式",
            )
        )
    # **以下只印、不擋**：節名不是承諾，內容才是；而「有沒有一節專門收它們」
    # 是整理問題——做成閘門等於替另外六個功能的 schema 立一條 E1 沒有的規矩。
    if no_section:
        stats.hints.append(
            f"{len(no_section)} 支 schema 沒有集中的守衛節："
            + "、".join(f"`{n}`" for n in no_section)
            + f"——指名的檢查器散在各條規則旁邊。節名認三種："
            f"`{_CANONICAL_SECTION}`／`誰守它`／`檢查點`"
        )
    if off_name:
        stats.hints.append(
            f"{len(off_name)} 支 schema 的守衛節不叫 `{_CANONICAL_SECTION}`："
            + "、".join(off_name)
            + "——內容都在，只是名字不齊。改名是那幾個功能各自的事，本項不擋"
        )
    return out


# ============================================================ 第 4 項：平行清單一致
#
# `SETTINGS_KINDS`／`DERIVED_SECTIONS`／`DERIVED_KEYS` 三份清單describe同一組產物。
# 08 抉擇 7 刻意把 `DERIVED_KEYS` 延到 14，理由正是「它會製造第三份平行清單」——
# 本輪付這筆代價，而**代價的配套就是這一項**（E1：新增格式承諾就要交出守它的檢查器）。

_LIST_NAMES = ("SETTINGS_KINDS", "DERIVED_SECTIONS", "DERIVED_KEYS")


def _literal(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name and node.value is not None:
                return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    return None


def check_parallel_lists(repo: Path, stats: MetaStats) -> list[Problem]:
    """第 4 項：三份平行清單的產物集合一致。"""
    p = repo / R.TOOLS_DIR / "derived_sync" / "src" / "derived_sync" / "validate.py"
    if not p.is_file():
        return [
            Problem("tools/derived_sync", f"找不到 {p.name}", "平行清單的擁有者不見了")
        ]
    tree = ast.parse(p.read_text(encoding="utf-8"))
    values = {n: _literal(tree, n) for n in _LIST_NAMES}
    stats.parallel_lists = sum(1 for v in values.values() if v is not None)
    out: list[Problem] = []
    absent = [n for n, v in values.items() if v is None]
    if absent:
        return [
            Problem(
                "validate.py",
                f"讀不到平行清單：{'、'.join(absent)}",
                "改名了就要同時改這一項——**這一項不見了，三份清單就會安靜地分岔**",
            )
        ]

    kinds = set(values["SETTINGS_KINDS"])
    # rollup 的鍵（`角色/_index`…）刻意不在 `DERIVED_KEYS` 裡，見那裡的註解。
    sections = {k for k in values["DERIVED_SECTIONS"] if "/" not in k}
    keys = set(values["DERIVED_KEYS"])
    if not kinds <= sections:
        out.append(
            Problem(
                "validate.py",
                f"`SETTINGS_KINDS` 有 `DERIVED_SECTIONS` 沒有的產物：{sorted(kinds - sections)}",
                "那個產物的節枚舉是空頭承諾——`validate` 對它只會驗 front-matter",
            )
        )
    if keys != sections:
        out.append(
            Problem(
                "validate.py",
                "`DERIVED_KEYS` 與 `DERIVED_SECTIONS` 的產物集合不一致："
                f"只在鍵表 {sorted(keys - sections)}／只在節表 {sorted(sections - keys)}",
                "兩份清單描述同一組產物。**只在節表**＝那個產物的 front-matter 沒有"
                "封閉集合，`終局` 那種自生欄會再長一次；**只在鍵表**＝打錯字，"
                "而打錯的那一份永遠不會被套用",
            )
        )
    return out


# ============================================================ 第 5 項：覆蓋率行含錯誤路徑
#
# V3 的一般化：`_print_sentinel` 曾在 0 筆時直接 `return`，而 `beat-lint` 曾在
# 「找不到幕綱目錄」時印一行就走人——**兩者都是「有一條路徑不印覆蓋率行」**。

_STATS_MARKERS = ("stats.render()", "檢查範圍", "掃了 0 支", "掃了 0 章", "_EMPTY_COVERAGE")

# 哪些 entry point 是**閘門**（要被第 5 項驗）。投影不在射程內——見 `check_...` 內註。
_GATE_SUFFIXES = ("-lint",)
_GATE_COMMANDS = ("derived-sync",)


def _lint_entries(bodies: dict[str, str], scripts: dict[str, str]) -> set[str]:
    """`[project.scripts]` 裡屬閘門的那幾支 → 它們的函式名。"""
    out: set[str] = set()
    for cmd, target in scripts.items():
        if not (cmd.endswith(_GATE_SUFFIXES) or cmd in _GATE_COMMANDS):
            continue
        fn = target.rpartition(":")[2]
        if fn in bodies:
            out.add(fn)
    return out


def check_coverage_on_every_path(repo: Path, stats: MetaStats) -> list[Problem]:
    """第 5 項：每支 lint 的 CLI 入口，**每一條 return 路徑上都印得出覆蓋率行**。

    做法是 AST：找出 `cli.py` 裡的 `*_main`／`main`，看函式體內有沒有覆蓋率標記。
    **這是結構判準不是語意判準**——不去讀「它印的是不是覆蓋率」，只問「有沒有印」。
    """
    out: list[Problem] = []
    bad: list[str] = []
    total = 0
    entry_points = {pk.name: pk.scripts for pk in R.packages(repo)}
    for pkg, p in R.cli_modules(repo):
        text = p.read_text(encoding="utf-8")
        tree = ast.parse(text)
        lines = text.splitlines()
        bodies = {
            n.name: "\n".join(lines[n.lineno - 1 : (n.end_lineno or n.lineno)])
            for n in tree.body
            if isinstance(n, ast.FunctionDef)
        }

        def prints_coverage(name: str, seen: frozenset[str] = frozenset()) -> bool:
            """**跟著同模組的呼叫鏈走**：入口常常只是分派給 `_cmd_*` helper。

            不跟的話 15/24 個入口會被誤報，而那 15 個裡有 14 個其實印得好好的
            ——一個會誤報的閘門就是下一個沒有人看的閘門（03 記的警報疲勞）。

            **`seen` 每一條分支各一份**（`frozenset`，不是共用的可變 set）：共用會讓
            某個兄弟分支的遞迴把後面的 callee 全部標成「走過了」，於是真正印覆蓋率
            的那一支被跳過——實作時第一版就是這樣，而它報的 15 筆看起來完全合理。
            """
            if name in seen or name not in bodies:
                return False
            body = bodies[name]
            if any(m in body for m in _STATS_MARKERS):
                return True
            branch = seen | {name}
            return any(
                f"{callee}(" in body and prints_coverage(callee, branch)
                for callee in bodies
            )

        # **射程＝閘門，不是投影**（報告 §三 3.1 第 5 項的字面：「每支 **lint** 的
        # CLI 路徑上都有 `stats.render()`」）。投影的「覆蓋率」長在它的報表標題裡
        # （`## 全書伏筆帳（掃 11 個 arc；spine 讀自 …）`），形狀不同，逐一列舉
        # 那些 formatter 名字就是一份會漂移的清單。**兩支還沒有覆蓋率行的統計工具
        # （`beat-metrics`／`prose-metrics`）是已登記的欠債** → 功能 02。
        entries = _lint_entries(bodies, entry_points.get(pkg, {}))
        for name in sorted(entries):
            total += 1
            # argparse 分派器（`args.func(args)`）靜態追不到——改驗它分派到的
            # 那組 `_cmd_*` 全部印得出覆蓋率行。
            if "args.func(" in bodies[name]:
                # 只驗**會回報問題**的那幾支子指令（body 裡出現 `EXIT_PROBLEMS`）。
                # `stamp`／`hash` 是動作不是閘門——它們回答不了「我檢查了幾筆」，
                # 而把它們算進來只會逼人在一個 `stamp` 指令上印一行假的覆蓋率。
                sub = [
                    n
                    for n in bodies
                    if n.startswith("_cmd_") and "EXIT_PROBLEMS" in bodies[n]
                ]
                if sub and all(prints_coverage(n) for n in sub):
                    continue
            if not prints_coverage(name):
                bad.append(f"{pkg}:{name}")
    stats.cli_entries = total
    stats.cli_entries_without_stats = len(bad)
    if bad:
        out.append(
            Problem(
                "tools/*/cli.py",
                f"{len(bad)} 個 CLI 入口的路徑上找不到覆蓋率行：" + "、".join(bad),
                "**「我檢查了 0 筆」本身就是最有用的那一筆訊息**（`設計原則.md` E2）。"
                "只回答「發現幾個問題」的檢查器，在它自己被關掉時會印「乾淨」"
                "——實測就是這樣讓 206 個問題報 0 的",
            )
        )
    return out


# ============================================================ 第 6 項：輸出與 exit 契約
#
# **唯一一項要實跑的閘門。** 靜態掃不出「問題到底進了哪個通道」——那正是 V10
# 活下來的原因（12 支指令兩套慣例、零文件、零守衛）。

# (指令, 套件, 額外參數)。**跑不動那一組刻意用純 raw 書**——3/6 本書長期是這個狀態，
# 而在功能 14 之前 `beat-lint --book gothic_witch` 與「格式壞了」完全不可分辨。
LIVE_COMMANDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("beat-lint", "beat_metrics", ()),
    ("ch-lint", "beat_metrics", ()),
    ("outline-lint", "beat_metrics", ()),
    ("structure-project", "beat_metrics", ()),
    ("beat-metrics", "beat_metrics", ()),
    ("derived-sync", "derived_sync", ("check",)),
    ("derived-sync", "derived_sync", ("validate",)),
    ("world-lint", "derived_sync", ()),
    ("char-lint", "derived_sync", ()),
    ("style-lint", "derived_sync", ()),
    ("summary-lint", "derived_sync", ()),
    ("readiness-lint", "derived_sync", ()),
    ("readiness", "derived_sync", ()),
    ("fact-lint", "fact_projection", ()),
    ("object-lint", "fact_projection", ()),
    ("decision-lint", "decision_projection", ()),
    ("decision-project", "decision_projection", ()),
    ("foreshadow-project", "foreshadow_project", ()),
    ("prose-metrics", "prose_metrics", ()),
)

# 「我檢查了幾筆」的實際寫法（各軸的量詞不同，這是**它們現有的**寫法，不是新規矩）：
#   閘門 → `檢查範圍：…`／`掃描範圍：…`／`掃描了 N 列…`
#   投影 → 報表標題裡的 `（掃 N 個 arc…）`／`（N 個 arc；…）`／`合計 N 個衍生檔…`
# **兩支統計工具（`beat-metrics`／`prose-metrics`）還沒有正式的覆蓋率行**——那是
# 已登記的欠債（報告 §七 → 功能 02）；它們的報表標題算數，但那一格要記著。
_SCOPE_MARKERS = ("檢查範圍", "掃描範圍", "掃描了", "（掃 ", "個 arc；", "合計 ")


def _has_scope_line(out: str) -> bool:
    return any(m in out for m in _SCOPE_MARKERS)


CLEAN_BOOK = "書本模板"
EMPTY_BOOK = "gothic_witch"


# **`-q` 不是裝飾**：`uv run` 自己會把「Building…／Installed N packages」寫進
# stderr，而本項驗的正是「乾淨跑一次不該有任何 stderr」——不安靜的話 19/19 都會
# 被誤報成違約，而那種全中的輸出正是本輪要消滅的東西（03 記的警報疲勞）。
_UV = ("uv", "run", "-q", "--project")


def _run(repo: Path, pkg: str, cmd: str, extra: tuple[str, ...], book: str):
    return subprocess.run(  # noqa: S603
        [*_UV, f"{R.TOOLS_DIR}/{pkg}", cmd, *extra, "--book", book],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def check_output_contract(repo: Path, stats: MetaStats, live: bool) -> list[Problem]:
    """第 6 項：對 fixture 書實跑，比對 stdout／stderr／exit。

    三條契約（唯一真相在 `結構定義/共同約定.md`「輸出與 exit 契約」）：
    1. **乾淨的書**：exit 0，且覆蓋率行在 **stdout**；
    2. **還沒到那一層的書**：**exit 2**，而且**照樣印覆蓋率行**；
    3. **stderr 只裝執行錯誤**——乾淨跑一次不該有任何 stderr。
    """
    if not live:
        stats.live_skipped = True
        stats.hints.append(
            "第 6 項（輸出與 exit 契約）**未接**——`--no-live` 跳過了實跑。"
            "靜態掃不出「問題進了哪個通道」，那正是 V10 活下來的原因"
        )
        return []
    if not (repo / CLEAN_BOOK).is_dir():
        stats.live_skipped = True
        stats.hints.append(f"第 6 項未接——找不到 fixture 書 `{CLEAN_BOOK}`")
        return []

    out: list[Problem] = []
    dirty: list[str] = []
    bad_exit: list[str] = []
    no_coverage: list[str] = []
    for cmd, pkg, extra in LIVE_COMMANDS:
        label = " ".join((cmd, *extra))
        r = _run(repo, pkg, cmd, extra, CLEAN_BOOK)
        stats.live_checked += 1
        if r.returncode not in (0, 2):
            bad_exit.append(f"{label}（{CLEAN_BOOK} → exit {r.returncode}）")
        if r.stderr.strip():
            dirty.append(f"{label}（{CLEAN_BOOK}）")
        if not _has_scope_line(r.stdout):
            no_coverage.append(f"{label}（{CLEAN_BOOK}）")

        if (repo / EMPTY_BOOK).is_dir():
            r2 = _run(repo, pkg, cmd, extra, EMPTY_BOOK)
            stats.live_checked += 1
            if r2.returncode == 1:
                bad_exit.append(
                    f"{label}（{EMPTY_BOOK} → exit 1，而那本書只有 raw/）"
                )
            if r2.returncode == 2 and not _has_scope_line(r2.stdout):
                no_coverage.append(f"{label}（{EMPTY_BOOK}·exit 2 卻沒印覆蓋率行）")

    if bad_exit:
        out.append(
            Problem(
                "輸出契約",
                f"{len(bad_exit)} 次 exit 不符語意：" + "、".join(bad_exit),
                "0 乾淨／1 有格式問題／**2 這本書還沒有這一層**。"
                "「還沒到那一層」與「格式壞了」共用 exit 1，會讓 3/6 本純 raw 書"
                "把 CI 永遠釘在紅色（抉擇 6 A）",
            )
        )
    if dirty:
        out.append(
            Problem(
                "輸出契約",
                f"{len(dirty)} 次在乾淨的書上寫了 stderr：" + "、".join(dirty),
                "**stderr 只裝執行錯誤**（讀不到檔、參數錯）。覆蓋率行、問題、"
                "資訊、提示、投影輸出一律走 stdout——實測 "
                "`fact-lint --book 一世之尊 > report.txt` 曾只得到 2 行，"
                "而 206 個問題全部落進 stderr",
            )
        )
    if no_coverage:
        out.append(
            Problem(
                "輸出契約",
                f"{len(no_coverage)} 次沒有印覆蓋率行：" + "、".join(no_coverage),
                "**0 也印**（E2）。exit 2 的路徑上更要印——那是「我掃了 0 支」與"
                "「argparse 用法錯誤」唯一的分辨方式（兩者都是 exit 2）",
            )
        )
    return out


# ============================================================ 第 7 項：門檻常數（投影）

_CONST_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*(?::[^=]+)?=\s*([0-9]+(?:\.[0-9]+)?)\s*(?:#(.*))?$")
_SAMPLE_RE = re.compile(r"n\s*=\s*(\d+)")
# `EXIT_*` 是**契約**不是門檻——它們沒有「取值理由」可言（0／1／2 的語意寫在
# `共同約定.md`，不是量出來的）。把它們算進來會讓「未宣告」那一格灌水。
_NOT_A_THRESHOLD = ("EXIT_",)


def project_thresholds(repo: Path) -> list[str]:
    """第 7 項：48 個門檻常數 ＋ 各自的檔:行與樣本數宣告，**沒宣告印「未宣告」**。

    **只印、不擋、不落表**（抉擇 7 A）：
    - 選項 B（落一支登記表檔）＝「一份會漂移而無人維護的機讀資料」的第七次提案；
    - 選項 C（規定必須有樣本數、擋）**會逼出假數字**——`prose_metrics` 的 12 個
      節奏門檻取自技巧知識庫而非實測分佈，補不出 `n=`（那是 10 的「把作者判斷編成
      機械規則」同一個坑）。
    """
    rows: list[tuple[str, str, str]] = []
    for pkg, p in R.source_files(repo):
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines):
            m = _CONST_RE.match(ln.strip())
            if not m:
                continue
            name, value, tail = m.group(1), m.group(2), m.group(3) or ""
            if name.startswith(_NOT_A_THRESHOLD):
                continue
            # 樣本數宣告：同一行的註解，或**上方連續註解區塊**（取值理由通常寫在那裡）。
            # **要能跨過相鄰的常數行**——一段註解常常一次交代兩個門檻
            # （`SETTINGS_DERIVED_LINE_CHARS` 與 `SETTINGS_SOURCE_LINE_CHARS` 的
            # `n=4` 就寫在同一塊裡），停在第一個非註解行會讓第二個誤報「未宣告」。
            context = [tail]
            j = i - 1
            # 第一段：跨過**緊鄰的**常數行（中間沒有註解＝它們共用上面那一塊）
            while j >= 0 and _CONST_RE.match(lines[j].strip()):
                j -= 1
            # 第二段：收上面那一段連續註解，收完就停——**不能再往上跨第二個常數**，
            # 那會讓一個常數繼承到別人的取值理由（實測 `LINE_CHARS` 會冒領
            # `SOURCE_BYTES` 的 `n=11`）。
            while j >= 0 and lines[j].lstrip().startswith("#"):
                context.append(lines[j])
                j -= 1
            sample = _SAMPLE_RE.search("\n".join(context))
            rows.append(
                (
                    f"{pkg}/{p.name}:{i + 1}",
                    f"{name} = {value}",
                    f"n={sample.group(1)}" if sample else "**未宣告**",
                )
            )
    declared = sum(1 for _, _, s in rows if not s.startswith("**"))
    out = [
        "",
        f"### 門檻常數（{len(rows)} 個，其中 **{declared} 個寫出了樣本數**）",
        "",
        "> **只印、不擋**（抉擇 7 A）。門檻該不該定，先看分佈有沒有空隙"
        "（06 抉擇 5 A）；沒有空隙時任何取值都是任意的，而任意的門檻就是"
        "下一個警報疲勞來源。**已駁回落一支登記表檔**（會漂移的機讀資料第七次）"
        "與**規定必須有樣本數並擋**（`prose_metrics` 的 12 個節奏門檻取自技巧知識庫"
        "而非實測分佈，補不出 `n=`，硬要就會逼出假數字）。",
        "",
        "| 位置 | 常數 | 樣本數 |",
        "|------|------|--------|",
    ]
    out += [f"| `{loc}` | `{const}` | {sample} |" for loc, const, sample in rows]
    return out


# ============================================================ 第 8 項：同形實作份數（投影）
#
# **抉擇 1 依賴這一項**：本輪只收同套件內那 14 份，跨套件那 42 份留著，
# **由這一項把份數印成一個逐輪可見的數字**——先讓成本可見，再決定要不要付
# （同 D2「量出來再蓋」的紀律）。

# **數的是「定義處」不是「出現次數」**：`所屬arc` 這種欄名在散文裡出現 35 次，
# 但那不是 35 份實作。判準是 `def …(` 或 `re.compile(` 那一行——一個 shape 在
# 一支檔裡出現幾次不重要，**它散在幾支檔裡才是成本**。
DUPLICATE_SHAPES: tuple[tuple[str, str], ...] = (
    ("`spine_path` 落點", r"def spine_path\("),
    ("`parse_spine` 解析", r"def parse_spine\("),
    ("`spine_note` 回退提示", r"def spine_note\("),
    # 不綁 `re.compile(`——語法也可能先存成一個字串片段再組（`marks._MARK`）。
    # `\[\[伏筆` 這個**跳脫過**的形狀只會出現在 regex 原始碼裡，散文寫的是 `[[伏筆:x]]`。
    ("`[[伏筆:x]]` regex", r"\\\[\\\[伏筆"),
    ("`^## 幕NNN` regex", r"re\.compile\([^\n]*\^##[^\n]*幕\(?\\d"),
    ("front-matter 解析", r"def (?:_)?(?:front_matter|split_frontmatter|fm)\("),
    ("`_force_utf8`", r"def _force_utf8\("),
    ("節內容切片", r"def (?:_)?section_body\("),
    ("表格資料列", r"def (?:_)?table_rows\("),
    # **只數實作，不數呼叫端**：`beat_metrics` 的兩支 `_check_destinations` 現在是
    # 薄包裝，各自把自己那一層的檔餵給共用的 `scan_md_refs`——那是一份實作、兩個射程。
    ("目的地存在性", r"MD_REF_RE\s*=\s*re\.compile|missing_destinations\(book"),
    ("`所屬arc` regex", r"re\.compile\([^\n]*所屬arc"),
    ("exit 契約常數", r"^EXIT_LAYER_MISSING\s*="),
)


def project_duplicates(repo: Path) -> list[str]:
    """第 8 項：同形實作份數（**只印**）。"""
    files = R.source_files(repo)
    out = [
        "",
        "### 同形實作份數（只印，不擋）",
        "",
        "> **零相依政策（`dependencies = []`）解釋得了跨套件那幾份，解釋不了同一個"
        "套件裡的**——2026-07-28（功能 14，抉擇 1 D）收掉了後者 14 份。"
        "**跨套件那些留著是決定，不是遺漏**：本表把份數印成一個逐輪可見的數字，"
        "成本可見之後再談要不要開 `tools/_shared/`（選項 B）或併成單一套件（選項 C）。",
        "",
        "| 形狀 | 份數 | 跨幾個套件 | 同一套件內超額 |",
        "|------|------|-----------|---------------|",
    ]
    for label, pattern in DUPLICATE_SHAPES:
        rx = re.compile(pattern, re.MULTILINE)
        per_pkg: dict[str, int] = {}
        for pkg, p in files:
            # **一支檔算一份**（同一支檔裡寫兩次同形 regex 是同一份實作的細節）
            if rx.search(p.read_text(encoding="utf-8")):
                per_pkg[pkg] = per_pkg.get(pkg, 0) + 1
        total = sum(per_pkg.values())
        excess = sum(v - 1 for v in per_pkg.values() if v > 1)
        mark = f"**{excess}**" if excess else "0"
        out.append(f"| {label} | {total} | {len(per_pkg)} | {mark} |")
    out += [
        "",
        "> **「同一套件內超額」應該恆為 0**——那是抉擇 1 D 收掉的那一半。"
        "它變成非 0 ＝有人在同一個 `import` 空間裡又複製了一份，"
        "而 V4 已經實測過那種複製會**語意分歧且分歧無人守**。",
    ]
    return out


# ============================================================ 第 9 項：測試狀態（投影）


@dataclass(frozen=True)
class KnownRed:
    test: str
    reason: str


def load_known_red(repo: Path) -> list[KnownRed]:
    """`tools/meta_lint/known-red.toml`——**紅的幾支 ＋ 登記在案的理由**。

    **雙向擋**（在 CI 那一側）：紅而不在清單裡 → fail；**在清單裡卻變綠了也 fail**
    ——一份過期的已知紅清單就是下一個「守衛壞了而沒有人知道」。
    """
    import tomllib

    p = repo / R.TOOLS_DIR / "meta_lint" / "known-red.toml"
    if not p.is_file():
        return []
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    return [KnownRed(t["test"], t["reason"]) for t in data.get("known_red", [])]


def project_tests(repo: Path, stats: MetaStats, live: bool) -> list[str]:
    """第 9 項：8 個套件、N 支測試、**紅的幾支 ＋ 登記在案的理由**。"""
    reds = load_known_red(repo)
    out = [
        "",
        f"### 測試（{len(R.packages(repo))} 個套件；已知紅 {len(reds)} 支）",
        "",
    ]
    if not live:
        out += [
            "> **未接**（`--no-live`）——沒跑 pytest。CI 一律跑（`tools.yml`）。",
            "",
        ]
    else:
        for pkg in R.packages(repo):
            if not pkg.tests.is_dir():
                out.append(f"- `{pkg.name}`：**沒有 tests/**")
                continue
            r = subprocess.run(  # noqa: S603
                [
                    sys.executable if False else "uv",
                    "run",
                    "--project",
                    f"{R.TOOLS_DIR}/{pkg.name}",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    f"{R.TOOLS_DIR}/{pkg.name}/tests",
                ],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            tail = [ln for ln in r.stdout.splitlines() if "passed" in ln or "failed" in ln]
            out.append(f"- `{pkg.name}`：{tail[-1] if tail else '（讀不到結果）'}")
    out += ["", "**已知紅清單**（不在清單裡的紅字要 fail；在清單裡卻變綠了也要 fail）：", ""]
    if not reds:
        out.append("- （無）")
    for kr in reds:
        out.append(f"- `{kr.test}`\n  - {kr.reason}")
    return out
