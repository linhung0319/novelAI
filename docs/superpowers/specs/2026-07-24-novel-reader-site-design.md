# 小說手機閱讀網站（GitHub Pages 自動 host）設計

- 日期：2026-07-24
- 狀態：設計已定案，待排實作計畫
- 範圍：把書資料夾 `<book>/chapters/` 下的小說正文，經 GitHub Actions 建置成純靜態網站，push 後自動部署到 GitHub Pages，供手機閱讀。

---

## 1. 目標與非目標

### 目標
- 手機優先的閱讀網站：dark mode、章節內文、上一頁／下一頁翻頁、目錄頁、記住閱讀進度、字級／行距可調。
- push 到 `main` 後**自動**建置並部署，作者不需手動操作（除一次性的 Pages 來源設定）。
- 排版質感對齊參考站 `https://twkan.com/txt/93323/52116657` 的**手機 dark mode 版面數值**（背景／文字配色、字級、行距、段距、邊距）。只取版面數值，不取其內容、HTML/CSS 檔、廣告或追蹤程式。
- 從第一天就支援**多本書**的架構，但當前只發佈《一世之尊》。

### 非目標（YAGNI）
- 不做搜尋、留言、帳號、後端、資料庫。
- 不做 SEO／分享按鈕；反而要 noindex，避免被搜尋引擎收錄。
- 不做舊格式（章節標題下帶 `- 對應幕：`／`- POV：` metadata）相容——見 §4。
- 不動任何寫作系統檔（`結構定義/`、`技巧知識庫/`、`.claude/`、各書 `story/`、各書 `chapters/` 源檔）。網站是純消費端。

---

## 2. 定位與隱私

- 定位：**自己看為主，不想被搜尋引擎收錄**。網址仍是公開可存取的（GitHub Pages 無法加密碼），但：
  - 每個輸出頁面加 `<meta name="robots" content="noindex, nofollow">`。
  - 站台根加 `robots.txt`，全站 `Disallow: /`。
- 因為不做 SEO、不主動散布，書名／角色名與既有出版作品撞名的顧慮大幅降低，本設計不處理改名問題（作者已知悉）。
- **劇透防護是本設計的一等公民**。repo 內含大綱、幕綱、`_index.ai.md`、`.ai.md` 等寫滿伏筆與結局的檔。建置**只**吃各書 `chapters/` 下的乾淨正文源檔，其餘一律不進入輸出。任何會讓建置吃到非正文檔的做法（例如 Jekyll 預設發佈整個 repo）都不採用。

---

## 3. 架構總覽

```
push 到 main
   └─ GitHub Actions (.github/workflows/pages.yml)
        ├─ 讀 site.config.json（要發佈哪些書）
        ├─ 對每本 published 的書：
        │    ├─ 掃 <book>/chapters/ch<數字>.md（排除 .ai.md / _index.md / .gitkeep）
        │    ├─ 數值排序、格式檢查（見 §4）
        │    ├─ 剝幕錨點註解 <!-- 幕NNN --> → markdown 轉 HTML
        │    └─ 套模板產出目錄頁 + 各章頁
        ├─ 產出站台根：首頁、style.css、app.js、robots.txt
        └─ 部署 dist/ 到 GitHub Pages（產物不進 repo）
```

- 路線：**自寫小型 Node 建置腳本 + GitHub Actions**（非 SSG 框架、非前端即時 fetch）。理由：正文 markdown 極單純，輸出頁面要整頁自訂排版，用框架反而要跟主題慣例與排除規則打架；自寫腳本對「收哪些檔、輸出什麼」有完全控制，直接服務劇透防護與多書 slug 需求。
- 產物**不進 repo**：Actions 建置到 `dist/`，用 Pages 部署 artifact 直接上線，不建 `docs/` 靜態資料夾，避免 repo 被輸出 HTML 汙染、避免每次 push 產生大量無意義 diff。

---

## 4. 資料來源與收檔規則

### 4.1 多書設定 `site.config.json`（repo 根）
```json
{
  "site": { "title": "書櫃", "baseHref": "/novelAI/" },
  "books": [
    { "dir": "一世之尊", "slug": "yishizhizun", "title": "一世之尊", "published": true }
  ]
}
```
- 新增一本書 = 在 `books` 加一筆，**不改程式碼**。
- `published: false` 讓書留在設定裡但不輸出。
- `dir` 是 repo 內的中文資料夾名（只存在於 repo，不出現在網址）；`slug` 是網址用的英文短名；`title` 是顯示用書名。
- `baseHref` 對應 GitHub Pages 專案站台的子路徑（`https://linhung0319.github.io/novelAI/` → `/novelAI/`），所有站內連結以此為前綴。

### 4.2 收檔規則
- 只收 `<book>/chapters/` 下**檔名符合 `ch` + 一段數字 + `.md`** 的檔（regex 例：`^ch(\d+)\.md$`）。
- **排除**：`*.ai.md`、`_index.md`、`.gitkeep`、任何不符合上述 regex 的檔。
- **排序**：取檔名擷取到的數字做**數值排序**（非字串排序）。因此 `ch0001`（四位）與 `ch01`（兩位）兩種命名都通吃，跨書不需改設定。
- **章號顯示**：取檔名數字，去掉 `ch` 前綴後原樣顯示（一世之尊 → `0001`；芯片巫師 → `01`）。章名 = 該數字 + 全形空格 + 標題文字（例：`0001　一覺穿成小和尚`）。

### 4.3 格式契約（乾淨格式，唯一支援）
每個正文源檔的結構為：
```
# ch0001 · 一覺穿成小和尚      ← 第一行：標題行
                               ← 空行
天藍得不像話。                  ← 之後全是正文段落
...
```
- **標題行**：檔案第一行，形如 `# <章號token> · <標題>`。解析取 `·`（middle dot）之後的文字為顯示標題；`·` 之前的 `chNNNN` 只是識別，不用於顯示（章號改由檔名數字決定，見 §4.2）。
- **正文**：純段落 + 空行分段，偶有 `**粗體**`。無 frontmatter、無 `---` 分隔線、無清單／引用／程式碼區塊。
- **幕錨點註解** `<!-- 幕NNN -->`：散在正文中，**建置時剝除**（它是劇透線索，且渲染後本就不可見，不該留在輸出 HTML 原始碼）。

### 4.4 舊格式：不相容，改為建置失敗
- 舊格式（標題行下方有 `- 對應幕：[[…]]`、`- POV：…`、`- 狀態：…` 等 metadata 行，再接 `---`）**不支援**。
- 建置時對每個要發佈的章節做**格式檢查**：若標題行之後、正文之前出現 `-` 開頭的 metadata 行或 `---` 分隔線，**建置失敗**並指出是哪一個檔。
  - 理由：靜默剝除 metadata 會製造模糊地帶——若某天格式微妙變動、剝除規則沒命中，劇透會無聲上線；建置失敗則強制問題浮現。作者已確認未來新檔一律採乾淨格式。
- 副作用：以現況，`芯片巫師`、`harry_potter` 為舊格式，若被標為 `published: true` 會建置失敗。它們當前 `published: false`（或不列入 config），不影響。未來要發佈時，一次性把該書源檔轉為乾淨格式即可。

---

## 5. 網址結構

```
/                         首頁（書架）——單本時可直接呈現該書目錄，多本時列書
/yishizhizun/             目錄頁（章節列表）
/yishizhizun/0001.html    第 1 章
/yishizhizun/0002.html    第 2 章
...
/style.css  /app.js  /robots.txt
```
- 路徑**從第一天就帶 book slug**，即使目前只有一本。若走 `/0001.html` 之後加第二本必須改網址，會讓已存的書籤與 localStorage 進度紀錄失效。
- 章頁檔名用**檔名數字補零後的字串**（`0001.html`）；跨書以各自數字為準。
- 中文資料夾名不出現在網址（避免 percent-encode 成長串亂碼）。
- 站台完整網址：`https://linhung0319.github.io/novelAI/`。

---

## 6. 頁面與元件

### 6.1 目錄頁 `/<slug>/`
- 頁首：書名。
- 「繼續閱讀」區塊：若 localStorage 有該書進度，頂端顯示「繼續閱讀 <章號　章名>」連結，跳到該章並還原捲動位置。
- 章節列表：每章一列 `<章號>　<章名>`，點擊進章頁。
- 回首頁連結。

### 6.2 章節頁 `/<slug>/NNNN.html`
- 內容主體：靜態 HTML 正文（標題 + 段落），這是頁面的核心，**不依賴 JS 也能完整閱讀**。
- 導覽：頂部與底部各一組「← 上一章｜目錄｜下一章 →」。首章無上一章、末章無下一章時該按鈕停用。
- 觸控目標高度 ≥ 44px。
- 設定入口：字級／行距調整面板（見 §7.3）。

### 6.3 首頁 `/`
- 當前單本：直接呈現該書目錄，或極簡書架列出一本。
- 多本時：列出各 published 書的書名，點擊進各書目錄。（實作採「書架」通用版，單本時自然只有一項。）

---

## 7. 排版與樣式

### 7.1 取值方式
- 實作時用瀏覽器開啟參考站手機 dark mode 視圖，量測其 `background-color`、`color`、`font-size`、`line-height`、段落間距、左右邊距等**數值**，據以設定自家 CSS。量到的值列給作者確認，可逐項調整。
- 只取版面數值（功能性數字），不複製其 HTML/CSS、內容、廣告或追蹤。

### 7.2 已定的樣式原則
- **深灰底 + 中灰字**（非純黑底／純白字），降低手機捲動時的對比疲勞與拖影感；實際色碼以量測為準。
- **系統字型堆疊**（iOS 蘋方、Android Noto Sans CJK 等），**不 embed 網頁字型**——中文字型檔過大，行動網路載入痛苦。
- 左右留白用相對單位（vw），各種手機寬度下不貼邊也不過窄。
- 預設 dark mode（本次不做淺色切換）。

### 7.3 字級／行距可調
- 根層 CSS 變數 `--fs`（字級）、`--lh`（行距）。頁面提供小面板調整。
- 偏好存 localStorage，跨章節、跨開啟保留。
- 兼作作者微調排版的工具：調到滿意的數值可回寫成 CSS 預設值。

### 7.4 記住閱讀進度
- localStorage 以「book slug + 章號 + 捲動**百分比**」記錄。存百分比而非像素位置，因為字級可變、像素位置會失準。
- 進入章頁時還原該章捲動位置；目錄頁顯示「繼續閱讀」。

### 7.5 漸進增強原則
- 內容為靜態 HTML；JS 只負責字級／行距調整與閱讀進度。
- JS 載入失敗或執行錯誤時，正文與上下章導覽仍可正常使用。

---

## 8. 建置腳本 `site/build.js`

單一 Node 腳本，職責切分：

1. **讀設定**：載入 `site.config.json`，取 published 書清單。
2. **收檔**：對每本書掃 `chapters/`，套 §4.2 收檔與排序規則，得有序章節清單。
3. **格式檢查**：對每章套 §4.4，發現舊格式即中止並報出檔名。
4. **解析**：抽標題、剝幕錨點註解、markdown → HTML（僅需段落與 `**粗體**`，用輕量 markdown 或最小自寫轉換）。
5. **產頁**：套模板產出目錄頁、各章頁（含上下章連結，由排序位置計算）、首頁、`style.css`、`app.js`、`robots.txt`，寫入 `dist/`。
6. **健全性檢查**：章節數為 0、標題行抓不到、檔名數字重複 → 建置失敗並印出問題檔，不默默產出壞站。

- 模板置於 `site/templates/`，靜態資產（CSS/JS 原始檔）置於 `site/assets/`。
- 本機預覽：`node site/build.js && npx serve dist`，不必每次 push 等 Actions。

---

## 9. 部署 `.github/workflows/pages.yml`

- 觸發：push 到 `main`。
- 步驟：checkout → setup-node → `node site/build.js` → upload `dist/` 為 Pages artifact → deploy。
- 使用官方 `actions/deploy-pages` 流程；產物不 commit 回 repo。
- 權限：`pages: write`、`id-token: write`。

### 需作者手動一次
- GitHub repo → **Settings → Pages → Source** 選 **GitHub Actions**。此步無法由 push 自動完成，是全流程唯一手動動作。完成後每次 push 自動更新。

---

## 10. 檔案落點（新增，皆不動既有書檔）

```
site.config.json                      多書設定
site/build.js                         建置腳本
site/templates/                       頁面模板（目錄／章頁／首頁）
site/assets/style.css                 樣式原始檔
site/assets/app.js                    字級調整＋閱讀進度
.github/workflows/pages.yml           自動建置部署
docs/superpowers/specs/2026-07-24-novel-reader-site-design.md   本設計
```
- 不新增／不修改任何 `<book>/`、`結構定義/`、`技巧知識庫/`、`.claude/` 下的檔。作者寫作與 skill 流程零改動。

---

## 11. 驗收標準

1. push 後 Actions 綠燈，`https://linhung0319.github.io/novelAI/` 可開。
2. 手機開啟：dark mode 版面、字級行距接近參考站觀感。
3. `/yishizhizun/` 列出全 66 章，章名為 `<章號>　<章名>`，點擊可進。
4. 章頁可上一章／下一章翻頁；首章無上一章、末章無下一章。
5. 調整字級／行距後重開仍保留；讀到一半離開再回來，目錄頁出現「繼續閱讀」並能還原捲動位置。
6. 關閉 JS 後正文與上下章導覽仍可用。
7. 站上**無法**訪問到任何 `.ai.md`、大綱、幕綱、其他未發佈書內容；頁面含 noindex，`robots.txt` 全站 disallow。
8. 若把一本舊格式書設為 published，建置失敗並指出違規檔（負向驗收）。
