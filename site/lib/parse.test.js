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
