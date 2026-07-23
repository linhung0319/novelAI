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
