# 外部小說寫作軟體調查

**這份調查回答的問題**：市面上的小說寫作軟體，為了輔助寫作，實際維護了哪些資料夾與檔案？哪些東西大家都有（＝大概真的必要），哪些東西只有本系統有（＝自造成本）？

**調查動機**：現行系統把大量 token 與時間花在「保證檔案彼此不矛盾」與「把設定源檔展開成 LLM 衍生分析」，但這些成本對內容寫作與劇情發想的貢獻不高。為避免憑空提煉時被現行設計綁架，先看別人怎麼做。

**調查日期**：2026-08-10。**本輪只落研究資料，不含任何精簡決策。**

## 一頁結論

1. **結構化的天花板比想像中低。** 全部工具裡唯一被普遍結構化的劇情層欄位，是**每個場景一句 synopsis**；其餘全是自由散文卡片。
2. **沒有任何一家做「源檔 → LLM 衍生分析檔」的重生機制。** 也沒有任何一家做 hash 新鮮度、格式 lint、或裁決治理層。這四樣是本系統獨有的。
3. **角色／物件狀態隨章變化，主流答案是「不特別記錄」。** 有做的，要嘛極輕量（Novelcrafter 的 progression：一行自由文字＋生效場景＋add/replace），要嘛由**確定性程式**從正文維護（蛙趣拼文、oh-story 的 `tracking_commit.py`）。
4. **伏筆的資料模型只有三格**：埋在哪／收在哪／收了沒。而且**不需要跟設定檔同步**。
5. **AI context 的共同形狀是「偵測式注入 ＋ 摘要鏈」**，不是「全量載入 ＋ 保證正確」。
6. **最重要的一個對照**：同類的 Claude Code skill 包（`oh-story-claudecode`）用「單一 JSON 真相 ＋ 語意交易單一寫入口 ＋ 提交時驗證 ＋ 確定性渲染 ＋ 每支檔的位元組硬上限」，把守衛收成 **1 支**。它並沒有把 LLM 趕出去——狀態內容仍是 LLM 產的，但只能從一個窄口進去。**本系統 12 支閘門的根源是「寫入口有 12 個」，不是「檔太多」；砍檔本身不會讓成本線性下降。**
7. **一個被外部佐證、不該砍的原創**：`角色/<名>/水下.md` 的劇透隔離。oh-story 特地把時間線分成「作者真相／讀者已知」，Novelcrafter 有 `never include` 開關，馬良框架把「不要餵有可見性限制的資訊」列為明確禁令。

## 指路

| 檔 | 回答什麼 |
|---|---|
| [01-工具總覽.md](01-工具總覽.md) | 9 個工具各自結構化了什麼、一致性怎麼保證；跨工具最小共同核心；「大家都沒有」清單 |
| [02-機制拆解.md](02-機制拆解.md) | 五個機制的實作細節（摘要鏈／偵測式注入／progression／伏筆／同儕 skill 包）＋踩雷回報 |
| [03-對照與推論.md](03-對照與推論.md) | 對照現行系統的保留／質疑／降級三欄，＋可直接移植的招數 |
| [04-精煉提案.md](04-精煉提案.md) | **（2026-08-10 加）** 把外部資料對回本 repo 實測數字後的精煉提案：該保存哪些檔、每支檔的位元組上限、檔案結構要有的七個性質。**是提案不是決策** |

## 被調查的對象

- **歐美傳統**：Scrivener、Plottr、Campfire Writing、Obsidian 各家小說 vault 範本
- **AI 原生**：Novelcrafter、Sudowrite
- **中國網文**：閱文作家助手·妙筆、橙瓜碼字、筆落寫作、蛙趣拼文
- **同儕（markdown ＋ Claude Code skill 包）**：`worldwonderer/oh-story-claudecode`、`xindoo/sumeru`、馬良長篇框架

## 引用來源

- Scrivener：literatureandlatte.com／scrivenervirgin.com／jenterpstra.com
- Novelcrafter：novelcrafter.com/help（codex-types、codex-tracking、progressions-additions、guidelines-for-descriptions、prompt-functions、codex-context-in-prompting）、docs.novelcrafter.com（planning-with-the-matrix）、courses（codex-cookbook）
- Sudowrite：docs.sudowrite.com、sudowrite.com/blog
- Plottr：docs.plottr.com（timeline、plotlines、series-view）
- Campfire：selfpublishing.com（17 模組拆解）、campfirewriting.com
- Obsidian vault 範本：loreteller.com、pdworkman.com、github.com/rrbaker/obsidian-novel-starter-vault
- 閱文作家助手·妙筆：finance.sina.com.cn、pingwest.com、zuojiawrite.hl.cn
- 橙瓜碼字：douban.com/note/763246157、jingyan.baidu.com
- 筆落寫作：pendown.cn ／ 蛙趣拼文：waqupin.com
- 同儕系統：github.com/worldwonderer/oh-story-claudecode、github.com/xindoo/sumeru、maliangwriter.com/blog/ai-write-long-novel-framework
- 一致性實測與 story bible 慣例：novarrium.com、rivereditor.com、novela.so、janefriedman.com
