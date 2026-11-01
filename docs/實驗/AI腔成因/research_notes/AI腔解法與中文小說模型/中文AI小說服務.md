# 中文 AI 小說服務與網文作者如何降低「AI味」（截至 2026-11-01）

**證據標記**：〔量測〕有資料與方法｜〔平台〕官方或媒體轉述的平台數字｜〔廠商〕廠商自述，有利益｜〔軼事〕單一或少數實作者自述｜〔行銷〕SEO／賣課／賣 API，應打折。
**缺陷標記**：〔A〕敘述替讀者下判語｜〔B〕句句用力，沒有平過渡句，細節全回收｜〔C〕人物不說話，靠沉默與手勢｜〔D〕內心沒有音量，敘述太鎮定｜〔E〕收斂到同一批梗，每個動作後接反應鏡頭，段尾收束，補邏輯洞。

**取材限制（讀者必看）**：知乎（403）、linux.do（403，含 JSON 端點）、36 氪（安全檢測頁）都讀不到原文；linux.do 的內容只來自搜尋摘要，樓層與發言人對不上。龍的天空、小紅書、B 站、r/LocalLLaMA 中文串未取得一手內容。一手材料主要是 GitHub issue 與 repo 內容（用公開 API 直接讀）、兩篇論文 PDF（已轉文字讀）、媒體報導。多數網頁經摘要工具轉述，引號內文字建議引用前回查。這個領域的 SEO 文極多，我已排除或標記。

## 各服務的機制：自研或套殼？續寫或指令？拆書／仿寫／微調？

### Takeaway
公開可查的自有文風模型只有彩雲小夢一條線。其餘中文產品與開源專案本質上都是「通用模型＋記憶／流程層」，文風手段集中在拆書模板與文風指南。**沒有任何一家公布過降低 AI 味的對照評估。**

### Cited Findings

**彩雲小夢（自有模型·續寫式）**
- 〔廠商〕V3.5 基於彩雲自提的 DCFormer 架構（論文發於 ICML，以動態組合注意力頭取代 MHA），前文上限由 2000 字升到 10000 字，官方稱流暢性與連貫性提升約 20%；同期「雲錦天章」定位為「小說續寫通用模型」，可大量換文風。報導未談訓練資料與續寫的技術實作 — [量子位 2024-11](https://www.qbitai.com/2024/11/218315.html)
- 〔軼事〕2022 下半年起使用率下滑，並對續寫與聊天加限制以推動付費 — [萌娘百科（搜尋摘要；頁面正文未能讀取）](https://zh.moegirl.org.cn/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6)
- 找不到 2025–2026 年關於彩雲小夢文風品質的可信實測，也找不到把它與 chat 模型對比的資料。

**閱文（作家助手／妙筆）**
- 〔平台〕2023-07-19 發布「閱文妙筆」大模型與作家助手妙筆版，功能為世界觀、角色設定、情景與打鬥描寫等 — [中國作家網](https://www.chinawriter.com.cn/n1/2023/0719/c404023-40039252.html)
- 〔媒體〕2025 年作家助手已接入 DeepSeek-R1。老作者說妙筆可作詞彙與素材輔助 — [鈦媒體](https://www.tmtpost.com/7496002.html)
- 自研程度與目前主力模型未查到權威說明。

**番茄（字節系）與七貓**
- 〔媒體〕2024 年番茄上線 AI 輔助工具，平台當時「率先支持」 — [21 世紀經濟報導／澎湃 2026-10-22](https://www.21jingji.com/article/20261022/herald/1303a2284f30b7adf9489422df448b79.html)；工具位於編輯窗口一側 — [新浪財經 2026-07-04](https://finance.sina.com.cn/stock/t/2026-07-04/doc-inifrtka9308394.shtml)
- 〔媒體〕七貓自帶文心一言助理，番茄作家助手有 AI 工具箱 — [鈦媒體](https://www.tmtpost.com/7496002.html)
- **未證實**番茄工具底層是否為豆包。早期內測報導未指名模型 — [人人都是產品經理](https://www.woshipm.com/ai/5988474.html)

**蛙趣拼文（流程層·可自帶 API Key）**
- 〔廠商〕素材庫把匯入文本拆成詞彙、句式、動作、環境、心理描寫與段落節奏模板；精修系統 22 套模板含「去 AI 味」 — [中華網商業快訊類轉載](https://m.tech.china.com/articles/20260513/202605131867065.html)
- 〔廠商〕作者揭露自己參與開發；「寫得自然一點」這種模糊指令無效，給具體參考素材較好；未描述完整仿寫機制 — [少數派 DraGonk](https://sspai.com/post/109785)
- 〔行銷〕同家自評的橫評把自家打到 9 分以上，沒有實測去 AI 味 — [GitCode/CSDN](https://gitcode.csdn.net/6a03289654b52172bc73865c.html)

**蛙蛙寫作、筆靈**
- 蛙蛙寫作：波形智能開發，創辦人姜昱辰（ETH 博士，自然語言生成方向），宣稱內建五千餘工作流；未見文風與模型資訊 — [AI 工具集](https://ai-bot.cn/sites/8204.html)、[BAAI](https://hub.baai.ac.cn/view/38987)（後者只讀到摘要）
- 筆靈：搜得到的幾乎都是導流測評，定位為一站式生成與續寫；**找不到底層模型的可靠資訊** — [搜狐導流文範例](https://www.sohu.com/a/962813677_414124)

**阿里系**
- 未找到阿里系專門面向小說的寫作工具的可靠資料；只有 Qwen 模型本身被社群討論。

**開源專案（GitHub API 2026-11-01 數字）**
- [YILING0013/AI_NovelGenerator](https://github.com/YILING0013/AI_NovelGenerator/wiki)：6,373 星。多階段生成、狀態追蹤、向量檢索；重點在一致性。使用者回報正文出現「在第xxx章主角說過」這類元敘述，且「AI味還是太濃重」，並要求加禁詞 — [issue #240](https://github.com/YILING0013/AI_NovelGenerator/issues/240)
- [MaoXiaoYuZ/Long-Novel-GPT](https://github.com/MaoXiaoYuZ/Long-Novel-GPT)：1,251 星，最後 push 2025-11-05。大綱→章節→正文的階層生成；issue 搜「文筆」只有一筆無關結果。
- [Narcooo/inkos](https://github.com/Narcooo/inkos)：10,952 星。`inkos style analyze` 把參考文本編成「有證據的可執行文風指南」，`style import` 綁定到作品。README 未附任何量化評估。〔A〕〔E〕相關的機制見下一題。
- [lingfengQAQ/webnovel-writer](https://github.com/lingfengQAQ/webnovel-writer)：7,768 星，跑在 Claude Code 上。`/webnovel-learn` 記錄書中技法到長期記憶，致謝 `oh-story-claudecode` 的拆書流程；有一步「Anti-AI 終檢」但未說明方法；無實測數據。
- **微調**：有人在 HF 討論用 Qwen3.5-4B-Base 對原始小說文本做不經 chat 模板的 LoRA（未見結果）— [HF 討論](https://discuss.huggingface.co/t/how-should-i-fine-tune-qwen3-5-4b-base-on-raw-novel-text-without-a-chat-qa-format/179431)。現成「人性化」LoRA 用的是約 1.8 萬條中文**學術**文本對，不是小說 — [Qwen3.5-9B-Humanize-SFT](https://huggingface.co/XiangJinYu/Qwen3.5-9B-Humanize-SFT)。

**拆文→仿寫的法律與平台風險**
- 〔平台〕2025-04 十六家平台發布《網絡文學行業反洗稿自律公約》，針對 AI 洗稿 — [中國作家網](https://www.chinawriter.com.cn/n1/2025/0430/c404023-40471794.html)
- 〔媒體〕2026-06「會說話的肘子」發起反抄襲倡議，800 餘位作家簽署，把「中譯中」融梗與 AI 洗稿列為抄襲演變階段 — [揚子晚報](https://www.yzwb.net/news/wy/202606/t20260608_360542.html)

### Inferences
- 產品的拆書／文風指紋抽的多是詞彙、句式、句長、段落節奏（統計表層）。這些維度**幾乎碰不到 A、B、C、D**，因為這四項是「敘述在做什麼」，不是「句子長怎樣」。對話比例本應可抽，但我看到的描述沒有明列。
- 流程層專案解決的是記憶與一致性，連帶把人力轉去補邏輯，這可能反而強化〔E〕的「補洞」與〔B〕的「細節全回收」：伏筆追蹤與審計會獎勵一切細節都有去處。這點未見資料證實，是推論。

### Gaps
- 番茄工具底層模型、筆靈底層模型、蛙蛙寫作目前模型：無可靠來源。蛙蛙／波形智能我記得曾發表寫作基礎模型 Weaver（2024 前後），本輪未核實，勿直接引用。
- 彩雲小夢的訓練語料與「續寫式是否 AI 味較少」：無資料。**「continuation 比 instruction 少 AI 味」在中文市場我沒有找到實驗證據**；只有 HF 帖的合理性論證。

## 2026 年中文網文作者推薦哪些模型？為什麼？有比較測試嗎？

### Takeaway
沒有共識，也沒有可信的中文網文散文對照測試。社群體感是「分工」：便宜模型起草，另一模型審或潤。常被提的是 Gemini、Claude、DeepSeek、Kimi、GLM，評價互相矛盾；版本更新也比口碑快。

### Cited Findings
- 〔軼事·僅搜尋摘要〕linux.do 多串：「写文是Gemini的强项，目前Gemini 4就是rp和写作的天花板」；反面「gemini写的太墨迹了 还是claude好用」；「claude写出来很“稳重”，gemini就很有无脑爽文的感觉」〔D〕；「deepseek有长文情况下段落回环格式复读八股文问题」〔E〕；GPT 普遍被說 AI 味重，但有人拿來審大綱與精修；常見分工是一模型做大綱審計、另一模型寫正文 — [主串](https://linux.do/t/topic/3001833)、[網文用什麼模型](https://linux.do/t/topic/2939965?tl=zh_CN)、[國產模型](https://linux.do/t/topic/2583618)、[寫作最好的 AI](https://linux.do/t/topic/3015981?tl=en)
- 〔軼事〕便宜是實際選型主因：「我也是因为deepseek v4 flash便宜才用的多，然后也是这个问题」；另有人能從文本一眼認出 v4 flash — [webnovel-writer #94](https://github.com/lingfengQAQ/webnovel-writer/issues/94)
- 〔軼事〕有使用者以 GPT 5.6 高檔寫神話題材，回報「機翻感特別嚴重」，提案者判斷問題主要在提示與流程、與單一模型無關 — [webnovel-writer #134](https://github.com/lingfengQAQ/webnovel-writer/issues/134)
- 〔行銷〕API 轉售站的推薦：Claude 文筆最穩、MiniMax 口語與對白強、DeepSeek V4 Pro 便宜但愛排比；自承星級是社區體感 — [island AI Coding](https://www.codex789.com/blog/best-ai-model-for-writing/)
- 〔行銷〕常被搜到的「橫評」系列把「煉字工坊」排榜首，出自同一作者，應視為廣告 — [CSDN 範例](https://blog.csdn.net/qq_18733629/article/details/161729438)
- 〔第三手量測〕轉引 EQ-Bench Creative Writing v3（2026-05）：Kimi K2.6 83.35（Slop 1.8）、DeepSeek V4 Pro 82.25（2.7）、GLM-5.1 81.30（3.3）、Qwen3.5 397B 80.00（3.4）、MiniMax M2.5 75.90（3.7）。該文未說明方法與語言，也沒有小說專項 — [創藝提示符](https://www.tishifu.cn/news/1526)。（我印象中 EQ-Bench 是英文基準，未核實；不能當中文證據。）
- 〔量測但版本老〕WebNovelBench 排名：Qwen3-235B-A22B 99.9%、DeepSeek-R1 99.5%、DeepSeek-V3-0324 98.7%、Claude 3.7 Sonnet 98.7%、Qwen3-32B 98.6%、GPT-4.1 98.2%；GPT-4o 69.1%、Doubao-1.5-pro-32k 31.1% — [arXiv 2505.14818](https://arxiv.org/pdf/2505.14818v1)（解讀限制見最後一題）
- 〔軼事〕單一 Reddit 使用者稱 GLM 是非英語角色扮演唯一可靠者 — [快照](https://reddit.sentinel-team.org/posts/1rgwkn5/snapshots/2026-03-02T19%3A46%3A37.091087Z)

### Inferences
- 社群選模型的標準主要是價格、長上下文與「讀起來像不像人」的體感，不是 A–E 這類結構性缺陷。把模型榜單當成解法，對本實驗的缺陷大概率沒有鑑別力。
- 「Claude 穩重／Gemini 無腦爽」若可信，模型差異可能主要落在〔D〕音量，值得自己盲測；目前只是一句話的證據。

### Gaps
- 沒有找到以同一網文大綱、盲讀、人類評分比較 2026 模型的測試。
- 上面出現的模型版本名多來自轉述，本輪未逐一核實其存在與發布日期。

## 哪些去 AI 味手法被回報有效或失敗？規則清單 vs 樣本的證據

### Takeaway
最有力的一致訊號是**否定性的**：詞表與表層規則會被「換個同構句」繞過，約束過多則變流水賬，單純 humanizer 改不了長篇。樣本優於禁令的說法到處都有，但**全是軼事或廠商說法，沒有對照實驗**，而且樣本也有漂移。直接處理 A–D 的經驗非常少，社群主流語彙仍是「檢測率」和句式。

### Cited Findings

**規則／詞表失敗**
- 〔軼事·具體〕提案者列舉試過而不足的三案：只在潤色階段修（「初稿已經丢失言语行为时，润色很难知道应该补回哪一种意思」）；固定禁用詞表（「误报率高，也会让模型换一个同构句继续出现」）；強加口語詞、停頓詞或單句段（「可能进一步加重碎句和伪口语」）— [webnovel-writer #134](https://github.com/lingfengQAQ/webnovel-writer/issues/134)〔B〕〔C〕
- 〔軼事〕「可以禁止一些作者介入词，程度副词之类的，但它会在其他地方钻空子」，章節間逐步飄移「直到完全飘到AI味且绕过审计」 — [inkos #112](https://github.com/Narcooo/inkos/issues/112)〔A〕
- 〔軼事〕「用这套 感觉写出来的都是流水账 可能太多约束了」 — [webnovel-writer #3](https://github.com/lingfengQAQ/webnovel-writer/issues/3)
- 〔軼事〕「现在的检测机制过于死板了…完整的流程会让不管什么ai最后都汇总成一个风格」 — [#134 留言 2026-08-14](https://github.com/lingfengQAQ/webnovel-writer/issues/134)〔E〕：審查流程本身可能造成收斂。
- 〔軼事〕Humanizer Skill 下載逾 12 萬次；使用者稱改後仍有 AI 味，「AI会创造新的套路」 — [新浪財經](https://finance.sina.com.cn/stock/t/2026-07-04/doc-inifrtka9308394.shtml)；另一人測朱雀由 60% 變 100% — [#3](https://github.com/lingfengQAQ/webnovel-writer/issues/3)；「面对连续的长文本…做不到完全消除AI味」 — [humanizer-zh-update #1](https://github.com/Ttungx/humanizer-zh-update/issues/1)
- 〔專案設計轉向〕InkOS 較早版本有 11 條確定性後驗規則與統計指紋（[v0.4 fork](https://github.com/liunix61/inkos)，僅搜尋摘要）；目前 README 明言「不會由隱藏詞表自動改稿」，其 deslop Skill 寫「Diagnose by reading function and effect, not by counting banned words」，且「Do not mechanically delete transitions, metaphors, three-part lists」 — [SKILL.md](https://github.com/Narcooo/inkos/blob/HEAD/packages/core/skills/inkos-story-deslop/SKILL.md)。這是開發者的判斷轉向，不是量測。
- 〔軼事〕審計與文風控制本身可能失效：審計標出情緒直述，修訂後問題依然存在，違反「展示，不告知」 — [inkos #194](https://github.com/Narcooo/inkos/issues/194)〔A〕

**樣本錨定：有改善，但無對照**
- 〔軼事·最具體〕「我目前的做法是选了前四章，每个章节随机连续的150字，四个章节600字，让它仿照风格写每一章」，稱「可以有所改善」；同時指出「单靠prompt彻底解决貌似不太行」，且正反例結構化指導也會飄 — [inkos #112](https://github.com/Narcooo/inkos/issues/112)
- 〔廠商／行銷〕模糊指令無效、具體參考較好 — [少數派](https://sspai.com/post/109785)；給三五段自己的文字比羅列禁令有用 — [island](https://www.codex789.com/blog/best-ai-model-for-writing/)；[CSDN](https://blog.csdn.net/ksueh/article/details/163708159) 同說。三者都沒有資料。
- 〔軼事〕用了文風模仿「看起来比直接ai好了很多倍」，檢測率仍爆；不同題材從很低到 100% 不等 — [inkos #75](https://github.com/Narcooo/inkos/issues/75)。讀感與檢測率是兩回事。
- 〔軼事〕給模仿名家：魯迅風格不穩定 — [運營派（GLM-4，約一年前，單段測試）](https://www.yunyingpai.com/personal/1029559.html)

**流程類手法，對應本實驗缺陷**
- 〔B〕〔C〕**先白話、再人物化**：「白话语义稿：先写清谁对谁做什么、为什么，以及对白在完成什么言语行为」，再「按身份、关系、场景压力和题材风格压缩」，並要求只為關鍵交涉寫 5–8 條語義骨架；還指出「短段落 / 短句 / 留白」只能是排版偏好，「不能授权删除语义」，並點名電報體與「不是 X，是 Y」成組出現。例：「你有。」「三息。」這種含義懸空的金句化對白 — [#134](https://github.com/lingfengQAQ/webnovel-writer/issues/134)。**僅為提案**，維護者表示將部分納入 v7，兩遍起草擬按高風險風格條件觸發；尚無效果資料。
- 〔B〕〔E〕DeepSeek 提示思路：「不要让AI扮演研究者，让AI扮演人物进行推演」；「不要『先射箭再画靶』…每个人物所说的话、做的事一定要是他认知范围内的」；「先快速铺无关紧要的情节，然后再对高潮情节进行设定」；把犯過錯的句子原文列給它看並禁止。自述結果是檢測落到「疑似」，「还是得手工改」 — [#3 留言 2026-03-27](https://github.com/lingfengQAQ/webnovel-writer/issues/3)
- 〔B〕〔E〕「主要是爽点和钩子出现的位置太工整」；「写得太工整了…每章开始都是几月几日」 — [#3](https://github.com/lingfengQAQ/webnovel-writer/issues/3)
- 〔A〕語義層檢查問題：「Does the narrator explain an emotion already demonstrated?」「Could the sentence fit any character or story unchanged?」「Is detail carrying evidence, relationship, pressure, or voice?」「Is dialogue motivated, or is it disguised exposition?」，並列 unsupported conclusions、repeated interpretation、decorative detail — [InkOS semantic-cleanup.md](https://github.com/Narcooo/inkos/blob/HEAD/packages/core/skills/inkos-story-deslop/references/semantic-cleanup.md)。無效果資料。注意其中「detail carrying evidence」對〔B〕的方向是相反的：它鼓勵細節都要有功能。
- 〔D〕〔C〕**唯一對準口吻的測試**：「假装你正在向朋友讲故事，请以此口吻改写以下内容」單項最好；「扮演專業網文作者」只減少冗餘，書面化依舊；條列約束會口語化，但句式重複明顯；角色＋約束＋「因为你正在向朋友讲述这个故事」綜合最佳 — [運營派](https://www.yunyingpai.com/personal/1029559.html)。單一作者、單一片段、GLM-4，證據弱。
- 〔C〕〔A〕廣泛流傳的反向規則（同一篇）：「不要用叙述性的描述，多使用对话、动作描写、细节描写、环境描写」「结尾处不要有抒情、内心独白、展望未来的内容，以人物的动作结尾」「不要有心理描写」 — [運營派](https://www.yunyingpai.com/personal/1029559.html)
- 〔C〕提示結構「場景發生了什麼＋人物當下感受＋要做的動作或決定」，把「不懷好意」改成「靠在椅子上笑」就更有生氣；同一作者說 AI 對話「像智能客服」，改為只讓它寫事件、語氣和情緒自己補 — [CSDN「軒軒分享AI」](https://blog.csdn.net/huayishuo/article/details/149058446)
- 〔C〕關鍵對話和衝突親手寫、過渡段交 AI，是反覆出現的分工 — 同上；[網文作者新裝備（搜尋摘要）](https://www.tahou.com/article/204598985611333637)。值得注意：**〔B〕的平過渡句，作者們反而認為 AI 寫得順**，與本實驗觀察不同，可能因為他們是把 AI 當過渡工具用、提示語境不同。
- 〔E〕模型預設收斂的具體例：「ai取名不是陈默就是沈默」 — [#94](https://github.com/lingfengQAQ/webnovel-writer/issues/94)；化名作者程淼「刻意避開腦中最先浮現的詞」並先給別人讀 — [新浪財經](https://finance.sina.com.cn/stock/t/2026-07-04/doc-inifrtka9308394.shtml)；章節標題對稱結構趨同，如「寒夜与陵园」「铁门与暗影」 — [inkos #170](https://github.com/Narcooo/inkos/issues/170)
- 〔輸入污染〕「输入的ai味就要控制，目前该系统的根据纲章大纲的提示写任务书，这个就是ai味足，可以在这一层去除ai味」 — [#3 留言 2026-05-06](https://github.com/lingfengQAQ/webnovel-writer/issues/3)。與「上游任務書的文體會傳染正文」這個假說相關，只是一句自述。
- 〔編輯／作者判斷〕「咸魚軍頭」：AI 詞彙豐富，但「无法把控网文的节奏、读者的爽点」；讀者把「剧情停滞、原地大段描写」視為 AI 訊號；例句「如同一幅未完成的肖像，隐藏着某些无法探知的秘密」〔A〕 — [鈦媒體](https://www.tmtpost.com/7496002.html)

### Inferences
- **民間處方很可能正是〔C〕〔D〕的成因之一。**「多動作、少敘述、不要心理描寫、以動作收尾」與本實驗缺陷的形狀高度吻合：不准內心獨白→沒有音量〔D〕；以動作結尾→手勢與反應鏡頭、段尾收束〔C〕〔E〕；不准敘述→沒有平過渡句〔B〕。這些規則本來是拿來解〔A〕和「抒情總結」的，副作用恰好相反。這是我的推論，未有實驗；但本 repo 的 `write` 自己也有「展示而非講述」，值得列為待測假說。
- 〔A〕最接近的解法是語義層提問，而〔B〕最接近的是「先白話再人物化」與「先快速鋪無關情節」。兩者都未被量測。
- 〔D〕幾乎無人討論。中文社群說「口語化」「人味」，但沒有人提出「主角要脫口而出」這個機制。「向朋友講故事」是唯一相鄰線索，也可能只是敘述者口語化，未必帶來人物的爆發音量。
- 〔E〕提示流程愈重，收斂可能愈強（#134 留言）。若屬實，多代理審計管線對〔E〕是淨負面；僅一則意見。
- 「樣本勝規則」應降級表述為「多方相信、無對照」。本實驗若能跑盲讀對照，在這個市場就是稀有證據。

### Gaps
- 沒有任何一篇提供規則 vs 樣本的對照實驗（盲讀或可覆算）。
- 「喂爆款前三章→仿寫」的具體 prompt 與成效：只找到賣課與工具文，沒有可信的實作復盤。
- 知乎〈AI写小说怎么去除AI味（我实测过的方法）〉與〈怎样摆脱“机器味儿”〉讀不到全文，僅從搜尋摘要知道它主張去排比成語、分輪改、開頭與高潮自寫 — [知乎](https://zhuanlan.zhihu.com/p/2071744201377818281)。
- 小紅書、B 站、龍空的具體經驗本輪無法取得；這些地方可能有比 GitHub 更貼近爽文實作的說法。

## 商業成功作者回報多少人工修改？平台政策與 AI 偵測如何影響？

### Takeaway
**沒有可信的「成功作者修改比例」數字。**實作者的自述是修改時間接近手寫或 AI 只佔一半。2026 年平台急遽收緊，起點已動到均訂過萬的頭部書；偵測器易誤傷也易被形式變動騙過，所以「過檢測」與「讀者覺得好看」不應混為同一目標。

### Cited Findings

**修改量（皆軼事，樣本小）**
- 第一天 AI 寫約 3000 字，刪 2000、改 1000，實發約 1200；後來日更 3000 字中約 1500 為 AI 起草 — [CSDN](https://blog.csdn.net/huayishuo/article/details/149058446)（未推銷付費品，但頁面旁廣告多）
- 一位寫起點的作者：改一篇 4000 字 AI 稿約 1 小時，與手寫差不多；19 歲博主實操 100 天，番茄一本，上月全勤加分成 2847 元、每天約 2 小時。該文整理約 18 篇曬收益帖，多數大數字屬賣課漏斗 — [什麼值得買](https://post.smzdm.com/p/anvq62n7/)
- 「百分百靠AI生成不现实」「还是得手工改」 — [#3](https://github.com/lingfengQAQ/webnovel-writer/issues/3)；「真正正儿八经的小说，谁会全文ai啊」 — [#94](https://github.com/lingfengQAQ/webnovel-writer/issues/94)
- 「AI 輔助需 ≥30% 人工加工」「200+ 維度檢測」等數字只見於自媒體，**無官方出處，勿引用** — [今日頭條範例](https://www.toutiao.com/article/7626281118299357747/)

**起點／閱文**
- 〔媒體〕2026-04 公告：針對經核實的非真人自動化批量生成，暫停推薦、撤榜、屏蔽或下架，並按月公示典型案例 — [新浪 2026-08-19](https://t.cj.sina.com.cn/articles/view/5182171545/134e1a99902002iffk)
- 〔媒體〕2026-08-18 清理：27 本均訂過萬下榜，月票榜前 1000 約 100 本被清，含《我加載了神秘學面板》《山河鑑》。作品可更新可付費，但出榜、不再有新用戶分發。有作者稱「解脫了，像逃犯落網」 — [界面](https://m.jiemian.com/article/14971052.html)
- **來源衝突**：界面轉述平台「AI 生成內容佔比超過 10% 即觸發」；新浪同期報導稱平台尚未公布明確比例標準 — [界面](https://m.jiemian.com/article/14971052.html) vs [新浪](https://t.cj.sina.com.cn/articles/view/5182171545/134e1a99902002iffk)。10% 應視為未證實。

**番茄**
- 〔平台〕2026-02 處置違規帳號 855 個；2026-05 拒簽低質書 11.27 萬本；2026-06-25 調整推薦驗證流程（3 次機會）；2026-07 拒簽 AI 生成及空洞水文類 16 萬本、處置近 5.4 萬本 — [21 世紀經濟報導](https://www.21jingji.com/article/20261022/herald/1303a2284f30b7adf9489422df448b79.html)、[新浪財經](https://finance.sina.com.cn/stock/t/2026-07-04/doc-inifrtka9308394.shtml)、[新浪 8-19](https://t.cj.sina.com.cn/articles/view/5182171545/134e1a99902002iffk)。月份與數字在各家報導略有出入（另有 6 月 10.4 萬之說，[GIGAZINE 轉 Rest of World](https://gigazine.net/gsc_news/en/20260707-china-ai-web-novels/)）。
- 〔媒體〕2026-10：Lv.0／Lv.1 新建作品只能「完本簽約」，須依分類寫滿 15 萬或 30 萬字才可申請，簽約前不展示、無稿費；判定手段列技術監測、人工審核、讀者舉報。前 HR（匿名）稱主要由 AI 判斷 — [21 世紀經濟報導](https://www.21jingji.com/article/20261022/herald/1303a2284f30b7adf9489422df448b79.html)
- 〔未證實〕2026-06-10 公告 49 位金番作者受罰、17 帳號永封，僅見於賣工具的馬良寫作，且標題 15 萬與內文 4 萬自相矛盾 — [馬良寫作](https://maliangwriter.com/zh-hant/blog/fanqie-ai-crackdown-2026-guide/)

**其他平台與法規**
- 晉江 2025-02-17 試行公告，AI 限於資料查詢與校對類，違者鎖章、永久禁榜 — [鈦媒體](https://www.tmtpost.com/7496002.html)、[GIGAZINE](https://gigazine.net/gsc_news/en/20260707-china-ai-web-novels/)
- 七貓、起點編輯公開發過拒收 AI 文聲明；部分編輯要求投稿前做 AI 率檢測並改到通過 — [新浪財經](https://finance.sina.com.cn/stock/t/2026-07-04/doc-inifrtka9308394.shtml)

**偵測器的可靠度（軼事與官方自承）**
- 長篇作者稱未用 AI，6 月中被從推薦消失，客服判「低質水文」且不給依據；朱雀官方自承「存在一定的误报可能性」 — [新浪財經](https://finance.sina.com.cn/stock/t/2026-07-04/doc-inifrtka9308394.shtml)
- 「朱雀检测我用同样的文本，只要把空行删掉，就能从 100%AI特征 -> 100%疑似AI」 — [#94](https://github.com/lingfengQAQ/webnovel-writer/issues/94)（單一使用者，未重現）
- 讀者實際辨識線索：提示詞殘留、不自然比喻、重複表達 — [GIGAZINE](https://gigazine.net/gsc_news/en/20260707-china-ai-web-novels/)；另有人從計數錯誤認出（台詞字數寫錯）— [新浪財經](https://finance.sina.com.cn/stock/t/2026-07-04/doc-inifrtka9308394.shtml)

### Inferences
- 平台標準不透明且偏向帳號、規模與低質行為，不是句法指紋。社群因此把「過朱雀」當代理目標，但其與讀感相關性存疑（#75、#94），也與本實驗要解的 A–E 不是同一件事。
- 起點清理打到均訂 3 萬級作品，可推知至少有部分高訂閱書大量用 AI，而讀者照買；但這不告訴我們它們人工改了多少。

### Gaps
- 沒有任何已驗證的頭部作者公開其 AI 比例與修改工時。
- 番茄、起點的原始公告本輪未取得，上述皆為媒體轉述。
- 偵測器準確率：只有廠商或工具商的數字（如「95%」），無獨立評測。

## 有沒有已發表的中文小說品質評估或基準？

### Takeaway
有兩個值得知道的學術基準。**WebNovelBench 的量表獎勵修辭與感官密度，方向可能與本實驗的缺陷相反**；ChangJuan 評的是「給現成書打分」，不是生成。兩者都無法測 A–E。

### Cited Findings
- 〔量測〕**WebNovelBench**（EACL 2026 Findings）：4000+ 部中文網文（各逾萬讀者），大綱→故事任務；評審為 DeepSeek-V3（LLM-as-Judge），八維經 PCA 與 ECDF 映射為相對人類的百分位；測 24 模型，每模型 100 部×10 樣本。八維與權重：D1 修辭手法的**數量**與品質 0.1304、D2 感官細節頻率 0.1160、D3 角色存在感（含對話比例、心理深度）0.1152、D4 對白區別度 0.1171、D5 角色一致 0.1377、D6 氛圍與主題契合 0.1290、D7 語境適切 0.1281、D8 場景銜接 0.1263。頂尖模型「near-perfect」，作者結論是已達網文頂層水準 — [arXiv 2505.14818](https://arxiv.org/pdf/2505.14818v1)、[ACL Anthology](https://preview.aclanthology.org/credits/2026.findings-eacl.94)
- 〔量測〕**ChangJuan**（ACL 2026 Findings）：300 部近五年長篇，配豆瓣評分與評論，蒸餾為優缺點共識；評的是模型與人類評分的相關。Kendall τ：GPT-5 45.6、DeepSeek-Chat 41.7、GPT-4o 40.1、Qwen3-8B 24.8，微調後的 CLEM-8B 34.1（表格欄位由我依 PDF 排版對齊，摘要中 24.8→34.1 已核對，其餘回查原表）— [ACL Anthology PDF](https://aclanthology.org/2026.findings-acl.2044.pdf)
- 〔量測〕**Towards A "Novel" Benchmark**（ACL 2025 Findings）：含中英文人類、模型與人機協作長篇；模型在前 40–60% 表現較好，其後下降（僅讀搜尋摘要）— [ACL Anthology](https://preview.aclanthology.org/display_plenaries/2025.findings-acl.1114.pdf)
- 〔量測〕**LFED**（2024）是長篇文學理解題庫，不評生成 — [arXiv 2405.10166](https://arxiv.org/html/2405.10166v1)

### Inferences
- WebNovelBench 上 Qwen3-235B 高於 99.9% 的人類網文，很可能反映量表與評審口味，而非真的寫得更好：D1、D2 直接獎勵修辭和感官**頻率**，等於獎勵〔B〕；評審自身是 LLM，且前段名次多為 Qwen 與 DeepSeek 系（論文解讀為開源追上，也可能含評審偏好，論文對此未排除）。D3 把對話比例與「心理深度」混成一格，測不出〔C〕〔D〕。**不要把這個榜單當「寫得像網文」的證據。**
- 真實網文的平過渡句在這份量表裡會被扣分，這是可檢驗的預測：拿本 repo `corpus` 中真人平淡段落與 AI 稿給同一量表，若真人較低即證實量表反向。

### Gaps
- 未找到以人類盲讀評中文生成小說的公開基準，也未找到測量敘述判語、對話比例、內心爆發這類維度的基準。
- WebNovelBench 只讀了 2025-05 的 v1，EACL 版與線上榜單是否更新未核對；榜單未含 2026 模型。
