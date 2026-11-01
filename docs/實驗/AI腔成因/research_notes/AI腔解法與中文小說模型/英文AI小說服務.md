# 英文市場 AI 小說服務與進階使用者如何降低「AI 腔」（截至 2026-11-01）

> **證據標記**：【廠商】廠商自述／行銷；【使用者】個人軼聞；【量測】有方法與數字的研究；【競品】發文者賣對手產品。
> **缺陷代號**：A 敘述替讀者下意義判決｜B 句句用力、無平句、細節必兌現｜C 角色不說話、靠沉默與手勢｜D 內心無音量、不脫口｜E 收斂到同樣的點子／動作後必反應鏡頭／段尾收束／替讀者補邏輯洞。
> **讀法限制（全篇適用）**：
> 1. reddit.com 對本工具封鎖。r/NovelAi 與 r/ClaudeAI 僅透過第三方快照（reddit.sentinel-team.org）讀到少數幾串；**r/WritingWithAI、r/SillyTavernAI、r/LocalLLaMA 幾乎沒有直接讀到**。社群證據因此偏薄，不代表社群沒有這類討論。
> 2. 網頁擷取經過摘要模型，引文可能有輕微失真；承重引文請回原頁核對。
> 3. 所有英文資料都是英文散文。**沒有一筆資料直接測過 A–E 在中文網文上的表現。**

## 各服務的架構是什麼？哪些機制對應 A–E？

### Takeaway
架構分三類：一是自訓模型＋續寫（NovelAI，及部分意義上的 Sudowrite Muse）；二是「多模型包裝＋結構化 context」（Sudowrite 其餘模式、Novelcrafter、Raptor Write）；三是本機／RP 工具的取樣與模板調整（SillyTavern 生態）。公開機制幾乎全在處理**聲音與連續性**，沒有查到任何服務宣稱有專門針對 A、C、D 的機制；最接近的是 prompt 的分鏡長度、對白比例預設與事後改寫。

### Cited Findings

**Sudowrite**
- 流程【廠商】：Braindump → Synopsis → Genre/Style → Characters → Worldbuilding → Outline → Scenes → Draft；Write 動筆前讀 "up to 20,000 words of your preceding story plus your Story Bible"，Guided 模式 "lets you say what should happen next"，Draft 由 Scene 轉散文且預設用 Muse；Rewrite 上限 6,000 字；Describe 依五感與隱喻提供選項；"Style Examples teach Muse your register" — [How Sudowrite Works](https://sudowrite.com/blog/how-sudowrite-works/)
- 風格樣本的機制【廠商】：把稿件原文貼進 Story Bible 的 Style 區，"These samples become persistent context that gets injected into your generation requests"，建議五段以上、跨場景類型；**是 context 注入，不是微調**。未說明截斷方式，也未提出任何量測，只有三個示範輸出 — [AI Voice Matching](https://sudowrite.com/blog/ai-voice-matching/)
- 多模型【廠商】：作者自選 Prose Mode 或實驗模型（Muse、Ballad、GPT-4o Mini、Claude 4.x、GPT-5、Gemini 3、DeepSeek、Grok 4、Kimi K2 等）。官方文件記載的取捨與本研究相關者：GPT-5 "tends toward dialogue-heavy output with less descriptive prose"（**C**）但可能 "veer off-plot"；Ballad 適合對白重場景，但偏 "safer"、會 "faithfully reproduce errors" 於大綱；Sonnet 4.5 改寫時 "sometimes doubles word counts"（**B**）；Haiku 4.5 被建議用於快速迭代與過場；Muse 被形容為 "definitely voice-y" — [Which AI model should I use?](https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/which-ai-model-should-i-use/veMq9xRH6KLCQPFm5XkQx7)
- 資料衝突：該文件列 Claude 4.x，而 2026-06 的語音比對文仍列 Prose Mode 為 Muse、Claude 3.7 Sonnet、Claude 3 Opus、Deepseek-R1、GPT-4o Mini — [AI Voice Matching](https://sudowrite.com/blog/ai-voice-matching/)。Sudowrite 部落格的模型細節不宜當精確規格。

**NovelAI**
- 續寫架構：SillyTavern 文件指其模型圍繞 text completion，試圖續接輸入而非「回應」，並指 Instruct 模組傾向較不具創意 — [SillyTavern docs](https://docs.sillytavern.app/usage/api-connections/novelai/)
- Erato【廠商】（2024-09，**偏舊**）：在 Llama 3 70B 上 "continued pre-training ... for hundreds of billions of tokens"，再於 "our high quality literature dataset" 微調；新增 Min P、Unified Sampling；CFG 取消的理由是推論架構不相容，**不是品質理由** — [NovelAI Journal](https://journal.novelai.net/inference-update-llama-3-erato-release-window-new-text-gen-samplers-and-goodbye-cfg-6b9e247e0a63/)
- Xialong（2026-03-31 發布，GLM-4.6 微調）：官方文件稱 "genuinely different outcomes on retries and improved name variety"（【廠商】，**E**），context 28,672 tokens＋8,192 rollover — [NovelAI docs](https://docs.novelai.net/en/text/models)；發布日與 355B 參數見 [NovelMage（競品）](https://novelmage.com/blog/novelai-review-2026-is-it-right-for-novelists)，該文並稱 Anlatan 針對重複迴圈做了訓練、預設不再帶 repetition penalty。粉絲 wiki 把日期寫成 2025-03-31，參數另有 "~300B+" 的說法，應以 2026 與 355B 為準但未見官方公告原文 — [fan wiki](https://shapes.inc/fandom/novelai/ai-models)；[AIDS wiki](https://aids.miraheze.org/wiki/NovelAI)
- ATTG 與星等：官方格式 `[ Author: ; Title: ; Tags: ; Genre: ]`，可加 `[ S: X ]` 指定寫作品質（Erato／Xialong 專屬），"Two to four stars seem to be most effective"；`***` 表場景斷點、`----` 表資訊文；`[ Style: ... ]` 適用 Krake／Clio／Kayra／Erato — [NovelAI docs: special symbols](https://docs.novelai.net/en/text/specialsymbols/)。開發者另稱 Style 放進以 `***` 為 key、用 Cascade Activation 的 Lorebook 條目，比放 Author's Note "way better" — [r/NovelAi 鏡像（僅見搜尋片段）](https://lr.in.psf.lt/r/NovelAi/comments/1foia3k/comment/loq0u2x)
- 取樣器是 NovelAI 系與本機系的主要機制，但我讀到的都是用來處理**重複與連貫**，不是 A–E 這類敘事習慣 — [NovelAI Journal](https://journal.novelai.net/inference-update-llama-3-erato-release-window-new-text-gen-samplers-and-goodbye-cfg-6b9e247e0a63/)；[SillyTavern 重複修復](https://techtactician.com/sillytavern-repetition-fixes-best-settings/)
- Author's Note 位於 context 底部、影響過大，2023 年的新手指南說 "It's a trap"（**偏舊**）— [Blip's Guide](https://rentry.org/novelai-quick-start)；2026 年社群較溫和：大段多行內容不建議，"Using AN is fine. Just don't put the ATTG in there" — [r/NovelAi 快照](https://reddit.sentinel-team.org/posts/1s9fgew/snapshots/2026-04-03T15%3A05%3A24.89649Z)
- Lorebook 是關鍵字觸發的 context 注入，處理的是連續性；評論者稱其為 "keyword lottery"【競品，動機明確】— [NovelMage](https://novelmage.com/blog/novelai-review-2026-is-it-right-for-novelists)

**Novelcrafter（BYO 模型）**
- 無自有模型；核心是自訂 prompt（Scene Beat Completion、Text Replacement、Chat）與 Codex（可設 always-included，如 genre、style guide）。官方把 "removing AI-isms"、改 POV、貼近作者風格列為文字替換 prompt 的範例 — [Custom Prompts](https://novelcrafter.com/docs/ai/custom-prompts)；[Glossary](https://docs.novelcrafter.com/en/articles/9329937-glossary-of-novelcrafter-terms)
- Scene Beat 預設 400 字 — [Prompt docs](https://www.novelcrafter.com/help/docs/prompts/prompt-types)
- 風格樣本走 "Your Voice" preset＋snippet 放入 Context；官方稱 Sonnet 與 Gemini Flash/Pro 模仿最佳（未附數據）— [Writing samples](https://www.novelcrafter.com/help/faq/write/writing-samples)
- AI-isms 官方建議不是叫模型避開，而是建 Codex 條目、以別名標亮，**讓人事後審**（字詞清單本身不在本研究範圍，但「偵測交給程式、修改交給人」這個分工值得注意）— [AI-isms FAQ](https://www.novelcrafter.com/help/faq/ai-and-prompting/ai-isms)
- 官方教過 fine-tune（2024-02、gpt-3.5，**偏舊**）：分「散文修正」與較難的「beat→散文」兩種，約 75 筆樣本；"good habits" 應放進資料而非 prompt；**壞習慣會被放大**（作者自己的 "was [verb]"）— [Fine-tuning AI for authors](https://novelcrafter.com/blog/fine-tuning-ai-for-authors)

**Raptor Write／其他**
- Raptor Write 由 Future Fiction Academy 提供，軟體免費，所有 LLM 呼叫走使用者自己的 OpenRouter；未找到關於 prompt 結構或散文品質的技術文件 — [FAQ](https://shy-jackrabbit-e9e.notion.site/FAQ-Troubleshooting-9089a5492f5440c5a1263ba7e85dc6b9)
- SillyTavern 生態：Sphiratrioth 的 preset 是我找到**唯一明文控制對白比例**的機制（**C**）：[150T] "around 1/2 dialogues against 1/2 narration"、[350] "around 1/3 dialogues against 2/3 narration"，GM 預設則 "around 50/50 narration and inner thoughts"（**D**）；另警告中途切換 system prompt "OFTEN BREAKS" — [Sphiratrioth presets](https://huggingface.co/sphiratrioth666/SillyTavern-Presets-Sphiratrioth)。比例是 preset 作者自述，未見量測。

**機制 × 缺陷對照（我的整理；「✕」＝我沒找到任何聲稱或證據）**

| 機制 | A 下判決 | B 句句用力 | C 不說話 | D 無音量 | E 收斂／反應／收束 | 依據 |
|---|---|---|---|---|---|---|
| 在文學語料上微調 | 未測 | 未測，有反證（Muse 過度描寫） | 未測 | 未測 | 樣式怪癖下降【量測】；敘事層未測 | Chakrabarty；UCStrategies |
| 續寫而非指令 | ✕ | ✕ | ✕ | ✕ | 間接：指令化模型的可預測性更高【量測】 | 2602.16162 |
| 風格樣本注入 | ✕ | 部分（可能模仿節奏） | 部分（若樣本對白多，推論） | 部分（推論） | 反效果風險：照抄樣本的模式 | Novelcrafter |
| 短 beat 分段 | ✕ | ✕ | ✕ | ✕ | 減緩風格漂移【使用者】 | Opus 5 文 |
| 多模型選擇 | ✕ | Haiku 用於過場（廠商建議） | GPT-5 偏對白【廠商】 | ✕ | ✕ | Sudowrite docs |
| 預設對白比例 | ✕ | ✕ | 直接 | 部分 | ✕ | Sphiratrioth |
| 自評後重寫 | 未分項 | 未分項 | 未分項 | 未分項 | 未分項，僅「明顯較好」【使用者】 | Del Arroz |
| 線編輯（人或 AI） | 部分（只動 span） | 部分 | ✕ | ✕ | 敘事結構不動【量測】 | StoryScope |

### Inferences
- 商品機制與 A–E 之間有落差：廠商把問題定義成「聲音」與「連續性」，所以機制落在樣本注入與記憶上；A、C、D、E 屬**敘事決策**，這一層在這些產品裡沒有對應的旋鈕，只能靠寫 prompt。
- Sudowrite 的 Describe（五感與隱喻選項），以及其部落格所稱以 "Show, Don't Tell" 類指令調模型，**方向上可能加重 B、C**（鼓勵肢體化、感官化）；這是我的推測，未被測試。StoryScope 的 81% 身體感受數據與此方向一致（見下節）。

### Gaps
- 查無 Muse 的基底模型、語料規模或訓練方法的官方技術文件。
- 查無 Sudowrite 的 multi-pass 機制公開說明；讀到的頁面未提及。
- 查無 Raptor Write 的 prompt 內容與品質資料。

## Sudowrite 為何訓練 Muse？語料是什麼？宣稱與使用者實測的差距？

### Takeaway
訓練理由、語料與成效的公開說法都是廠商自述，且彼此不一致；沒有找到獨立的 Muse 評測數據。獨立性較高的評語集中在「過度描寫」——這正是 B 的方向。但獨立研究顯示，**同類做法（單一作者全集微調）確實可大幅提升讀者偏好**，所以「微調有用」不能因 Muse 宣稱空泛就否定；只是該研究測的不是 A–E。

### Cited Findings
- 動機【廠商】："a purpose-built LLM designed exclusively for the messy, nuanced, and often contradictory art of writing a novel"；語料 "a massive, proprietary dataset of published novels and stories"、"fine-tuned on a curated library of literature"；並以 "Show, Don't Tell"、"Raise the stakes" 等寫作指令做指令調校。**該文竟推測自家模型 "likely starts with a powerful foundation model"**，又自認可能產出 "stylistically perfect but emotionally hollow" 的文字 — [Muse deep dive](https://sudowrite.com/blog/what-is-sudowrite-muse-a-deep-dive-into-sudowrites-custom-ai-model/)
- 語料說法的張力【廠商】：Muse 頁面稱 "exclusively trained on a curated dataset with 100% informed consent from the authors"，與上述「massive ... published novels」未必矛盾但並未互相解釋，且無獨立稽核 — [Muse](https://sudowrite.com/muse)
- 廠商唯一的「成效數字」："manuscripts drafted with Muse require 40% fewer revision passes for voice consistency"，標示為內部資料，**無方法、樣本或基準** — [Sudowrite Muse](https://sudowrite.com/blog/sudowrite-muse-ai-writer-for-fiction/)
- 其餘為 beta 見證【使用者，廠商挑選】："Thoroughly cut back ai-ism"、"far less AI-isms"；具名者 Jason Hamilton："the best model I have ever seen for creative writing"；"My book is finished using Muse at 67,400 words in two days" — [Muse](https://sudowrite.com/muse)
- 負面【使用者／評測站，方法單薄】：Muse "defaults to descriptive language that can feel overwrought"；短篇散文 "needed editing"；中篇花 3 小時刪修飾語（"the ancient oak table with intricately carved legs" 其實只要 "table"）；該文自己承認 "No head-to-head benchmarks exist for 2026"，評分為作者主觀 — [UC Strategies](https://ucstrategies.com/news/sudowrite-review-i-tested-the-22-month-ai-against-chatgpt-across-70000-words/)
- 負面【競品】：未編輯的 Muse 落在 "the ornate, adjective-heavy register"，稱紫色文筆是最常見批評，但未列來源或計數；Trustpilot 2.9/5（29 則，並自承樣本小）— [Chapter](https://blog.chapter.pub/is-sudowrite-legit/)
- 廠商本身也承認少數評論者認為輸出 "wordy or cliched" — [Sudowrite Reviews](https://sudowrite.com/blog/reviews/)
- 同類做法的獨立證據【量測，預註冊預印本】：ChatGPT／Claude／Gemini 仿 50 位獲獎作者（≤450 字），28 名 MFA 讀者＋516 名一般讀者盲評。MFA 讀者對 prompt 注入（in-context）版：風格 OR=0.16、品質 OR=0.13；對全集微調版：風格 OR=8.16、品質 OR=1.87。偵測器標記率 prompt 版 97%、微調版 3%。中介分析指微調消除了可偵測的 AI 怪癖。中位成本每位作者 $81，且作者註明**不含修到可出版的人工成本** — [arXiv 2510.13939 v4](https://arxiv.org/abs/2510.13939)（v1 讀者數不同，引用時注意版本）

### Inferences
- Chakrabarty 的結果指向：**「把樣本貼進 context」與「用同作者全集微調」不是同一件事，差距可以大到翻轉偏好方向**。Sudowrite／Novelcrafter 的主流樣本功能都屬於前者。但該研究的單位是 ≤450 字片段，沒有測長篇敘事結構，也沒有測 A–E。
- 同作者全集微調與 Muse「多作者語料」也不是同一種東西，不應把此研究當成 Muse 的佐證。「文學語料」可能把模型推向文學腔，對網文的 C、D 未必有利（Muse 被評「過度描寫」、Opus 4.1 "too literary and gentle" 是同方向的弱訊號）。這是推論。

### Gaps
- 未找到 Muse 的獨立盲測、Muse 1.5 版本的具體改動說明。評測站關於 2025-03 發布、2026-01 更新到 1.5 的日期只來自次級來源，未核對官方。
- r/WritingWithAI 對 Muse 的實際評語未能讀到。

## 有經驗的使用者說什麼有效、什麼失敗？什麼比「不要做 X」清單好？

### Takeaway
最一致的訊號是**示範勝過指令**，且長篇分析式風格指令會變差。但這是少數個案，且示範也有副作用（照抄模式）。對 A，有 2026-08 的直接觀察：換上專屬風格指南後壞習慣仍會回來。**沒有找到真正比較「範例 vs 禁令清單」的受控實驗**。

### Cited Findings
- **示範 > 指令**【使用者，11 模型同專案】："It responded much better to demonstration than instruction"；15–20 個目標風格範例＋少量反例最好；**長篇分析式風格指令在所有測試模型上都變差**。同文對 Gemini：角色聲音跨章漂移、"over-explain things the reader already understood"（**A/E**）；GPT-5.2 情緒平、都在同一強度（**D**）；專門小說工具句子好但結構弱 — [r/ClaudeAI 快照，約 2026-03，子版為推定](https://reddit.sentinel-team.org/posts/1rxyz9s/snapshots/2026-03-20T20%3A10%3A12.107136Z)
- **Sonnet 4.5 "rewards you for being specific"**【使用者／工具方】：給範例後明顯變好，但 "follow examples closely"，會複製模式；續寫比原文更 polished，失去 raw energy（**D 的近親**）；改寫常使字數加倍（**B**）；反覆出現叫 Marcus 的角色（**E**）。無對白標籤的三人對話測試表現佳（**C：能力存在，不是模型做不到**）— [Novelcrafter Sonnet 4.5](https://www.novelcrafter.com/blog/testing-sonnet-4-5-for-writing)
- **風格指南壓不住 A**【使用者／工具方，2026-08】：Opus 5 "narrate the emotion explicitly and then summarize what just happened"，"announces realizations rather than letting the reader piece them together"（**A 的精確描述**）；"metaphor sandwich"（**B**）；內建聲音強，專屬 style guide 後壞習慣仍回來；風格與指令只撐前幾百字後漂移；短 beat 有幫助但更費來回。作者最後留 Opus 4.6 寫散文、Opus 5 只用於大綱批評 — [Novelcrafter Opus 5](https://novelcrafter.com/blog/opus-5-for-writers)
- **"Steer, not instruct"**：據 Discord 紀錄轉述，開發者建議 "Don't use instruct. Write."，用指令或改 system prompt 時 Xialong "will revert to base GLM behavior"，prefill 也會把模型推離訓練分布（**三手來源**）— [r/NovelAi 快照](https://reddit.sentinel-team.org/posts/1s9fgew/snapshots/2026-04-03T15%3A05%3A24.89649Z)
- **Xialong 的反方意見**（同一串）：宣稱消除陳腔濫調，但 "The very first person it named was Elara"（**E**）、"falls into repetitiveness at the drop of a hat"、"There is nothing \"beautiful\" about Xialong's generated prose. It's rushed and low brow"、"writes like a 9th grader half the time"。公認缺點是 "speedrun stories"，急著收場 — [r/NovelAi 快照](https://reddit.sentinel-team.org/posts/1s9fgew/snapshots/2026-04-03T15%3A05%3A24.89649Z)。官方文件另稱 GLM-4.6 的 ATTG "not explicitly supported"，Xialong 未提；社群有 "ATTGS is highly recommended" 與 "I'm damn sure it's not mandatory" 兩派 — [NovelAI docs](https://docs.novelai.net/en/text/models)
- **自評後重寫**【使用者，全自動三本書，有促銷成分】：draft→自評→重寫 "noticeably better prose than a single-pass draft"；全書回讀修連續性 "improved significantly"；但自承 "It repeats. It has patterns. A trained reader will spot them."，無前後對比 — [Del Arroz](https://substack.aicentral.blog/p/i-let-ai-write-three-complete-novels)
- **Story profile 的有限效果**【使用者，揭露自家產品，n=1 提示】："real, but not automatic"；同模型加 profile 反而 "less memorable"；raw 模型傾向 "the safest version of the story"（**E**）；留言者質疑單次測試的意義 — [r/ClaudeAI 快照](https://reddit.sentinel-team.org/posts/1ulrih1/snapshots/2026-07-03T03%3A00%3A16.73148Z)
- **全部作品塞進 context**【使用者，LessWrong】：把全部舊作放進 context 加一句指令，作者稱 "good enough to be mildly dispiriting"；留言者仍評 "sounds like a Claude story"，結尾太順、後段變弱、"laughed, actually laughed" 重複 — [LessWrong](https://www.lesswrong.com/posts/SwiChH68fRERBiCHe/experiments-with-sonnet-4-5-fiction)
- **GPT-5 Chat**【使用者／工具方】："rather bland and stilted"，且常有直接對作者說話的內容（助理腔）— [Novelcrafter GPT-5](https://www.novelcrafter.com/blog/is-gpt-5-any-good-for-writing-fiction)
- **禁令的證據品質很低**：搜到的「負面指令無效」主張來自初學教材（無研究）與**圖像**模型文件（Amazon Nova）；不能遷移到散文 — [Neural Base](https://theneuralbase.com/prompt-engineering/learn/beginner/no-negative-examples/)；[Amazon Nova](https://docs.aws.amazon.com/nova/latest/userguide/prompting-image-negative.html)

### Inferences
- 依據上述個案，有效性粗略排序（**我的判斷，非量測**）：大量同質範例／作者全集 ＞ 具體場景指令＋短 beat ＞ 長篇風格分析。這與本專案「輸入端載入 0.0、逐條自查 +2.0」的既有結果不完全同向，值得對照，不宜直接套用。
- 「用動作表達情緒」這類 prompt 建議在我搜到的提示教學中反覆出現（僅見搜尋摘要，未逐頁核對；Muse 的 "Show, Don't Tell" 指令調校見上節），**可能是 C 的成因候選**：英文建議似乎多把 pantomime 當解方而非缺陷。本專案對 C 的定義與此方向相反，引用英文技巧時要小心。
- C、D 在英文資料裡很少被指名。GPT-5 偏對白、preset 可設比例、無標籤對話測試表現佳，三者合起來提示 C 主要是**預設與提示問題，不是能力問題**；這是推論。

### Gaps
- **查無**「範例 vs 禁令」的受控實驗，也查無直接討論 B（平句、過場）與 D（脫口、內心音量）的實作報告。
- 未能讀到 r/SillyTavernAI、r/LocalLLaMA 的實際討論串；Sukino 指南僅見索引。

## 有沒有服務公開評估資料？有哪些獨立量測？

### Takeaway
**沒有查到任何一家服務公開可覆算的散文品質評估。** 能用的量測都來自學界，其中 StoryScope 最貼近 A、C、E：它顯示這些是敘事層特徵，而且跨模型共有。

### Cited Findings
- Sudowrite 僅有無方法的 "40% fewer revision passes" — [Sudowrite Muse](https://sudowrite.com/blog/sudowrite-muse-ai-writer-for-fiction/)
- Novelcrafter 公開推薦準則（如 "Dialogue should sound like people speaking"、"follow your voice rather than fighting it"），但沒有測試集、計分或結果 — [How we recommend](https://novelcrafter.com/blog/how-we-recommend-ai-models-for-writers)
- NovelAI：只見 "genuinely different outcomes on retries" 類定性敘述 — [NovelAI docs](https://docs.novelai.net/en/text/models)
- **StoryScope**（UMD＋DeepMind，2026-04）【量測】：10,272 組 prompt，每組 1 篇人類（Books3）＋5 模型（Sonnet 4.6、GPT-5.4、Gemini 3 Flash、DeepSeek V3.2、Kimi K2.5），共 61,608 篇、每篇約 5,000 字，抽 304 個敘事特徵且排除文風。人類 vs AI 分類 93.2% macro-F1，來源歸屬 68.4% — [StoryScope](https://arxiv.org/html/2604.03136v6)
  - **A**：敘述者明說主題，AI 77%／人類 52%（注意人類也有過半）
  - **C**：情緒靠身體感受，AI 81%／人類 38%；直接標示情緒，AI 8%／人類 29%；對白用於哲學辯論，AI 59%／人類 34%。**即 AI 不是沒對白而是對白功能不同**；我讀到的部分未見對白比例數字
  - **E**：五模型在敘事空間聚成一團，人類更分散；稀有度百分位 0.71 vs 0.49（d=0.83），人類版是六版中最稀有的比例 57.8%（隨機 16.7%）；無副線 79% vs 57%；主角驅動的結局 69% vs 46%
  - 各模型指紋：Claude 事件平坦升級、GPT 用八卦推劇情 64%、Gemini 外部描寫與陰鬱場景 88%（**換模型換的是指紋，不離開 AI 群**）
  - 編輯：對 278 篇 Gemini 故事套 LAMP 片段改寫，敘事分類器僅 95.5%→93.9%
- **LAMP／"Can AI writing be salvaged?"**（CHI 2025）【量測】：18 位寫作者編輯 1,057 段（平均約 205 字），8,035 處、每段約 8 處。類別佔比：用字 28%、句構 20%、**多餘解釋 18%（＝替讀者說破，A）**、陳腔濫調 17%；操作上取代 74%、刪除 18%、插入 8%。Claude-3.5、GPT-4o、Llama 3.1 之間品質**無顯著差異**，小說分數低於創意非虛構 — [LAMP](https://arxiv.org/html/2409.14509v2)
- **不確定性落差**（2026-02 預印本）【量測，弱相關】：28 個開放權重模型續寫 New Yorker 與 Tell-Me-A-Story，人類一律比模型更難預測；同族 instruct／thinking 版落差大於 base（如 Gemma-3-4B PPL 比 3.90 base vs 8.82 instruct；Qwen3-4B 4.07 base vs 7.37 instruct）。但與品質只有 ρ≈0.07–0.11，品質分由自動模型給，非人評 — [arXiv 2602.16162](https://arxiv.org/html/2602.16162v1)
- Llama-2 的 RLHF 研究也指出對齊可能削減創造潛能（**僅讀到搜尋摘要**）— [arXiv 2406.05587](https://arxiv.org/pdf/2406.05587)

### Inferences
- StoryScope 給了 E 的硬證據，並支持「換模型無法解決收斂」。但它量的是「可判別」，不是「更好」：判別特徵不等於缺陷，人類也有 52% 明說主題。
- 續寫／base 優於 instruct 的量測支持的是**較不可預測**，不是直接支持散文較好；NovelAI 使用者對 Xialong 的兩極評價也顯示續寫架構不保證品質。

### Gaps
- 查無 base vs chat 同模型續寫、人類盲評的受控比較。
- StoryScope 全文末尾約 26,000 字元未讀；其對白比例數據未確認。lechmazur 的寫作風格基準擷取遭 403，未讀。

## 人工後編輯是否仍是普遍退路？流程佔比多少？

### Takeaway
是，所有非全自動的來源都預設要人修，包含廠商與想賣東西的人；連自動派也只是選擇接受殘留。但**沒有查到可靠的修改佔比量測**，常見百分比都是建議或假設。而且線編輯到不了敘事層，人自己也感覺不到殘留。

### Cited Findings
- 無佔比量測：30% AI／70% 人工是評測者的規劃假設 — [UC Strategies](https://ucstrategies.com/news/sudowrite-review-i-tested-the-22-month-ai-against-chatgpt-across-70000-words/)。另有某指南建議「40–60% 人工修改」、無證據（僅見搜尋摘要，未確認出自哪一頁，勿引用為數據）。
- 採用面：BookBub 2025-05 調查 1,200+ 作者，約 45% 用 AI，其中 70% 用於編輯（僅見搜尋摘要轉述，未讀原調查，也未確認轉述頁；候選頁 [State of Author AI](https://authorlytica.com/state-of-author-ai/)、[Matesic](https://www.alyssamatesic.com/free-writing-resources/are-writers-really-using-ai)）。
- 分輪修訂【廠商系指南】：結構→連續性→對白與場景目的→線編輯，一輪只做一件事 — [Five-Pass Revision](https://www.entangledtext.com/guides/five-pass-revision-order-ai-novels)
- 編輯的上限【量測】：
  - 敘事層不動：95.5%→93.9% — [StoryScope](https://arxiv.org/html/2604.03136v6)
  - 專家偏好專家編輯版；自動編輯有改善但未達專家水準 — [LAMP](https://arxiv.org/abs/2409.14509)
  - 81 名受試者後編輯 GPT-o4-mini 草稿（**非小說**，如婚誓、道歉信）：文風更近本人（g=0.55），但仍比本人更近 LLM（g=−1.43），也比純人寫同質化（g=1.42）；受試者自評與純手寫一樣像自己（p=.906），主觀與量測僅 r=0.244 — [arXiv 2604.24444](https://arxiv.org/html/2604.24444v1)
- 微調研究也明說成本不含修到可出版所需的人工 — [arXiv 2510.13939](https://arxiv.org/abs/2510.13939)
- 全自動的反例：Del Arroz 不做人工潤修直接上架，但其讀者反應無資料，且文章帶聯盟連結 — [Del Arroz](https://substack.aicentral.blog/p/i-let-ai-write-three-complete-novels)

### Inferences
- 後編輯對 B、用字、陳腔濫調有效，對 A 有部分效果（可刪），對 E 的敘事收斂及 C 的場景組成**不適合用線編輯處理**；這些應提前到幕綱或重寫層。
- 作者的主觀感受與文風量測只弱相關，這支持「盲讀＋客觀量測」並用，而不是只問作者滿不滿意。不過該研究是非小說、一般受試者，遷移到小說作者需保留。

### Gaps
- 查無 AI 小說作者的修改量佔比的可靠調查。KDP Builder 的 775 本樣本偏低內容書、小說僅 8.7%，不適用 — [KDP Builder](https://kdpbuilder.com/reports/state-of-ai-self-publishing-2026)。
