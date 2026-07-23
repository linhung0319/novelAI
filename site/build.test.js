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
