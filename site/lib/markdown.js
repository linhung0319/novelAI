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
