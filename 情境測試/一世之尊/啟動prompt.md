# 一世之尊 端到端貫穿測試 · 啟動 prompt（開新 session 複製用）

> 用法：開一個**乾淨的新 session**（或 `/clear`），把下面對應區塊的**程式碼框內容**整段複製貼上即可。
> 換別本書：把所有「一世之尊」改成該書名、`examples/一世之尊/卷一` 改成該書路徑（見 `../端到端貫穿測試流程.md` §10）。

---

## A. P session（前置，**只跑一次、必須最先**）

```
請讀 情境測試/端到端貫穿測試流程.md，執行 P session（前置，§6）：
為 examples/一世之尊/卷一 建立這套端到端貫穿測試的初始素材——
按 §4 切分原則產出 一世之尊/raw/ 與 情境測試/一世之尊/（刻意留 elicitation 缺口，
答案不要都塞進 raw），複製 書本模板/ init 一世之尊/ 書架，
並建 情境測試/一世之尊/session台帳.md（P 列標 ✅）。
```

## B. 標準 session（S1、S2、逐 arc……，**每次都貼這段**）

```
請讀 情境測試/端到端貫穿測試流程.md，照 §5 續跑協定開場三讀
（本 doc + 情境測試/一世之尊/session台帳.md + 一世之尊/story/參照/就緒儀表.md），
然後執行台帳「下一步」指定的 session。
過程守三角色硬防火牆（§3）：系統 agent 用冷 subagent、不得讀 examples/ 與 情境測試/；
作者 agent 的答案要標來源（腦／fallback:examples），fallback 記進 fallback-log.md。
收場二寫：更新 session台帳 + commit 書資料夾。
```

## C.（可選）指定範圍

想控制這個 session 只做某段時，在 B 後面**加一句**，例如：

```
這個 session 只做 arc01 的 beat-sheet + beat-test，不要往下寫正文。
```

---

## 三個實務注意

1. **每個 session 用乾淨對話**——導演 context 越乾淨，越不會把記得的原著情節注入。
2. **prompt 裡不要貼原著內容**——你只餵「跑哪個 session」，劇情由作者 agent 自己從 `情境測試/` 和 `examples/` 撈；一貼原著就繞過防火牆。
3. **收在乾淨的階段邊界**——context 快滿時讓導演「先收完這階段、寫台帳、commit」再停，別停在問作者問到一半（§5 鐵則）。
