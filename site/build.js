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
