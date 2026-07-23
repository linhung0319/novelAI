# 小說手機閱讀網站 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Canonical location:** after plan-mode approval, copy this file to `docs/superpowers/plans/2026-07-24-novel-reader-site.md` and commit it (plan mode only permits editing the plan-mode file, so it lives here until then).

## Context

作者用 GitHub 管理寫作 repo `linhung0319/novelAI`（public）。書資料夾 `<book>/chapters/` 下的 `chNNNN.md` 是小說正文源（`.ai.md` 是機讀衍生檔）。作者想在手機上閱讀《一世之尊》（`一世之尊/chapters/`，66 章），要 dark mode、上下頁翻頁、目錄、記住進度、字級可調，且 push 後 GitHub Pages 自動更新。定案設計見 spec `docs/superpowers/specs/2026-07-24-novel-reader-site-design.md`。

關鍵約束：repo 內含大綱／幕綱／`.ai.md` 等**劇透**檔，網站**只**能吃各書 `chapters/` 下的乾淨正文；架構從第一天支援多書但當前只發佈一世之尊；網站是純消費端，**不動任何既有書檔或系統檔**。

**Goal:** 一支零依賴 Node 建置腳本把各書乾淨正文轉成純靜態手機閱讀網站，GitHub Actions 在 push 時自動建置並部署到 GitHub Pages。

**Architecture:** `site.config.json` 宣告要發佈哪些書（dir→slug）。`node site/build.js` 掃各 published 書的 `chapters/chNNNN.md`，過濾／數值排序／格式檢查後，把 markdown 轉 HTML、套模板產出目錄頁＋各章頁＋首頁＋`style.css`／`app.js`／`robots.txt` 到 `dist/`。Actions 建置 `dist/` 並用官方 Pages 流程部署，產物不進 repo。純靜態 HTML 為閱讀主體，JS 只加字級調整與進度記憶（漸進增強）。

**Tech Stack:** Node.js ≥ 20（ES modules、`node --test`、`node:fs`），**零 npm 依賴**（markdown 極單純，自寫最小轉換）。前端純 HTML/CSS/vanilla JS，系統字型堆疊，不 embed webfont。

## Global Constraints

逐條複製自 spec，每個 task 的需求都隱含包含本節：

- **執行環境**：Node.js ≥ 20，**零 runtime／build 依賴**（不 `npm install` 任何套件）。
- **只吃正文**：只收 `<book>/chapters/` 下檔名符合 `^ch(\d+)\.md$` 的檔；**排除** `*.ai.md`、`_index.md`、`.gitkeep` 及所有不符 regex 的檔。其餘 repo 內容一律不得進入 `dist/`。
- **只支援乾淨格式**：標題行之後、正文之前若出現 `-`/`*`/`+` 開頭的 metadata 行或 `---` 分隔線，**建置失敗**並印出違規檔名（不靜默剝除）。
- **剝幕錨點**：正文中的 `<!-- ... -->`（含 `<!-- 幕NNN -->`）建置時剝除。
- **標題解析**：標題行形如 `# <token> · <標題>`，分隔為 U+00B7（`·`）；顯示標題取 `·` 之後文字。章號取檔名數字字串（保留補零，如 `0001`／`01`），顯示為 `<章號>　<標題>`（全形空格 U+3000）。
- **網址帶 slug**：`/<slug>/`（目錄）、`/<slug>/<章號>.html`（章頁）；`baseHref` 前綴 `/novelAI/`。中文 dir 名不出現在網址。
- **隱私**：每頁 `<meta name="robots" content="noindex, nofollow">`；站根 `robots.txt` 全站 `Disallow: /`。
- **產物不進 repo**：建置輸出到 `dist/`（加入 `.gitignore`），由 Actions 部署，不 commit。
- **不動既有檔**：不新增／修改任何 `<book>/`、`結構定義/`、`技巧知識庫/`、`.claude/` 下的檔。
- **樣式**：預設 dark mode、系統字型堆疊、字級／行距為根層 CSS 變數可調、進度存**捲動百分比**（非像素）。

---

### Task 1: 專案骨架 + 章節收集 `site/lib/chapters.js`

建立零依賴 Node 專案骨架與測試夾具，實作章節檔名解析、收集、數值排序、缺號／重號偵測。

**Files:**
- Create: `package.json`
- Create: `site.config.json`
- Create: `site/lib/chapters.js`
- Create: `site/lib/chapters.test.js`
- Create fixtures: `site/test-fixtures/goodbook/chapters/ch0001.md`, `.../ch0002.md`, `.../ch0001.ai.md`, `.../_index.md`, `.../.gitkeep`
- Modify: `.gitignore`（新增 `dist/`）

**Interfaces:**
- Produces:
  - `parseChapterNum(filename: string): { pad: string, num: number } | null` — `"ch0007.md"` → `{ pad: "0007", num: 7 }`；不符 `^ch(\d+)\.md$` 回 `null`。
  - `collectChapters(chaptersDir: string): Array<{ pad: string, num: number, filename: string, path: string }>` — 已按 `num` 升冪排序；遇重號 throw `Error`。

- [ ] **Step 1: 建立 `package.json`（零依賴、ES module、測試腳本）**

```json
{
  "name": "novel-reader-site",
  "private": true,
  "type": "module",
  "engines": { "node": ">=20" },
  "scripts": {
    "build": "node site/build.js",
    "test": "node --test",
    "serve": "node site/build.js && npx --yes serve dist"
  }
}
```

- [ ] **Step 2: 建立 `site.config.json`（多書設定，當前只發佈一世之尊）**

```json
{
  "site": { "title": "書櫃", "baseHref": "/novelAI/" },
  "books": [
    { "dir": "一世之尊", "slug": "yishizhizun", "title": "一世之尊", "published": true }
  ]
}
```

- [ ] **Step 3: 建立測試夾具**

`site/test-fixtures/goodbook/chapters/ch0001.md`：
```markdown
# ch0001 · 第一章標題

第一段正文。

第二段有**重點**字。
```
`site/test-fixtures/goodbook/chapters/ch0002.md`：
```markdown
# ch0002 · 第二章標題

只有一段。
```
`.../ch0001.ai.md` 內容：`derived, must be excluded`
`.../_index.md` 內容：`index, must be excluded`
`.../.gitkeep` 內容：空

- [ ] **Step 4: 寫失敗測試 `site/lib/chapters.test.js`**

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parseChapterNum, collectChapters } from './chapters.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const goodDir = path.join(here, '..', 'test-fixtures', 'goodbook', 'chapters');

test('parseChapterNum parses 4-digit and 2-digit names', () => {
  assert.deepEqual(parseChapterNum('ch0007.md'), { pad: '0007', num: 7 });
  assert.deepEqual(parseChapterNum('ch01.md'), { pad: '01', num: 1 });
});

test('parseChapterNum rejects non-chapter files', () => {
  assert.equal(parseChapterNum('ch0001.ai.md'), null);
  assert.equal(parseChapterNum('_index.md'), null);
  assert.equal(parseChapterNum('.gitkeep'), null);
});

test('collectChapters filters, sorts, excludes derived/index', () => {
  const chs = collectChapters(goodDir);
  assert.equal(chs.length, 2);
  assert.deepEqual(chs.map((c) => c.pad), ['0001', '0002']);
  assert.ok(chs.every((c) => c.filename.endsWith('.md') && !c.filename.includes('.ai.')));
});
```

- [ ] **Step 5: 執行測試確認失敗**

Run: `node --test site/lib/chapters.test.js`
Expected: FAIL（`chapters.js` 不存在／未匯出）

- [ ] **Step 6: 實作 `site/lib/chapters.js`**

```js
import fs from 'node:fs';
import path from 'node:path';

const CHAPTER_RE = /^ch(\d+)\.md$/;

export function parseChapterNum(filename) {
  const m = CHAPTER_RE.exec(filename);
  if (!m) return null;
  return { pad: m[1], num: Number(m[1]) };
}

export function collectChapters(chaptersDir) {
  const out = [];
  const seen = new Map();
  for (const filename of fs.readdirSync(chaptersDir)) {
    const parsed = parseChapterNum(filename);
    if (!parsed) continue; // 排除 .ai.md / _index.md / .gitkeep / 其他
    if (seen.has(parsed.num)) {
      throw new Error(
        `重號章節：ch 編號 ${parsed.num} 同時出現在 ${seen.get(parsed.num)} 與 ${filename}`
      );
    }
    seen.set(parsed.num, filename);
    out.push({ ...parsed, filename, path: path.join(chaptersDir, filename) });
  }
  out.sort((a, b) => a.num - b.num);
  return out;
}
```

- [ ] **Step 7: 執行測試確認通過**

Run: `node --test site/lib/chapters.test.js`
Expected: PASS（3 tests）

- [ ] **Step 8: 更新 `.gitignore`（產物不進 repo）**

在檔尾新增：
```
# 網站建置產物（由 GitHub Actions 部署，不版控）
/dist/
```

- [ ] **Step 9: Commit**

```bash
git add package.json site.config.json site/lib/chapters.js site/lib/chapters.test.js site/test-fixtures/ .gitignore
git commit -m "feat(site): 專案骨架＋章節收集與排序"
```

---

### Task 2: 標題解析與乾淨格式檢查 `site/lib/parse.js`

實作標題行解析與舊格式偵測（違規即 throw）。

**Files:**
- Create: `site/lib/parse.js`
- Create: `site/lib/parse.test.js`
- Create fixture: `site/test-fixtures/oldbook/chapters/ch01.md`（舊格式，供負向測試）

**Interfaces:**
- Produces:
  - `parseTitle(firstLine: string): string` — `"# ch0001 · 一覺穿成小和尚"` → `"一覺穿成小和尚"`；抓不到 throw。
  - `assertCleanFormat(bodyLines: string[], filename: string): void` — 標題後第一個非空區塊若含 `-`/`*`/`+` 起始行或 `---`，throw 指名 `filename`。

- [ ] **Step 1: 建立舊格式夾具 `site/test-fixtures/oldbook/chapters/ch01.md`**

```markdown
# ch01 · 落地頂替

- 對應幕：[[幕001]]
- 所屬 arc：arc01
- POV：主角

---

冷。先是冷。
```

- [ ] **Step 2: 寫失敗測試 `site/lib/parse.test.js`**

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseTitle, assertCleanFormat } from './parse.js';

test('parseTitle takes text after middle dot U+00B7', () => {
  assert.equal(parseTitle('# ch0001 · 一覺穿成小和尚'), '一覺穿成小和尚');
});

test('parseTitle throws on malformed heading', () => {
  assert.throws(() => parseTitle('天藍得不像話。'));
});

test('assertCleanFormat passes clean prose', () => {
  const body = ['', '天藍得不像話。', '', '第二段。'];
  assert.doesNotThrow(() => assertCleanFormat(body, 'ch0001.md'));
});

test('assertCleanFormat rejects old-format metadata list', () => {
  const body = ['', '- 對應幕：[[幕001]]', '- POV：主角', '', '---', '', '冷。'];
  assert.throws(() => assertCleanFormat(body, 'ch01.md'), /ch01\.md/);
});

test('assertCleanFormat rejects thematic break before prose', () => {
  const body = ['', '---', '', '冷。'];
  assert.throws(() => assertCleanFormat(body, 'ch01.md'), /ch01\.md/);
});
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `node --test site/lib/parse.test.js`
Expected: FAIL（`parse.js` 不存在）

- [ ] **Step 4: 實作 `site/lib/parse.js`（本 task 只放 parseTitle／assertCleanFormat）**

```js
const TITLE_RE = /^#\s+\S+\s+·\s+(.+?)\s*$/; // # <token> · <標題>
const META_RE = /^[-*+]\s/;   // 舊格式 metadata 清單行
const HR_RE = /^-{3,}\s*$/;   // 舊格式分隔線

export function parseTitle(firstLine) {
  const m = TITLE_RE.exec(firstLine);
  if (!m) throw new Error(`標題行格式不符（應為「# … · 標題」）：${firstLine}`);
  return m[1];
}

// 檢查標題後、正文前是否為舊格式。乾淨格式的第一個非空區塊即散文段落。
export function assertCleanFormat(bodyLines, filename) {
  let i = 0;
  while (i < bodyLines.length && bodyLines[i].trim() === '') i++; // 跳過標題後空行
  for (; i < bodyLines.length; i++) {
    const line = bodyLines[i];
    if (line.trim() === '') break; // 第一個非空區塊結束
    if (META_RE.test(line) || HR_RE.test(line)) {
      throw new Error(
        `${filename}：偵測到舊格式（標題下方有 metadata／分隔線）。請轉為乾淨格式後再發佈。`
      );
    }
  }
}
```

- [ ] **Step 5: 執行測試確認通過**

Run: `node --test site/lib/parse.test.js`
Expected: PASS（5 tests）

- [ ] **Step 6: Commit**

```bash
git add site/lib/parse.js site/lib/parse.test.js site/test-fixtures/oldbook/
git commit -m "feat(site): 標題解析＋乾淨格式檢查"
```

---

### Task 3: Markdown → HTML `site/lib/markdown.js`

實作剝 HTML 註解、HTML 轉義、`**粗體**`、段落切分，及組合成章節內容的函式。

**Files:**
- Create: `site/lib/markdown.js`
- Create: `site/lib/markdown.test.js`

**Interfaces:**
- Consumes: `parseTitle`, `assertCleanFormat`（`site/lib/parse.js`）。
- Produces:
  - `stripAnchors(text: string): string` — 移除所有 `<!-- ... -->`。
  - `escapeHtml(s: string): string` — 轉義 `& < >`。
  - `mdToHtml(body: string): string` — 空行切段，每段轉義後套 `**bold**`→`<strong>`，包 `<p>…</p>`，`\n` join。
  - `renderChapterContent(raw: string, filename: string): { title: string, html: string }` — 讀整檔文字 → 標題＋內文 HTML（內部呼叫 parseTitle／assertCleanFormat／stripAnchors／mdToHtml）。

- [ ] **Step 1: 寫失敗測試 `site/lib/markdown.test.js`**

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { stripAnchors, escapeHtml, mdToHtml, renderChapterContent } from './markdown.js';

test('stripAnchors removes 幕 anchor comments', () => {
  assert.equal(stripAnchors('前\n<!-- 幕001 -->\n後'), '前\n\n後');
});

test('escapeHtml escapes angle brackets and amp', () => {
  assert.equal(escapeHtml('a < b & c > d'), 'a &lt; b &amp; c &gt; d');
});

test('mdToHtml splits paragraphs and renders bold', () => {
  const out = mdToHtml('第一段。\n\n有**重點**字。');
  assert.equal(out, '<p>第一段。</p>\n<p>有<strong>重點</strong>字。</p>');
});

test('renderChapterContent returns title and body html, anchors stripped', () => {
  const raw = '# ch0001 · 標題\n\n<!-- 幕001 -->\n第一段。\n\n第二段。';
  const { title, html } = renderChapterContent(raw, 'ch0001.md');
  assert.equal(title, '標題');
  assert.equal(html, '<p>第一段。</p>\n<p>第二段。</p>');
});

test('renderChapterContent throws on old format', () => {
  const raw = '# ch01 · 標題\n\n- 對應幕：[[幕001]]\n\n---\n\n冷。';
  assert.throws(() => renderChapterContent(raw, 'ch01.md'), /ch01\.md/);
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `node --test site/lib/markdown.test.js`
Expected: FAIL（`markdown.js` 不存在）

- [ ] **Step 3: 實作 `site/lib/markdown.js`**

```js
import { parseTitle, assertCleanFormat } from './parse.js';

export function stripAnchors(text) {
  return text.replace(/<!--[\s\S]*?-->/g, '');
}

export function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function inline(s) {
  return escapeHtml(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

export function mdToHtml(body) {
  return body
    .split(/\r?\n\s*\r?\n/)
    .map((p) => p.replace(/\r?\n/g, ' ').trim())
    .filter((p) => p.length > 0)
    .map((p) => `<p>${inline(p)}</p>`)
    .join('\n');
}

export function renderChapterContent(raw, filename) {
  const lines = raw.split(/\r?\n/);
  const title = parseTitle(lines[0]);
  const bodyLines = lines.slice(1);
  assertCleanFormat(bodyLines, filename);
  const html = mdToHtml(stripAnchors(bodyLines.join('\n')));
  return { title, html };
}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `node --test site/lib/markdown.test.js`
Expected: PASS（5 tests）

- [ ] **Step 5: Commit**

```bash
git add site/lib/markdown.js site/lib/markdown.test.js
git commit -m "feat(site): markdown→HTML（剝註解／轉義／粗體／段落）"
```

---

### Task 4: 頁面模板 `site/lib/render.js`

實作章頁、目錄頁、首頁的 HTML 輸出。含 noindex meta、baseHref 前綴連結、上下章導覽（端點停用）。

**Files:**
- Create: `site/lib/render.js`
- Create: `site/lib/render.test.js`

**Interfaces:**
- Produces（`base` = `site.baseHref`，如 `/novelAI/`）：
  - `renderChapterPage({ base, slug, bookTitle, pad, title, contentHtml, prev, next }): string` — `prev`/`next` 為相鄰章 `pad` 或 `null`。
  - `renderTocPage({ base, slug, bookTitle, chapters }): string` — `chapters` = `[{ pad, title }]`。
  - `renderHomePage({ base, siteTitle, books }): string` — `books` = `[{ slug, title }]`。

- [ ] **Step 1: 寫失敗測試 `site/lib/render.test.js`**

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderChapterPage, renderTocPage, renderHomePage } from './render.js';

const base = '/novelAI/';

test('chapter page has noindex, title, content, base-prefixed nav', () => {
  const html = renderChapterPage({
    base, slug: 'yishizhizun', bookTitle: '一世之尊',
    pad: '0002', title: '標題二', contentHtml: '<p>內文。</p>',
    prev: '0001', next: '0003',
  });
  assert.match(html, /noindex, nofollow/);
  assert.match(html, /0002　標題二/);
  assert.match(html, /<p>內文。<\/p>/);
  assert.match(html, /href="\/novelAI\/yishizhizun\/0001\.html"/); // 上一章
  assert.match(html, /href="\/novelAI\/yishizhizun\/0003\.html"/); // 下一章
  assert.match(html, /href="\/novelAI\/yishizhizun\/"/);           // 目錄
  assert.match(html, /data-slug="yishizhizun"/);
  assert.match(html, /data-chapter="0002"/);
});

test('chapter page disables prev at first, next at last', () => {
  const first = renderChapterPage({ base, slug: 's', bookTitle: 'B', pad: '0001', title: 'T', contentHtml: '<p>x</p>', prev: null, next: '0002' });
  assert.match(first, /aria-disabled="true"[^>]*>‹/); // 上一章停用
  const last = renderChapterPage({ base, slug: 's', bookTitle: 'B', pad: '0009', title: 'T', contentHtml: '<p>x</p>', prev: '0008', next: null });
  assert.match(last, /aria-disabled="true"[^>]*>下一章|下一章[^<]*<[^>]*aria-disabled/);
});

test('toc page lists chapters with continue anchor placeholder', () => {
  const html = renderTocPage({ base, slug: 'yishizhizun', bookTitle: '一世之尊', chapters: [{ pad: '0001', title: '一' }, { pad: '0002', title: '二' }] });
  assert.match(html, /0001　一/);
  assert.match(html, /href="\/novelAI\/yishizhizun\/0002\.html"/);
  assert.match(html, /id="continue"/); // JS 填入「繼續閱讀」
});

test('home page lists published books', () => {
  const html = renderHomePage({ base, siteTitle: '書櫃', books: [{ slug: 'yishizhizun', title: '一世之尊' }] });
  assert.match(html, /href="\/novelAI\/yishizhizun\/"/);
  assert.match(html, /一世之尊/);
});
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `node --test site/lib/render.test.js`
Expected: FAIL（`render.js` 不存在）

- [ ] **Step 3: 實作 `site/lib/render.js`**

```js
function layout({ base, title, bodyClass = '', bodyAttrs = '', main }) {
  return `<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<title>${title}</title>
<link rel="stylesheet" href="${base}style.css">
</head>
<body class="${bodyClass}"${bodyAttrs}>
${main}
<script src="${base}app.js" defer></script>
</body>
</html>`;
}

function navBtn({ href, label, disabled }) {
  if (disabled || !href) return `<span class="nav-btn" aria-disabled="true">${label}</span>`;
  return `<a class="nav-btn" href="${href}">${label}</a>`;
}

export function renderChapterPage({ base, slug, bookTitle, pad, title, contentHtml, prev, next }) {
  const tocHref = `${base}${slug}/`;
  const prevHref = prev ? `${base}${slug}/${prev}.html` : null;
  const nextHref = next ? `${base}${slug}/${next}.html` : null;
  const nav = `<nav class="chapter-nav">
${navBtn({ href: prevHref, label: '‹ 上一章', disabled: !prev })}
<a class="nav-btn" href="${tocHref}">目錄</a>
${navBtn({ href: nextHref, label: '下一章 ›', disabled: !next })}
</nav>`;
  const main = `<header class="site-head"><a href="${tocHref}">${bookTitle}</a>
<button id="prefs-toggle" class="prefs-toggle" aria-label="閱讀設定">Aa</button></header>
<div id="prefs-panel" class="prefs-panel" hidden>
  <label>字級 <button data-fs="-1">A−</button><button data-fs="1">A＋</button></label>
  <label>行距 <button data-lh="-1">緊</button><button data-lh="1">鬆</button></label>
</div>
<article class="chapter">
<h1>${pad}　${title}</h1>
${nav}
<div class="prose">${contentHtml}</div>
${nav}
</article>`;
  return layout({
    base, title: `${pad}　${title}`,
    bodyClass: 'page-chapter',
    bodyAttrs: ` data-slug="${slug}" data-chapter="${pad}"`,
    main,
  });
}

export function renderTocPage({ base, slug, bookTitle, chapters }) {
  const items = chapters
    .map((c) => `<li><a href="${base}${slug}/${c.pad}.html">${c.pad}　${c.title}</a></li>`)
    .join('\n');
  const main = `<header class="site-head"><a href="${base}">← 書櫃</a></header>
<h1 class="book-title">${bookTitle}</h1>
<a id="continue" class="continue" hidden></a>
<ol class="toc">
${items}
</ol>`;
  return layout({
    base, title: bookTitle,
    bodyClass: 'page-toc',
    bodyAttrs: ` data-slug="${slug}"`,
    main,
  });
}

export function renderHomePage({ base, siteTitle, books }) {
  const items = books
    .map((b) => `<li><a href="${base}${b.slug}/">${b.title}</a></li>`)
    .join('\n');
  const main = `<h1 class="book-title">${siteTitle}</h1>
<ul class="shelf">
${items}
</ul>`;
  return layout({ base, title: siteTitle, bodyClass: 'page-home', main });
}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `node --test site/lib/render.test.js`
Expected: PASS（4 tests）

- [ ] **Step 5: Commit**

```bash
git add site/lib/render.js site/lib/render.test.js
git commit -m "feat(site): 章頁／目錄頁／首頁模板"
```

---

### Task 5: 靜態資產 `style.css` + `app.js`

Dark mode 排版（系統字型、字級／行距 CSS 變數）與前端行為（字級調整、閱讀進度、繼續閱讀）。先寫合理預設值，色碼／字級留待 Task 8 對照參考站校準。

**Files:**
- Create: `site/assets/style.css`
- Create: `site/assets/app.js`

（本 task 為前端資產，以建置後手機實測驗收，不寫單元測試；純函式行為在 Task 6 的整合測試間接覆蓋輸出存在性。）

- [ ] **Step 1: 建立 `site/assets/style.css`（dark 預設、系統字型、CSS 變數）**

```css
:root {
  --fs: 20px;           /* 字級，可由 app.js 調整 */
  --lh: 1.9;            /* 行距 */
  --bg: #1c1c1c;        /* 深灰底（非純黑），Task 8 校準 */
  --fg: #bfbfbf;        /* 中灰字，Task 8 校準 */
  --fg-dim: #7a7a7a;
  --accent: #8ab4c8;
  --maxw: 40rem;
  --pad: 5vw;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font-family: "PingFang TC", "Noto Sans CJK TC", "Microsoft JhengHei",
    system-ui, -apple-system, "Helvetica Neue", sans-serif;
  font-size: var(--fs); line-height: var(--lh);
  padding: env(safe-area-inset-top) 0 env(safe-area-inset-bottom);
}
a { color: var(--accent); text-decoration: none; }
.site-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.75rem var(--pad); border-bottom: 1px solid #2c2c2c;
  color: var(--fg-dim); font-size: 0.85rem;
}
.chapter, .page-toc, .page-home { max-width: var(--maxw); margin: 0 auto; padding: 0 var(--pad) 3rem; }
.chapter h1, .book-title { font-size: 1.35rem; line-height: 1.5; margin: 1.4rem 0; color: var(--fg); }
.prose p { margin: 0 0 1.15em; text-align: justify; }
.prose strong { color: #d8d8d8; font-weight: 600; }
.chapter-nav {
  display: flex; justify-content: space-between; gap: 0.5rem; margin: 1.6rem 0;
}
.nav-btn {
  flex: 1; text-align: center; min-height: 44px; line-height: 44px;
  border: 1px solid #333; border-radius: 8px; color: var(--accent);
}
.nav-btn[aria-disabled="true"] { color: #444; border-color: #262626; }
.toc { list-style: none; padding: 0; margin: 1rem 0; }
.toc li a, .shelf li a { display: block; min-height: 44px; line-height: 44px;
  padding: 0 0.5rem; border-bottom: 1px solid #262626; color: var(--fg); }
.continue { display: block; margin: 0.5rem 0 1rem; padding: 0.6rem 0.8rem;
  background: #262626; border-radius: 8px; color: var(--accent); }
.prefs-toggle { background: none; border: 1px solid #333; border-radius: 6px;
  color: var(--fg-dim); min-width: 40px; min-height: 32px; }
.prefs-panel { max-width: var(--maxw); margin: 0 auto; padding: 0.6rem var(--pad);
  display: flex; gap: 1.5rem; border-bottom: 1px solid #2c2c2c; }
.prefs-panel button { min-width: 40px; min-height: 36px; margin-left: 0.3rem;
  background: #262626; color: var(--fg); border: 1px solid #333; border-radius: 6px; }
```

- [ ] **Step 2: 建立 `site/assets/app.js`（字級調整＋進度記憶，漸進增強）**

```js
(function () {
  var PREFS = 'reader:prefs';
  var root = document.documentElement;

  // 1) 套用字級／行距偏好
  function loadPrefs() {
    try { return JSON.parse(localStorage.getItem(PREFS)) || {}; } catch (e) { return {}; }
  }
  function applyPrefs(p) {
    if (p.fs) root.style.setProperty('--fs', p.fs + 'px');
    if (p.lh) root.style.setProperty('--lh', String(p.lh));
  }
  var prefs = loadPrefs();
  applyPrefs(prefs);

  function savePrefs() { try { localStorage.setItem(PREFS, JSON.stringify(prefs)); } catch (e) {} }
  function nudge(kind, dir) {
    if (kind === 'fs') prefs.fs = Math.min(28, Math.max(15, (prefs.fs || 20) + dir));
    else prefs.lh = Math.min(2.4, Math.max(1.4, Math.round(((prefs.lh || 1.9) + dir * 0.1) * 10) / 10));
    applyPrefs(prefs); savePrefs();
  }
  var toggle = document.getElementById('prefs-toggle');
  var panel = document.getElementById('prefs-panel');
  if (toggle && panel) {
    toggle.addEventListener('click', function () { panel.hidden = !panel.hidden; });
    panel.addEventListener('click', function (e) {
      var t = e.target;
      if (t.dataset.fs) nudge('fs', Number(t.dataset.fs));
      if (t.dataset.lh) nudge('lh', Number(t.dataset.lh));
    });
  }

  var slug = document.body.getAttribute('data-slug');
  var chapter = document.body.getAttribute('data-chapter');
  var KEY = slug ? 'reader:progress:' + slug : null;

  // 2) 章頁：還原捲動、記錄進度（捲動百分比）
  if (KEY && chapter) {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}
    if (saved && saved.chapter === chapter && saved.percent > 0) {
      requestAnimationFrame(function () {
        var h = document.documentElement.scrollHeight - window.innerHeight;
        window.scrollTo(0, h * saved.percent);
      });
    }
    var t = null;
    function record() {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      var percent = h > 0 ? Math.min(1, window.scrollY / h) : 0;
      try { localStorage.setItem(KEY, JSON.stringify({ chapter: chapter, percent: percent })); } catch (e) {}
    }
    window.addEventListener('scroll', function () {
      if (t) return; t = setTimeout(function () { t = null; record(); }, 400);
    }, { passive: true });
    window.addEventListener('pagehide', record);
  }

  // 3) 目錄頁：顯示「繼續閱讀」
  if (KEY && !chapter) {
    var el = document.getElementById('continue');
    var p = null;
    try { p = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}
    if (el && p && p.chapter) {
      el.textContent = '繼續閱讀 ' + p.chapter;
      el.href = p.chapter + '.html';
      el.hidden = false;
    }
  }
})();
```

- [ ] **Step 3: Commit**

```bash
git add site/assets/style.css site/assets/app.js
git commit -m "feat(site): dark 排版樣式＋字級調整與進度記憶"
```

---

### Task 6: 建置協調器 `site/build.js`

串接 config→收檔→格式檢查→轉 HTML→套模板→寫 `dist/`，含健全性檢查（0 章、標題抓不到、空章清單）與整合測試。

**Files:**
- Create: `site/build.js`
- Create: `site/build.test.js`

**Interfaces:**
- Consumes: `collectChapters`（chapters.js）、`renderChapterContent`（markdown.js）、`renderChapterPage`/`renderTocPage`/`renderHomePage`（render.js）。
- Produces: `build({ configPath, repoRoot, outDir }): { books: number, chapters: number }` — 產出 `dist/`；供整合測試以夾具 config 呼叫。

- [ ] **Step 1: 建立整合測試用夾具 config `site/test-fixtures/site.config.json`**

```json
{
  "site": { "title": "測試書櫃", "baseHref": "/novelAI/" },
  "books": [
    { "dir": "test-fixtures/goodbook", "slug": "goodbook", "title": "好書", "published": true },
    { "dir": "test-fixtures/oldbook", "slug": "oldbook", "title": "舊書", "published": false }
  ]
}
```
（`dir` 相對 `repoRoot`；測試傳 `repoRoot = site/` 使其指向 `site/test-fixtures/...`。）

- [ ] **Step 2: 寫失敗測試 `site/build.test.js`**

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from './build.js';

const here = path.dirname(fileURLToPath(import.meta.url));

function run() {
  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'novelsite-'));
  const res = build({
    configPath: path.join(here, 'test-fixtures', 'site.config.json'),
    repoRoot: here,          // dir 相對 site/
    outDir: out,
  });
  return { out, res };
}

test('build emits chapter pages, toc, home, assets for published book only', () => {
  const { out, res } = run();
  assert.equal(res.books, 1);          // oldbook published:false 被跳過
  assert.equal(res.chapters, 2);
  assert.ok(fs.existsSync(path.join(out, 'goodbook', '0001.html')));
  assert.ok(fs.existsSync(path.join(out, 'goodbook', '0002.html')));
  assert.ok(fs.existsSync(path.join(out, 'goodbook', 'index.html')));
  assert.ok(fs.existsSync(path.join(out, 'index.html')));
  assert.ok(fs.existsSync(path.join(out, 'style.css')));
  assert.ok(fs.existsSync(path.join(out, 'app.js')));
  assert.ok(fs.existsSync(path.join(out, 'robots.txt')));
  const ch1 = fs.readFileSync(path.join(out, 'goodbook', '0001.html'), 'utf8');
  assert.match(ch1, /noindex/);
  assert.match(ch1, /第一段正文。/);
  assert.ok(!fs.existsSync(path.join(out, 'oldbook'))); // 未發佈書不輸出
});

test('robots.txt disallows all', () => {
  const { out } = run();
  assert.match(fs.readFileSync(path.join(out, 'robots.txt'), 'utf8'), /Disallow:\s*\//);
});

test('build fails loudly when a published book is old-format', () => {
  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'novelsite-'));
  const badCfg = path.join(out, 'cfg.json');
  fs.writeFileSync(badCfg, JSON.stringify({
    site: { title: 'x', baseHref: '/novelAI/' },
    books: [{ dir: 'test-fixtures/oldbook', slug: 'oldbook', title: '舊', published: true }],
  }));
  assert.throws(() => build({ configPath: badCfg, repoRoot: here, outDir: path.join(out, 'dist') }), /ch01\.md/);
});
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `node --test site/build.test.js`
Expected: FAIL（`build.js` 不存在）

- [ ] **Step 4: 實作 `site/build.js`**

```js
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { collectChapters } from './lib/chapters.js';
import { renderChapterContent } from './lib/markdown.js';
import { renderChapterPage, renderTocPage, renderHomePage } from './lib/render.js';

const here = path.dirname(fileURLToPath(import.meta.url));

export function build({ configPath, repoRoot, outDir }) {
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const base = config.site.baseHref;
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(outDir, { recursive: true });

  const published = config.books.filter((b) => b.published);
  let totalChapters = 0;

  for (const book of published) {
    const chaptersDir = path.join(repoRoot, book.dir, 'chapters');
    const chapters = collectChapters(chaptersDir);
    if (chapters.length === 0) {
      throw new Error(`${book.dir}：chapters/ 沒有任何章節，無法建置。`);
    }
    const bookOut = path.join(outDir, book.slug);
    fs.mkdirSync(bookOut, { recursive: true });

    const tocEntries = [];
    for (let i = 0; i < chapters.length; i++) {
      const ch = chapters[i];
      const raw = fs.readFileSync(ch.path, 'utf8');
      const { title, html } = renderChapterContent(raw, ch.filename);
      tocEntries.push({ pad: ch.pad, title });
      const page = renderChapterPage({
        base, slug: book.slug, bookTitle: book.title,
        pad: ch.pad, title, contentHtml: html,
        prev: i > 0 ? chapters[i - 1].pad : null,
        next: i < chapters.length - 1 ? chapters[i + 1].pad : null,
      });
      fs.writeFileSync(path.join(bookOut, `${ch.pad}.html`), page);
    }
    fs.writeFileSync(
      path.join(bookOut, 'index.html'),
      renderTocPage({ base, slug: book.slug, bookTitle: book.title, chapters: tocEntries })
    );
    totalChapters += chapters.length;
  }

  // 首頁 + 資產 + robots
  fs.writeFileSync(
    path.join(outDir, 'index.html'),
    renderHomePage({ base, siteTitle: config.site.title, books: published.map((b) => ({ slug: b.slug, title: b.title })) })
  );
  const assets = path.join(here, 'assets');
  for (const f of fs.readdirSync(assets)) {
    fs.copyFileSync(path.join(assets, f), path.join(outDir, f));
  }
  fs.writeFileSync(path.join(outDir, 'robots.txt'), 'User-agent: *\nDisallow: /\n');
  fs.writeFileSync(path.join(outDir, '.nojekyll'), '');

  return { books: published.length, chapters: totalChapters };
}

// CLI：node site/build.js
const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const repoRoot = path.join(here, '..');
  const res = build({
    configPath: path.join(repoRoot, 'site.config.json'),
    repoRoot,
    outDir: path.join(repoRoot, 'dist'),
  });
  console.log(`建置完成：${res.books} 本書、${res.chapters} 章 → dist/`);
}
```

- [ ] **Step 5: 執行測試確認通過**

Run: `node --test site/build.test.js`
Expected: PASS（3 tests）

- [ ] **Step 6: 全套測試 + 真實建置冒煙測試**

Run: `node --test`
Expected: 全部 PASS（chapters／parse／markdown／render／build）

Run: `node site/build.js`
Expected: 印出「建置完成：1 本書、66 章 → dist/」；`dist/yishizhizun/0001.html`…`0066.html`、`dist/yishizhizun/index.html`、`dist/index.html`、`dist/style.css`、`dist/app.js`、`dist/robots.txt` 皆存在。

- [ ] **Step 7: Commit**

```bash
git add site/build.js site/build.test.js site/test-fixtures/site.config.json
git commit -m "feat(site): 建置協調器＋整合測試（含舊格式失敗）"
```

---

### Task 7: GitHub Actions 自動部署 `.github/workflows/pages.yml`

push 到 `main` 時建置 `dist/` 並用官方 Pages 流程部署。

**Files:**
- Create: `.github/workflows/pages.yml`

- [ ] **Step 1: 建立 workflow**

```yaml
name: Deploy reader site
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Run tests
        run: node --test
      - name: Build site
        run: node site/build.js
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: 本機確認 workflow 內的指令可跑**

Run: `node --test && node site/build.js`
Expected: 測試全綠、建置成功（模擬 CI 兩步）。

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "ci(site): push 到 main 自動建置並部署到 GitHub Pages"
```

---

### Task 8: 上線、樣式校準、端到端驗收

推上 GitHub、開啟 Pages 來源、對照參考站校準排版、手機實測驗收全部驗收標準。此 task 含人工步驟。

**Files:**
- Modify: `site/assets/style.css`（依量測調整 `--bg`／`--fg`／`--fs`／`--lh`／段距）

- [ ] **Step 1: 推上 GitHub 觸發首次部署**

```bash
git push origin main
```
到 repo → Actions 確認 workflow 綠燈。

- [ ] **Step 2: 手動開啟 Pages 來源（全流程唯一手動動作）**

repo → Settings → Pages → Source 選 **GitHub Actions**。等站台上線：`https://linhung0319.github.io/novelAI/`。

- [ ] **Step 3: 量測參考站排版數值**

用 Playwright MCP 開 `https://twkan.com/txt/93323/52116657`（手機視窗，如 `browser_resize` 390×844），對正文容器與段落 `getComputedStyle` 取 `backgroundColor`、`color`、`fontSize`、`lineHeight`、段落 `marginBottom`、容器左右 `padding`。把數值列給作者確認。只取版面數值，不取其內容／程式碼／廣告。

- [ ] **Step 4: 依量測結果校準 `site/assets/style.css` 並重新部署**

把 `--bg`／`--fg`／`--fs`／`--lh`／`.prose p` 段距／`--pad` 調到貼近量測值（作者可逐項再改）。
```bash
node site/build.js   # 本機預覽確認
git add site/assets/style.css && git commit -m "style(site): 依參考站校準 dark 排版數值"
git push origin main
```

- [ ] **Step 5: 手機端到端驗收（對照 spec §11）**

在手機開 `https://linhung0319.github.io/novelAI/` 逐項確認：
1. 站台可開、dark mode、字級行距觀感接近參考站。
2. `/yishizhizun/` 列出全 66 章、章名 `<章號>　<章名>`、可進章。
3. 章頁上一章／下一章可翻；`0001` 無上一章、`0066` 無下一章（按鈕停用）。
4. 調字級／行距後重開仍保留。
5. 讀一半離開再回目錄頁出現「繼續閱讀」、進章還原捲動位置。
6. 瀏覽器關 JS 後正文與上下章導覽仍可用。
7. 直接猜網址存取 `.../story/01-大綱.md`、`.../yishizhizun/../` 等取不到劇透檔；頁面有 noindex、`/novelAI/robots.txt` 全站 disallow。
8.（負向）暫時把 `芯片巫師` 設 `published:true` 跑 `node site/build.js`，確認建置失敗並指名 `ch01.md`；還原設定。

---

## Verification（整體）

- **單元＋整合**：`node --test` 全綠（chapters／parse／markdown／render／build 共約 20 tests，含舊格式失敗負向測試）。
- **本機端到端**：`node site/build.js` 產出 66 章＋目錄＋首頁＋資產＋robots；`npx --yes serve dist` 本機瀏覽。
- **線上端到端**：Task 8 Step 5 的 8 項對照 spec §11 驗收標準（含劇透不可達、JS-off 可讀、舊格式建置失敗負向驗收）。

## 檔案落點總覽（皆新增，不動既有書檔／系統檔）

```
package.json                          零依賴 Node 專案
site.config.json                      多書設定（當前只發佈一世之尊）
site/build.js                         建置協調器（＋CLI）
site/lib/chapters.js                  收檔／數值排序／重號偵測
site/lib/parse.js                     標題解析＋乾淨格式檢查
site/lib/markdown.js                  剝註解／轉義／粗體／段落
site/lib/render.js                    章頁／目錄頁／首頁模板
site/lib/*.test.js                    node --test 單元測試
site/build.test.js                    建置整合測試
site/assets/style.css                 dark 排版（CSS 變數，Task 8 校準）
site/assets/app.js                    字級調整＋進度記憶（漸進增強）
site/test-fixtures/                   測試夾具（goodbook／oldbook／site.config.json）
.github/workflows/pages.yml           push→建置→部署
.gitignore                            +/dist/
docs/superpowers/plans/2026-07-24-novel-reader-site.md   本計畫（核准後從 plan-mode 檔複製）
```
