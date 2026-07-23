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
