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
