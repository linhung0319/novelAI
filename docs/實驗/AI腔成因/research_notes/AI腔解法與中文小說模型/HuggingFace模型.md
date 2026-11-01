# Hugging Face 中文小說模型調查（截至 2026-11-01）

**證據標記**：〔卡〕＝模型卡／HF API／官方文件直接寫的；〔本機〕＝這次在作者機器上實跑或實讀；〔二手〕＝聚合站或論壇，未能回到一手；〔推論〕＝我的計算或判斷，沒有直接證據。

**硬體已查實，不必用假設值**〔本機〕：RTX 2080 Ti 11,264 MiB、系統 RAM 32 GB（DDR4-2667 ×2）、Ryzen 7 3700X、ollama 0.40.13。

**HF API 的日期**是 repo 建立日（`createdAt`），不一定等於官方發表日。下載數是 API 回報值。

---

## Q1. 本機模型只是太弱嗎？9B 是瓶頸嗎？

### Takeaway
「太弱」大概是主因之一，但目前無法定論：沒有任何公開資料在同世代、同題材下比較過中文小說品質與模型大小。花不到 1 美元的 API 階梯測試（Q4）就能回答，應該先做這個再談硬體。另外查到一個真實的設定問題：`presence_penalty=1.5` 一直在生效，而實驗報告沒記錄到。不過實測顯示，關掉它修不好語意錯誤。

### Cited Findings
**版本與量化**
- `qwen3.5:9b` 就是 `latest`，manifest 的 `file_type` 是 **Q4_K_M**：權重 5.63 GB ＋ 視覺投影器 0.92 GB，合計約 6.6 GB。讀文字用不到投影器，但它照樣佔大小 — [ollama registry manifest](https://registry.ollama.ai/v2/library/qwen3.5/manifests/9b)〔本機讀取〕；[ollama 頁面](https://ollama.com/library/qwen3.5)
- 官方 Qwen3.5-9B 是 2026-02-27 建立，Apache-2.0。HF 量化檔：Q4_K_M 5.68、Q5_K_M 6.58、Q6_K 7.46、Q8_0 9.53 GB — [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)、[unsloth GGUF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF)〔卡〕
- **它是目前官方最新的 9B，但不是最新世代。** Qwen 官方帳號之後開放的文字模型只有 Qwen3.6（27B／35B-A3B）與 Qwen3.8（27B、Flash-Next 180B、2.4T-A95B），沒有更新的 9B。Qwen3.7 系列在 OpenRouter 上有，但官方帳號沒有權重 — [Qwen 帳號列表](https://huggingface.co/api/models?author=Qwen&sort=createdAt&direction=-1&limit=25)
- 名為 `Qwen3.8-9B-…` 的 repo 不是官方底模，是社群合併（見 Q3）。

**實驗參數的漏網項**
- 本機 `ollama show qwen3.5:9b --parameters` 顯示內建 `presence_penalty 1.5`、`temperature 1`、`top_k 20`、`top_p 0.95` — 〔本機〕
- `code/run_ollama.py` 只覆寫了 temperature 0.8、top_p 0.95、num_ctx 32768、repeat_penalty 1.0、think false，**所以 presence_penalty 1.5 與 top_k 20 一直生效**。`神秀實驗/code/run_qwen.py` 只設 num_ctx 16384 與 num_predict，所以還多吃了 temperature 1。`01-結果報告.md` 第六節寫了 `repeat_penalty=1.0`，沒提 presence_penalty — 〔本機〕
- **context 截斷已排除**：ollama 在 VRAM 低於 24 GiB 時預設只有 4k context（[官方文件](https://docs.ollama.com/context-length)），但實驗明確設了 32768，且報告記錄 prompt 10,243／10,556 tokens 未截斷。「指令被截掉造成漂移」這條解釋不成立。

**固定 seed 的 A/B 實測**〔本機〕（3 個 seed × 3 組，同一段短仙俠 brief，繁中，num_ctx 8192，repeat_penalty 1.0）
- 不傳 presence_penalty 與傳 1.5 的輸出**逐字相同**（3/3），傳 0 則不同（3/3）。可確認 1.5 真的在生效。
- 不重複字數：預設 415／355／408，pp=0 為 340／341／373。方向符合懲罰會逼模型換字，但 n=3 且輸出長度不同，只算線索。
- 速度：預設約 66–68 tok/s，pp=0 約 76–79 tok/s（全在 GPU）。約 1.23 字／token。
- **兩組都有錯，關掉懲罰並未消除**（以下是我親讀的判斷，樣本很小）：
  - 預設組：「讓我們師妹陪你」人稱錯；把執事長老叫「大師伯」；憑空設定阿朮是內門弟子。
  - pp=0 組：brief 寫明林照攔下阿朮，seed 33 卻變成沈青梧喝止她，事件漂移。
- 簡體混入兩組都有（`门`、`辩`、`双`／`个`、`衆`、`话`、`声`），與 presence_penalty 無關的可能性較高。這些原文與 OpenCC 測試樣本放在暫存區 `C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Programming-novelAI\c2cc4d2d-7014-457a-a8cc-0c83b486fb8e\scratchpad\hf\ab.json`，不在 repo 內。

**大小與文筆的關聯證據**
- WebNovelBench（4,000+ 部中文網文，梗概→故事，8 維度，LLM 評審）：Qwen3-235B-A22B 最高，norm 5.21；頂尖組 3.5–4.6；GPT-4o、DeepSeek-V3 等中段 2.5–3.8；GLM-4-9B-chat、LLaMA-3-8B 低於 2.0。論文沒有分析大小與分數的關係，大小與世代也混在一起，而且模型都是 2025 年以前的 — [arXiv 2505.14818](https://arxiv.org/html/2505.14818)；已刊於 [Findings of EACL 2026](https://preview.aclanthology.org/ingest-eacl/2026.findings-eacl.94.pdf)
- 該論文的 [GitHub repo](https://github.com/OedonLestrange42/webnovelbench) 頁面沒有逐模型分數。
- LocalLLaMA 討論串有人說「創意寫作模型本質上不是本地的」，理由是需要世界知識與長尾機率，而小模型裝不下。這是意見，不是量測；該串也沒人談中文 — [Reddit 快照](https://reddit.sentinel-team.org/posts/1sx47x0/snapshots/2026-05-02T03%3A06%3A21.60641Z)〔二手〕
- **大不一定好，新也不一定好**：HF 討論有使用者認為 Qwen3.8 偏向 agent 與寫程式的訓練傷了創作，故事較重複矛盾，建議改用 Gemma 4 31B；同串另一人則說 3.8 比 3.6 大幅進步。雙方都沒附樣本 — [Qwen3.8-27B discussion #97](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/97)〔軼事〕

### Inferences
- 作者列的五個症狀該分開看〔推論〕：
  - **語意與人稱錯誤、事件漂移、背角色卡**：最可能跟模型能力有關，這次 A/B 也重現了前兩項。
  - **簡體混入**：後處理就能解決，不是換模型的理由（見 Q6）。
  - **指令文字漏進正文**：較可能是 prompt 與模型的互動，可用 Q6 的 raw 模式或結構調整試驗。
  - **文風平**：微調模型宣稱針對這點，但沒有獨立證據。
- 從 Q4_K_M 換到 Q5／Q6 是目前 VRAM 裝得下的免費升級，但我沒找到量化等級影響中文文筆的量測，別預期有明顯差異。
- 實驗報告第五節寫「Qwen 能力較弱」，第六節的參數沒寫 presence_penalty。建議補記這一項，否則之後重現會對不上。

### Gaps
- 找不到 2026 年的中文小說專項榜單。SuperCLUE 只查到 [2023 年論文](https://arxiv.org/abs/2307.15020)，沒找到 2026 年的創作或小說分榜。
- 沒有同世代、同語料、不同大小的中文小說比較。

---

## Q2. 通用大模型：現在誰最新？誰的中文創作最好？

### Takeaway
各家現行版本都查得到，但**沒有可信的中文創作排名**。英文 Creative Writing Arena 的前十全是閉源模型。開放權重之中誰的中文最好，目前只有軼事，只能自己盲評。

### Cited Findings
**現行開放權重版本**（參數量與日期取自 HF API）

| 家族 | 現行版本 | 建立日 | 授權 | 規模 | 11 GB 可行性 |
|---|---|---|---|---|---|
| Qwen | [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | 2026-08-05 | Apache-2.0 | 27.8B；[Q4_K_M 16.46 GB](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) | 分層，慢 |
| Qwen | [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) | 2026-08-24 | other | 180B；[最小 GGUF 約 66 GB](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF) | 不可行 |
| GLM | [GLM-5.3-Flash](https://huggingface.co/zai-org/GLM-5.3-Flash)、[GLM-5.3](https://huggingface.co/zai-org/GLM-5.3) | 2026-08-25 | MIT | Flash 321B | 不可行，走 API |
| Kimi | [Kimi-K3](https://huggingface.co/moonshotai/Kimi-K3) | 2026-06-13 | other | 2.78T | 不可行，走 API |
| DeepSeek | [V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)、[V4-Pro](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro) | 2026-09-10／04-22 | MIT（V4.1-Flash） | V4.1-Flash 763B | 不可行，走 API |
| MiniMax | [M3.1-Flash](https://huggingface.co/MiniMaxAI/MiniMax-M3.1-Flash)、[M3](https://huggingface.co/MiniMaxAI/MiniMax-M3) | 2026-10-17／06-02 | other | M3.1-Flash 220B | 不可行，走 API |
| 騰訊 | [Hy3](https://huggingface.co/tencent/Hy3) | 2026-07-02 | 未查 | 社群 repo 名標 [295B-A21B](https://huggingface.co/YanissAmz/Hy3-295B-A21B-GGUF) | 不可行 |
| Google | [Gemma 4 12B](https://huggingface.co/google/gemma-4-12B-it) | 2026-05-23 | Apache-2.0 | 11.96B；[Q4_K_M 7.12、Q5_K_M 8.41 GB](https://huggingface.co/unsloth/gemma-4-12b-it-GGUF) | **全進 VRAM** |
| Google | [Gemma 4 31B](https://huggingface.co/google/gemma-4-31B-it)、[26B-A4B](https://huggingface.co/google/gemma-4-26B-A4B-it) | 2026-03-11 | Apache-2.0 | [31B Q4 18.32](https://huggingface.co/unsloth/gemma-4-31B-it-GGUF)、[26B-A4B Q4 16.95 GB](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF) | 分層 |
| Mistral | [Small-4-119B-2603](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603) | 2026-01-23 | 未查 | 119B | 不可行；無中文創作證據 |
| 中國電信 | [Xing4.0-29B-A4B](https://huggingface.co/XingChen-AGI/Xing4.0-29B-A4B) | 2026-09-16 | Apache-2.0 | 定位是 agent 與程式；卡片未提創作 | 非首選 |

- **Yi、百川已停在舊世代**：HF 上下載最多的是 2023–2024 年的 [Yi-1.5-9B](https://huggingface.co/01-ai/Yi-1.5-9B) 與 [Baichuan2-13B-Chat](https://huggingface.co/baichuan-inc/Baichuan2-13B-Chat)，不值得測。

**榜單**
- Creative Writing Arena（2026-06 的轉述）前十全是閉源：Claude 六席、Gemini 三席、Grok 一席 — [OfficeChai](https://officechai.com/learn/these-are-the-best-ai-models-for-creative-writing-june-2026/)〔二手，未對到 live 榜〕
- BenchLM 把 instruction-following 當寫作代理指標，不評中文，頁面自己也承認這與人類偏好榜不一致。它把 Qwen3.8 Max 標為開放權重，但我在 Qwen 官方帳號列表沒看到這個權重，兩者衝突 — [BenchLM](https://www.benchlm.ai/best/writing)〔二手，不可採信為創作排名〕
- 某路由商頁面聲稱 deepseek-v4-pro 的 EQ-bench 為 75、是最好的開放創意模型、中文突出；實際抓取只拿到標題，數據無法核對。這是路由商自己的頁面，有利益關係 — [OrcaRouter](https://www.orcarouter.ai/zh-CN/best/creative)〔不可驗證〕
- OpenRouter 角色扮演用量：只找到非官方轉述（DeepSeek V3.2 佔 40.2%），且用量不等於品質 — [HackMD](https://hackmd.io/@BASHCAT/r1sWYOs6be)〔二手〕
- 「Qwen 的中文比 Gemma 自然」來自比較文的概括，不是小說測試 — [比較文](https://gemma4guide.pages.dev/guides/gemma4-vs-qwen)〔二手〕

### Inferences
- 中文創作的開放權重排名，現階段**沒有可引用的答案**。任何「X 中文文筆最好」都只是軼事。
- 11 GB 的實際選項只剩 Qwen 27B 級、Gemma 4（12B／26B／31B）與 Qwen3.6-35B-A3B。GLM、Kimi、DeepSeek、MiniMax 只能走 API。

### Gaps
- LMArena live 榜的中文子集、WritingBench、SuperCLUE 2026 創作分榜：本次都沒取得一手資料。

---

## Q3. 中文小說／角色扮演微調模型

### Takeaway
真的有，而且有兩支直接對準網文與仙俠。但**沒有一支附輸出樣本或獨立評測**，「比底模好」目前全是作者自述。它們全是 27B 級，在 11 GB 上都得分層。

### Cited Findings
**值得測的**

| 模型 | 底模 | 訓練方式（卡片自述） | 授權 | GGUF | 下載 |
|---|---|---|---|---|---|
| [wcn123/Qwen3.5-27B-WebNovel-Writer-zh](https://huggingface.co/wcn123/Qwen3.5-27B-WebNovel-Writer-zh) | Qwen3.5-27B 自抽文字版（非官方） | 20,320 筆網文 SFT ＋ 8,000 組 ORPO，目標是去 AI 味；語料不公開 | other，**僅限研究與個人使用** | [Q4_K_M 16.55](https://huggingface.co/wcn123/Qwen3.5-27B-WebNovel-Writer-zh-GGUF)；[i1 Q3_K_M 13.30](https://huggingface.co/mradermacher/Qwen3.5-27B-WebNovel-Writer-zh-i1-GGUF) | GGUF 約 1.6–1.7 萬 |
| [yuxinlu1/qwen3-6-27b-chinese-xianxia-lora-v2](https://huggingface.co/yuxinlu1/qwen3-6-27b-chinese-xianxia-lora-v2) | Qwen3.6-27B | 章節級修仙語料 QLoRA，r=16，尚未做 DPO | adapter MIT | LoRA `*-f16.gguf` 159 MB（已由 API 確認存在）；底模 [Q4_K_M 16.82](https://huggingface.co/unsloth/Qwen3.6-27B-GGUF) | 135 |
| [JiangLing-js/…Xuanhuan-Novel-Writer-DPO](https://huggingface.co/JiangLing-js/Qwen3.8-27B-Chinese-Xuanhuan-Novel-Writer-DPO) | Qwen3.8-27B | 單一部奇幻小說：2,380 筆 SFT、607 對 DPO | other | **名為 GGUF 的 [repo](https://huggingface.co/JiangLing-js/Qwen3.8-27B-Chinese-Xuanhuan-Novel-Writer-DPO-GGUF) 實際只有 safetensors，沒有 .gguf**（已列檔確認） | 205 |
| [cyanelis/ElisNovel-V3-32B](https://huggingface.co/cyanelis/ElisNovel-V3-32B) | Qwen3-32B | 行間填充（給奇數行，生成偶數行）；附 ollama Modelfile | Apache-2.0 | Q4_K_M 19.76 | 4,415 |
| [gugujiji/novel-humanize-4b](https://huggingface.co/gugujiji/novel-humanize-4b) | Qwen3-4B | **改寫器，非寫手**：把 AI 感章節改寫成人寫感，保留情節；訓練資料未述 | CC BY-NC 4.0 | [Q4_K_M 2.59](https://huggingface.co/bartowski/gugujiji_novel-humanize-4b-GGUF) | 851（GGUF 4,691） |

**卡片自己寫的限制，比宣稱更有用**
- xianxia LoRA：單次生成超過約 600–700 tokens 可能漂移、迴圈、人名不穩；**重複懲罰太高會讓中文人名同音漂移**；不處理全書連貫；評測只是作者內部的定性觀察。
- Xuanhuan：33 組驗證集準確率 1.0，但卡片明說這不代表寫作品質；未完整稽核是否背誦原著；朱雀檢測的結果不可靠。
- novel-humanize：偶爾刪細節；太短會自創情節；要求半形標點；只驗證過中文網文。卡片未說明是否處理繁體。
- ElisNovel 宣稱「完美穿透朱雀檢測，AI率為0」。這是偵測器指標，不是品質證據；文風也取決於輸入。

**不建議，或與需求不符**
- [dongfangshuo Qwen3.8-27B-NSFW-Novel](https://huggingface.co/dongfangshuo/Dongfangshuo-Qwen3.8-27B-NSFW-Novel)：下載高，但卡片沒有任何訓練或評測說明；底模血統也沒寫清楚。
- [vurtnesaerdna/Qwen3.8-27B-Uncensored-Chinese](https://huggingface.co/vurtnesaerdna/Qwen3.8-27B-Uncensored-Chinese)：明確定位成人小說，約 4.2k 筆，與仙俠網文的主需求不合。
- [Qwen3.8-9B-Distill-SLERP-F451-Pro-Writer](https://huggingface.co/nuofang/Qwen3.8-9B-Distill-SLERP-F451-Pro-Writer-Uncensored)：唯一裝得進 VRAM 的「寫手」候選（[Q4 5.78 GB](https://huggingface.co/mradermacher/Qwen3.8-9B-Distill-SLERP-F451-Pro-Writer-Uncensored-GGUF)），但卡片沒寫來源、方法、資料與授權，標籤只顯示 mergekit 合併與 qwen3_5 架構。**不建議，除非當對照。**
- [DavidAU 系列 Qwen3.5-9B-Defiant-Fable](https://huggingface.co/DavidAU/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF)：下載 195 萬，但這是解除審查與一般強化的系列，下載量不代表中文小說能力。本次未讀全卡，沒有中文證據。
- [Gemma-4-Novelist-Eclipse-31B](https://huggingface.co/mradermacher/Gemma-4-Novelist-Eclipse-31B-i1-GGUF)：語言標籤只有 en。

**清單中其他名字的查核結果**
- **MiniMax M2-her**：只在 OpenRouter 上有（$0.30／$1.20，context 65,536），API 未回報 HF ID；[MiniMax 帳號](https://huggingface.co/api/models?author=MiniMaxAI&sort=createdAt&direction=-1&limit=8)最近 8 支與 HF 搜尋都沒找到權重 — [OpenRouter](https://openrouter.ai/minimax/minimax-m2-her)
- **通義星辰**：HF 搜不到。搜尋命中的 `XingChen-AGI` 是中國電信，不是同一家。
- **CharacterGLM**：[thu-coai/CharacterGLM-6B](https://huggingface.co/thu-coai/CharacterGLM-6B) 存在，但屬 2023–2024 年世代。
- **LongWriter**：[LongWriter-Zero-32B](https://huggingface.co/bartowski/THU-KEG_LongWriter-Zero-32B-GGUF)（Apache，Q4 19.85 GB）與舊版 glm4-9b、llama3.1-8b 存在。本次只核了存在與大小，沒有小說品質證據。
- **Sakura**：[SakuraLLM](https://huggingface.co/SakuraLLM/Sakura-14B-Qwen3-v1.5-GGUF) 是日翻中翻譯模型，授權 CC BY-NC-SA，不適合原創。
- **ChatWaifu**：只有 mradermacher 等人的量化檔，舊世代；未讀卡。
- **XuanYuan**：是[度小滿](https://huggingface.co/Duxiaoman-DI/XuanYuan-70B)的金融模型（我的既有認知，本次未讀卡），2023–2024 年，與小說無關。
- **SCHub**：搜尋結果沒有相關模型，判定不存在。

### Inferences
- 訓練語料幾乎都來自未授權的網文。若要**商業出版**，除了授權條款（wcn123 僅限個人研究）之外，還有背誦原著的風險。Xuanhuan 卡片明說未稽核，其他卡片則根本沒提〔推論〕。
- 語料與卡片皆為簡體，可預期微調會**加重**繁中輸出的簡體混入。需要實測，但 Q6 的後處理應視為必備〔推論〕。

### Gaps
- 沒有任何一支有第三方盲評。[wcn123 的社群 Space](https://huggingface.co/spaces/simonchen4545/qwen-webnovel-writer) 也許可以免下載試用，本次未測。

---

## Q4. 11 GB 能跑什麼？該先測什麼？

### Takeaway
**先別買硬體，也先別下載 27B。** 用 OpenRouter 跑四階對照，約 1 美元內就能判斷「太笨」假說。本機首選是 WebNovel-Writer-zh，但要接受分層的慢速；要快就用 Gemma 4 12B 或 Qwen3.6-35B-A3B（後者需 llama.cpp），兩者都沒有中文小說證據。

### Cited Findings
**實測與報告的速度**
- Qwen3.5-9B 全在 GPU：66–79 tok/s〔本機〕
- 分層 MoE：Qwen3.6-35B-A3B Q5_K_M，RTX A2000 12GB、128GB RAM、32K context，用 llama.cpp `-ncmoe 26`：生成 35 tok/s，prompt 79 tok/s，VRAM 約 10.3 GB，RAM 約 18.4 GB — [Reddit 快照](https://reddit.sentinel-team.org/posts/1ta4r5m/snapshots/2026-05-15T22%3A59%3A01.155307Z)〔單一使用者回報〕
- SpecPicks 宣稱 RTX 3060 達 80 tok/s，但其頁面前後不一致，不採信 — [SpecPicks](https://specpicks.com/reviews/qwen36-35b-a3b-rtx-3060-mtp-deep-dive-2026)
- 這個 `-ncmoe` 是 llama.cpp 參數。[ollama Modelfile 文件](https://ollama.readthedocs.io/en/modelfile)的參數表沒有對應項，所以這條路得改用 llama-server。

**本機候選**（GGUF 大小都已由 HF API 確認；速度全是〔推論〕，**未實測**）

| 順位 | 模型 | 檔案 | 預估速度 | 3,000 字約需 | 證據狀況 |
|---|---|---|---|---|---|
| 首選 | WebNovel-Writer-zh Q4_K_M | 16.55 GB | 上限約 5–6 tok/s，實際可能 2–4 | 10–20 分鐘 | 唯一對準「去 AI 味的網文」且語料量最大；**無評測、無樣本** |
| 次選 | Qwen3.6-27B Q4 ＋ xianxia LoRA | 16.82 GB ＋ 159 MB | 同上 | 同上 | 題材最對口；作者建議逐場景生成 400–700 tokens；**只有定性自述** |
| 快速對照 | Gemma 4 12B Q4_K_M／Q5_K_M | 7.12／8.41 GB | 全在 GPU，應達數十 tok/s | 1–2 分鐘 | 不同血統；**無中文小說證據** |
| 快速對照 | Qwen3.6-35B-A3B UD-Q4_K_M | [22.13 GB](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) | 相近配置回報約 35 tok/s | 約 2 分鐘 | 需 llama-server；32 GB RAM 偏緊；**無中文小說證據** |
| 省事升級 | Qwen3.5-9B Q6_K | 7.46 GB | 接近現況 | 不到 1 分鐘 | 同模型高精度，預期改善有限 |

- 估算依據：分層時，放在 CPU 的權重每個 token 要掃一次。DDR4-2667 雙通道理論約 42.7 GB/s，Q4_K_M 約 7–8 GB 留在 CPU，所以上限約 5–6 tok/s。實際還要打折，10k tokens 的 prompt 處理也要另算數分鐘。**量到實數前都只是估計**，用 `--verbose` 或回傳的 `eval_duration` 就能量。
- i1 Q3_K_M（13.30 GB）放在 CPU 的權重較少，上限估約 9 tok/s，但量化更低；對文筆的影響沒有資料。
- 其餘 RAM 餘裕：16.5 GB 級在 32 GB RAM 上沒有問題。

**API 階梯測試**（價格取自 [OpenRouter API](https://openrouter.ai/api/v1/models)，2026-11-01；每篇成本依 10k 輸入、3k 輸出〔推論〕）

| 階 | 模型 | 輸入／輸出 $/M | 每篇約 | 這一階回答什麼 |
|---|---|---|---|---|
| 0 | qwen/qwen3.5-9b | 0.17／0.25 | $0.003 | 與本機同模型：量化與 ollama 有影響嗎？ |
| 1 | qwen/qwen3.5-27b | 0.26／2.60 | $0.010 | 同世代放大 3 倍有用嗎？**這階直接決定值不值得跑分層** |
| 1 | google/gemma-4-31b-it | 0.20／0.40（另有 :free） | $0.003 | Qwen 以外的血統 |
| 1 | qwen/qwen3.6-35b-a3b | 0.10／0.90 | $0.004 | 本機跑得快的 MoE 路線能力夠嗎？ |
| 1 | qwen/qwen3.8-27b | 0.15／1.875 | $0.007 | 驗證「3.8 傷創作」的軼事 |
| 2 | z-ai/glm-5.3 | 0.07／1.40（batch 0.45／2.00） | $0.005–0.011 | 開放權重旗艦 |
| 2 | deepseek/deepseek-v4.1-flash | 0.045／0.50 | $0.002 | 同上 |
| 2 | minimax/minimax-m3 | 0.30／1.20 | $0.007 | 同上 |
| 2 | moonshotai/kimi-k3 | 0.192／15.00（batch 2.28／11.40） | $0.05–0.06 | 同上，輸出貴 |
| 3 | anthropic/claude-sonnet-5.5 | 2.00／10.00 | $0.05 | 天花板參照 |

- **部分輸入價看起來不正常**：z-ai/glm-5.3 與 kimi-k3 的輸入價比自己的 batch 價還低，glm-5.2 更只有 $0.006。可能反映快取或特定供應商。實際費用請以模型頁為準，上表有區間的列已用 batch 價算上限。
- 微調模型在 OpenRouter 上沒有：wcn123 的卡片明說目前沒有 inference provider。要測得自己租 GPU 或用 Space。本次未查 GPU 租用價格。
- 2080 Ti 的升級或租用方案未查價。

### Inferences
- **判讀規則**〔推論〕：
  - 階 0 已比本機明顯好 → 問題在量化或 ollama，不是模型。
  - 階 1 語意錯誤大幅減少 → 9B 確實是瓶頸，值得跑 27B 分層或微調。
  - 階 2、3 才變好，階 1 沒有 → 11 GB 救不了，該走 API，而不是買一張普通顯卡。
  - 連階 3 都犯同樣的錯 → 問題在 prompt 或流程。
- 階 0 與本機不算嚴格對照：OpenRouter 供應商的精度未必公開。可用同一份 `S1`／`S2` prompt 跑，既有實驗框架幾乎能直接沿用；每階 n=5 共約 10 支模型，成本約 1 美元。
- **隱私**：API 會把書稿內容送到第三方，供應商的保存政策各異。先用非核心內容測〔推論〕。
- 微調模型的「去 AI 味」與作者正在做的 AI 腔實驗同一主題，可以當實驗的一臂，但語料是簡體，需先處理腳本差異。

### Gaps
- 本機分層實際速度未測，因為沒有下載 16 GB 以上的檔案。
- 微調模型相對底模的改善幅度，無任何資料。

---

## Q5. 純續寫／base 模型

### Takeaway
有可用的選項，而且在 VRAM 內：Qwen3.5-9B-Base 與 RWKV-7。但**兩者都沒有中文小說證據**，也都不會聽大綱，預期事件控制會更差。值得當實驗一臂，不適合當主力。

### Cited Findings
- [Qwen/Qwen3.5-9B-Base](https://huggingface.co/Qwen/Qwen3.5-9B-Base)：Apache-2.0，2026-02-26。卡片稱「pre-trained only」，用途是微調與 in-context learning，「not direct interaction」；但同卡也寫了「Pre-training & Post-training」，自相矛盾。沒提續寫。[Q4_K_M 5.63 GB](https://huggingface.co/mradermacher/Qwen3.5-9B-Base-GGUF)
- [BlinkDL/rwkv7-g1](https://huggingface.co/BlinkDL/rwkv7-g1)：0.1–13.3B，Apache-2.0，2026-10-31 仍在更新，語言含 zh。卡片給創作建議 temp 0.6、top-p 0.6–0.8，有社群 GGUF；訓練資料未特別提中文小說，**卡片沒有中文小說證據**。
- 中文小說向 RWKV：[BlinkDL/rwkv-4-novel](https://huggingface.co/BlinkDL/rwkv-4-novel)（2023，舊世代）、[xiaol/rwkv-novel-agent-g1h-13b-ctx10240](https://huggingface.co/xiaol/rwkv-novel-agent-g1h-13b-ctx10240)（2026-07，下載 29）、[RWKV7-2.9B-UnlimitedRP-mini-novel](https://huggingface.co/mzwing/Seikaijyu_RWKV7-2.9B-v3-UnlimitedRP-mini-novel-chat-preview-GGUF)（2025，未讀卡）。都沒有品質證據。
- [Kimi-Linear-48B-A3B-Base](https://huggingface.co/moonshotai/Kimi-Linear-48B-A3B-Base) 存在（2025-10-30）；大小與可行性未查。
- ollama 支援原始續寫：`/api/generate` 的 `raw:true` 不套模板，由你提供完整 prompt，也不回傳 context — [ollama API 文件](https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md)
- ElisNovel 的行間填充（Q3）是另一種非指令介面，清空 system prompt，以 ollama `/api/generate` 服務。

### Inferences
- **指令外洩**在 raw 續寫中結構上不會發生，因為根本沒有指令〔推論〕。代價是作者的劇情約束只能放進前文或 few-shot。
- 一般的 chat 模型也能 `raw:true` 跑，不必為此換 base 模型，這是成本最低的試驗〔推論〕。
- 續寫模型會複製前文風格，所以用**人寫的繁中樣文**當前綴，可能同時緩解簡體混入與文風平。這與報告第四節「人類文本範例是下一個該試的方向」吻合，但尚未驗證〔推論〕。

### Gaps
- 找不到任何中文 base 模型續寫小說的比較資料。

---

## Q6. 實用設定：採樣、繁簡、繁中模型

### Takeaway
三件事立刻可做：明確設 `presence_penalty=0`、把預設參數寫進實驗紀錄、改用「只轉 Big5 之外的字」的繁簡後處理。**不要對全文直接跑 OpenCC**，實測多數改動都是誤傷。台灣繁中模型目前沒有寫作優勢的證據。

### Cited Findings
**採樣參數**

| 來源 | temperature | top_p | 其他 | 備註 |
|---|---|---|---|---|
| [wcn123 卡片](https://huggingface.co/wcn123/Qwen3.5-27B-WebNovel-Writer-zh) | 0.7 | 0.90 | repeat 1.10 | |
| [xianxia 卡片](https://huggingface.co/yuxinlu1/qwen3-6-27b-chinese-xianxia-lora-v2) | 0.7–0.85 | 0.85–0.92 | repeat 1.1–1.18；400–700 tokens | 必須關 thinking，否則可能以英文推理開頭；重複懲罰太高有人名同音漂移的風險 |
| [Xuanhuan 卡片](https://huggingface.co/JiangLing-js/Qwen3.8-27B-Chinese-Xuanhuan-Novel-Writer-DPO) | 0.85 | 0.90 | top_k 40；repeat 1.05 | thinking 關閉 |
| 作者目前 | 0.8（神秀實驗為預設 1） | 0.95（神秀實驗為預設 0.95） | repeat 1.0；**未設而繼承 presence 1.5、top_k 20** | 〔本機〕 |

- `think`：`/api/chat` 與 `/api/generate` 都支援布林值或等級；`min_p`、`num_ctx` 等走 `options`，未設的項目用模型預設 — [API 文件](https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md)。A/B 也確認了這個合併行為〔本機〕。
- `min_p` 預設 0 — [Modelfile 文件](https://raw.githubusercontent.com/ollama/ollama/main/docs/modelfile.mdx)。沒有任何小說模型卡推薦特定值。
- 文件互相矛盾：Modelfile 寫 `num_ctx` 預設 2048，context-length 頁寫 VRAM 低於 24 GiB 時為 4k。**一律明確設定**，別依賴預設。
- LoRA：Modelfile 用 `ADAPTER ./x.gguf`，底模與訓練時不同則「behaviour will be erratic」 — [Modelfile 文件](https://ollama.readthedocs.io/en/modelfile)。所以 xianxia LoRA 要配 Qwen3.6-27B，不能掛在 3.5 或 3.8 上。

**繁簡處理實測**〔本機〕（6 篇輸出，共約 4,700 字；OpenCC 用 opencc-python-reimplemented，即 repo 既有依賴）
- OpenCC [預定義配置](https://github.com/BYVoid/OpenCC)包含 `s2t`、`s2tw`、`s2twp` 等。
- `s2tw` 共改 22 字，其中真正的簡體或異體只有 7 字（`门 辩 双 衆 个 话 声`）。其餘屬誤傷：`台→臺`、`念→唸`、`哄→鬨`、`污→汙`、`戚→慼`、`仆→僕`、`划→劃`。
- `s2t` 更把 `群→羣`、`才→纔`、`唇→脣`。
- `s2twp` 還會做詞彙替換，把「天理**循環**」改成「天理**迴圈**」，**直接把小說改壞**。
- **Big5 過濾**：只找 `ch.encode("big5")` 失敗的字，在這 6 篇中**恰好抓到同樣那 7 個字，零誤傷**。做法：只把這些字送進 `s2tw`（或人工對照表），其他字一律不動。

**繁中模型**
- [taide/Gemma-3-TAIDE-12b-Chat](https://huggingface.co/taide/Gemma-3-TAIDE-12b-Chat)：官方，需同意條款（gated），授權 other。第三方 [Q4_K_M 8.17 GB](https://huggingface.co/audreyt/Gemma-3-TAIDE-12b-Chat-2602-GGUF)，可全進 VRAM。底模是 Gemma 3，世代較舊。
- [xCloudinfo/Gemma-4-26B-A4B-TAIDE-zhTW](https://huggingface.co/xCloudinfo/Gemma-4-26B-A4B-TAIDE-zhTW)：**社群衍生，非官方 TAIDE**，27,955 筆蒸餾資料的 LoRA SFT；[Q4_K_M 16.80 GB](https://huggingface.co/xCloudinfo/Gemma-4-26B-A4B-TAIDE-zhTW-GGUF)。定位通用對話，**沒有創作評測或樣本**。
- [Gemma-4-31B-xVITA-zhTW](https://huggingface.co/xCloudinfo/Gemma-4-31B-xVITA-zhTW-GGUF)：同一家，Q4 18.69 GB；未讀卡。
- Breeze：HF 搜尋只見 [Breeze-7B](https://huggingface.co/RichardErkhov/MediaTek-Research_-_Breeze-7B-Instruct-v0_1-gguf) 這類舊版，新的 Breeze 都是語音模型。
- Taiwan-LLM：[Taiwan-LLM-13B-v2.0](https://huggingface.co/mradermacher/Taiwan-LLM-13B-v2.0-chat-i1-GGUF) 等屬 2023–2024 年世代。
- [Tarklanse/Llama3-8B_Traditional_Chinese_roleplay](https://huggingface.co/Tarklanse/Llama3-8B_Traditional_Chinese_roleplay_chat_GGUF)：2024 年，下載 61，舊世代。

**建議起始設定**（數值組合是〔推論〕，個別依據見上表，需對照測試）
```json
{
  "think": false,
  "options": {
    "temperature": 0.8, "top_p": 0.9, "top_k": 40, "min_p": 0.05,
    "presence_penalty": 0, "repeat_penalty": 1.05, "repeat_last_n": 256,
    "num_ctx": 32768, "num_predict": 1000, "seed": 1
  }
}
```

### Inferences
- `presence_penalty=0` 省成本也合理，但別把它當解方：A/B 裡 pp=0 同樣有事件漂移。同一份 brief 在統計上要 n≥5 才看得出差異〔推論〕。
- 把長章拆成逐場景生成（400–700 tokens）是微調作者的共同建議，也可能是本機模型目前稿子偏短（報告記中位 1,643–2,340 字，要求 3,000）的實際解法。但這會改動實驗的因子〔推論〕。
- TAIDE 類模型或許能減少簡體混入，但沒有證據顯示文筆較好；用 Big5 後處理就能解決腳本問題，**不值得為此換模型**〔推論〕。
- Big5 過濾的盲點：Big5 外的合法繁體罕用字（人名常見）會被抓出，所以應列出來確認，或用白名單排除書中專名。這次樣本沒遇到〔推論〕。

### Gaps
- `think:false` 經由 ollama `/v1` OpenAI 相容端點的行為沒找到官方說明；既有腳本走 `/api/chat`，不受影響。
- `min_p` 與 `repeat_penalty` 對中文人名穩定性的影響，只有 xianxia 卡片的定性描述，沒有量測。
