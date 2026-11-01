# 先換流程再換模型：拆解 AI 腔五缺點

兩個判斷都只對一半。「prompt 只算緩解」成立，但要分開看：規則與禁令幾乎無效，刪掉 brief 裡的意義句和給人類片段則有明顯效果，內部最大的改善都來自這兩招。「模型太笨」也成立，但只解釋地板：Qwen 3.5 9B 的語意錯誤、事件漂移和照念角色卡確實是能力問題，而 A–E 在 Claude 和其他前沿模型上照樣存在，換大模型不會自動消失。所以我的建議是：新專案先用大模型加「短事件 brief、作者選的人類片段、多稿選優、人工修改」當基線，本機模型暫時只當實驗臂；Hugging Face 上有對準網文的微調模型，但沒有一支有盲評，不該現在押注。第一步也不是下載模型，而是作者回填現成的盲讀包，因為目前所有優劣判斷都出自 Claude。第二步花不到 2 美元跑 API 階梯，就能回答「太笨」問題。外部資料幾乎全是英文，沒有任何研究以 A–E 為結果變項，下面對應到 A–E 的部分多半是代理指標或我的推論，我會標明。

## prompt 的判決要分三種，模型的判決要分兩層

「prompt」其實混了三件事，證據方向各不相同。第一種是**規則與禁令**，這一種最差。內部實驗裡，「第二個句號改逗號」被照字面執行成一逗到底；神秀實驗明令禁止的段尾收束照樣出現（`01-結果報告.md`、`神秀實驗/01-結果.md`）。中文使用者的回報同型：固定禁用詞表會讓模型「换一个同构句继续出现」（[webnovel-writer #134](https://github.com/lingfengQAQ/webnovel-writer/issues/134)），也會「在其他地方钻空子」（[inkos #112](https://github.com/Narcooo/inkos/issues/112)）。Novelcrafter 測 Opus 5 也發現，換上專屬風格指南後壞習慣仍會回來（[Novelcrafter](https://novelcrafter.com/blog/opus-5-for-writers)）。

第二種是**控制輸入內容**，這一種對特定問題很有效。細綱寫了意義句，S1 有 3/3 的稿子照抄，拿掉後 0/3，Qwen 也一樣（`01-結果報告.md`）。第三種是**示範**，也就是人類片段與聲音卡。Claude 的問題總分從 S1 的 13 降到 5、S2 的 7 降到 3–5（`03-修復實驗結果.md`，每格 1 篇，Claude 讀者）。外部有個一致的訊號，「示範勝過指令」、長篇分析式風格指令在 11 個模型上都變差（[r/ClaudeAI 快照](https://reddit.sentinel-team.org/posts/1rxyz9s/snapshots/2026-03-20T20%3A10%3A12.107136Z)），但這是個案，**我沒有找到任何比較範例與禁令的受控實驗**，「樣本勝規則」只能算多方相信。

「解決不了」這半句也有外部支持。OLMo 同血統的逐階段實驗顯示，同一基底權重改用續寫指令，情緒負荷的跌幅約只佔整段後訓練跌幅的 17%，其餘來自權重；文風變異則光靠提示就能拉動（[Narrative Flattening](https://arxiv.org/html/2605.27878v2)）。最強的一筆是 Chakrabarty 的讀者研究：MFA 讀者對提示版的品質勝算比 0.13，對單一作者全集微調版 1.87，方向翻轉（[arXiv 2510.13939](https://arxiv.org/abs/2510.13939)）。這筆要打折：兩條件的作者集與模型集不同，並非隨機同組比較；只測到 450 字、只微調 GPT-4o，沒有獨立複製，也沒有量 A–E。神秀實驗的最佳稿「像同一位作者」6–6.5 分（原文基準 8 分），方向相同。

模型的判決分地板與天花板。**地板上，9B 確實太笨。**神秀三章都是 Claude 四篇全勝 Qwen 四篇，Qwen 的問題包括指示語漏進正文、事件走樣、人稱錯誤。這類錯誤可以直接核對，不靠口味，所以不太受「Claude 偏袒同門」影響。Qwen 也吃不到示範的好處：它把聲音卡當規格照念，Claude 則把卡片轉成行為。外部也有同方向的線索：Llama 3.1 因不擅長遵循長上下文指令被排除在微調研究之外（[arXiv 2510.13939](https://arxiv.org/html/2510.13939)），Verbalized Sampling 的多樣性增益在較大模型上約為較小模型的 1.5–2 倍（[Verbalized Sampling](https://arxiv.org/html/2510.01171)）。

但**內部的 Qwen 臂其實沒有在乾淨設定下跑過**。ollama 內建 `presence_penalty 1.5` 與 `top_k 20`，而我核對了 `code/run_ollama.py`、`code/fix_qwen.py` 和 `神秀實驗/code/run_qwen.py`，三支都沒有覆寫；神秀那支連 temperature 1 和預設的重複懲罰也一併繼承。固定 seed 的 A/B 確認 1.5 真的在生效，不過 pp=0 組同樣出現事件漂移，所以這解釋不了語意錯誤（3 seed、短 brief，樣本很小）。結論是 Qwen 沒被冤枉太多，但報告第六節該補記，下一輪也要固定參數。

**天花板上，太笨不是原因。**StoryScope 用五個 2026 年模型產出 61,608 篇（含人類對照），敘述者明說主題 AI 77%、人類 52%，模型指紋各異，但都留在同一個 AI 群內（[StoryScope](https://arxiv.org/html/2604.03136v6)）。另一份研究的 LLM 故事自相似多在 80–90%，人類 30.8%（[Same Stories](https://arxiv.org/html/2606.17350)），不過那是英文極短篇。LAMP 的編輯資料裡，Claude-3.5、GPT-4o、Llama 3.1 之間品質沒有顯著差異（[LAMP](https://arxiv.org/html/2409.14509v2)）。還沒人在中文小說上比較過同世代不同大小的模型，也沒人測過 9B 本身，這一點只能自己測。

## 業界賣的是聲音與連續性，沒有 A–E 的旋鈕

服務大致分三類。第一類是自訓模型加續寫：NovelAI 在文學語料上微調，彩雲小夢用自有架構做續寫（[NovelAI Journal](https://journal.novelai.net/inference-update-llama-3-erato-release-window-new-text-gen-samplers-and-goodbye-cfg-6b9e247e0a63/)、[量子位](https://www.qbitai.com/2024/11/218315.html)）。Sudowrite 的 Muse 也算半個，但基底與語料的公開說法含糊，唯一的成效數字「少 40% 修訂輪次」沒有方法與樣本（[Sudowrite](https://sudowrite.com/blog/sudowrite-muse-ai-writer-for-fiction/)）。第二類是多模型包裝加結構化 context，例如 Sudowrite 其餘模式與 Novelcrafter；InkOS、webnovel-writer、AI_NovelGenerator 這些中文開源專案也是這個形狀，重點都在記憶與一致性。第三類是本機與角色扮演生態的取樣器與模板。Sudowrite 的風格樣本明說是 context 注入，不是微調（[AI Voice Matching](https://sudowrite.com/blog/ai-voice-matching/)）。

從這些資料我讀出四點心得。**第一，沒有一家公開可覆算的散文評估，**中文市場也沒有任何降低 AI 味的對照資料，所以「某服務解決了 AI 腔」都無從驗證。**第二，產品機制碰不到敘事決策。**拆書與文風指紋抽的多是詞彙、句式、句長和段落節奏，而 A–D 是「敘述在做什麼」。我只找到一個明文控制對白比例的機制，是 SillyTavern 的一份社群 preset（[Sphiratrioth](https://huggingface.co/sphiratrioth666/SillyTavern-Presets-Sphiratrioth)），比例也只是作者自述。

**第三，開發者自己在轉向。**InkOS 較早版本有確定性後驗規則，現在的 deslop Skill 寫「Diagnose by reading function and effect, not by counting banned words」（[SKILL.md](https://github.com/Narcooo/inkos/blob/HEAD/packages/core/skills/inkos-story-deslop/SKILL.md)）。這是判斷轉向，沒有量測，但走到了本 repo 同一個結論。同時有使用者抱怨，完整的審查流程「会让不管什么ai最后都汇总成一个风格」（[#134 留言](https://github.com/lingfengQAQ/webnovel-writer/issues/134)），重流程可能反而加重 E，雖然這只是一則意見。

**第四，人工修改仍是所有非全自動流程的前提，但修多少沒有可信數字。**實作者自述是 AI 只佔一半（[CSDN](https://blog.csdn.net/huayishuo/article/details/149058446)），或改一篇 4000 字約 1 小時、與手寫差不多（[什麼值得買](https://post.smzdm.com/p/anvq62n7/)）。線編輯也有上限：對 278 篇 AI 故事套片段改寫，敘事分類器只從 95.5% 掉到 93.9%（[StoryScope](https://arxiv.org/html/2604.03136v6)）。

如果日後要上架，還有平台風險。起點 2026-08 清理了 27 本均訂過萬的書（[界面](https://m.jiemian.com/article/14971052.html)），「AI 佔比超過 10%」的門檻與新浪報導衝突，應視為未證實（[新浪](https://t.cj.sina.com.cn/articles/view/5182171545/134e1a99902002iffk)）。朱雀官方也承認有誤報（[新浪財經](https://finance.sina.com.cn/stock/t/2026-07-04/doc-inifrtka9308394.shtml)）。過檢測和 A–E 是兩個目標，新專案不該拿檢測率當實驗指標。

## 五個缺點要五種解法

下表的「主要施力點」是我綜合內外證據的判斷。外部證據沒有一項直接以 A–E 為結果，內部證據都是 Claude 讀者。

| 缺點 | prompt 能到哪 | 模型與權重的角色 | 主要施力點 | 證據強度 |
|---|---|---|---|---|
| A 替讀者下判決 | 輸入管制有效，禁令無效 | 跨模型都有 | 刪 brief 意義句＋人工修改 | 內部有對照，最強 |
| B 每句用力 | 示範部分有效，聲音卡反而加重 | 未知 | 分段生成、把過場當獨立任務 | 最弱，幾乎只有閱讀判斷 |
| C 不開口 | 可能大半可解，未測 | 多半不是能力問題 | brief 寫對白意圖、拿掉反向規則 | 機械可量，介入未測 |
| D 內心沒音量 | 聲音卡有效但有副作用 | 最可能需要改權重 | 聲音來源，其次微調 | 間接 |
| E 共用的梗與收束 | 生成端禁令無效 | 跨模型都有 | 多稿在選擇端淘汰 | 趨同有硬證據，解法沒有 |

### A：意義要留在討論層，事後靠人刪

A 是內部證據最完整的一項，也是目前唯一有對照的解法，brief 只寫發生什麼。但目標不是零：內部測到人類也解釋（自解釋率 3.27 對舊 AI 4.65），StoryScope 的人類也有 52% 明說主題（[StoryScope](https://arxiv.org/html/2604.03136v6)）。要抓的是類型，也就是替讀者下判決，不是所有解釋。

事後修改的部分，人有效、LLM 不行。專業作家的編輯有 18% 屬於「不必要解說」，但 LLM 刪解說只對「主句＋逗號＋解說」有效，跨句片段和揭示潛台詞都會失敗，偵測問題片段的精確率最高也只有 0.46，專家彼此是 0.57（[LAMP](https://arxiv.org/html/2409.14509v5)）。這和內部獨立刪句誤刪約 37% 同型，雖然精確率和誤刪率不是同一個指標。編輯分不出多餘的解釋和人物的聲音，所以新專案不要用獨立刪句 agent。InkOS 的語義問句（「Does the narrator explain an emotion already demonstrated?」）可以當人工修改的檢查單（[semantic-cleanup](https://github.com/Narcooo/inkos/blob/HEAD/packages/core/skills/inkos-story-deslop/references/semantic-cleanup.md)），但它沒有效果資料，其中「detail carrying evidence」還會鼓勵每個細節都要有功能，正好加重 B。

### B：平句可能要靠分工，不能靠要求

「細節必回收」和「沒有平句」沒有任何研究量過，內部也標明是閱讀判斷，這一項最需要作者親自判。有兩條線索。第一，中文作者的常見分工是關鍵對話親手寫、過渡交給 AI，而且認為 AI 過渡寫得順（[CSDN](https://blog.csdn.net/huayishuo/article/details/149058446)）。這和內部觀察相反，我猜差別在任務語境：模型拿到完整場景時把每段都當重點，只拿到過場任務時才放鬆。這是假說，Sudowrite 文件建議把 Haiku 用於過場算是相鄰的跡象（[Sudowrite docs](https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/which-ai-model-should-i-use/veMq9xRH6KLCQPFm5XkQx7)）。第二，流水線本身可能在懲罰平句：伏筆審計獎勵每個細節都有去處。WebNovelBench 的量表直接給修辭數量與感官頻率加權（[arXiv 2505.14818](https://arxiv.org/pdf/2505.14818v1)），等於獎勵 B，所以它的榜單不能拿來選模型。

微調的相關證據是負面的多：文學語料訓練的 Muse 最常被批評過度描寫（[UC Strategies](https://ucstrategies.com/news/sudowrite-review-i-tested-the-22-month-ai-against-chatgpt-across-70000-words/)，評測方法單薄）。聲音卡則明確加重 B，段尾短句比例到 0.46，人類是 0.13。選片段時要記得，模型連格式和腔調一起搬，片段幾乎一句一段，稿子的單句成段比例就到 0.98。

### C：別再教模型用手勢說話

這一項我最樂觀，因為多個線索指向預設與指示，不是能力不足。無對白標籤的三人對話 Sonnet 4.5 表現佳（[Novelcrafter](https://www.novelcrafter.com/blog/testing-sonnet-4-5-for-writing)），GPT-5 甚至偏對白重（[Sudowrite docs](https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/which-ai-model-should-i-use/veMq9xRH6KLCQPFm5XkQx7)）。而 StoryScope 的數字很值得注意：AI 以身體感受表達情緒 81%、人類 38%，人類直接標示情緒 29%、AI 8%（[StoryScope](https://arxiv.org/html/2604.03136v6)）。這表示「展示不要講述」已經是模型的預設，再加碼只會更偏。

中文流傳的去 AI 味規則（「不要有心理描写」「以人物的动作结尾」，[運營派](https://www.yunyingpai.com/personal/1029559.html)）和 C、D、E 的形狀高度吻合。Muse 也有用 "Show, Don't Tell" 類指令調校的說法（[Muse deep dive](https://sudowrite.com/blog/what-is-sudowrite-muse-a-deep-dive-into-sudowrites-custom-ai-model/)）。**我的假說是，業界最常見的處方正是這些缺點的成因之一。**這還沒有實驗，但很便宜就能測。反證也要留著：內部 A 臂沒有那些規則，對白佔字比也只有 0.15（人類 0.25）；內部報告也指出 brief 只列事件可能加重這個現象。

解法要小心兩個坑。對白比例若變成配額，模型會照字面打卡，內部已看過多次。AI 也不是單純少對白，而是對白功能不同，用於哲學辯論 59% 對人類 34%（[StoryScope](https://arxiv.org/html/2604.03136)），所以比例上去不等於好。**目前沒有任何介入被實測能提升對話比**，Agents' Room 的「更多對白」經不起它自己的表格（[Agents' Room](https://arxiv.org/html/2410.02603)）。最值得試的是神秀實驗提出的「對白只寫意圖，不寫可貼上的句子」，以及中文提案的「白話語義稿再人物化」（[#134](https://github.com/lingfengQAQ/webnovel-writer/issues/134)），兩者都未驗證。C 是唯一能純機械量的缺點，自己測的價值很高。

### D：最可能碰到權重的一項

D 幾乎沒人討論，連語彙都沒有。最接近的量測是後訓練把情緒壓平：New Yorker 語料上中性情緒人類約 29%、RLVR 約 45%，衝突約 20% 對 7.5%，而提示只能拉回一小部分（[Narrative Flattening](https://arxiv.org/html/2605.27878v2)）。這一項來自 OLMo，也沒有讀者驗證，但它是我把 D 排給權重的主要理由。社群一句「claude写出来很“稳重”，gemini就很有无脑爽文的感觉」（[linux.do，僅見搜尋摘要](https://linux.do/t/topic/3001833)）若可信，模型差異也主要落在這裡，階梯測試可以順便驗。

提示層面，聲音卡給出全實驗最好的句子（「煩惱落盡個鬼，煩惱明明多了一項。」），代價是發明情節、改人物、句句抖包袱。「假裝向朋友講故事」是外部唯一相鄰線索，來自單一作者、單一片段、GLM-4（[運營派](https://www.yunyingpai.com/personal/1029559.html)），也可能只帶來敘述者口語化，不是人物爆發。續寫路線要小心：基底模型情緒負荷與衝突會過衝（衝突約 47%），OLMo base 甚至寫不成連貫故事（[Same Stories](https://arxiv.org/html/2606.17350)）。敘述驚嘆號是內部最乾淨的分界（AI 0/56 篇，人類 11/13），但它是事後挑的，也會跟片段起舞，只能當監測，不要變成指示。

### E：在生成端禁不掉，要在選擇端淘汰

趨同有硬證據，而且已試過的解法多半失敗。讓模型看過先前所有故事並要求不同，整體多樣性幾乎沒改善；溫度和 top-p 對偏好微調模型大致無效（[Same Stories](https://arxiv.org/html/2606.17350)）；min-p 的優勢主張也被詳細反駁（[Min-p, Max Exaggeration](https://arxiv.org/html/2506.13681)，同儕狀態未核實）。換模型換的是指紋，不離開 AI 群。內部的「他以為下雨了」（3/6）和「我開玩笑的」（6/6）是同一件事的縮影。反應鏡頭、段尾收束和替讀者補洞則沒有直接量測，Antislop 能把可寫成 regex 的句型硬壓到 0，但吞吐降 69–96%，也只處理詞與片語（[Antislop](https://arxiv.org/html/2510.15061)）。

有用的是**選擇**。多候選選優在 MFA 作家的盲測裡有 66% 偏好，分差大時 72.2%，但作者自己說遠不及專家品質（[AI-Slop to AI-Polish?](https://arxiv.org/html/2504.07532)）。Verbalized Sampling 把嵌入多樣性提高 1.6–2.1 倍，但沒有在敘事相似度上驗證（[VS](https://arxiv.org/html/2510.01171)）。AI 裁判在這裡倒是可用，敘事相似三聯判斷上 GPT-5 與人類 81% 一致（[Same Stories](https://arxiv.org/html/2606.17350)）。所以我建議用同一 brief 生多稿，程式和 AI 找出稿間共有的點子當「模型預設清單」，由作者淘汰或換掉。這個組合是我的推論，沒人測過。

另一個槓桿來自神秀實驗的副作用：指示寫明的東西幾乎每篇照演（點名李白、兩根手指）。這在當時是毛病，但也表示作者自己的怪點子只要以事件形式放進 brief 就能存活。獨特性可能要由人從 brief 帶進來，不能指望模型產生。

## 11 GB 能跑的中文小說模型，全都沒有盲評

硬體已查實：RTX 2080 Ti 11,264 MiB、RAM 32 GB、ollama 0.40.13。先說結論：**沒有一支有輸出樣本或第三方評測，「比底模好」全是作者自述**，所以這是待測清單，不是推薦榜。下表速度除 9B 外都是推論，未實測。

| 用途 | 模型 | 檔案大小 | 預估 3,000 字 | 我的看法 |
|---|---|---|---|---|
| 微調·語料量最大 | [Qwen3.5-27B-WebNovel-Writer-zh](https://huggingface.co/wcn123/Qwen3.5-27B-WebNovel-Writer-zh) | [Q4_K_M 16.55 GB](https://huggingface.co/wcn123/Qwen3.5-27B-WebNovel-Writer-zh-GGUF) | 10–20 分鐘，分層 | 網文 SFT 20,320 筆，另有 8,000 組 ORPO；**僅限研究與個人使用** |
| 微調·題材對口 | [qwen3-6-27b xianxia LoRA v2](https://huggingface.co/yuxinlu1/qwen3-6-27b-chinese-xianxia-lora-v2)＋[底模](https://huggingface.co/unsloth/Qwen3.6-27B-GGUF) | 159 MB＋16.82 GB | 同上，宜逐場景 400–700 tokens | 只做 QLoRA、未做 DPO，比較貼近下述證據；adapter MIT，評測只有定性自述 |
| 快速對照·換血統 | [Gemma 4 12B](https://huggingface.co/unsloth/gemma-4-12b-it-GGUF) | Q4 7.12／Q5 8.41 GB | 1–2 分鐘 | 全進 VRAM；無中文小說證據 |
| 快速對照·MoE | [Qwen3.6-35B-A3B](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) | UD-Q4 22.13 GB | 約 2 分鐘（單一使用者回報的相近配置） | 需 llama-server，32 GB RAM 偏緊 |
| 續寫對照 | [Qwen3.5-9B-Base](https://huggingface.co/mradermacher/Qwen3.5-9B-Base-GGUF) | Q4 5.63 GB | 不到 1 分鐘 | 不聽大綱；一般模型用 [`raw:true`](https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md) 也能試 |
| 改寫器（非寫手） | [novel-humanize-4b](https://huggingface.co/gugujiji/novel-humanize-4b) | [Q4 2.59 GB](https://huggingface.co/bartowski/gugujiji_novel-humanize-4b-GGUF) | 很快 | CC BY-NC；可能刪細節，繁體未驗證，預期也碰不到 C、E |

我把 WebNovel-Writer-zh 和 xianxia LoRA 並列，沒有排先後，因為兩條依據互相矛盾。前者語料最多，但混了偏好訓練。而兩份獨立研究都顯示偏好微調會加重趨同：DPO 自相似高於 SFT（[Same Stories](https://arxiv.org/html/2606.17350)），DPO 在 LLM 判分下品質由 67.80 掉到 54.61（[Antislop](https://arxiv.org/html/2510.15061)）。ORPO 不等於 DPO，這只是警訊。不過這幾支模型的訓練資料多半來源未明，有背誦原著的風險，語料也是簡體，可能加重繁中混簡體。

不建議優先測的有這些：下載 195 萬的 [DavidAU 系列](https://huggingface.co/DavidAU/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF)是解除審查系列，沒有中文證據；[Qwen3.8-9B-…-Pro-Writer](https://huggingface.co/nuofang/Qwen3.8-9B-Distill-SLERP-F451-Pro-Writer-Uncensored) 卡片沒寫來源與方法；[ElisNovel](https://huggingface.co/cyanelis/ElisNovel-V3-32B) 的宣傳點是朱雀 AI 率為 0，那是偵測器指標，不是品質證據；[Sakura](https://huggingface.co/SakuraLLM/Sakura-14B-Qwen3-v1.5-GGUF) 是翻譯模型。繁中模型如 [TAIDE](https://huggingface.co/taide/Gemma-3-TAIDE-12b-Chat) 也沒有文筆優勢的證據。

混簡體用後處理解決，不需要換模型。本機實測只轉 `big5` 編不出來的字，6 篇恰好抓到全部 7 個簡體字且零誤傷；全文跑 OpenCC 多數是誤傷，`s2twp` 還把「天理循環」改成「天理迴圈」。Big5 外的合法罕用字要列出確認。取樣器的建議只有一句：明確設 `presence_penalty=0` 並把全部參數寫進紀錄，其他不值得花時間調，因為它不改敘事結構。

## 建議：新專案的基線與實驗順序

**帶進新專案的基線**是分層與分工。討論層用長 context；落筆層只給事件要點、對白意圖、事實摘要和作者挑的人類片段，不給意義句、不給 AI 寫的前文、不給行文規則清單。寫手先用大模型，每場景多稿，由人選；關鍵對話和內心戲由作者下手或重改；改完記錄工時。**不要帶過去的**有規則與禁詞表、全面性的「展示而非講述」、獨立刪句 agent、以檢測率或 WebNovelBench 當目標、DPO、取樣器調參。其中「展示而非講述」和分工順序都是推論，下表 3、6 會驗。

下表由便宜到貴，門檻都是我提的，建議開跑前先預註冊。所有實驗都只用獨立腳本與短 brief，放在實驗資料夾或新專案，不動本 repo 的系統層。

| 順序 | 實驗 | 怎麼跑 | 怎麼判 | 成本 |
|---|---|---|---|---|
| 0 | 作者回填盲讀 | 讀 `盲讀包/` 現成四包，每稿另外勾 A–E 五格；神秀稿補一包 | 作者與 Claude 排序不一致 → AI 讀者降為篩選，後面全以作者為準 | 作者閱讀時間 |
| 1 | 校正儀器 | Qwen 固定 `presence_penalty=0`、全部參數入紀錄、Big5 過濾；重跑 S1／S2 乾淨短 brief n=5 | 若與舊稿無差別，舊結論成立 | 幾分鐘 |
| 2 | API 階梯 | 同 prompt 跑 [10 支](https://openrouter.ai/api/v1/models)：9B → 27B／Gemma 31B／3.6-35B／3.8-27B → GLM／DeepSeek／MiniMax／Kimi → Claude，n=5；核對語意錯誤、事件漂移，加對白佔字比、否定手勢、段尾短句、跨稿撞梗 | 階 1 錯誤大減 → 9B 是瓶頸；階 2、3 才變好 → 走 API；階 3 仍犯 → 問題在流程 | 依筆記單價估每場景約 0.8 美元，兩場景不到 2 美元 |
| 3 | C、D 的成因與解法 | 最佳兩模型 × 四臂：基準／加「多動作、少心理、動作收尾」反向規則／對白意圖／先語義稿再人物化 | 反向規則臂明顯加重 → 假說成立；對白比接近人類 0.25 **且**作者盲讀不覺得灌水，才算有效 | 兩場景 n=5 共 80 稿，含 Claude 時最多約 4 美元 |
| 4 | 聲音來源組合 | 片段 V、卡片 P、V＋P、多本片段；片段與卡片都由作者挑或寫 | 看活人感與副作用（發明情節、單句成段、段尾短句） | Claude 每篇約 0.05 美元級 |
| 5 | E 的選擇端 | 同一 brief 各 10 稿：普通／Verbalized Sampling／多模型混合；三聯法量相似度，列撞梗清單，作者選稿對照隨機稿 | 自相似明顯下降且選出稿在盲讀勝出 → 納入流程 | 低 |
| 6 | B 的分段路由 | 同一章兩種生成：整場一次／重點與過場分開（過場可試小模型） | 作者盲讀「累不累」，雙人編碼平句數 | 低 |
| 7 | 權重 | 7a 現成微調＋續寫臂 vs 同底模提示版；7b 依 [Chakrabarty 回譯法](https://arxiv.org/html/2510.13939)自訓 SFT LoRA，對照提示版和實驗 4 最佳稿 | 微調版盲讀勝提示版 → 本地「太弱」的說法被削弱；無差別才算能力上限 | 下載 16 GB 以上、每篇估 10–20 分鐘；訓練與 GPU 租用未查價 |

有兩個分支要注意。微調是全部介入裡外部效應最大的，排最後只因它最貴、又要靠作者盲讀才判得準，還牽涉語料授權。**如果實驗 0 顯示作者對 Claude 最佳稿仍不滿意，應跳過 4–6 直接做 7。**反過來，若實驗 3、4 後作者覺得可用，7 就可以不做。自訓語料也要先想清楚：Chakrabarty 的下限是一位作者 2 本書，單本沒有證據；用他人作品只適合私下實驗，平台的[反洗稿公約](https://www.chinawriter.com.cn/n1/2025/0430/c404023-40471794.html)已明確針對 AI 洗稿。

評估方式應分三層：機械量測、A–E 的人工編碼，以及分讀者群的盲讀。分讀者群很重要，因為同一份提示版 AI 文字，MFA 讀者勝算比 0.13、一般讀者 1.82，方向相反（[arXiv 2510.13939](https://arxiv.org/abs/2510.13939)）。作者自評也不能單獨當標準：非小說的後編輯研究裡，受試者自覺與手寫一樣像自己，但主觀感受和量測僅 r=0.244（[arXiv 2604.24444](https://arxiv.org/html/2604.24444v1)）。

## 這份判斷可能錯在哪

**內部證據的最大限制是作者還沒讀。**所有優劣判斷都來自 Claude，盲讀每格 1 篇或 2 篇，Claude 讀 Claude 可能不敏感，也可能偏袒。LLM 零訓練裁判在人機配對上表現很差（[AI-Slop to AI-Polish?](https://arxiv.org/html/2504.07532)），不過直接的 AI 偏袒證據來自商品描述，不是小說（[AI AI Bias](https://arxiv.org/html/2407.12856v1)）。所以「Claude 有改善」的方向我信中等，幅度不信。Qwen 的語意錯誤可核對，比較穩。`01-結果報告.md` 第三節的 B、D 與驚嘆號指標是讀稿後挑出來的，只算線索。

**外部證據則有語言與取材缺口。**沒有中文網文微調加人類盲讀的研究，捷克語研究還顯示基底模型的可用性依語言而異（[Benchmark](https://arxiv.org/html/2509.10179v2)）。知乎、linux.do、龍空、小紅書和 B 站都未能取得一手內容，reddit 只讀到少數快照，社群證據偏薄不代表沒有討論。多數論文數字來自摘錄工具，未對照 PDF，要引為定論前應回查。另外本 repo 先前的技法驗證輪得出「輸入端載入 0.0、逐條自查 +2.0」（commit 訊息，本報告未細查），和「示範勝過指令」不完全同向，不宜直接合併；那一輪也可當實驗 4 之後的對照。

## Conclusion

這輪調查最大的改變是問題的形狀。原本的問題是「哪個 prompt 或哪個模型能消除 AI 腔」，但 A–E 其實落在不同層：A 在 brief，C 可能在我們自己給的處方，E 在選擇，D 可能在權重，B 還沒人知道。沒有單一解法能跨這些層，而外部最常見的處方（展示不要講述、以動作收尾、加審查關卡）有可能正在製造其中幾項。如果實驗 3 證實這點，那會是比任何模型推薦都有用的發現，而且公開資料裡沒有人測過。

另一個值得記住的是，這個市場沒有人公開可覆算的散文評估。作者手上已有預註冊、盲讀包、跨模型語料和可重現腳本，只差人類讀者。回填盲讀的價值因此高過任何一次下載，它決定後面所有實驗該信誰的眼睛。
