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
