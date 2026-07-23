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
