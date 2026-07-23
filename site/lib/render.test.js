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
