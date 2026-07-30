"""repo 佈局的定位層——`meta-lint` 的「這本書有哪些受管檔」。

**它與 `derived_sync/book_layout.py` 是同一個形狀、不同的射程**：那一支回答
「一本書有哪些受管檔」，這一支回答「這個 repo 有哪些受管的**工具鏈**檔」。
兩份不能合併（跨套件零相依），但**兩份都印得出「我掃了幾支」**——那才是十次
漏檔的解藥。
"""

from __future__ import annotations

import ast
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = "tools"
# **開發期的套件根**（2026-07-30 驗證輪階段 1.5）。`tools/` 從此只住「生產包」
# ——21 支吃 `--book` 的指令，消費者是 12 支 SKILL.md；`meta_lint` 住這裡，
# 因為它的消費者是 `.github/workflows/tools.yml`，而 `.github/` 本來就不在
# 系統層白名單上。**一支指令在生產包裡而它的觸發者不在，是 E1 的反面。**
DEVTOOLS_DIR = "devtools"
PACKAGE_ROOTS = (TOOLS_DIR, DEVTOOLS_DIR)
SKILLS_DIR = ".claude/skills"
SCHEMA_DIR = "結構定義"
WORKFLOW_DIR = ".github/workflows"
KB_DIR = "技巧知識庫"
KB_INDEX = "_index.md"
TEMPLATE_BOOK = "書本模板"
CONVENTIONS = "共同約定.md"
PROJECT_DOC = "CLAUDE.md"
DEVDOC_DIR = "情境測試"


def find_repo(start: Path | None = None) -> Path:
    """往上找到帶 `tools/` 與 `結構定義/` 的那一層。

    **不吃 `--book`**（本工具唯一的識別特徵），所以入口要自己找得到 repo 根。
    """
    here = (start or Path(__file__)).resolve()
    for p in [here, *here.parents]:
        if (p / TOOLS_DIR).is_dir() and (p / SCHEMA_DIR).is_dir():
            return p
    raise FileNotFoundError(f"找不到 repo 根（要有 {TOOLS_DIR}/ 與 {SCHEMA_DIR}/）：{here}")


# 射程宣告的兩個合法值（`[tool.novelai] scope`）。**封閉枚舉**——第三個值要先改
# 這裡，而第 13 項會把不認得的值報出來。ASCII 鍵是刻意的：TOML 裸鍵不收非 ASCII。
SCOPE_BOOK = "book"  # 吃 `--book`，消費者是 SKILL.md，進生產包
SCOPE_REPO_DEV = "repo-dev"  # 守 repo 自己，觸發者是 workflow，不進生產包
SCOPES = {SCOPE_BOOK: TOOLS_DIR, SCOPE_REPO_DEV: DEVTOOLS_DIR}


@dataclass(frozen=True)
class Package:
    name: str  # 資料夾名（`derived_sync`）
    path: Path
    root: str  # 套件根（`tools` / `devtools`）
    scripts: dict[str, str] = field(default_factory=dict)  # 指令名 → entry point
    scope: str | None = None  # `[tool.novelai] scope`；None ＝沒宣告（第 13 項會報）

    @property
    def rel(self) -> str:
        """`uv run --project` 吃的相對路徑（`tools/derived_sync`）。

        **不要再用 `f"{TOOLS_DIR}/{pkg.name}"` 拼**——階段 1.5 之前有四處那樣拼，
        而套件一搬家，那四處會安靜地指到不存在的路徑（其中 `load_known_red` 讀不到
        清單時回 `[]`，於是「已知紅 0 支」照印，而那是假的）。
        """
        return f"{self.root}/{self.name}"

    @property
    def src(self) -> Path:
        return self.path / "src"

    @property
    def tests(self) -> Path:
        return self.path / "tests"

    @property
    def ships(self) -> bool:
        """進不進生產包（系統層 ＋ 一本書）。`tests/` 一律不進，見第 13 項。"""
        return self.root == TOOLS_DIR


def packages(repo: Path) -> list[Package]:
    """所有 uv 套件（有 `pyproject.toml` 的 `tools/*` 與 `devtools/*`）。

    **兩個根都要掃。** 階段 1.5 把 `meta_lint` 搬進 `devtools/`，而這支函式是
    第 1／5／6／9／13 項共用的枚舉器——只掃 `tools/` 的話 `meta-lint` 從此**看不見
    自己**，那五項各少驗一支而輸出完全正常（`設計原則.md` E2 最糟那一格）。
    """
    out: list[Package] = []
    for root in PACKAGE_ROOTS:
        base = repo / root
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            pj = d / "pyproject.toml"
            if not pj.is_file():
                continue
            data = tomllib.loads(pj.read_text(encoding="utf-8"))
            out.append(
                Package(
                    name=d.name,
                    path=d,
                    root=root,
                    scripts=dict(data.get("project", {}).get("scripts", {})),
                    scope=data.get("tool", {}).get("novelai", {}).get("scope"),
                )
            )
    return out


def package_rel(repo: Path, name: str) -> str:
    """套件名 → `uv run --project` 吃的相對路徑。**根由枚舉決定，不由字面拼接。**

    找不到就回 `tools/<name>`——讓後續的 `uv run` 大聲失敗，而不是在這裡吞掉。
    """
    for pkg in packages(repo):
        if pkg.name == name:
            return pkg.rel
    return f"{TOOLS_DIR}/{name}"


def commands(repo: Path) -> dict[str, str]:
    """指令名 → 它住哪個套件。**這是全 repo 唯一一份指令 registry**。

    在 2026-07-28（功能 14）之前**它不存在**：21 個指令的唯一登記處是 8 支
    `pyproject.toml` 的 `[project.scripts]` 區塊，而系統對書內檔立了 C1（ID 優先
    成為檔名）與 C3（每一種 ID 都要有一份 registry）——**工具鏈是這個 repo 裡唯一
    一批「有 ID、而 ID 沒有 registry」的東西**（V12）。
    """
    out: dict[str, str] = {}
    for pkg in packages(repo):
        for cmd in pkg.scripts:
            out[cmd] = pkg.name
    return out


def skill_files(repo: Path) -> list[Path]:
    d = repo / SKILLS_DIR
    return sorted(d.glob("*/SKILL.md")) if d.is_dir() else []


def schema_files(repo: Path) -> list[Path]:
    d = repo / SCHEMA_DIR
    return sorted(d.glob("*.schema.md")) if d.is_dir() else []


def kb_files(repo: Path) -> list[Path]:
    """技法檔（`技巧知識庫/*.md` 減掉 `_index.md`）。第 12 項掃它。"""
    d = repo / KB_DIR
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.md") if p.name != KB_INDEX)


def workflow_files(repo: Path) -> list[Path]:
    d = repo / WORKFLOW_DIR
    return sorted(d.glob("*.yml")) + sorted(d.glob("*.yaml")) if d.is_dir() else []


def devdoc_files(repo: Path) -> list[Path]:
    """開發期的**活指示檔**（`情境測試/*.md`）。第 10 項的墓碑那一格掃它。

    **為什麼要掃它**：`設計原則.md` 末節的射程表原本只有三格（書內檔／`tools/*.py`／
    `.claude/skills/`＋`技巧知識庫/`＋`結構定義/` 非 schema 檔），`情境測試/` 一格都不在。
    於是 `端到端貫穿測試流程.md` 能在功能 10 廢除 `就緒儀表.md` 兩天後照樣叫人去讀它，
    **而 `meta-lint` 的覆蓋率行印「0 條指向已廢除的檔」**——這正是第 10 項自己寫的那句
    「掃描對象是對的，掃描的欄位只有一格」的下一個實例：欄位對了，**射程少一個資料夾**。

    **只掃頂層、不遞迴**（`情境測試/<書>/` 不掃）。那底下住的是 S1–S51 的逐 session
    紀錄——**歷史紀錄提到一支當時還活著的檔是正確的**，那是它當時的事實，不是今天的
    指示。把 append-only 的歷史納入墓碑檢查，等於要求歷史隨著今天的廢除而改寫，而
    「判例要能回查」是 `CLAUDE.md` 第三問立事件流的理由本身。
    代價是「有人把活指示放進 `情境測試/<書>/`」抓不到；依 E1，**驗不到的就不宣稱**。
    """
    d = repo / DEVDOC_DIR
    return sorted(d.glob("*.md")) if d.is_dir() else []


def cli_modules(repo: Path) -> list[tuple[str, Path]]:
    """(套件名, `cli.py` 路徑)。第 5 項掃它。"""
    out = []
    for pkg in packages(repo):
        if not pkg.src.is_dir():
            continue
        out += [(pkg.name, p) for p in sorted(pkg.src.rglob("cli.py"))]
    return out


def source_files(repo: Path) -> list[tuple[str, Path]]:
    """(套件名, `src/**/*.py`)。第 7／8 項掃它——**不含 tests、不含 `.venv`**。"""
    out = []
    for pkg in packages(repo):
        if not pkg.src.is_dir():
            continue
        out += [(pkg.name, p) for p in sorted(pkg.src.rglob("*.py"))]
    return out


# 反引號裡的指令 token：`` `beat-lint` ``／`` `derived-sync check` ``／
# `` `uv run --project … outline-lint --book <書>` ``。取**第一個**看起來像指令名的詞。
_BACKTICK_RE = re.compile(r"`([^`\n]{1,120})`")
_TOKEN_RE = re.compile(r"(?<![\w./-])([a-z][a-z0-9]*(?:-[a-z0-9]+)+)(?![\w/-])")


def command_tokens(text: str, known: set[str]) -> set[str]:
    """散文裡提到的指令 token（只認**反引號內**的）。

    **射程刻意窄**（同 `outline-lint` 第 9 項的取法）：反引號外的中文散文會撈到
    一堆 kebab-case 的英文詞（`front-matter`／`8-gram`／`Deep-POV`），那些不是指令。
    """
    out: set[str] = set()
    for m in _BACKTICK_RE.finditer(text):
        for t in _TOKEN_RE.findall(m.group(1)):
            if t in known or t in _SUSPECT_SHAPES:
                out.add(t)
    return out


# **已知的殭屍指令名**——它們形狀像指令、而且確實曾經是指令，所以第 2 項要抓得到。
# 沒有這一組的話，一個「不在 registry 裡」的 token 與「一個剛好有連字號的英文詞」
# 不可分辨，而後者多到無法逐一排除（實測 `front-matter`／`8-gram`／`pass/fail`）。
#
# **這不是一份會漂移的機讀資料**：它是封閉的（只裝已知的殭屍），不隨 repo 成長，
# 而且新增一個殭屍名的時機就是刪掉一個指令的時機——同 `結構公式.md` 的 registry
# 先例（功能 11 抉擇 4 B：**封閉、不隨書成長、與它的真相同居一檔**）。
_SUSPECT_SHAPES = frozenset(
    {
        "state-project",  # 章末狀態快照的產生器，2026-07-27（功能 03）廢除
        "ch-project",  # 只在 docs 出現過，從未實作
        "index-project",  # 功能 12 抉擇 4 B 已駁回的跨套件聚合器
    }
)


# ============================================================ 書內路徑（第 10／11 項）
#
# **射程與 `command_tokens` 完全相同**：只認**反引號內**的。反引號外的中文散文會
# 撈到路徑的片段與敘述性的「story/…」比喻，而那些不是取用宣告。

# **`*` 要留在裡面**：查詢入口表那一側寫的就是 glob（`chapters/*.ai.md`、
# `story/設定/角色/*`），濾掉 `*` 會讓 `story/設定/角色/*` 被截成
# `story/設定/角色/`，於是第 11 項對每一支角色檔都報「不在表裡」。實作時實測到
# ——16 筆假陽性裡有 3 筆就是這個原因。
_BOOK_PATH_RE = re.compile(
    r"(?<![\w/.-])((?:story|chapters|raw)/[^\s`（）()、，。；：｜|＋+\[\]]*)"
)


def book_paths(text: str) -> set[str]:
    """散文裡提到的書內路徑（只認反引號內的）。第 10／11 項的原生單位。"""
    out: set[str] = set()
    for m in _BACKTICK_RE.finditer(text):
        out.update(_BOOK_PATH_RE.findall(m.group(1)))
    return out


_BRACE_RE = re.compile(r"\{([^{}]*)\}")


def normalize_paths(p: str) -> set[str]:
    """把一個宣告出來的路徑收成一組 glob，讓「宣告的形狀」與「受管的形狀」可比。

    `story/設定/角色/<名>.md` → `story/設定/角色/*.md`；`arcNN`／`chNNNN` → `arc*`／`ch*`。

    **大括號是展開、不是收成 `*`**（實作時實測到）：`story/00-摘要.{md,ai.md}` 收成
    `story/00-摘要.*` 之後，與 skill 側寫的 `story/00-摘要.md` 就對不上了，於是
    第 11 項對摘要軸同時報「這一列沒有讀者」與「這支檔不在表裡」——**同一筆內容
    被報成兩個相反的問題**。展開成兩支檔之後兩邊逐字相同。

    **這是結構正規化不是語意判斷**——只認佔位符的形狀，不去猜 `<名>` 是什麼。
    """
    p = p.replace("\\", "/").rstrip("/")
    p = re.sub(r"<[^>]*>", "*", p)  # <名> <主題> <實體> <切面>
    p = re.sub(r"arcNN|arcAA|arc\d+", "arc*", p)
    p = re.sub(r"chNNNN|ch\d{4}", "ch*", p)
    p = re.sub(r"幕NNN|幕\d+", "幕*", p)
    out = {re.sub(r"\*+", "*", p)}
    while any(_BRACE_RE.search(x) for x in out):
        nxt: set[str] = set()
        for x in out:
            m = _BRACE_RE.search(x)
            if not m:
                nxt.add(x)
                continue
            nxt |= {x[: m.start()] + alt.strip() + x[m.end() :] for alt in m.group(1).split(",")}
        out = nxt
    return out


# **已廢除的書內檔**——basename → (哪一輪廢的, 內容現在跑什麼)。
#
# **這不是一份會漂移的機讀資料**：它是封閉的（只裝已經廢除的），不隨 repo 也不隨書
# 成長，而且**新增一筆的時機就是廢除一支檔的時機**——同 `_SUSPECT_SHAPES` 與
# `結構公式.md` 的 registry 先例（功能 11 抉擇 4 B：封閉、不隨書成長、與它的真相同居）。
#
# **為什麼要它**：功能 10／11／12 廢除了七支檔，而**廢除只寫進了 schema 與 SKILL.md
# 的註解**。實測 2026-07-29：24 條取用宣告仍在命令讀／寫它們，一半是寫入命令，而
# `meta-lint` 的覆蓋率行印「0 個 registry 查無」——**掃描對象是對的，掃描的欄位只有
# 一格**。沒有這一組的話，「已廢除的檔」與「還沒被想到的檔」在檢查器眼裡不可分辨。
ABOLISHED: dict[str, tuple[str, str]] = {
    "_index.ai.md": ("功能 12（2026-07-28）", "`ch-lint --emit`／`char-lint --emit`"),
    "_總覽.ai.md": ("功能 12（2026-07-28）", "`world-lint --emit`"),
    "_index.md": ("功能 12（2026-07-28）", "`beat-lint --emit`／`outline-lint --emit`"),
    "就緒儀表.md": ("功能 10（2026-07-28）", "`readiness` ＋源 `story/參照/就緒.md`"),
    "就緒儀表.ai.md": ("功能 10（2026-07-28）", "`readiness` ＋源 `story/參照/就緒.md`"),
    "結構.md": ("功能 11（2026-07-28）", "`structure-project` ＋大綱的 `## 選用結構公式`"),
    "結構.ai.md": ("功能 11（2026-07-28）", "`structure-project` ＋大綱的 `## 選用結構公式`"),
}

# 墓碑 token。**刻意只有一個**——一組會長大的「等價說法」清單就是一份會漂移的詞表
# （`style-lint` 第 4 項的紀律：判準要是結構或位置判準）。要提到一支已廢除的檔，就在
# **同一行**寫出它已廢除；做不到就別提它。
TOMBSTONE = "廢除"


# `_index.md` 是**唯一**一個與活檔撞名的：`技巧知識庫/_index.md` 是知識庫的檢索入口、
# 完全健在。實作時實測到——不排除它的話這一項會對 12 支 SKILL.md 報一堆假陽性，
# **而一個會誤報的閘門就是下一個沒有人看的閘門**（03 記的警報疲勞）。
_NOT_A_BOOK_FILE = (KB_DIR,)


def landing_places(repo: Path) -> tuple[set[str], list[str]]:
    """(受管的目錄集合, 這份集合是從哪裡算出來的)。

    **兩個來源，都是機械的**：
    1. `書本模板/` 的實際骨架——一本新書開出來長什麼樣（C1：檔名天生是選擇器）；
    2. `derived_sync/book_layout.py` 的路徑常數——「這本書有哪些受管檔」的唯一真相。

    **用 AST 讀，不 import**（跨套件零相依，同第 4 項讀 `validate.py` 的先例）。
    模板缺了某一層是正常的（它只有 15 支檔、沒有角色與世界觀資料夾），所以**兩個
    來源要聯集**——只靠模板會把 `story/設定/角色/` 報成「指不到」。
    """
    out: set[str] = set()
    notes: list[str] = []

    tmpl = repo / TEMPLATE_BOOK
    if tmpl.is_dir():
        n = 0
        for p in tmpl.rglob("*"):
            if p.is_dir():
                out.add(p.relative_to(tmpl).as_posix())
                n += 1
        notes.append(f"`{TEMPLATE_BOOK}` 骨架 {n} 個資料夾")
    else:
        notes.append(f"**找不到 `{TEMPLATE_BOOK}`**")

    bl = repo / TOOLS_DIR / "derived_sync" / "src" / "derived_sync" / "book_layout.py"
    if bl.is_file():
        tree = ast.parse(bl.read_text(encoding="utf-8"))
        consts: dict[str, object] = {}
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            for name in targets:
                try:
                    consts[name] = ast.literal_eval(node.value)  # type: ignore[arg-type]
                except (ValueError, TypeError, SyntaxError):
                    pass
        dirs = 0
        for key in ("OUTLINE_DIR", "BEAT_DIR", "REFERENCE_DIR"):
            v = consts.get(key)
            if isinstance(v, tuple):
                out.add("/".join(str(x) for x in v))
                dirs += 1
        if isinstance(consts.get("CHAPTERS_DIR"), str):
            out.add(str(consts["CHAPTERS_DIR"]))
            dirs += 1
        if isinstance(consts.get("OUTLINE_RETIRED"), str) and isinstance(
            consts.get("OUTLINE_DIR"), tuple
        ):
            out.add("/".join([*consts["OUTLINE_DIR"], str(consts["OUTLINE_RETIRED"])]))  # type: ignore[misc]
            dirs += 1
        notes.append(f"`book_layout.py` 路徑常數 {dirs} 個")
    else:
        notes.append("**讀不到 `book_layout.py`**")

    # 設定層三個 kind ＋ 角色的目錄形態。`SETTINGS_KINDS` 的擁有者是 `validate.py`
    # （第 4 項已經在讀它），這裡從同一支檔取——**不新開第四份清單**。
    val = repo / TOOLS_DIR / "derived_sync" / "src" / "derived_sync" / "validate.py"
    if val.is_file():
        tree = ast.parse(val.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "SETTINGS_KINDS" for t in node.targets
            ):
                try:
                    kinds = ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError):
                    kinds = ()
                for k in kinds:
                    out.add(f"story/設定/{k}")
                    out.add(f"story/設定/{k}/*")  # 角色的目錄形態 `<名>/<切面>.md`
                notes.append(f"`SETTINGS_KINDS` {len(kinds)} 個 kind")
    out.add("story")
    out.add("raw")
    return out, notes


# 子句邊界。**墓碑要逐子句判、不能整串判**——實作時實測到：`char-lint` 的
# description 為了別的事寫了「已廢除的欄」，整串判會讓同一串裡「`_index.ai.md` 的
# 角色清單 ≡ 資料夾」這句拿到免死金牌，6 筆只抓到 4 筆。子句是中文散文天然的單位
# （同 markdown 那一側逐「行」判的道理）。
_CLAUSE_RE = re.compile(r"[、；。]")


def abolished_in(text: str) -> set[str]:
    """整段文字裡提到的已廢除檔（**不做反引號 scoping，逐子句判墓碑**）。

    給 argparse `description` 用：那整個字串**就是**一條宣告，沒有「散文 vs 反引號」
    的分別。而它內部有自己的反引號，所以不能靠外面包一層——實作時實測到：包起來之後
    嵌套的反引號會讓 `_BACKTICK_RE` 配到錯的區間，6 筆只抓到 1 筆。
    """
    if any(x in text for x in _NOT_A_BOOK_FILE):
        return set()
    out: set[str] = set()
    for seg in _CLAUSE_RE.split(text):
        if TOMBSTONE in seg:
            continue
        for name in ABOLISHED:
            stem = name[: -len(".ai.md")] if name.endswith(".ai.md") else name[: -len(".md")]
            if name in seg or f"{stem}.{{md,ai.md}}" in seg:
                out.add(name)
    return out


def abolished_mentions(text: str) -> list[tuple[int, str]]:
    """(行號, 已廢除的檔名)——**只回沒有墓碑的那些**。

    逐行判斷：這一行的反引號裡提到了已廢除的**書內**檔，而同一行沒有寫「廢除」。
    """
    out: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        if TOMBSTONE in line:
            continue
        hits: set[str] = set()
        for m in _BACKTICK_RE.finditer(line):
            inner = m.group(1)
            if any(x in inner for x in _NOT_A_BOOK_FILE):
                continue
            for name in ABOLISHED:
                # `{md,ai.md}` 這種合寫也要抓到（`就緒儀表.{md,ai.md}`）
                stem = name[: -len(".ai.md")] if name.endswith(".ai.md") else name[: -len(".md")]
                if name in inner or f"{stem}.{{md,ai.md}}" in inner:
                    hits.add(name)
        out += [(i, n) for n in sorted(hits)]
    return out
