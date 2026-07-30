"""`meta-lint` 的九項。第 1–6 項是閘門（機械可判、有對錯），第 7–9 項是投影（只印）。

形狀照抄 `style-lint`：問題進問題數，提示不進。

**刻意不做的那一欄**：「這支 lint 守 schema 的哪幾條」——那是被駁回**六次**的形狀
（12 支 schema × ~10 條 ≈ 120 列會漂的對照表；前六次見 `docs/重構/02-待用構想.md`）。
**正解是方向反轉**：schema 那一側已經在寫「格式由 `X` 守」，第 3 項驗它指得到
——**驗既有的一句話，不新開一份表**。
"""

from __future__ import annotations

import ast
import fnmatch
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
    # 第 10–12 項（2026-07-29 功能 15）
    skill_paths: int = 0
    skill_paths_unlanded: int = 0
    skill_paths_abolished: int = 0
    devdocs: int = 0  # 掃了幾支開發期活指示檔（`情境測試/*.md`）——0 也印
    entry_rows: int = 0
    entry_rows_unread: int = 0
    skill_axes_unlisted: int = 0
    kb_files: int = 0
    kb_referenced: int = 0
    kb_unreferenced: int = 0
    kb_without_toc: int = 0
    claude_kb_named: int = 0
    # 第 13 項（2026-07-30 驗證輪階段 1.5）：生產包封閉性
    ship_packages: int = 0  # `scope = "book"` 的套件數（進生產包）
    ship_commands: int = 0  # 它們的指令數
    dev_packages: int = 0  # `scope = "repo-dev"` 的套件數（不進生產包）
    dev_commands: int = 0
    scope_undeclared: int = 0  # 沒宣告或值不認得
    ship_src_files: int = 0  # 掃了幾支生產側 `.py`
    ship_src_leaks: int = 0  # 其中幾處出現開發期落點
    notes: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    _bad_entries: list[str] = field(default_factory=list)

    def render(self) -> str:
        live = "未接（`--no-live`）" if self.live_skipped else f"{self.live_checked} 次實跑"
        return (
            f"檢查範圍：{self.packages} 個套件／{self.commands} 個指令／"
            f"{self.skills} 支 SKILL.md／{self.schemas} 支 schema／"
            f"{self.workflows} 支 workflow／{self.kb_files} 支技法檔；"
            f"指令觸發者：**{self.cmd_without_trigger} 個指令沒有任何觸發者**；"
            f"散文裡的指令 token {self.tokens_checked} 個"
            f"（**{self.tokens_unknown} 個 registry 查無**）；"
            f"schema 指名的守衛 {self.schema_guards} 處"
            f"（**{self.schema_guards_missing} 處指不到**"
            f"·**{self.schemas_without_checker} 支 schema 一個都指不出來**）；"
            f"平行清單 {self.parallel_lists} 份；"
            f"CLI 入口 {self.cli_entries} 個"
            f"（**{self.cli_entries_without_stats} 個路徑上沒有覆蓋率行**）；"
            f"輸出契約：{live}；"
            # ---- 第 10–12 項：取用宣告那一半（0 也印）
            f"取用宣告 {self.skill_paths} 條書內路徑"
            f"（**{self.skill_paths_unlanded} 個沒有落點**"
            f"·**{self.skill_paths_abolished} 條指向已廢除的檔**"
            f"·墓碑那一格另掃 {self.devdocs} 支開發期活指示檔）；"
            f"查詢入口表 {self.entry_rows} 列"
            f"（**{self.entry_rows_unread} 列無讀者**"
            f"·**{self.skill_axes_unlisted} 個 skill 讀的路徑兩份清單都沒有**）；"
            f"技法檔 {self.kb_referenced} 支被引用"
            f"（**{self.kb_without_toc} 支無檔頭目錄**"
            f"·另 {self.kb_unreferenced} 支零引用·`CLAUDE.md` 列舉 {self.claude_kb_named} 支）；"
            # ---- 第 13 項：生產包封閉性（0 也印）
            f"生產包 {self.ship_packages} 個套件／{self.ship_commands} 個指令"
            f"·開發包 {self.dev_packages} 個套件／{self.dev_commands} 個指令"
            f"（**{self.scope_undeclared} 個套件沒宣告射程**）；"
            f"生產側 src/ 掃了 {self.ship_src_files} 支 `.py`"
            f"（**{self.ship_src_leaks} 處出現開發期落點**）"
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
    stats._bad_entries = list(bad)  # `--emit guards` 的最後一欄重用它，不重算
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
    # **2026-07-30（階段 1.5）補進來的第 20 支。** 它吃 `--book` 以外的必填參數，
    # 所以原本兩份清單（本表與 `tools.yml` 步驟 ②）**都把它漏在外面**——於是
    # 「乾淨的書上 `settings-select` 回幾」從來沒有被問過一次，而答案是 **exit 1**，
    # 違反第 2 條契約。它自己定了 `EXIT_LAYER_MISSING = 2` 卻沒有任何路徑回傳過。
    # **漏一支指令的代價不是少驗一支，是那一支從此可以違反任何契約。**
    ("settings-select", "settings_select", ("--arc", "arc01")),
)

# 「我檢查了幾筆」的實際寫法（各軸的量詞不同，這是**它們現有的**寫法，不是新規矩）：
#   閘門 → `檢查範圍：…`／`掃描範圍：…`／`掃描了 N 列…`
#   投影 → 報表標題裡的 `（掃 N 個 arc…）`／`（N 個 arc；…）`／`合計 N 個衍生檔…`
# **兩支統計工具（`beat-metrics`／`prose-metrics`）還沒有正式的覆蓋率行**——那是
# 已登記的欠債（報告 §七 → 功能 02）；它們的報表標題算數，但那一格要記著。
# **2026-07-30 補 ` 章；`**（驗證輪階段 1c）：`prose-metrics` 成功時印的是
# `## <書名> 正文結構（93 章；零 LLM、可覆算）`——那是一條合格的覆蓋率行
# （它說得出「我掃了幾章」），只是形狀與既有六個 marker 都不同。
#
# **為什麼拖到今天才發現**：第 6 項本來只跑 `書本模板`（無 chapters/ → exit 2 走
# 「掃了 0 章」那條，命中 `檢查範圍`）與一本純 raw 書（同樣走 exit 2）——
# **`prose-metrics` 的成功輸出從來沒有被這一項看過**。病例書是唯一一本有 93 章
# 正文的書，把它加進第 4 條契約的當天，這一格就露出來了。
#
# 這與階段 0 擴 `情境測試/` 射程時抓到的是同一件事：**掃描對象是對的，
# 而樣本沒有涵蓋那條分支**。
_SCOPE_MARKERS = ("檢查範圍", "掃描範圍", "掃描了", "（掃 ", "個 arc；", "合計 ", " 章；")


def _has_scope_line(out: str) -> bool:
    return any(m in out for m in _SCOPE_MARKERS)


CLEAN_BOOK = "書本模板"

# **病例書**（2026-07-30 驗證輪階段 1c 新增）。它是第 4 條契約的樣本。
#
# 為什麼要一本「刻意壞掉」的書當 fixture：階段 1c 移除了成組的 legacy 讀取路徑
# （spine 舊落點 ×4、舊單檔事實流、`裁決流.co.md`、`_arc_of` 雙格式），而拍板的
# 驗收條件是——**移除一條 legacy 讀取路徑必須降級成「被回報的問題」，
# 絕不能降級成 traceback**。這一條沒有守衛的話，下一次刪 legacy 分支時
# 「它現在報什麼」只會在有人手動跑一次的時候才被看見。
#
# **這裡刻意不驗 exit 值等於幾**：那本書每一支指令報什麼，由 17 份黃金檔逐支釘死。
# 本項只驗三件事——不 traceback、exit 在契約枚舉內、覆蓋率行照印。
# **書名硬編碼是可接受的**（與 `empty_book` 的自動挑選不同）：`tools.yml` 有一步
# `test -d 一世之尊`，理由寫著「否則 17 份黃金檔的射程是空的」——這本書的存在
# 本來就是一個被明文守住的前提，而它一旦不在，本項印「未接」而不是「都合格」。
CASE_BOOK = "一世之尊"
_TRACEBACK_MARK = "Traceback (most recent call last)"


def empty_book(repo: Path) -> str | None:
    """挑一本「有 `raw/`、還沒有 `story/`」的書，當第 2 條契約（exit 2）的樣本。

    **2026-07-30 起不硬編書名。** 原本這裡寫死 `gothic_witch`，而那本書是作者的實驗
    素材——**任何人開始寫它、`story/` 一出現，這一格就會靜默失去射程**：迴圈照跑、
    覆蓋率行照印、`live_checked` 照加，而「還沒到那一層要 exit 2 且照樣印覆蓋率行」
    這條契約再也沒有被驗過一次。那是 `設計原則.md` E2 最糟的一格——**壞了永遠不會
    發現，而且守衛回報正常**。而它的觸發條件不是誰改壞了什麼，是**有人正常地開始
    寫一本書**。

    判準是機械的：`raw/` 在、`story/` 不在。`書本模板`／`驗證範例`／`一世之尊` 都有
    `story/`，自動排除；`examples/` 沒有 `raw/`，也不會被誤認成書。
    `sorted` 是為了可覆算——同一個 repo 每次挑到同一本。
    找不到就回 `None`，由呼叫端印「未接」（同 `CLEAN_BOOK` 找不到時的降級）。
    """
    for d in sorted(repo.iterdir()):
        if d.is_dir() and (d / "raw").is_dir() and not (d / "story").is_dir():
            return d.name
    return None


# **`-q` 不是裝飾**：`uv run` 自己會把「Building…／Installed N packages」寫進
# stderr，而本項驗的正是「乾淨跑一次不該有任何 stderr」——不安靜的話 19/19 都會
# 被誤報成違約，而那種全中的輸出正是本輪要消滅的東西（03 記的警報疲勞）。
_UV = ("uv", "run", "-q", "--project")


def _run(repo: Path, pkg: str, cmd: str, extra: tuple[str, ...], book: str):
    return subprocess.run(  # noqa: S603
        [*_UV, R.package_rel(repo, pkg), cmd, *extra, "--book", book],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def check_output_contract(repo: Path, stats: MetaStats, live: bool) -> list[Problem]:
    """第 6 項：對 fixture 書實跑，比對 stdout／stderr／exit。

    四條契約（唯一真相在 `結構定義/共同約定.md`「輸出與 exit 契約」）：
    1. **乾淨的書**：exit 0，且覆蓋率行在 **stdout**；
    2. **還沒到那一層的書**：**exit 2**，而且**照樣印覆蓋率行**；
    3. **stderr 只裝執行錯誤**——乾淨跑一次不該有任何 stderr。
    4. **病例書不吐 traceback**（2026-07-30 驗證輪階段 1c 新增，見 `CASE_BOOK`）。
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

    empty = empty_book(repo)
    if empty is None:
        stats.hints.append(
            "第 6 項的**第 2 條契約未接**——找不到一本「有 `raw/`、還沒有 `story/`」的書，"
            "於是「還沒到那一層要 exit 2 且照樣印覆蓋率行」這一格本次沒有被驗到。"
            "第 1／3 條（乾淨的書、stderr 只裝執行錯誤）照驗"
        )
    else:
        stats.notes.append(f"第 6 項的 exit 2 樣本：`{empty}`（有 `raw/`、無 `story/`，自動挑選）")

    case = CASE_BOOK if (repo / CASE_BOOK).is_dir() else None
    if case is None:
        stats.hints.append(
            f"第 6 項的**第 4 條契約未接**——找不到病例書 `{CASE_BOOK}`，"
            "於是「移除 legacy 讀取路徑之後不吐 traceback」這一格本次沒有被驗到"
        )
    else:
        stats.notes.append(
            f"第 6 項的病例書：`{case}`（第 4 條契約＝不吐 traceback·exit 在契約內·照印覆蓋率行）"
        )

    out: list[Problem] = []
    dirty: list[str] = []
    bad_exit: list[str] = []
    no_coverage: list[str] = []
    tracebacks: list[str] = []
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

        if empty is not None:
            r2 = _run(repo, pkg, cmd, extra, empty)
            stats.live_checked += 1
            if r2.returncode == 1:
                bad_exit.append(f"{label}（{empty} → exit 1，而那本書只有 raw/）")
            if r2.returncode == 2 and not _has_scope_line(r2.stdout):
                no_coverage.append(f"{label}（{empty}·exit 2 卻沒印覆蓋率行）")

        if case is not None:
            # **第 4 條契約**：病例書滿身紅字是它的價值，**吐 traceback 不是**。
            # 這裡不驗 exit 等於幾（那由 17 份黃金檔逐支釘），只驗它在契約枚舉內。
            r3 = _run(repo, pkg, cmd, extra, case)
            stats.live_checked += 1
            if _TRACEBACK_MARK in r3.stderr:
                tracebacks.append(f"{label}（{case}）")
            if r3.returncode not in (0, 1, 2):
                bad_exit.append(f"{label}（{case} → exit {r3.returncode}）")
            if not _has_scope_line(r3.stdout):
                no_coverage.append(f"{label}（{case}·exit {r3.returncode} 卻沒印覆蓋率行）")

    if tracebacks:
        out.append(
            Problem(
                "輸出契約",
                f"{len(tracebacks)} 支指令對病例書吐 traceback：" + "、".join(tracebacks),
                "**移除一條 legacy 讀取路徑必須降級成「被回報的問題」，"
                "絕不能降級成 traceback**（2026-07-30 驗證輪階段 1c 的硬驗收條件）。"
                "報錯要說得出「舊落點在哪、新落點是哪支、怎麼搬」——"
                "一個 raw errno 說不出這三件事裡的任何一件",
            )
        )

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


def known_red_path(repo: Path) -> Path:
    """`devtools/meta_lint/known-red.toml`（2026-07-30 階段 1.5 起在 `devtools/`）。"""
    return repo / R.DEVTOOLS_DIR / "meta_lint" / "known-red.toml"


def load_known_red(repo: Path) -> list[KnownRed]:
    """**紅的幾支 ＋ 登記在案的理由**。

    **雙向擋**（在 CI 那一側）：紅而不在清單裡 → fail；**在清單裡卻變綠了也 fail**
    ——一份過期的已知紅清單就是下一個「守衛壞了而沒有人知道」。

    **「清單空的」與「清單檔不在」是兩件事**（2026-07-30 階段 1.5）：前者是正常狀態
    （階段 1d 之後就是 0 筆），後者是路徑壞了。這支函式對兩者都回 `[]`，所以
    **區分它們的責任在呼叫端**——`project_tests` 印「清單檔不在」，見那裡。
    本階段搬 `meta_lint` 時這條路徑就差點靜靜地壞掉：讀不到會印「已知紅 0 支」。
    """
    import tomllib

    p = known_red_path(repo)
    if not p.is_file():
        return []
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    return [KnownRed(t["test"], t["reason"]) for t in data.get("known_red", [])]


# ============================================================ 第 10 項：SKILL.md 的取用宣告
#
# **本輪（功能 15）新增的三項，對象是「讀」而不是「寫」。** 前十四輪把每個產物軸的
# 產出格式與守衛補齊了，而**「誰在什麼時候把什麼讀進來」從來沒有被任何檢查器碰過
# 一次**——實測 24 條取用宣告指向 5 支已廢除的檔（9/12 支 skill 命中，一半是寫入
# 命令），而這一支工具的覆蓋率行印「散文裡的指令 token 197 個（**0 個 registry 查無**）」。
# **掃描對象是對的，掃描的欄位只有一格**（`設計原則.md` E2 那條推論的新形態）。


def _dir_of(norm: str) -> str:
    return norm.rpartition("/")[0] or norm


def _is_dir_pattern(p: str) -> bool:
    """**判準是「basename 裡有沒有點」，不是「結不結尾於 `.md`」。**

    實作時實測到：用後者會把 `story/00-摘要.*`（`{md,ai.md}` 的舊收法）當成目錄，
    於是它去比 `story/00-摘要.*/…` 的前綴、對誰都不成立。
    """
    return p.endswith("/") or "." not in p.rpartition("/")[2]


def _covers(pattern: str, path: str) -> bool:
    """入口表／豁免清單的一個 pattern 涵蓋不涵蓋一支 SKILL.md 讀的路徑。

    **兩種涵蓋**：pattern 是**目錄**（`raw/`、`story/設定/角色/*`）時涵蓋底下的一切；
    是**檔**時走雙向 glob（入口表那一側可能比 SKILL.md 更寬，也可能更窄）。

    ⚠️ **它的粒度是路徑，不是「取用切面」**——一列寫 `story/幕綱/*.md`（伏筆帳）就會
    涵蓋同資料夾的 `_順序.md`，即使那一列講的是別的事。所以這一項抓得到的是
    「**整支檔／整一層沒有任何一列提到**」（實測風格軸就是這一格），抓不到「有一列
    但它講的是這支檔的另一個切面」。依 E1，**驗不到的就不宣稱**：切面級的一致性
    仍然要靠人在重構輪逐支比對。
    """
    if _is_dir_pattern(pattern):
        base = pattern.rstrip("/").removesuffix("*").rstrip("/")
        return path == base or path.startswith(base + "/")
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(pattern, path)


def check_skill_paths(repo: Path, stats: MetaStats) -> list[Problem]:
    """第 10 項：SKILL.md 指名的書內路徑有落點，且**不得指向已廢除的檔**。

    **兩個閘門，強度刻意不同——而射程也不同**：
    1. **落點**（目錄級）：正規化後的目錄要在受管集合裡。**它刻意只驗到目錄**——
       SKILL.md 裡有大量示例路徑（`story/幕綱/arc02.md`），驗檔名存在會把示例
       全部報成問題，而那是警報疲勞。這一格抓的是「整個一層不存在」。
       射程：**只有 `.claude/skills/`**。
    2. **已廢除**（檔名級）：`repo.ABOLISHED` 是封閉清單，提到就報——除非**同一行**
       寫出它已廢除（`repo.TOMBSTONE`）。**這一格才是本項的利刃**：實測 2026-07-29
       它在 12 支 SKILL.md 上抓到 24 條，其中一半是「重生它／封章它」的寫入命令。
       射程：`.claude/skills/` ＋ argparse `description` ＋ **`情境測試/*.md`**
       （2026-07-30 擴，見 `repo.devdoc_files`）。
    """
    places, notes = R.landing_places(repo)
    out: list[Problem] = []
    unlanded: dict[str, set[str]] = {}
    zombies: list[str] = []
    total = 0
    for p in R.skill_files(repo):
        where = p.parent.name
        text = p.read_text(encoding="utf-8")
        paths = R.book_paths(text)
        total += len(paths)
        for raw in sorted(paths):
            for one in R.normalize_paths(raw):
                d = _dir_of(one)
                if not any(d == pl or fnmatch.fnmatch(d, pl) for pl in places):
                    unlanded.setdefault(raw, set()).add(where)
        for lineno, name in R.abolished_mentions(text):
            when, instead = R.ABOLISHED[name]
            zombies.append(f"`{where}/SKILL.md:{lineno}` → `{name}`（{when} 廢除，改跑 {instead}）")

    # **開發期的活指示檔也是取用宣告**（`情境測試/*.md`）。射程刻意只到墓碑那一格、
    # **不驗落點**：那幾支檔講的是「怎麼測這個系統」，裡面的書內路徑多半是佈局示意與
    # `<書>/` 佔位，驗落點會把示意圖報成問題，而那是警報疲勞（同本項落點閘門刻意只驗
    # 到目錄的理由）。而墓碑那一格對它們**完全適用**——實測 2026-07-30：
    # `端到端貫穿測試流程.md:63` 的「開場三讀」第 3 條仍叫人去讀 `就緒儀表.md`，
    # 那支檔功能 10（2026-07-28）已廢除，而在此之前沒有任何東西看得到這一行。
    devdocs = R.devdoc_files(repo)
    stats.devdocs = len(devdocs)
    for p in devdocs:
        rel = p.relative_to(repo).as_posix()
        for lineno, name in R.abolished_mentions(p.read_text(encoding="utf-8")):
            when, instead = R.ABOLISHED[name]
            zombies.append(f"`{rel}:{lineno}` → `{name}`（{when} 廢除，改跑 {instead}）")

    # **argparse `description` 也是一條取用宣告**，而它 2026-07-29 起是
    # `--emit guards` 的機械來源——**投影的輸入自己在描述已廢除的檔，投影就會把那句話
    # 印成事實**。實測：六支指令的 description 仍寫著 `_index.md` spine／`_總覽.ai.md`
    # 的核心規則索引／`_index.ai.md` 的視圖一致性。射程刻意只到 description，**不掃整支
    # `.py`**——那幾支 lint 的程式碼裡確實還有殘留偵測的分支，那是對的。
    for cmd, desc in sorted(_argparse_descriptions(repo).items()):
        for name in sorted(R.abolished_in(desc)):
            when, instead = R.ABOLISHED[name]
            zombies.append(
                f"`{cmd}` 的 argparse description → `{name}`（{when} 廢除，改跑 {instead}）"
            )
    stats.skill_paths = total
    stats.skill_paths_unlanded = len(unlanded)
    stats.skill_paths_abolished = len(zombies)
    stats.notes.append("SKILL.md 路徑落點取自：" + "、".join(notes))
    if unlanded:
        shown = "、".join(f"`{k}`（{'、'.join(sorted(v))}）" for k, v in sorted(unlanded.items()))
        out.append(
            Problem(
                ".claude/skills/",
                f"{len(unlanded)} 支書內路徑在受管清單裡沒有落點：{shown}",
                "**箭頭指向空氣，而箭頭本身格式完全合法**（E1 的目的地承諾推論）。"
                f"要嘛那一層真的該存在（補進 `{R.TEMPLATE_BOOK}/` 骨架與 "
                "`book_layout.py`），要嘛那一句連同它宣稱的動作一起刪掉",
            )
        )
    if zombies:
        out.append(
            Problem(
                f".claude/skills/ ＋ {R.DEVDOC_DIR}/",
                f"{len(zombies)} 條取用宣告指向已廢除的檔：" + "；".join(zombies),
                "**這一格「壞了永遠不會發現，而且守衛回報正常」**：照著跑會把一支已"
                "廢除的檔造回來，而 `world-lint` 會印「格式合規」、`derived-sync check` "
                "會主動報 `[STALE]` 要你去 `stamp` 它（`設計原則.md` A5：撤銷要從機制"
                "看得出來）。刪掉那個動作、改跑投影；**真要提到它，就在同一行寫出它"
                f"已{R.TOMBSTONE}**",
            )
        )
    return out


# ============================================================ 第 11 項：查詢入口表 ↔ SKILL.md
#
# **V3 的守衛**：查詢入口表（產物側）與 12 支 SKILL.md 的步驟（skill 側）是同一筆
# 內容的兩份，而在此之前**沒有任何 lint 在驗它們 ≡ 彼此**，於是兩份都自稱權威而
# 實測已分岔。依 `設計原則.md` A1 的補述：有一條 lint 在驗它 ≡ 別的檔，那支檔就是
# **視圖**——這一項就是那條 inbound 規則，而**權威在 skill 側**。

_SECTION8 = "## 八、"
_ENTRY_TABLE_HEAD = "### 成長型產物與各自的查詢入口"
_EXEMPT_HEAD = "### 不受此限的"


def _section8(repo: Path) -> list[str]:
    p = repo / R.SCHEMA_DIR / R.CONVENTIONS
    if not p.is_file():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith(_SECTION8)), None)
    if start is None:
        return []
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines)
    )
    return lines[start:end]


def entry_table(repo: Path) -> tuple[list[tuple[str, set[str]]], set[str]]:
    """(存活的表列, 明文豁免的路徑集合)。

    **墓碑列不算存活**：`~~story/大綧/_index.md~~ 2026-07-28 廢除` 那種列留在表上是
    刻意的（它是給下一輪的指路），但它**不該被要求有讀者**。
    """
    rows: list[tuple[str, set[str]]] = []
    exempt: set[str] = set()
    where = ""
    for ln in _section8(repo):
        s = ln.strip()
        if s.startswith(_ENTRY_TABLE_HEAD):
            where = "table"
            continue
        if s.startswith(_EXEMPT_HEAD):
            where = "exempt"
            continue
        if s.startswith("### "):
            where = ""
            continue
        if where == "table" and s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not cells or set(cells[0]) <= set("-: ") or cells[0] in ("產物", ""):
                continue
            if "~~" in cells[0]:  # 墓碑列
                continue
            pats = R.book_paths(cells[0])
            if pats:
                norm: set[str] = set()
                for x in pats:
                    norm |= R.normalize_paths(x)
                rows.append((cells[0], norm))
        elif where == "exempt" and s.startswith("- "):
            for x in R.book_paths(s):
                exempt |= R.normalize_paths(x)
    return rows, exempt


def check_entry_table(repo: Path, stats: MetaStats) -> list[Problem]:
    """第 11 項：查詢入口表的每一列至少 1 支 SKILL.md 讀它，**而且反過來也成立**。

    反向那一半是本項的重點：**SKILL.md 讀的每一個產物軸都要在表裡或明文豁免裡**。
    實測 2026-07-29 抓到三列缺席（風格軸／`chapters/chNNNN.ai.md`／`幕綱/_順序.md`），
    而**風格軸是最糟的一型**——不在表裡、也不在豁免裡，**兩份清單都沒有它**，那個
    狀態從 2026-07-27（功能 07 把它從豁免清單移除）起活了兩天。
    """
    rows, exempt = entry_table(repo)
    skill_paths: dict[str, set[str]] = {}
    for p in R.skill_files(repo):
        for raw in R.book_paths(p.read_text(encoding="utf-8")):
            # **只算指名一支檔的宣告**：`story/參照/`／`chapters/` 這種裸目錄提及是
            # 位置指路、不是取用宣告（它沒說要讀哪一支）。**已廢除的檔也不算**
            # ——那是第 10 項的事，兩項都報等於同一筆算兩次。
            for one in R.normalize_paths(raw):
                if not one.endswith(".md") or one.rpartition("/")[2] in R.ABOLISHED:
                    continue
                skill_paths.setdefault(one, set()).add(p.parent.name)

    out: list[Problem] = []
    stats.entry_rows = len(rows)
    if not rows:
        stats.entry_rows_unread = 0
        stats.skill_axes_unlisted = 0
        return [
            Problem(
                f"{R.SCHEMA_DIR}/{R.CONVENTIONS}",
                "讀不到查詢入口表（第八節的表頭改了？）",
                "**這一項不見了，兩份清單就會安靜地分岔**——那正是它誕生要擋的事",
            )
        ]

    unread = [
        label
        for label, pats in rows
        if not any(_covers(pat, sp) for pat in pats for sp in skill_paths)
    ]
    covered = {
        sp
        for sp in skill_paths
        if any(_covers(pat, sp) for _, pats in rows for pat in pats)
        or any(_covers(ex, sp) for ex in exempt)
    }
    unlisted = sorted(set(skill_paths) - covered)
    stats.entry_rows_unread = len(unread)
    stats.skill_axes_unlisted = len(unlisted)

    if unread:
        out.append(
            Problem(
                f"{R.SCHEMA_DIR}/{R.CONVENTIONS} 八",
                f"{len(unread)} 列查詢入口沒有任何 SKILL.md 讀它："
                + "、".join(f"「{x[:40]}」" for x in unread),
                "**一個沒有讀者的查詢入口與一個不存在的查詢入口，在系統的行為上完全"
                "相同**（E1 的消費者推論）。把它掛進某支 SKILL.md 的讀輸入步驟，"
                "或連同那一列一起刪掉",
            )
        )
    if unlisted:
        out.append(
            Problem(
                f"{R.SCHEMA_DIR}/{R.CONVENTIONS} 八",
                f"{len(unlisted)} 個 SKILL.md 讀的路徑既不在查詢入口表、也不在「不受此限」："
                + "、".join(
                    f"`{x}`（{'、'.join(sorted(skill_paths[x]))}）" for x in unlisted
                ),
                "**兩份清單都沒有它**——那是「宣稱的入口與實際的入口不一致」最糟的"
                "一型（實測風格軸就這樣活了兩天）。補一列查詢入口，或依 E2 第七形態"
                "把它寫進「不受此限」**並寫出它豁免的是哪一項**",
            )
        )
    return out


# ============================================================ 第 12 項：技法檔與它的三份清單
#
# ① `技巧知識庫/_index.md` 的「被哪些 skill 引用」欄（2026-07-29 改成投影，降級成殘留
# 偵測）／② `CLAUDE.md` 的技法檔列舉 ≡ 資料夾／③ **被引用的技法檔都有檔頭目錄且標核心**。
#
# ③ 是本項最硬的一格：**10/12 支 SKILL.md 寫著「先讀各檔檔頭『目錄』標核心的小節」，
# 而 2026-07-29 實測 14/28 支技法檔根本沒有檔頭目錄**（`write` 引用的 19 支有 11 支
# 沒有，佔 44% 的位元組）——**指令指向一個不存在的結構，而沒有任何東西會發現**
# （E2 最後一格：LLM 讀不到目錄就整檔讀，輸出完全正常）。

_KB_REF_COLUMN = "被哪些 skill 引用"
_TOC_HEAD = "## 目錄"
_TOC_CORE = "核心"
# **同一行幾支才算「列舉」**。不是取自分佈的空隙（那不是一個分佈），是取自形狀：
# 1 支＝指向那一支的具體內容，2 支＝一組對照（`A.md` 與 `B.md` 的分工），**3 支以上
# 在一行上就是在複述資料夾**。實測舊 `CLAUDE.md` 那一行是 19 支。
_ENUMERATION = 3


def kb_referrers(repo: Path) -> dict[str, set[str]]:
    """技法檔 → 引用它的 skill 名集合。**這是「被哪些 skill 引用」欄的機械來源。**

    比對的是**檔名**（`對白.md`），不是路徑——實測 12 支 SKILL.md 多數寫裸檔名
    （`` `對白.md` ``），只有 `write` 那幾條寫全路徑。
    """
    skills = {p.parent.name: p.read_text(encoding="utf-8") for p in R.skill_files(repo)}
    return {
        kb.name: {name for name, text in skills.items() if kb.name in text}
        for kb in R.kb_files(repo)
    }


def _has_core_toc(text: str) -> bool:
    """檔頭有 `## 目錄` 節，且該節裡標了「核心」。**結構判準**：只問在不在、
    不問目錄寫得好不好（那是內容，不是格式）。"""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip().startswith(_TOC_HEAD)), None)
    if start is None:
        return False
    body = []
    for ln in lines[start + 1 :]:
        if ln.strip().startswith("## ") or ln.strip().startswith("---"):
            break
        body.append(ln)
    return _TOC_CORE in "\n".join(body)


def check_kb_lists(repo: Path, stats: MetaStats) -> list[Problem]:
    """第 12 項：技法檔的三份平行清單。"""
    out: list[Problem] = []
    refs = kb_referrers(repo)
    stats.kb_files = len(refs)
    stats.kb_unreferenced = sum(1 for v in refs.values() if not v)

    # ① 殘留偵測：那一欄 2026-07-29 改成 `meta-lint --emit kb` 投影。
    # **只看表頭列，不看整支檔**——說明那一欄為什麼消失的散文本來就會提到它的名字，
    # 而整檔比對會把那段說明自己報成殘留（實作時實測到）。
    idx = repo / R.KB_DIR / R.KB_INDEX
    if idx.is_file() and any(
        ln.lstrip().startswith("|") and _KB_REF_COLUMN in ln
        for ln in idx.read_text(encoding="utf-8").splitlines()
    ):
        out.append(
            Problem(
                f"{R.KB_DIR}/{R.KB_INDEX}",
                f"還有「{_KB_REF_COLUMN}」欄——它 2026-07-29（功能 15）改成投影了",
                "那一欄的機械來源是 grep 12 支 SKILL.md，而手抄的那一份實測 **15/27 列"
                "不一致**（宣稱而無實據 19 筆、實測而未登記 9 筆）。跑 "
                "`meta-lint --emit kb`；「何時查它」欄是源，留著",
            )
        )

    # ② `CLAUDE.md` **列舉了技法檔，就要列齊**。
    #
    # **判準是位置不是總數**：一行上出現 ≥`_ENUMERATION` 支就算列舉（那是在複述資料夾），
    # 1–2 支是**指路**（指向某一支的具體內容，例如分類公理裡那句「公式名照
    # `技巧知識庫/結構公式.md` 的 registry 寫」）。實作時實測到：用「全檔命名集合 ≡
    # 資料夾，否則報」會把那一句合法的指路報成「漏列 26 支」——**一個會誤報的閘門就是
    # 下一個沒有人看的閘門**。
    doc = repo / R.PROJECT_DOC
    if doc.is_file():
        text = doc.read_text(encoding="utf-8")
        named = {n for n in refs if n in text}
        stats.claude_kb_named = len(named)
        enumerated: set[str] = set()
        for ln in text.splitlines():
            on_line = {n for n in refs if n in ln}
            if len(on_line) >= _ENUMERATION:
                enumerated |= on_line
        if enumerated and enumerated != set(refs):
            missing = sorted(set(refs) - enumerated)
            out.append(
                Problem(
                    R.PROJECT_DOC,
                    f"某一行列舉了 {len(enumerated)}/{len(refs)} 支技法檔，漏 {len(missing)} 支："
                    + "、".join(f"`{n}`" for n in missing),
                    "**列舉了就要齊**（C3：每一種 ID 都要有一份 registry）。實測漏列的"
                    "那幾支在答問檔位永遠不會被想到（那一檔位照 `CLAUDE.md` 定位）。"
                    f"要嘛補齊，要嘛改成指路 `{R.KB_DIR}/{R.KB_INDEX}`（唯一入口）",
                )
            )

    # ③ 被 SKILL.md 引用的技法檔都要有檔頭目錄且標核心
    no_toc = sorted(
        kb.name
        for kb in R.kb_files(repo)
        if refs.get(kb.name) and not _has_core_toc(kb.read_text(encoding="utf-8"))
    )
    stats.kb_referenced = sum(1 for v in refs.values() if v)
    stats.kb_without_toc = len(no_toc)
    if no_toc:
        out.append(
            Problem(
                f"{R.KB_DIR}/",
                f"{len(no_toc)} 支被 SKILL.md 引用的技法檔沒有「{_TOC_HEAD}」節或該節沒標"
                f"「{_TOC_CORE}」：" + "、".join(f"`{n}`" for n in no_toc),
                "**10/12 支 SKILL.md 寫著「先讀各檔檔頭『目錄』標核心的小節」——"
                "承諾的結構必須存在**（E1）。前提為假時 LLM 讀不到目錄就整檔讀，"
                "而輸出完全正常（E2 最後一格）。補一個 `## 目錄` 節（條目從既有的 "
                "`##` 標題重述），或把引用它的那一句改成「整檔讀」",
            )
        )
    return out


# ============================================================ 第 13 項：生產包封閉性
#
# **新增於 2026-07-30（驗證輪階段 1.5）。為什麼需要它。**
# 生產形態是「系統層 ＋ 一本書」，而在此之前系統層白名單把 `tools/` **整支**列進去，
# 於是生產包裡會有 `meta_lint`——一支消費者是 `.github/workflows/tools.yml` 的指令，
# 而 `.github/` 不在白名單上。**指令進了生產包，它的觸發者沒有**，那是 E1 的反面；
# 更糟的是它在生產側的第 6 項（要病例書 `一世之尊/`）與第 10 項（要 `情境測試/`）
# 都會印「未接」而 exit 0 —— **守衛在、射程空、輸出綠**，E2 最糟那一格。
#
# **這一項守的是「拆完之後不會慢慢黏回去」。** 拆分本身是一次性的動作，而讓它保持
# 拆開的是：① 每支套件都要宣告自己屬哪一邊；② 宣告要與它住的資料夾一致；
# ③ 生產側的 `src/` 不准提到開發期的落點。
#
# **第 ③ 條抓的是「路徑字面」，不是「提到那個名字」。** 這一格第一版寫錯過，值得記：
# 原本只要字串常數裡出現 `docs/` 就報，實測**7 處全是誤報**——`lint.py:492` 的
# `「（見 docs/重構/功能報告/02-幕綱.md §八）」` 與 `style_lint.py:1` 的模組 docstring
# 都是**出處引用**（這條門檻的實測依據在哪份報告），與註解完全同一個性質，只是剛好
# 存成字串。刪掉它們會讓常數變成天上掉下來的數字。
#
# **判準因此是形狀**：字串要**長得像一條路徑**（無空白、無全形標點）且**第一段**是
# 開發期資料夾。散文句子有全形括號與空白，一律不match；`Path("examples/一世之尊")`
# 這種真的會去讀檔的寫法一定match。
# **代價要認**：藏在 f-string 散文裡的真實讀取抓不到——但那種寫法也組不出路徑。
# 今天這一條是 **0 命中，擋的是未來**，與 `tools.yml` 步驟 ① 的「有 pyproject 而沒有
# tests/」同形。

# 開發期資料夾（`00-系統層邊界與儀器.md` §一 開發期表 ＋ `設計原則.md` 射程表第五格）。
# **`書本模板/` 不在裡面**：它是系統層（開新書的骨架），生產包要帶著它。
_DEV_ONLY_DIRS = ("examples", "情境測試", "docs", "Data", "site", "devtools")
# 路徑字面的形狀：不含空白，也不含中文散文的全形標點。
_PROSE_CHARS = frozenset(" \t\n（）「」『』，。：；、？！—…`")


def _path_like_constants(path: Path) -> list[tuple[int, str]]:
    """一支 `.py` 裡**長得像路徑**的字串常數＋行號。

    **註解不在射程內**（AST 不留註解），而那是對的：註解寫「門檻取自 `examples/` 六本」
    是實測出處。散文型的字串常數也不在射程內——判準見上面那段。
    語法錯誤時回空 list 並不報：這一項的對象是落點，不是語法（語法壞了 pytest 會先炸）。
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    out: list[tuple[int, str]] = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
            continue
        s = n.value
        if not s or len(s) > 200 or set(s) & _PROSE_CHARS:
            continue
        if s.split("/", 1)[0] in _DEV_ONLY_DIRS:
            out.append((n.lineno, s))
    return out


def check_ship_closure(repo: Path, stats: MetaStats) -> list[Problem]:
    """第 13 項：射程宣告存在／宣告 ↔ 位置一致／生產側 src 不提開發期落點。"""
    out: list[Problem] = []
    pkgs = R.packages(repo)

    misplaced: list[str] = []
    for pkg in pkgs:
        cmds = len(pkg.scripts)
        if pkg.scope == R.SCOPE_BOOK:
            stats.ship_packages += 1
            stats.ship_commands += cmds
        elif pkg.scope == R.SCOPE_REPO_DEV:
            stats.dev_packages += 1
            stats.dev_commands += cmds
        else:
            stats.scope_undeclared += 1
            out.append(
                Problem(
                    f"{pkg.rel}/pyproject.toml",
                    f"沒有可辨識的射程宣告（`[tool.novelai] scope`，讀到 {pkg.scope!r}）",
                    "**沒宣告的套件不知道自己該不該進生產包**，而複製系統層的人也不會知道。"
                    f"加一行 `scope = \"{R.SCOPE_BOOK}\"`（吃 `--book`、消費者是 SKILL.md）"
                    f"或 `scope = \"{R.SCOPE_REPO_DEV}\"`（守 repo、觸發者是 workflow）",
                )
            )
            continue
        expected = R.SCOPES[pkg.scope]
        if pkg.root != expected:
            misplaced.append(f"`{pkg.rel}` 宣告 `{pkg.scope}` 卻住在 `{pkg.root}/`")

    if misplaced:
        out.append(
            Problem(
                "tools/ 與 devtools/",
                f"{len(misplaced)} 個套件的宣告與位置不一致：{'；'.join(misplaced)}",
                "**宣告與位置必須是同一件事的兩種說法**，否則「複製 `tools/`」這個"
                f"資料夾粒度的規則就失效了。`{R.SCOPE_BOOK}` 住 `{R.TOOLS_DIR}/`、"
                f"`{R.SCOPE_REPO_DEV}` 住 `{R.DEVTOOLS_DIR}/`",
            )
        )

    leaks: list[str] = []
    for pkg in pkgs:
        if not pkg.ships or not pkg.src.is_dir():
            continue
        for py in sorted(pkg.src.rglob("*.py")):
            stats.ship_src_files += 1
            for lineno, text in _path_like_constants(py):
                stats.ship_src_leaks += 1
                leaks.append(f"`{py.relative_to(repo).as_posix()}:{lineno}` → `{text}`")
    if leaks:
        out.append(
            Problem(
                "生產側 src/",
                f"{len(leaks)} 處生產側程式碼帶開發期路徑字面：{'；'.join(leaks[:5])}"
                + ("…" if len(leaks) > 5 else ""),
                "生產 project 裡那些資料夾**不存在**，所以讀它們要嘛 raise、要嘛靜靜地"
                "當成「沒有資料」——後者更糟。**註解與出處引用不算**（那是門檻的實測"
                "依據），這一項只抓路徑形狀的字面。要吃開發期語料的程式碼住 "
                f"`{R.DEVTOOLS_DIR}/`，或改成由呼叫端傳路徑進來"
                "（先例：`prose-metrics --corpus <作者給的路徑>`）",
            )
        )
    return out


# ============================================================ --emit：兩個投影
#
# **投影不是閘門、一律 exit 0**（形狀照抄功能 12 的五個 `--emit`）。


def emit_guards(repo: Path) -> list[str]:
    """`--emit guards`：22 個指令的閘門清單。

    **它取代 `共同約定.md` 八 那 11,399 B 的手抄 bullet**（2026-07-29 功能 15
    抉擇 1 A）。四欄全部有機械來源，逐欄對得上：

    | 欄 | 機械來源 |
    |---|---|
    | 指令／套件 | `pyproject.toml` 的 `[project.scripts]`（＝ `repo.commands()`） |
    | 守什麼 | 各 `cli.py` 的 argparse `description` |
    | 觸發者 | grep 12 支 SKILL.md ＋ workflow（＝第 1 項的同一份資料） |
    | 覆蓋率行 | 第 5 項的 AST 結果 |

    **全靜態、零 subprocess**——所以它可以有黃金檔。
    """
    cmds = R.commands(repo)
    descs = _argparse_descriptions(repo)
    triggers: dict[str, list[str]] = {c: [] for c in cmds}
    for p in R.skill_files(repo):
        t = p.read_text(encoding="utf-8")
        for c in cmds:
            if c in t:
                triggers[c].append(p.parent.name)
    for p in R.workflow_files(repo):
        t = p.read_text(encoding="utf-8")
        for c in cmds:
            if c in t:
                triggers[c].append(f"workflow:{p.name}")

    stats = MetaStats()
    bad = {x.split(":")[1] for x in _entries_without_coverage(repo, stats)}
    out = [
        f"## 工具鏈閘門清單（{len(cmds)} 個指令／{len(R.packages(repo))} 個套件）",
        "",
        "> **這是投影，不是閘門**（一律 exit 0）。四欄的機械來源：指令與套件＝"
        "`pyproject.toml` 的 `[project.scripts]`；守什麼＝各 `cli.py` 的 argparse "
        "`description`；觸發者＝grep 12 支 SKILL.md 與 workflow；覆蓋率行＝第 5 項的 "
        "AST 掃描。**手抄的那一份 2026-07-29（功能 15）從 `共同約定.md` 八 移除**"
        "——它曾是那一節的 11,399 B，而沒有任何東西驗過它與程式一致。",
        "",
        "| 指令 | 套件 | 守什麼 | 觸發者 | 覆蓋率行 |",
        "|------|------|--------|--------|---------|",
    ]
    for c in sorted(cmds):
        who = "、".join(sorted(set(triggers[c]))) or "**無**"
        d = descs.get(c, "**讀不到 description**")
        fn = _entry_fn(repo, c)
        cov = "—" if fn is None else ("**無**" if fn in bad else "有")
        out.append(f"| `{c}` | `{cmds[c]}` | {d} | {who} | {cov} |")
    out += [
        "",
        f"覆蓋率行那一欄只對**閘門**有意義（`*-lint` 與 `derived-sync`）；投影印 `—`"
        "——它們的「我掃了幾筆」長在報表標題裡，形狀不同（第 5 項的射程註解）。",
    ]
    return out


def emit_kb(repo: Path) -> list[str]:
    """`--emit kb`：技法檔 ↔ 引用它的 skill。

    **它取代 `技巧知識庫/_index.md` 的「被哪些 skill 引用」欄**（2026-07-29 功能 15
    抉擇 4 A，形狀完全同功能 12 的五支 rollup）。機械來源＝grep 12 支 SKILL.md。

    **0 支也印**：實測 `角色關係網與群像.md`（10,513 B）與 `角色魅力與登場.md`
    （13,189 B）零 skill 引用，而手抄的那一欄宣稱它們各有 6／7 支——那 23,702 B 是
    「索引宣稱有消費者、而消費者為零」的知識。**那一格是給下一輪看的儀表，不是本輪
    要填掉的洞**（同功能 10 對「未接」的處置）：要不要接上它們是內容決定。
    """
    refs = kb_referrers(repo)
    zero = [k for k, v in refs.items() if not v]
    out = [
        f"## 技法檔的 skill 引用（{len(refs)} 支；**{len(zero)} 支零引用**）",
        "",
        "> **這是投影，不是閘門**（一律 exit 0）。機械來源＝grep "
        f"{len(R.skill_files(repo))} 支 `SKILL.md` 的檔名提及。"
        "「何時查它」欄是**源**（重跑不會回來），留在 "
        f"`{R.KB_DIR}/{R.KB_INDEX}`；這一欄是視圖，所以不落檔。",
        "",
        "| 技法檔 | 幾支 | 哪幾支 |",
        "|--------|------|--------|",
    ]
    for k in sorted(refs, key=lambda x: (-len(refs[x]), x)):
        v = sorted(refs[k])
        out.append(f"| `{k}` | {len(v)} | {'、'.join(f'`{s}`' for s in v) or '**0 支**'} |")
    if zero:
        out += [
            "",
            f"**零引用的 {len(zero)} 支**："
            + "、".join(f"`{k}`" for k in sorted(zero))
            + "——它們只服務答問檔位（`CLAUDE.md`「答問」那一格）。**這不是待修的洞**："
            "要不要讓某支 skill 引用它們是內容決定，不是格式決定。",
        ]
    return out


_DESC_RE = re.compile(r"^\s*description=")


def _argparse_descriptions(repo: Path) -> dict[str, str]:
    """指令名 → argparse `description` 的第一句。

    做法是 AST：找 `cli.py` 裡每個 `ArgumentParser(description=...)`，用它所在的函式
    名對回 `[project.scripts]` 的 entry point。**多行隱式字串串接在 AST 裡是單一
    `Constant`**，所以取得到完整值；**f-string（`JoinedStr`）取它的字面段**，插值處
    印回那個常數的名字——實測 `fact-lint`／`object-lint` 兩支就是 f-string，而
    「讀不到」在一份取代了手抄清單的投影上是一個真的洞（E2：未接要說出來）。
    """
    ep: dict[str, str] = {}
    for pkg in R.packages(repo):
        for cmd, target in pkg.scripts.items():
            ep[f"{pkg.name}:{target.rpartition(':')[2]}"] = cmd
    out: dict[str, str] = {}
    for pkg, p in R.cli_modules(repo):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            cmd = ep.get(f"{pkg}:{node.name}")
            if cmd is None:
                continue
            for sub in ast.walk(node):
                if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)):
                    continue
                if sub.func.attr != "ArgumentParser":
                    continue
                for kw in sub.keywords:
                    if kw.arg != "description":
                        continue
                    text = _literal_text(kw.value)
                    if text is not None:
                        out[cmd] = re.sub(r"\s+", " ", text).strip()
    return out


def _literal_text(node: ast.expr) -> str | None:
    """`Constant` 直接回；`JoinedStr` 回字面段 ＋ 插值處印那個名字。"""
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            elif isinstance(v, ast.FormattedValue) and isinstance(v.value, ast.Name):
                parts.append(v.value.id)
            else:
                parts.append("…")
        return "".join(parts)
    return None


def _entry_fn(repo: Path, cmd: str) -> str | None:
    """這個指令是不是閘門；是的話回它的入口函式名（第 5 項的同一把尺）。"""
    if not (cmd.endswith(_GATE_SUFFIXES) or cmd in _GATE_COMMANDS):
        return None
    for pkg in R.packages(repo):
        if cmd in pkg.scripts:
            return pkg.scripts[cmd].rpartition(":")[2]
    return None


def _entries_without_coverage(repo: Path, stats: MetaStats) -> list[str]:
    """第 5 項的結果，重用給 `--emit guards` 的最後一欄——**不重算**。"""
    check_coverage_on_every_path(repo, stats)
    return getattr(stats, "_bad_entries", [])


def project_tests(repo: Path, stats: MetaStats, live: bool) -> list[str]:
    """第 9 項：8 個套件、N 支測試、**紅的幾支 ＋ 登記在案的理由**。

    **套件數含兩個根**（`tools/` 生產 ＋ `devtools/` 開發期，階段 1.5 起）。
    """
    reds = load_known_red(repo)
    pkgs = R.packages(repo)
    ships = sum(1 for p in pkgs if p.ships)
    out = [
        "",
        f"### 測試（{len(pkgs)} 個套件＝生產 {ships} ＋ 開發期 {len(pkgs) - ships}；"
        f"已知紅 {len(reds)} 支）",
        "",
    ]
    # **「清單空的」與「清單檔不在」不可以長得一樣**（見 `load_known_red`）。
    if not known_red_path(repo).is_file():
        out += [
            f"> ⚠️ **已知紅清單檔不在**（`{known_red_path(repo).relative_to(repo).as_posix()}`）"
            "——下面那個「0 支」是**讀不到**，不是**沒有**。",
            "",
        ]
    if not live:
        out += [
            "> **未接**（`--no-live`）——沒跑 pytest。CI 一律跑（`tools.yml`）。",
            "",
        ]
    else:
        for pkg in pkgs:
            if not pkg.tests.is_dir():
                out.append(f"- `{pkg.rel}`：**沒有 tests/**")
                continue
            r = subprocess.run(  # noqa: S603
                [
                    sys.executable if False else "uv",
                    "run",
                    "--project",
                    pkg.rel,
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    f"{pkg.rel}/tests",
                ],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            tail = [ln for ln in r.stdout.splitlines() if "passed" in ln or "failed" in ln]
            out.append(f"- `{pkg.rel}`：{tail[-1] if tail else '（讀不到結果）'}")
    out += ["", "**已知紅清單**（不在清單裡的紅字要 fail；在清單裡卻變綠了也要 fail）：", ""]
    if not reds:
        out.append("- （無）")
    for kr in reds:
        out.append(f"- `{kr.test}`\n  - {kr.reason}")
    return out
