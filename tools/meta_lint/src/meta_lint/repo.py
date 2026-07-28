"""repo 佈局的定位層——`meta-lint` 的「這本書有哪些受管檔」。

**它與 `derived_sync/book_layout.py` 是同一個形狀、不同的射程**：那一支回答
「一本書有哪些受管檔」，這一支回答「這個 repo 有哪些受管的**工具鏈**檔」。
兩份不能合併（跨套件零相依），但**兩份都印得出「我掃了幾支」**——那才是十次
漏檔的解藥。
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = "tools"
SKILLS_DIR = ".claude/skills"
SCHEMA_DIR = "結構定義"
WORKFLOW_DIR = ".github/workflows"


def find_repo(start: Path | None = None) -> Path:
    """往上找到帶 `tools/` 與 `結構定義/` 的那一層。

    **不吃 `--book`**（本工具唯一的識別特徵），所以入口要自己找得到 repo 根。
    """
    here = (start or Path(__file__)).resolve()
    for p in [here, *here.parents]:
        if (p / TOOLS_DIR).is_dir() and (p / SCHEMA_DIR).is_dir():
            return p
    raise FileNotFoundError(f"找不到 repo 根（要有 {TOOLS_DIR}/ 與 {SCHEMA_DIR}/）：{here}")


@dataclass(frozen=True)
class Package:
    name: str  # 資料夾名（`derived_sync`）
    path: Path
    scripts: dict[str, str] = field(default_factory=dict)  # 指令名 → entry point

    @property
    def src(self) -> Path:
        return self.path / "src"

    @property
    def tests(self) -> Path:
        return self.path / "tests"


def packages(repo: Path) -> list[Package]:
    """所有 uv 套件（有 `pyproject.toml` 的 `tools/*`）。"""
    out: list[Package] = []
    for d in sorted((repo / TOOLS_DIR).iterdir()):
        pj = d / "pyproject.toml"
        if not pj.is_file():
            continue
        data = tomllib.loads(pj.read_text(encoding="utf-8"))
        out.append(
            Package(
                name=d.name,
                path=d,
                scripts=dict(data.get("project", {}).get("scripts", {})),
            )
        )
    return out


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


def workflow_files(repo: Path) -> list[Path]:
    d = repo / WORKFLOW_DIR
    return sorted(d.glob("*.yml")) + sorted(d.glob("*.yaml")) if d.is_dir() else []


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
