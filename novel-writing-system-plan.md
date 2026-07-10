# AI 輔助小說創作系統 — 計畫書

## 一、系統概述

本系統以 Claude Code 為核心，建立一個「人機協作」的長篇小說創作環境。作者保有所有創作決策權，AI 作為顧問、編輯、一致性檢查員等角色提供輔助。

### 適用場景

- 網文長篇連載，單章約 3000 字，全書約 200 萬字（700+ 章）
- 作者本人進行主要寫作，AI 輔助劇情規劃、風格潤飾、一致性檢查、靈感整理等
- 使用 git 做版本控制，偶爾使用分支實驗不同劇情走向

### 設計原則

- 所有創作決策由作者做出，AI 提供建議和執行指示
- 資訊分層：從宏觀（摘要）到微觀（原文），AI 應逐層深入，避免一次讀取過多原文
- 檔案保護：區分「常改檔案」和「少改檔案」，防止 AI 誤改重要設定
- 工作流提醒：防止作者忘記更新 state 和 digest 等輔助紀錄

---

## 二、目錄結構

```
my-novel/
├── CLAUDE.md                          # Claude Code 總指令（詳見第三節）
├── .claude/
│   ├── skills/                        # 專案級 skill（詳見第五節）
│   │   ├── consistency-checker/
│   │   │   └── SKILL.md
│   │   ├── state-updater/
│   │   │   └── SKILL.md
│   │   ├── digest-writer/
│   │   │   └── SKILL.md
│   │   ├── plot-advisor/
│   │   │   └── SKILL.md
│   │   ├── character-voice-reviewer/
│   │   │   └── SKILL.md
│   │   ├── outline-organizer/
│   │   │   └── SKILL.md
│   │   ├── inspiration-search/
│   │   │   └── SKILL.md
│   │   └── wrap-up/
│   │       └── SKILL.md
│   └── agents/                        # 需要獨立 session 的 agent（詳見第六節）
│       ├── consistency-checker.md
│       ├── state-updater.md
│       └── digest-writer.md
├── bible/                             # 小說設定（少改，受保護）
│   ├── outline.md                     # 大綱
│   ├── world-rules.md                 # 世界觀設定
│   ├── style.md                       # 文風規則
│   └── characters/                    # 角色設定
│       ├── _template.md               # 角色模板
│       └── (每個角色一個 .md)
├── state/                             # 狀態快照（少改，受保護）
│   ├── current -> arc-XX-chXXX        # symlink 指向最新快照
│   └── arc-NN-chNNN/                  # 以劇情弧線 + 章節命名
│       └── state.md                   # 單一檔案，包含所有狀態
├── story/                             # 實際小說內容
│   ├── synopsis.md                    # 故事簡介 / pitch
│   ├── plan.md                        # 章節計畫（比 outline 更細的執行層面）
│   └── chapters/                      # 章節檔案（常改，可自由修改）
│       ├── vol01/
│       │   ├── ch001.md
│       │   └── ch002.md
│       ├── vol02/
│       └── ...
├── digest/                            # 摘要系統（少改，受保護）
│   ├── _index.md                      # 摘要索引（關鍵檔案，詳見第四節）
│   ├── arcs/                          # 段落級摘要（10-30 章為一段）
│   │   └── arc-NN-chXXX-chYYY.md
│   └── volumes/                       # 卷級摘要
│       └── volNN-chXXX-chYYY.md
├── inspiration/                       # 靈感素材
│   ├── _index.md                      # 靈感索引
│   └── (按主題分類的子資料夾)/
│       ├── 某個靈感.md
│       └── assets/                    # 圖片等媒體檔案
├── writing-techniques/                # 作者準備的寫作技巧資料（原始素材）
│   └── (各種寫作技巧文件)
├── scripts/                           # 輔助腳本
│   └── (需要時再加)
└── .gitignore
```

### 各目錄說明

| 目錄 | 用途 | 修改頻率 | 保護等級 |
|------|------|---------|---------|
| `story/chapters/` | 實際的小說章節 | 極高（每次寫作都會動） | 無限制，AI 可自由讀寫 |
| `bible/` | 大綱、角色設定、世界觀、文風規則 | 低（只有作者決定修改時才動） | 受保護，AI 需要作者明確同意才能修改 |
| `state/` | 角色和世界的狀態快照 | 低（每完成一段弧線更新一次） | 受保護，僅由 state-updater 操作 |
| `digest/` | 敘事摘要、劇情節奏、角色發展紀錄 | 低（每完成一段弧線更新一次） | 受保護，僅由 digest-writer 操作 |
| `inspiration/` | 靈感素材（文字、圖片連結、影片連結） | 中（收集靈感時更新） | 低保護 |
| `writing-techniques/` | 作者準備的寫作技巧原始資料 | 極低（初始放入後很少改動） | 唯讀參考 |

### 關於 symlink

`state/current` 是一個符號連結（symbolic link），指向最新的狀態快照資料夾。

```bash
# 建立 symlink（第一次）
cd state && ln -s arc-01-ch012 current

# 更新 symlink（完成新的 state 後）
cd state && rm current && ln -s arc-04-ch053 current
```

所有 skill 和 agent 都只需要讀 `state/current/state.md`，不需要知道目前寫到第幾章。state-updater 負責在更新 state 時移動 symlink。

如果不想用 symlink，替代方案是在 `CLAUDE.md` 中維護一行「最新 state: state/arc-04-ch053/」，每次更新後修改這一行。

---

## 三、CLAUDE.md 內容規劃

`CLAUDE.md` 是 Claude Code 每次啟動都會自動讀取的檔案，定義 AI 的角色、規則和行為。以下是需要包含的各個區塊：

### 3.1 角色定義

告訴 AI 它是一位小說創作顧問與編輯，不是自動寫作機器。所有創作決策由作者做出，AI 提供建議和執行作者的指示。輸出語言為繁體中文。

### 3.2 專案結構說明

描述每個資料夾的用途，讓 AI 知道去哪裡找什麼資料。直接列出目錄結構並加上簡短說明。

### 3.3 檔案保護規則

明確分為兩類：

**可自由修改的檔案：**
- `story/chapters/` 下的章節檔案

**需要作者明確同意才能修改的檔案：**
- `bible/` 下的所有檔案
- `state/` 下的所有已存檔快照
- `digest/` 下的所有檔案

具體規則：
- 修改章節內容時，只動 `story/chapters/` 裡的檔案
- 不要因為改了章節就自動更新 state 或 digest
- 不要因為劇情討論就自動修改大綱
- 如果發現受保護檔案可能需要更新，告知作者並等待確認

### 3.4 資訊檢索策略

定義從宏觀到微觀的逐層深入策略：

1. `digest/_index.md` → 找到相關的摘要檔案
2. `digest/arcs/` 對應檔案 → 了解敘事弧線和上下文
3. `state/` 對應快照 → 了解角色和世界狀態
4. `story/chapters/` 對應章節 → 最後才讀原文

大多數問題在第 1-3 層就能回答，不要一開始就讀原文。

### 3.5 工作流提醒規則

- 修改章節後，提醒作者 state 和 digest 的最後更新位置，詢問是否需要更新
- 單次 session 涉及 3 章以上的新內容或修改時，主動提醒

### 3.6 Git 分支策略

- `main`：主線劇情，已確定的內容
- `alt/*`：替代劇情分支（如 `alt/villain-redemption`）
- 章節內容的 commit 使用 `[chapter]` 前綴
- 設定修改的 commit 使用 `[meta]` 前綴
- state/digest 更新的 commit 使用 `[state]` 或 `[digest]` 前綴
- 跟分支無關的全域修正在 `main` 上做，再 merge 到各分支

---

## 四、摘要系統（Digest）設計

摘要系統是整個架構中最重要的輔助紀錄。它讓 AI 能在不讀原文的情況下理解故事的宏觀結構。

### 4.1 摘要的定位

摘要回答的問題是「這段故事在講什麼」，包含 state 和事件紀錄沒有的資訊：敘事弧線、主題、張力走向、角色內在變化、劇情在整部小說中的定位。

摘要同時承擔了「事件紀錄」的角色（即 Claude Book 中 timeline 的功能），在摘要末尾附上逐章事件列表。

### 4.2 摘要的粒度

- **段落級摘要（arc digest）：** 涵蓋一個故事弧線，通常 10-30 章。用於劇情節奏分析、段落比較、宏觀故事走向分析。
- **卷級摘要（volume digest）：** 更粗的粒度，每卷一個。用於超宏觀結構思考。

### 4.3 段落級摘要的內容格式

每份 arc digest 應包含以下 section：

```markdown
---
arc: (編號)
title: (段落標題)
chapters: (起始章-結束章)
characters_focus: [主要角色列表]
themes: [主題標籤列表]
tension_curve: (整體張力走向：上升/下降/起伏/平穩)
previous_arc: (前一個 arc 的檔名)
next_arc: (下一個 arc 的檔名，如有)
---

# (段落標題)（第X-Y章）

## 敘事概要
（2-3 段文字，概述這段劇情的核心故事）

## 劇情節奏
（按章節區間描述節奏變化，例如：第32-34章鋪墊，第35-37章加速...）

## 角色發展
（每個主要角色在這段劇情中的變化和成長）

## 埋下的伏筆
（列出這段劇情中埋下或解開的伏筆）

## 與其他段落的關係
（承接什麼、引出什麼）

## 情緒基調
（一句話描述這段劇情的整體情緒）

## 逐章事件
（每章 3-5 條事件，簡短條列）
```

### 4.4 索引檔案（_index.md）

`digest/_index.md` 是 AI 搜尋摘要的入口。包含：

- 段落級摘要的完整列表（檔名、章節範圍、標題、主要角色、主題、情緒走向）
- 卷級摘要的列表
- 快速查找索引：按角色、按主題、按伏筆

AI 在需要理解劇情時，第一步永遠是讀 `_index.md`，從索引中找到需要的 digest 檔案，再進一步讀取。

### 4.5 摘要的產生與更新

- 由 `digest-writer` agent 產生（獨立 session，因為需要讀多章原文）
- 通常在完成一段故事弧線後產生
- 產生時同時更新 `_index.md`
- 如果回頭大改了某些章節，需要重新產生對應的 digest

### 4.6 大綱與摘要的關係

- 大綱（`bible/outline.md`）是前瞻的：計畫要寫什麼
- 摘要（`digest/`）是回顧的：實際寫了什麼
- 兩者獨立存在，AI 可以比對兩者的差異來分析實際寫作偏離計畫的程度

---

## 五、Skills 設計

Skill 是一份指令文件（SKILL.md），定義 AI 執行特定任務的步驟和規則。被觸發時，其內容注入到當前 session 的 context 中。

### 5.1 各 Skill 概述

| Skill | 用途 | 觸發方式 | 是否需要獨立 agent |
|-------|------|---------|-------------------|
| `consistency-checker` | 檢查章節間的一致性（角色狀態、時間線、能力使用、物品位置等矛盾） | 手動：`/consistency-checker [章節範圍]` | 是（需讀大量檔案） |
| `state-updater` | 讀取章節內容，產生或更新狀態快照 | 手動：`/state-updater [章節範圍]` | 是（可能讀多章） |
| `digest-writer` | 讀取章節內容，產生段落級或卷級摘要，更新索引 | 手動：`/digest-writer [章節範圍]` | 是（需讀多章全文） |
| `plot-advisor` | 根據大綱、角色設定、當前 state 提供劇情建議和推演 | 自動觸發或手動 | 否（互動性質，在主 session）|
| `character-voice-reviewer` | 檢查對話是否符合角色性格和語言風格 | 手動：`/character-voice-reviewer [章節]` | 否（通常只讀1-2章）|
| `outline-organizer` | 把零散想法整理成結構化大綱 | 手動 | 否 |
| `inspiration-search` | 搜尋和引用靈感資料夾中的素材 | 自動觸發或手動 | 否 |
| `wrap-up` | 工作收尾檢查，報告 state 和 digest 是否需要更新 | 手動：`/wrap-up` | 否 |

### 5.2 Skill 的 SKILL.md 結構

每個 skill 的 SKILL.md 包含兩部分：

```markdown
---
name: (skill 名稱，也是 /slash 命令的名稱)
description: >
  (描述這個 skill 的用途，Claude Code 根據此描述判斷是否自動載入)
---

# (Skill 標題)

## 輸入
（描述使用者會提供什麼參數）

## 步驟
（詳細的執行步驟）

## 輸出格式
（定義輸出的格式和結構）

## 注意事項
（特殊規則和限制）
```

### 5.3 各 Skill 的具體內容要點

#### consistency-checker

- 輸入：章節範圍（如「第45到60章」）
- 步驟：讀 digest/_index.md 找到涵蓋範圍的摘要 → 讀對應摘要了解上下文 → 讀對應 state 快照 → 讀 bible/characters/ 角色設定 → 針對性讀取需要檢查的章節原文 → 比對找出矛盾
- 檢查項目：角色使用未學會的能力、提到未得知的情報、時間線衝突、物品位置錯誤、角色關係狀態與設定不符
- 輸出：結構化的矛盾報告，每個問題標明章節、類型、嚴重程度、建議修正方式

#### state-updater

- 輸入：章節範圍
- 步驟：讀 state/current/ 了解當前狀態 → 讀指定章節的原文 → 提取狀態變化 → 產生新的 state 快照 → 更新 symlink
- state.md 包含：各角色的境界/能力/已知情報/持有物品/當前位置/目標/人際關係、勢力狀態、世界狀態、未解伏筆清單
- 注意：只記錄有變化的內容，沒變的從前一個 state 繼承

#### digest-writer

- 輸入：章節範圍和段落標題
- 步驟：讀取章節全文 → 分析敘事結構和節奏 → 整理角色發展 → 標記伏筆 → 按模板輸出 → 更新 _index.md
- 如果章節數超過 context window 容量，分批讀取，先產出筆記再合成摘要

#### plot-advisor

- 不需要特定輸入格式，作者直接用自然語言描述需求
- 讀取 bible/outline.md、相關角色設定、state/current/、相關 digest
- 提供劇情建議時，考慮已埋的伏筆、角色性格一致性、敘事節奏

#### character-voice-reviewer

- 輸入：章節編號
- 讀取角色設定（bible/characters/）和章節原文
- 逐一檢查每段對話是否符合該角色的語言風格、口頭禪、說話邏輯
- 輸出：不符合的對話列表，附上原因和修改建議

#### outline-organizer

- 輸入：作者提供的零散想法（直接貼在對話中）
- 讀取現有大綱（bible/outline.md）
- 將新想法整合進大綱結構，產出修改建議
- 等作者確認後才實際修改大綱檔案

#### inspiration-search

- 輸入：關鍵字或主題描述
- 搜尋 inspiration/_index.md 和各靈感檔案
- 返回相關的靈感素材供作者參考

#### wrap-up

- 無需輸入
- 檢查 state/current/ 的最後更新位置
- 掃描 story/chapters/ 找出比 state 更新的章節
- 檢查 digest/_index.md 找出未被摘要涵蓋的章節
- 產出收尾報告，建議需要更新的項目
- 等作者決定要執行哪些操作

---

## 六、Agents 設計

Agent 是獨立的 Claude session，有自己的 context window，不繼承主 session 的對話歷史。僅在以下情況需要 agent：需讀取大量檔案、需限制工具權限、想用較便宜的模型。

### 6.1 Skill 與 Agent 的關係

- Skill 定義「做什麼」（指令和流程）
- Agent 定義「怎麼執行」（模型、工具權限、預載的 skill）
- Agent 引用 skill，skill 是「知識」，agent 是「帶著知識的獨立工人」
- 大多數 skill 在主 session 直接執行即可，不需要 agent

### 6.2 Agent 定義檔格式

放在 `.claude/agents/` 下，每個 agent 一個 .md 檔案：

```markdown
---
name: (agent 名稱)
description: (描述用途)
model: sonnet 或 opus
tools: (允許使用的工具列表)
skills:
  - (預載的 skill 名稱)
maxTurns: (最大迭代次數)
---

（給這個 agent 的額外指令，描述它的角色和行為規範）
```

### 6.3 各 Agent 配置

#### consistency-checker agent

- model: sonnet（一致性檢查不需要最頂級推理，sonnet 足夠且更便宜）
- tools: Read, Glob, Grep（只有讀取權限，不可修改任何檔案）
- skills: consistency-checker
- maxTurns: 30
- 額外指令：找出問題後回報給主 session，由作者決定如何處理

#### state-updater agent

- model: sonnet
- tools: Read, Glob, Grep, Write（需要寫入權限來產生 state 檔案）
- skills: state-updater
- maxTurns: 20
- 額外指令：產生 state 後需要更新 symlink（透過 Bash 工具執行 ln -s）
- 注意：需要額外給予 Bash 工具權限來操作 symlink

#### digest-writer agent

- model: opus（摘要寫作需要較強的理解和歸納能力）
- tools: Read, Glob, Grep, Write
- skills: digest-writer
- maxTurns: 30
- 額外指令：如果章節數量超過 context window 容量，自動分批處理

---

## 七、State 設計

### 7.1 設計原則

- 不需要每章都建 state，在「有意義的狀態變化」發生時才建立
- 估計每 10-20 章更新一次，700 章大約產生 40-70 個 state 快照
- 每個快照是一個資料夾，內含單一的 `state.md`
- 命名格式：`arc-NN-chNNN`（弧線編號 + 截止章節）

### 7.2 state.md 內容格式

```markdown
# 狀態快照 — 第X章結束時

## 建立資訊
- 前一個快照：(前一個 state 的資料夾名)
- 涵蓋章節：第X到Y章
- 建立日期：YYYY-MM-DD

## 主要角色狀態

### (角色名)
- 境界/等級：
- 已知情報：（知道什麼）
- 未知情報：（不知道什麼重要的事）
- 能力：（會什麼技能/法術）
- 持有物品：
- 當前位置：
- 當前目標：
- 人際關係變化：
- 近期重大事件：

（每個重要角色一個 section）

## 勢力狀態
（各勢力的當前狀態和關係）

## 世界狀態
（季節、重要事件倒數、世界級變化等）

## 未解伏筆
（列出所有已埋下但尚未解開的伏筆，標明埋設章節）
```

---

## 八、Bible 設計

### 8.1 設計原則

- 所有設定統一放在 `bible/` 下，不區分 immutable/evolving
- 統一歸類為「少改」，受 CLAUDE.md 的保護規則約束
- AI 需要作者明確同意才能修改任何 bible 檔案

### 8.2 各檔案用途

#### outline.md（大綱）

按卷/篇章結構組織的故事計畫。包含每一段的預期劇情走向、重要事件、轉折點。這是「前瞻的」——描述計畫要寫什麼。

#### world-rules.md（世界觀設定）

修仙體系/力量系統、地理設定、歷史背景、各種規則和限制。

#### style.md（文風規則）

寫作風格偏好、敘事視角、禁止使用的元素、對話風格偏好等。

#### characters/（角色設定）

每個角色一個 .md 檔案。提供 `_template.md` 作為新角色的模板。

角色模板應包含：基本資訊、性格特質、語言風格（口頭禪、說話習慣、用詞傾向）、背景故事、動機與目標、角色弧光（預期的成長/變化方向）。

---

## 九、靈感管理

### 9.1 儲存格式

使用 Markdown 檔案 + 本地資料夾，結構類似 Obsidian vault：

```
inspiration/
├── _index.md              # 靈感索引，帶標籤和分類
├── combat-scenes/         # 按主題分類
│   ├── 某個靈感.md
│   └── assets/
│       └── 參考圖片.jpg
├── world-building/
├── character-design/
└── plot-ideas/
```

### 9.2 靈感檔案格式

```markdown
---
tags: [標籤1, 標籤2]
source: "(來源 URL 或出處)"
date: YYYY-MM-DD
---

# 靈感標題

## 核心靈感
（描述靈感的核心內容）

## 圖片/影片參考
（圖片用相對路徑引用，影片用 URL 連結）

## 可以怎麼用
（這個靈感可以用在小說的什麼地方）
```

### 9.3 與 AI 的整合

- `inspiration-search` skill 負責搜尋靈感
- AI 在提供劇情建議時可以引用靈感素材
- 靈感索引（_index.md）提供標籤和分類供快速查找

---

## 十、寫作技巧資料整合

### 10.1 原始資料放置

作者準備的寫作技巧資料（如世界觀建構方法、懸念結尾法等）統一放在 `writing-techniques/` 資料夾中。

### 10.2 整理為 skills 的計畫

後續需要讓 Claude Code 將這些資料整理為 skills 或 agents。可能的做法：

- 通用型寫作技巧（如「7種懸念結尾法」）→ 整理為個人級 skill，放在 `~/.claude/skills/`，所有專案可用
- 專案特定技巧（如特定世界觀的設定方法論）→ 整理為專案級 skill，放在 `.claude/skills/`
- 每個 skill 的 SKILL.md 應包含：技巧的描述、使用場景、具體步驟、範例

### 10.3 執行步驟

1. 將所有寫作技巧資料放入 `writing-techniques/`
2. 在 Claude Code 中指示：「讀取 writing-techniques/ 下的所有資料，根據內容分類，幫我整理成 skills」
3. 審查 Claude Code 產出的 skill 草稿
4. 將確認的 skill 移到 `.claude/skills/` 或 `~/.claude/skills/`

---

## 十一、Git 使用策略

### 11.1 Commit 規範

| 前綴 | 用途 | 範例 |
|------|------|------|
| `[chapter]` | 章節內容的新增或修改 | `[chapter] 第51章：林小凡進入北域冰原` |
| `[meta]` | bible 下的設定修改 | `[meta] 調整第三卷大綱` |
| `[state]` | state 快照的建立或更新 | `[state] 更新至 arc-04-ch053` |
| `[digest]` | 摘要的建立或更新 | `[digest] 新增 arc-04 摘要` |
| `[inspiration]` | 靈感素材的新增 | `[inspiration] 新增戰鬥場面參考` |
| `[system]` | 系統檔案修改（CLAUDE.md、skills、agents） | `[system] 更新 consistency-checker skill` |

### 11.2 分支策略

- **`main`：** 主線劇情，已確定的內容。日常 90% 的工作都在 main 上
- **`alt/*`：** 替代劇情分支，用於實驗不同劇情走向。例如 `alt/villain-redemption`
- 跟分支無關的全域修正在 `main` 上做，再 merge 到各分支
- 決定採用某條路線後，merge 回 `main`

### 11.3 Git Hook（可選）

在 `.git/hooks/post-commit` 放一個腳本，當 commit 包含章節修改時，在 terminal 印出 state 和 digest 的最後更新位置，提醒作者考慮是否需要更新。

---

## 十二、工作流提醒機制

三層防護，防止忘記更新 state 和 digest：

### 12.1 CLAUDE.md 規則

在 CLAUDE.md 中定義：修改章節後提醒 state/digest 的最後更新位置；單次 session 涉及 3 章以上時主動提醒。

### 12.2 /wrap-up skill

每次工作 session 結束前手動跑 `/wrap-up`。它會：
1. 讀取 state/current/ 確認最後更新位置
2. 掃描 story/chapters/ 找出比 state 更新的章節
3. 讀取 digest/_index.md 確認摘要覆蓋範圍
4. 產出報告，列出需要更新的項目
5. 等作者決定要執行哪些操作

### 12.3 Git Hook

post-commit hook 在章節 commit 後印出提醒（不阻止 commit）。

---

## 十三、實施步驟

### 階段一：基礎建設

1. 建立目錄結構
2. 產生 `CLAUDE.md`
3. 產生 `bible/` 下的模板檔案（`_template.md` 等）
4. 產生 `state/template/` 的 state 模板
5. 產生 `digest/` 的摘要模板和空的 `_index.md`
6. 設定 `.gitignore`
7. 初始化 git repo

### 階段二：Skills 與 Agents

8. 產生所有 skill 的 SKILL.md
9. 產生所有 agent 的定義檔
10. 將 `writing-techniques/` 資料整理為 skills

### 階段三：填入小說內容

11. 填入 bible 的實際內容（大綱、角色、世界觀）
12. 寫 synopsis.md 和 plan.md
13. 建立初始 state（`state/arc-00-ch000/state.md`）
14. 開始寫作

### 階段四：可選強化

15. 撰寫 git hook 腳本
16. 根據使用經驗調整 skill 內容
17. 如有需要，加入輔助 Python 腳本（如 style checker、digest 統計分析）
