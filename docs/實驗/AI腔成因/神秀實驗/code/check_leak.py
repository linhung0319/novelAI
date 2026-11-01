"""列出指示與原文長度 ≥7 的共同字串。"""
from prepare import BOOK, ROOT, SOURCES, norm

for ch, name in SOURCES.items():
    human = norm((BOOK / name).read_text(encoding="utf-8"))
    brief = norm((ROOT / "指示" / f"ch{ch}.md").read_text(encoding="utf-8"))
    found, i = [], 0
    while i < len(brief):
        n = 0
        while i + n < len(brief) and brief[i:i + n + 1] in human:
            n += 1
        if n >= 7:
            found.append(brief[i:i + n])
            i += n
        else:
            i += 1
    print(ch, found)
