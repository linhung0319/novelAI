# 子專案 C（逐章實體狀態定位）v1 建置計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. fold 程式各任務走 superpowers:test-driven-development。

**Goal:** 建置子專案 C v1——狀態事件流 schema、純確定性 fold 投影程式（Python/uv、零 LLM）、context-cap 效果驗證，驗證通過且作者拍板後才把「產事件＋章首讀投影」接進 `write`。

**Architecture:** 四元件以檔案介面溝通（LLM 產、程式算、作者審分離）：`write` 寫 chNN 時把該章狀態變化 append 進單檔事件流 `story/參照/狀態事件流.md`（單一真實來源）；純程式 `fold` 讀事件流＋`story/幕綱/_index.md` spine，對「實體×維度 as-of 第 N 幕」做確定性摺疊；`write` 章首呼叫 fold 拿投影當進場知識邊界（閉合 read-loop）。章末快照由手維護降級為事件流的衍生投影。

**Tech Stack:** Python ≥3.11、uv（自足專案於 `tools/state_projection/`）、pytest；純標準庫（無 runtime 依賴）。

## Global Constraints

- **語言/環境**：Python + uv；程式放 `tools/state_projection/`（自足 `pyproject.toml` + `src/` 佈局 + `tests/`），import 路徑英文。
- **機械邊界**：程式只做 fold 投影（零 LLM、100% 可覆算、同輸入永遠同輸出）；**程式唯讀，永不寫任何書內檔或事件**。事件由 `write` 寫作當下產、作者可審可改。
- **schema 固定 4 欄**：`- 幕NNN（arcAA）· <實體 或 實體A↔實體B> · <變化維度>：<自由內容>`。
- **變化維度＝封閉 6 枚舉**：`知識前沿｜關係｜持有｜位置｜能力｜所屬`；不在枚舉內 → 程式報錯（不靜默丟）。
- **定序**：走 `story/幕綱/_index.md`「全書順序」spine；判先後不比幕號大小；位置＝幕號＋arc（不用章號）；無法定位的 arc/幕 → 報錯。
- **系統哲學（硬約束）**：不另立第二本帳（事件流是唯一新增軸，快照變衍生、伏筆/弧線/已承諾事實仍歸原處、引用只用名字不重抄）；不自動鏈式觸發；不建 runtime 登記簿（維度是 schema 固定枚舉）；作者掌決定權。
- **YAGNI（v1 明確不做）**：程式端一致性校驗、持久 cache 層、跨 arc/跨集狀態機——一律延到日後。
- **閘門**：`fold` 單元測試全綠 → context-cap 驗證顯示「控制臂失敗／處理臂成功」 → **且作者拍板** → 才接進 `write`（Task 6 為 gated，未獲雙重放行不得執行）。
- **fold 版控**：本 plan 另存一份到 `docs/superpowers/plans/2026-07-17-subproject-c-state-layer-build.md`（執行首步落檔；plan-mode 期間僅能寫本檔）。

---

## Context / 為什麼建

系統已有「章末狀態快照」但 **write-only**——沒有任何 skill 把它當進場狀態讀回；今天「第 XX 章當下狀態」靠 AI 即時重讀前文重建。兩輪 RED（忠正史／反正史）在 ≤12 章、全文可讀規模 **0 複現**正確性失敗，證明 C 不是正確性修補，而是**規模化下的效率／可靠性基建**：書大到「要用第 30 章狀態卻得回頭重讀前 29 章」時（context 塞不下、略讀漏早章）才咬人。RED 這個正確性閘門結構上摸不到該規模（冷跑要讀得完 fixture、失敗要 fixture 大到讀不完，互斥），故本 v1 改用「限制 context 大小」的模擬（Task 5）抵達失敗 regime。作者已拍板 C 必須做；本計畫依定案設計書 `docs/superpowers/specs/2026-07-17-subproject-c-state-layer-build-spec.md` 實作，不重新設計。

---

## 檔案結構

| 檔案 | 職責 |
|------|------|
| `結構定義/狀態事件流.schema.md`（新增） | 事件 schema 權威格式：4 欄信封、6 維度枚舉、定序規則、與其他軸分界、fold 契約 |
| `結構定義/章節.schema.md`（改） | 「章末狀態快照」區塊註明降級為事件流衍生 cache |
| `tools/state_projection/pyproject.toml`（新增） | uv 自足專案設定 |
| `tools/state_projection/src/state_projection/fold.py`（新增） | 純投影邏輯：`parse_events`／`parse_spine`／`project`（零 LLM、純函數） |
| `tools/state_projection/src/state_projection/cli.py`（新增） | 章首查詢入口：讀檔、`--as-of`、輸出 Markdown 投影 |
| `tools/state_projection/tests/test_fold.py`（新增） | 純單元測試（涵蓋 ≤N 邊界、跨 arc 定序、實體×維度分組、得而復失、關係雙向、錯誤處理） |
| `tools/state_projection/tests/test_cli.py`（新增） | CLI 讀檔＋格式化＋錯誤退出碼測試 |
| `情境測試/哈利波特實測/GP3-fixture-反正史/story/參照/狀態事件流.md`（新增，Task 5） | 反正史 fixture 手搭事件流（驗證用） |
| `情境測試/哈利波特實測/GP3-GREEN-狀態定位-contextcap.md`（新增，Task 5） | context-cap 驗證報告（兩臂對照結果） |
| `.claude/skills/write/SKILL.md`（改，Task 6 gated） | 加「產事件」＋「章首讀投影」兩步 |

**parse 契約（所有任務共用，spec 五節 fold 演算法）**：事件行＝markdown bullet 且本文以「幕」起頭。分隔符為 U+00B7 MIDDLE DOT（` · `），內容分隔為全形冒號 `：`，關係用 `↔`。內容可含 `·`（如 `尼樂·勒梅`），故：位置從**左端** regex 取（`幕\d+（arc…）` 後第一個 `·` 為位置/實體分隔），維度用 **`rpartition('·')`** 從右取（維度是無點的枚舉 token，故最後一個 `·` 必為實體/維度分隔）。位置 → 全書序位 `(arc 在 spine 的 rank, 幕號)`；`project` 對每個事件都呼叫定位（含被過濾的），arc 不在 spine → 報錯，不靜默丟。**as-of 語意**：投影含所有序位 ≤ 目標的事件；因 `write` 只在寫完章後才 append，事件流自然只含 <目標章 的事件，故傳 `--as-of 幕N` 即得進場狀態；驗證用完整事件流時查「章首」請傳前一幕。

---

### Task 1: 事件流 schema ＋ 章節 schema 快照降級註記

**Files:**
- Create: `結構定義/狀態事件流.schema.md`
- Modify: `結構定義/章節.schema.md`（第 83–98 行「章末狀態快照」區塊）
- Create: `docs/superpowers/plans/2026-07-17-subproject-c-state-layer-build.md`（把本 plan 落檔到 repo）

**Interfaces:**
- Produces: schema 契約字串——4 欄信封格式、6 維度枚舉集合 `{知識前沿,關係,持有,位置,能力,所屬}`、位置 token `幕NNN（arcAA）`、定序走 `story/幕綱/_index.md`「全書順序」。Task 2–4 的程式與測試以此為權威。

- [ ] **Step 1: 把本 plan 落檔到 repo**（plan-mode 結束後執行）

複製本計畫全文到 `docs/superpowers/plans/2026-07-17-subproject-c-state-layer-build.md`。

- [ ] **Step 2: 撰寫 `結構定義/狀態事件流.schema.md`**

內容須含下列小節（沿用系統 schema 檔既有語氣與 `> 這是什麼／方法依據` 檔頭慣例）：

1. **檔頭**：`# 結構定義：狀態事件流（story/參照/狀態事件流.md）`；一句話定位「狀態的單一真實來源，append-only，一行一事件；輕量章末快照降級為它之上可重算的投影 cache」。方法依據指向 `共同約定.md` 定序規則第 44 行、`章節.schema.md` 快照區塊、設計書 build-spec。
2. **用途／邊界**：每本書一檔；只被 `write` 追加、被 fold 程式讀；**不另立第二本帳**（伏筆埋/收仍歸幕綱、靜態弧線仍歸角色需求、已承諾事實仍歸 sync，事件流引用它們只用名字、不重抄）。
3. **固定 4 欄信封格式**（附範例，範例用中性泛例，不引任何實書內容以免污染盲測）：
   ````markdown
   - 幕NNN（arcAA）· <實體 或 實體A↔實體B> · <變化維度>：<自由內容>
   ````
4. **四欄逐欄定義**：
   - **位置** ＝ 幕號＋所屬 arc（**不用章號**——章號可亂序、非定序原語）。判 ≤N 走 `story/幕綱/_index.md`「全書順序」spine，同一 arc 內才以幕號序為準。
   - **實體** ＝ 角色/物件名；關係類用 `實體A↔實體B`（一個雙向 slot）。
   - **變化維度** ＝ **封閉枚舉（固定 6 軸，跨小說通用）**：`知識前沿｜關係｜持有｜位置｜能力｜所屬`。「知識前沿」最承重（服務 Deep POV 資訊控制與伏筆回收）。**維度不在枚舉內 → fold 報錯。**
   - **內容** ＝ 自由文字，承載小說特有細節；引用伏筆/實體用名字，**不重抄幕綱埋/收**。
5. **固定 vs 通用**：schema 固定在「4 欄＋6 維度枚舉」；通用靠「內容自由＋名字引用」。一份 schema 適用所有小說，無 per-novel schema。
6. **定序規則**：全書序位＝(arc 在「全書順序」的 rank, 幕號)；跨 arc 比 rank，同 arc 比幕號；as-of＝篩序位 ≤ 目標、按 (實體,維度) 分組取序最新。
7. **與其他軸的分界**：一表列出 事件流（逐章狀態變化 delta）vs 角色需求（靜態弧線）vs 幕綱伏筆表（埋/收機制）vs sync（已承諾事實）——四軸不重疊。
8. **fold 契約與錯誤處理**：格式壞行（本文以「幕」起頭卻缺 `·` 或 `：`）、未知維度、無法定位的 arc/幕 → 程式 lint 報錯，不靜默丟。**漏事件**（正文有變化但 write 沒 append）＝ LLM 產出端天生缺口，v1 靠作者審＋`write-test` 兜底；程式端一致性校驗延到日後。
9. **範例事件（中性泛例）**：至少示範 持有得而復失、關係 `A↔B` 翻轉、知識前沿三種。

- [ ] **Step 3: 修改 `結構定義/章節.schema.md` 快照區塊**

在第 83–98 行「## 章末狀態快照」區塊開頭插入降級註記（不刪除既有內容，改寫定位描述）：

```markdown
> **⚠️ 定位更新（子專案 C v1）**：本區塊自子專案 C 起**降級為衍生產物**——狀態的單一真實來源改為 `story/參照/狀態事件流.md`（見 `結構定義/狀態事件流.schema.md`），章末快照是「fold 程式從事件流算出的 as-of 投影」，**非權威、非手抄、可重算可丟棄**。原「由 write 手維護」的做法在 `write` 接上事件流後退場（見該 skill）。保留本區塊格式定義，供投影輸出與人眼閱讀對照。
```

並把第 88 行「未來可平滑併入 C」改為「已於子專案 C v1 併入（真實來源移至事件流，本快照為其投影）」。

- [ ] **Step 4: 一致性自檢（grep）**

Run: `cd "C:/Users/user/source/repos/novelAI" && grep -rn "狀態事件流" 結構定義/`
Expected: `狀態事件流.schema.md` 與 `章節.schema.md` 都出現；維度枚舉在 schema 中完整列出 6 個。

- [ ] **Step 5: Commit**

```bash
git add 結構定義/狀態事件流.schema.md 結構定義/章節.schema.md docs/superpowers/plans/2026-07-17-subproject-c-state-layer-build.md
git commit -m "架構：子專案 C v1 事件流 schema 落檔＋章節快照降級為衍生"
```

---

### Task 2: uv 專案骨架 ＋ 事件行解析（`parse_events`）

**Files:**
- Create: `tools/state_projection/pyproject.toml`
- Create: `tools/state_projection/src/state_projection/__init__.py`
- Create: `tools/state_projection/src/state_projection/fold.py`
- Test: `tools/state_projection/tests/test_fold.py`

**Interfaces:**
- Produces:
  - `DIMENSIONS: frozenset[str]` = `{"知識前沿","關係","持有","位置","能力","所屬"}`
  - `class FoldError(Exception)`
  - `@dataclass(frozen=True) class Event: beat:int; arc:str; entity:str; dimension:str; content:str; lineno:int`
  - `parse_events(text: str) -> list[Event]`（壞事件行/未知維度 → raise FoldError；非事件行如標題/空行/非「幕」bullet 跳過）

- [ ] **Step 1: 建 uv 專案骨架**

Run:
```bash
cd "C:/Users/user/source/repos/novelAI/tools/state_projection" || mkdir -p "C:/Users/user/source/repos/novelAI/tools/state_projection"
```
建立 `pyproject.toml`：
```toml
[project]
name = "state-projection"
version = "0.1.0"
description = "novelAI 子專案 C：狀態事件流 as-of 投影（fold，零 LLM、可覆算）"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
state-project = "state_projection.cli:main"

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/state_projection"]
```
建立空 `src/state_projection/__init__.py`（內容：`"""novelAI 子專案 C：狀態事件流 as-of 投影。"""`）。

- [ ] **Step 2: 寫失敗測試 `tests/test_fold.py`**

```python
import pytest
from state_projection.fold import parse_events, DIMENSIONS, FoldError, Event

STREAM = """\
# 狀態事件流（範例）
- 幕001（arcF）· 哈利↔榮恩 · 關係：初識 → 同行結伴
- 幕006（arcF）· 哈利 · 持有：獲得隱形斗篷（父親遺物）
- 幕008（arcF）· 尼樂·勒梅 · 知識前沿：身分對哈利揭曉＝魔法石唯一煉製者

（以上為範例）
"""

def test_dimensions_are_the_closed_six():
    assert DIMENSIONS == {"知識前沿", "關係", "持有", "位置", "能力", "所屬"}

def test_parse_skips_non_event_lines_and_reads_three_events():
    events = parse_events(STREAM)
    assert len(events) == 3

def test_parse_position_entity_dimension_content():
    e = parse_events(STREAM)[0]
    assert (e.beat, e.arc, e.entity, e.dimension) == (1, "arcF", "哈利↔榮恩", "關係")
    assert e.content == "初識 → 同行結伴"

def test_parse_entity_name_containing_middle_dot():
    e = parse_events(STREAM)[2]
    assert e.entity == "尼樂·勒梅"
    assert e.dimension == "知識前沿"

def test_unknown_dimension_raises():
    with pytest.raises(FoldError, match="未知變化維度"):
        parse_events("- 幕001（arcF）· 哈利 · 心情：開心")

def test_missing_content_colon_raises():
    with pytest.raises(FoldError, match="：|內容"):
        parse_events("- 幕001（arcF）· 哈利 · 持有 隱形斗篷")

def test_missing_dimension_separator_raises():
    with pytest.raises(FoldError, match="·|維度"):
        parse_events("- 幕001（arcF） 哈利 持有：斗篷")
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `cd "C:/Users/user/source/repos/novelAI/tools/state_projection" && uv run pytest tests/test_fold.py -q`
Expected: FAIL（`ImportError` / `ModuleNotFoundError: state_projection.fold`）。

- [ ] **Step 4: 實作 `src/state_projection/fold.py`（parse 部分）**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

DIMENSIONS = frozenset({"知識前沿", "關係", "持有", "位置", "能力", "所屬"})


class FoldError(Exception):
    """事件流/spine 解析或定位失敗（格式壞行、未知維度、無法定位）。"""


@dataclass(frozen=True)
class Event:
    beat: int
    arc: str
    entity: str
    dimension: str
    content: str
    lineno: int


# 位置從左端解析：幕NNN（arcAA）後第一個 · 為位置/實體分隔；實體之後（含名字內的 ·）全歸實體。
_POS_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）\s*·\s*(.+)$")


def parse_events(text: str) -> list[Event]:
    events: list[Event] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("-"):
            continue
        body = line[1:].strip()
        if not body.startswith("幕"):  # 非事件行（標題/說明/其他 bullet）→ 跳過
            continue
        if "：" not in body:
            raise FoldError(f"第 {i} 行事件缺少內容分隔『：』：{raw!r}")
        head, _, content = body.partition("：")
        left, sep, dim = head.rpartition("·")  # 維度是無點枚舉，最後一個 · 必為實體/維度分隔
        if not sep:
            raise FoldError(f"第 {i} 行事件缺少維度分隔『·』：{raw!r}")
        dimension = dim.strip()
        if dimension not in DIMENSIONS:
            raise FoldError(
                f"第 {i} 行未知變化維度 {dimension!r}（限 {sorted(DIMENSIONS)}）"
            )
        m = _POS_RE.match(left.strip())
        if not m:
            raise FoldError(f"第 {i} 行位置/實體格式不符：{raw!r}")
        events.append(
            Event(
                beat=int(m.group(1)),
                arc=m.group(2).strip(),
                entity=m.group(3).strip(),
                dimension=dimension,
                content=content.strip(),
                lineno=i,
            )
        )
    return events
```

- [ ] **Step 5: 跑測試確認通過**

Run: `cd "C:/Users/user/source/repos/novelAI/tools/state_projection" && uv run pytest tests/test_fold.py -q`
Expected: PASS（7 passed）。

- [ ] **Step 6: Commit**

```bash
git add tools/state_projection/pyproject.toml tools/state_projection/src tools/state_projection/tests/test_fold.py
git commit -m "測試+實作：fold 事件行解析（4 欄信封、6 維度枚舉、名字含·、錯誤處理）"
```

---

### Task 3: spine 解析 ＋ as-of 投影（`parse_spine`／`project`）

**Files:**
- Modify: `tools/state_projection/src/state_projection/fold.py`
- Test: `tools/state_projection/tests/test_fold.py`（追加）

**Interfaces:**
- Consumes: Task 2 的 `Event`、`FoldError`。
- Produces:
  - `parse_spine(text: str) -> dict[str, int]`（讀「全書順序：」行的 arc token 序 → `{arc: rank}`；找不到 → FoldError）
  - `@dataclass(frozen=True) class Slot: entity:str; dimension:str; content:str; source_beat:int; source_arc:str`
  - `project(events, spine, target_beat: int, target_arc: str) -> list[Slot]`（as-of ≤ 目標；每事件都定位、arc 不在 spine → FoldError；(實體,維度) 分組取序最新，同位置以檔序後者勝）

- [ ] **Step 1: 追加失敗測試到 `tests/test_fold.py`**

```python
from state_projection.fold import parse_spine, project, Slot

SPINE_MULTI = """\
# 幕綱索引
- 全書順序：arc01 → arc02 → arc03
- arc01：幕001–幕100
- arc02：幕101–幕108
"""

SPINE_SINGLE = "- 全書順序：arcF（幕001–幕012，本 fixture 唯一 arc）"

def _slot(slots, entity, dim):
    return next(s for s in slots if s.entity == entity and s.dimension == dim)

def test_parse_spine_multi_arc_ranks_in_order():
    assert parse_spine(SPINE_MULTI) == {"arc01": 0, "arc02": 1, "arc03": 2}

def test_parse_spine_single_arc():
    assert parse_spine(SPINE_SINGLE) == {"arcF": 0}

def test_parse_spine_no_line_raises():
    with pytest.raises(FoldError, match="全書順序"):
        parse_spine("# 沒有 spine 的檔")

def test_asof_boundary_includes_target_excludes_later():
    events = parse_events(
        "- 幕006（arcF）· 哈利 · 持有：得斗篷\n"
        "- 幕009（arcF）· 哈利 · 持有：斗篷遭沒收（此後無）\n"
    )
    spine = {"arcF": 0}
    at7 = _slot(project(events, spine, 7, "arcF"), "哈利", "持有")
    assert "得斗篷" in at7.content and at7.source_beat == 6
    at10 = _slot(project(events, spine, 10, "arcF"), "哈利", "持有")
    assert "沒收" in at10.content and at10.source_beat == 9

def test_lose_after_gain_latest_wins():  # 得而復失
    events = parse_events(
        "- 幕006（arcF）· 哈利 · 持有：得斗篷\n"
        "- 幕009（arcF）· 哈利 · 持有：斗篷遭沒收\n"
    )
    slots = project(events, {"arcF": 0}, 12, "arcF")
    assert _slot(slots, "哈利", "持有").content == "斗篷遭沒收"

def test_relationship_bidirectional_slot_evolves():  # 關係雙向
    events = parse_events(
        "- 幕001（arcF）· 哈利↔榮恩 · 關係：初識結伴\n"
        "- 幕009（arcF）· 哈利↔榮恩 · 關係：摯友 → 鬧翻冷戰\n"
        "- 幕011（arcF）· 哈利↔榮恩 · 關係：鬧翻冷戰 → 和好\n"
    )
    spine = {"arcF": 0}
    assert _slot(project(events, spine, 10, "arcF"), "哈利↔榮恩", "關係").content == "摯友 → 鬧翻冷戰"
    assert _slot(project(events, spine, 11, "arcF"), "哈利↔榮恩", "關係").content == "鬧翻冷戰 → 和好"

def test_entity_dimension_grouping_independent():
    events = parse_events(
        "- 幕002（arcF）· 哈利 · 知識前沿：認定史奈普是嚴師\n"
        "- 幕006（arcF）· 哈利 · 持有：得斗篷\n"
    )
    slots = project(events, {"arcF": 0}, 12, "arcF")
    assert {(s.entity, s.dimension) for s in slots} == {("哈利", "知識前沿"), ("哈利", "持有")}

def test_cross_arc_ordering_uses_spine_rank_not_beat_number():
    # 幕101（arc02）序位晚於 幕900（arc01），因 arc01 rank 較小 → 幕900 不因號大而較晚
    events = parse_events(
        "- 幕900（arc01）· 哈利 · 位置：城堡\n"
        "- 幕101（arc02）· 哈利 · 位置：斜角巷\n"
    )
    spine = {"arc01": 0, "arc02": 1}
    at_arc01 = _slot(project(events, spine, 950, "arc01"), "哈利", "位置")
    assert at_arc01.content == "城堡"  # arc02 的 幕101 序位在其後，被排除
    at_arc02 = _slot(project(events, spine, 108, "arc02"), "哈利", "位置")
    assert at_arc02.content == "斜角巷"

def test_event_arc_not_in_spine_raises():
    events = parse_events("- 幕001（arcX）· 哈利 · 持有：斗篷")
    with pytest.raises(FoldError, match="不在 spine|無法定位"):
        project(events, {"arcF": 0}, 12, "arcF")

def test_target_arc_not_in_spine_raises():
    events = parse_events("- 幕001（arcF）· 哈利 · 持有：斗篷")
    with pytest.raises(FoldError, match="不在 spine|無法定位"):
        project(events, {"arcF": 0}, 1, "arcZZ")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd "C:/Users/user/source/repos/novelAI/tools/state_projection" && uv run pytest tests/test_fold.py -q`
Expected: FAIL（`ImportError: cannot import name 'parse_spine'`）。

- [ ] **Step 3: 追加實作到 `fold.py`**

```python
_SPINE_RE = re.compile(r"全書順序：(.+)$")
_ARC_TOKEN_RE = re.compile(r"arc[0-9A-Za-z]+")


def parse_spine(text: str) -> dict[str, int]:
    for raw in text.splitlines():
        m = _SPINE_RE.search(raw)
        if not m:
            continue
        arcs: list[str] = []
        for tok in _ARC_TOKEN_RE.findall(m.group(1)):
            if tok not in arcs:
                arcs.append(tok)
        if arcs:
            return {arc: rank for rank, arc in enumerate(arcs)}
    raise FoldError("幕綱 _index 找不到可解析的『全書順序：』arc 序列")


@dataclass(frozen=True)
class Slot:
    entity: str
    dimension: str
    content: str
    source_beat: int
    source_arc: str


def _pos(spine: dict[str, int], arc: str, beat: int) -> tuple[int, int]:
    if arc not in spine:
        raise FoldError(f"arc {arc!r} 不在 spine（全書順序）中，無法定位")
    return (spine[arc], beat)


def project(
    events: list[Event], spine: dict[str, int], target_beat: int, target_arc: str
) -> list[Slot]:
    target = _pos(spine, target_arc, target_beat)
    # 對每個事件都定位（含被過濾的），arc 無法定位即報錯、不靜默丟。
    positioned = [(_pos(spine, e.arc, e.beat), e) for e in events]
    kept = sorted(
        ((p, e) for p, e in positioned if p <= target),
        key=lambda pe: (pe[0], pe[1].lineno),  # 同位置以檔序後者勝
    )
    slots: dict[tuple[str, str], Slot] = {}
    for _p, e in kept:
        slots[(e.entity, e.dimension)] = Slot(
            entity=e.entity,
            dimension=e.dimension,
            content=e.content,
            source_beat=e.beat,
            source_arc=e.arc,
        )
    return list(slots.values())
```

- [ ] **Step 4: 跑全部 fold 測試確認通過**

Run: `cd "C:/Users/user/source/repos/novelAI/tools/state_projection" && uv run pytest tests/test_fold.py -q`
Expected: PASS（全數通過，含 Task 2 的 7 項）。

- [ ] **Step 5: Commit**

```bash
git add tools/state_projection/src/state_projection/fold.py tools/state_projection/tests/test_fold.py
git commit -m "測試+實作：fold spine 解析＋as-of 投影（≤N 邊界/跨arc定序/分組/得而復失/關係雙向/定位報錯）"
```

---

### Task 4: CLI 章首查詢入口（`cli.py`）

**Files:**
- Create: `tools/state_projection/src/state_projection/cli.py`
- Test: `tools/state_projection/tests/test_cli.py`

**Interfaces:**
- Consumes: `parse_events`／`parse_spine`／`project`／`Slot`／`FoldError`。
- Produces:
  - `format_projection(slots: list[Slot], target_beat: int, target_arc: str, entities: list[str] | None = None) -> str`（Markdown，按實體分組，附「←來源 幕NNN」可追溯）
  - `main(argv: list[str] | None = None) -> int`（args：`--book PATH`、`--as-of 幕NNN（arcAA）`、`--entities …`；讀 `<book>/story/參照/狀態事件流.md` 與 `<book>/story/幕綱/_index.md`；FoldError/檔案缺失 → stderr＋return 1）

- [ ] **Step 1: 寫失敗測試 `tests/test_cli.py`**

```python
import pytest
from state_projection.cli import format_projection, main
from state_projection.fold import parse_events, project

def _slots(target):
    events = parse_events(
        "- 幕006（arcF）· 哈利 · 持有：得隱形斗篷\n"
        "- 幕009（arcF）· 哈利 · 持有：斗篷遭麥教授沒收（此後無）\n"
        "- 幕009（arcF）· 哈利↔榮恩 · 關係：摯友 → 鬧翻冷戰\n"
    )
    return project(events, {"arcF": 0}, target, "arcF")

def test_format_groups_by_entity_with_source():
    out = format_projection(_slots(10), 10, "arcF")
    assert "### 哈利" in out and "### 哈利↔榮恩" in out
    assert "沒收" in out and "←來源 幕009" in out

def test_format_entity_filter():
    out = format_projection(_slots(10), 10, "arcF", entities=["哈利↔榮恩"])
    assert "### 哈利↔榮恩" in out and "### 哈利\n" not in out

def _make_book(tmp_path):
    book = tmp_path / "book"
    (book / "story" / "參照").mkdir(parents=True)
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "參照" / "狀態事件流.md").write_text(
        "# 狀態事件流\n- 幕009（arcF）· 哈利 · 持有：斗篷遭沒收（此後無）\n",
        encoding="utf-8",
    )
    (book / "story" / "幕綱" / "_index.md").write_text(
        "- 全書順序：arcF（幕001–幕012）\n", encoding="utf-8"
    )
    return book

def test_main_reads_book_and_prints(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）"])
    out = capsys.readouterr().out
    assert rc == 0 and "沒收" in out and "as-of 幕011（arcF）" in out

def test_main_bad_asof_format_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path)
    rc = main(["--book", str(book), "--as-of", "ch11"])
    assert rc == 1
    assert "幕NNN" in capsys.readouterr().err

def test_main_unknown_dimension_returns_1(tmp_path, capsys):
    book = _make_book(tmp_path)
    (book / "story" / "參照" / "狀態事件流.md").write_text(
        "- 幕001（arcF）· 哈利 · 心情：開心\n", encoding="utf-8"
    )
    rc = main(["--book", str(book), "--as-of", "幕011（arcF）"])
    assert rc == 1 and "未知變化維度" in capsys.readouterr().err
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd "C:/Users/user/source/repos/novelAI/tools/state_projection" && uv run pytest tests/test_cli.py -q`
Expected: FAIL（`ModuleNotFoundError: state_projection.cli`）。

- [ ] **Step 3: 實作 `src/state_projection/cli.py`**

```python
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .fold import FoldError, Slot, parse_events, parse_spine, project

_ASOF_RE = re.compile(r"^幕(\d+)（(arc[^）]+)）$")


def format_projection(
    slots: list[Slot],
    target_beat: int,
    target_arc: str,
    entities: list[str] | None = None,
) -> str:
    if entities:
        wanted = set(entities)
        slots = [s for s in slots if s.entity in wanted]
    lines = [
        f"## as-of 幕{target_beat:03d}（{target_arc}）狀態投影"
        f"（衍生自事件流，零 LLM、可覆算）",
        "",
    ]
    by_entity: dict[str, list[Slot]] = {}
    for s in slots:
        by_entity.setdefault(s.entity, []).append(s)
    if not by_entity:
        lines.append("（此 as-of 無相關狀態事件）")
    for entity, es in by_entity.items():
        lines.append(f"### {entity}")
        for s in es:
            lines.append(
                f"- {s.dimension}：{s.content}　←來源 幕{s.source_beat:03d}（{s.source_arc}）"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="狀態事件流 as-of 投影（fold，零 LLM、可覆算）。"
        "投影含所有序位 ≤ 目標幕的事件；查『進場 幕N 章首』狀態時，"
        "因 write 只在寫完章後追加事件，事件流自然只含 <幕N；傳 --as-of 幕N 即得。"
    )
    ap.add_argument("--book", required=True, type=Path, help="書資料夾路徑（含 story/）")
    ap.add_argument("--as-of", required=True, dest="as_of", help="目標位置，如 幕011（arcF）")
    ap.add_argument(
        "--entities", nargs="*", default=None, help="只輸出這些實體（如 哈利 哈利↔榮恩）"
    )
    args = ap.parse_args(argv)

    m = _ASOF_RE.match(args.as_of.strip())
    if not m:
        print(f"--as-of 格式須為『幕NNN（arcAA）』，得到 {args.as_of!r}", file=sys.stderr)
        return 1
    target_beat, target_arc = int(m.group(1)), m.group(2)

    stream_path = args.book / "story" / "參照" / "狀態事件流.md"
    spine_path = args.book / "story" / "幕綱" / "_index.md"
    try:
        events = parse_events(stream_path.read_text(encoding="utf-8"))
        spine = parse_spine(spine_path.read_text(encoding="utf-8"))
        slots = project(events, spine, target_beat, target_arc)
    except FileNotFoundError as e:
        print(f"找不到檔案：{e}", file=sys.stderr)
        return 1
    except FoldError as e:
        print(f"投影錯誤：{e}", file=sys.stderr)
        return 1

    print(format_projection(slots, target_beat, target_arc, args.entities), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑測試確認通過，並全包冒煙**

Run: `cd "C:/Users/user/source/repos/novelAI/tools/state_projection" && uv run pytest -q`
Expected: PASS（test_fold.py ＋ test_cli.py 全數通過）。

- [ ] **Step 5: Commit**

```bash
git add tools/state_projection/src/state_projection/cli.py tools/state_projection/tests/test_cli.py
git commit -m "測試+實作：狀態投影 CLI（--book/--as-of/--entities，Markdown 投影＋錯誤退出碼）"
```

---

### Task 5: context-cap 效果驗證（GREEN／RED gate；不改系統套件）

**Files:**
- Create: `情境測試/哈利波特實測/GP3-fixture-反正史/story/參照/狀態事件流.md`（手搭事件流；fixture 已有 spine `story/幕綱/_index.md`）
- Create: `情境測試/哈利波特實測/GP3-GREEN-狀態定位-contextcap.md`（驗證報告）

**Interfaces:**
- Consumes: Task 4 的 CLI（`uv run state-project`）。
- Produces: 驗證判讀——控制臂失敗＋處理臂成功 → 放行 Task 6；控制臂在 cap 下照樣答對 → cap 沒咬到，調小 K/加大 fixture 再試（Task 6 不得執行）。

**設計對照（反正史 fixture ground truth，取自 `GP3-RED-狀態定位-反正史.md` 偏離設計表）**：Q1 斗篷 ch06 得、ch09 沒收、ch12 還；Q2 中段疑胡奇夫人（非史奈普）；Q3 妙麗火車即友、榮恩 ch09 鬧翻/ch11 和好。事件流只承載事件驅動的三軸（持有/關係/知識前沿）；Q4 靜態弧線走 `角色需求.md`、Q5 🧊 母愛護盾走幕綱收點，兩者非事件流 slot、兩臂都從靜態參照取得。

- [ ] **Step 1: 手搭反正史事件流**（依 arcF.md 偏離劇情，綁幕號＋arc、引名字不重抄埋/收）

寫 `GP3-fixture-反正史/story/參照/狀態事件流.md`：
```markdown
# 狀態事件流（arcF）

> 依 `結構定義/狀態事件流.schema.md`。單一真實來源；章末快照為其投影。

- 幕001（arcF）· 哈利↔榮恩 · 關係：火車同坐一見如故 → 同行結伴
- 幕001（arcF）· 哈利↔妙麗 · 關係：車廂即熱心相助 → 好友
- 幕001（arcF）· 哈利↔馬份 · 關係：示好被拒 → 交惡
- 幕001（arcF）· 哈利 · 所屬：分類進葛來分多（帽本欲分史萊哲林，哈利抗拒）
- 幕002（arcF）· 哈利 · 知識前沿：認定史奈普是難搞嚴師，並不當他是陰謀者/敵人
- 幕003（arcF）· 哈利 · 所屬：破格選為葛來分多最年輕找球手
- 幕005（arcF）· 哈利 · 知識前沿：認定胡奇夫人＝下咒害他/想偷三頭犬守護物的嫌疑人
- 幕006（arcF）· 哈利 · 持有：獲得隱形斗篷（父親遺物，匿名禮物）
- 幕008（arcF）· 哈利 · 知識前沿：得知守護物＝魔法石（勒梅唯一煉製者）；仍疑胡奇夫人
- 幕009（arcF）· 哈利 · 持有：隱形斗篷遭麥教授沒收充公（此後無斗篷，直到 幕012 歸還）
- 幕009（arcF）· 哈利↔榮恩 · 關係：摯友 → 鬧翻冷戰（送龍事件遷怒，兩人不說話）
- 幕010（arcF）· 哈利 · 知識前沿：疤劇痛、隱約感黑巫師仍在；仍認定胡奇夫人在取石
- 幕011（arcF）· 哈利↔榮恩 · 關係：鬧翻冷戰 → 和好（榮恩主動道歉）
- 幕011（arcF）· 哈利 · 知識前沿：深信盡頭的偷石賊＝胡奇夫人
- 幕012（arcF）· 哈利 · 知識前沿：真凶＝奇洛（非胡奇夫人；史奈普暗中護他）
- 幕012（arcF）· 哈利 · 持有：鄧不利多歸還隱形斗篷
```

- [ ] **Step 2: 用 fold 產出各 as-of 投影（處理臂餵料），核對偏離版**

Run（章首 = 傳前一幕，見 parse 契約 as-of 語意）：
```bash
cd "C:/Users/user/source/repos/novelAI/tools/state_projection"
uv run state-project --book "../../情境測試/哈利波特實測/GP3-fixture-反正史" --as-of "幕010（arcF）" --entities 哈利 哈利↔榮恩
uv run state-project --book "../../情境測試/哈利波特實測/GP3-fixture-反正史" --as-of "幕009（arcF）" --entities 哈利 哈利↔榮恩
```
Expected（`幕010` 投影＝寫 ch11 章首進場態）：持有＝斗篷遭沒收/無（來源幕009）；知識前沿＝認定胡奇夫人（來源幕010）；哈利↔榮恩＝鬧翻冷戰（來源幕009）。**無「有斗篷」「疑史奈普」「已和好」**——即偏離版正確、無正史殘留。若不符，先修事件流再續。

- [ ] **Step 3: 備妥 repo 外冷跑沙盒（沿用反正史 RED 剝法）**

把 `GP3-fixture-反正史/` 複製到 scratchpad（repo 外、非 git）：`C:\Users\user\AppData\Local\Temp\claude\...\scratchpad\魔法石草稿-contextcap\`。**人為抽掉決定狀態的早章正文**：刪 `chapters/ch05.md`（誤疑胡奇夫人）、`ch06.md`（得斗篷）、`ch09.md`（沒收＋榮恩鬧翻），只留最近 K 章（ch10、ch11 及其鄰近）＋靜態參照（世界觀/角色需求/摘要/幕綱）。白紙寫下 cap：K＝2、抽掉 ch01–ch09 正文。事件流與答案鍵**不進沙盒**（答案鍵留主控端）。

- [ ] **Step 4: 冷跑——控制臂（無 C）**

對「寫 ch11、POV 貼哈利，盤點章首此刻的知識前沿/關係/持有，哪些絕不能寫進敘述」用**全新 Agent 子代理**（general-purpose、Sonnet，比照兩輪 RED；中立框法、不透露這是測試/不給正史或偏離答案），指向沙盒、只給截斷後前文＋靜態參照。每查詢冷跑 N=5。
判讀：讀不到早章 → 猜錯／回退背正史（斗篷答「有」、嫌疑答「史奈普」、榮恩答「摯友」）＝**失敗複現**。逐筆記 偏/正/糊。

- [ ] **Step 5: 冷跑——處理臂（有 C）**

同框法、同沙盒，**額外**在 context 附上 Step 2 fold 算出的投影（幕010 as-of）。冷跑 N=5。
判讀：沒早章正文也照投影答對（無斗篷/疑胡奇夫人/冷戰）＝**C 兌現價值**。

- [ ] **Step 6: 判讀與落報告**

寫 `情境測試/哈利波特實測/GP3-GREEN-狀態定位-contextcap.md`：cap 值、兩臂逐跑 tally、複現率。
- **控制臂失敗 ＋ 處理臂成功** → C 被驗證，Task 6 放行（仍待作者拍板）。
- **控制臂在 cap 下照樣答對** → cap 沒咬到；調小 K 或加大 fixture 再跑 Step 3–5，**不得執行 Task 6**。
系統套件三資料夾（`.claude/skills`／`結構定義`／`技巧知識庫`）本任務零改動（`git status` 覆核，只 `情境測試/` 有新增）。

- [ ] **Step 7: Commit**

```bash
git add "情境測試/哈利波特實測/GP3-fixture-反正史/story/參照/狀態事件流.md" "情境測試/哈利波特實測/GP3-GREEN-狀態定位-contextcap.md"
git commit -m "驗證：子專案 C context-cap 模擬（反正史 fixture 手搭事件流＋兩臂對照報告）"
```

---

### Task 6: 接進 write skill（GATED — 需 Task 5 通過 ＋ 作者拍板才執行）

**⚠️ 執行前置（雙重放行）**：(a) Task 5 報告顯示控制臂失敗／處理臂成功；(b) 作者明確拍板同意接進 write。兩者缺一不得動 `.claude/skills/write/SKILL.md`。

**Files:**
- Modify: `.claude/skills/write/SKILL.md`（依據段補一行工具引用；流程第 8 步；新增章首讀投影步驟）

**Interfaces:**
- Consumes: `tools/state_projection` CLI（`uv run state-project --book <書> --as-of 幕NNN（arcAA） --entities …`）。

- [ ] **Step 1: 加「章首讀投影」步驟（消費端，閉合 read-loop）**

在流程「1. 讀輸入」之後插入新步驟（其餘步驟順延重編號）：
```markdown
1.5. **章首讀狀態投影（閉合 read-loop）**：動筆某章前，對該章對應幕號呼叫狀態投影程式取得進場知識邊界——
   `uv run --project <套件根>/tools/state_projection state-project --book <書資料夾> --as-of 幕NNN（arcAA） --entities <POV主角＋關鍵配角>`
   （幕號＝該章對應幕；因事件流只含已寫章，傳該幕即得進場態）。把投影當「本章相關實體 as-of 狀態」的進場知識邊界，與 POV 知識邊界規則（步驟6）一起用。投影是衍生、可覆算；**程式唯讀，不改任何檔**。事件流／spine 尚未建立時此步跳過、退回即時重建。
```

- [ ] **Step 2: 改「產事件」步驟（產出端）**

把流程第 8 步「更新章末狀態快照」改寫為「append 狀態事件」：
```markdown
   - **append 本章狀態變化事件**（見 `結構定義/狀態事件流.schema.md`）：把本章發生的狀態變化，依 4 欄信封（`- 幕NNN（arcAA）· 實體 · 維度：內容`、維度限 6 枚舉）append 進 `story/參照/狀態事件流.md`；只記已寫章、位置＝該章對應幕號、引用伏筆/實體用名字不重抄幕綱埋/收。**章末快照改由投影程式衍生（非手抄）**；跨 arc/跨集一致性校驗不在此做（延後）。作者當場審改事件。
```

- [ ] **Step 3: 依據段補工具引用；邊界段更新**

在「## 依據」列表補一行：
```markdown
- `結構定義/狀態事件流.schema.md` ＋ `tools/state_projection`（fold 投影程式）——章首讀 as-of 投影、章末 append 狀態事件的格式與工具。
```
「## 邊界」把「不建規模化連貫性基建……子專案 C 範圍」更新為「規模化連貫性由子專案 C 事件流＋fold 投影承載（章首讀投影、章末產事件）；程式端一致性校驗/cache/跨集狀態機仍延後」。

- [ ] **Step 4: 端到端驗證（沿用反正史 fixture）**

Run：對 fixture 走一次 write 章首讀投影（`uv run state-project` 對 `幕010（arcF）`），確認 skill 描述的指令實際可跑、輸出偏離版投影。確認 `write` 產事件步驟寫出的事件行能被 `parse_events` 讀回（append 一行後重跑 CLI 不報錯）。

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/write/SKILL.md
git commit -m "整合：write 接上子專案 C（章首讀 as-of 投影＋章末 append 狀態事件；快照降級為衍生）"
```

---

## 驗證（end-to-end）

1. **fold 單元測試全綠**：`cd tools/state_projection && uv run pytest -q` → 全數通過（涵蓋 ≤N 邊界、跨 arc 定序、實體×維度分組、得而復失、關係雙向、未知維度/無法定位報錯、名字含 `·`、CLI 讀檔與退出碼）。
2. **CLI 冒煙**：`uv run state-project --book <反正史fixture> --as-of "幕010（arcF）" --entities 哈利 哈利↔榮恩` → 輸出偏離版投影（無斗篷/疑胡奇夫人/冷戰），零報錯。
3. **context-cap 驗證**（Task 5）：報告顯示控制臂失敗／處理臂成功（否則調 cap 重跑，Task 6 不放行）。
4. **系統哲學不破壞**：`git status` 覆核——除新增 schema／`tools/`／`情境測試/` 與（gated）write 整合外，系統套件三資料夾無破壞性改動；程式唯讀（未寫任何書內檔）。
5. **write 整合**（Task 6，gated）：skill 內指令實跑通、產出事件能被 `parse_events` 讀回。

## 自檢對照（spec 覆蓋）

- build-spec 四鎖定決策：機械邊界（fold 零 LLM，Task 2–4）／固定 4 欄＋6 枚舉（Task 1–2）／schema 通用（Task 1）／限制 context 驗證（Task 5）——全覆蓋。
- v1 四樣：① schema（Task 1）② fold＋單元測試（Task 2–4）③ write 整合（Task 6, gated）④ context-cap 驗證（Task 5）。
- YAGNI 延後項（一致性校驗/cache/跨集狀態機）未進任何 task ✓。
- 型別一致：`Event`/`Slot`/`FoldError`/`parse_events`/`parse_spine`/`project`/`format_projection`/`main` 跨 Task 2–4 命名一致。
