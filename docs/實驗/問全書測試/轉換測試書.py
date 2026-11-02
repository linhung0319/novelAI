"""把 一世之尊 複製成 novel-desk 的新格式測試書，不動原書。

用法：python 轉換測試書.py
輸出：novel-desk/books/一世之尊-測試/（在 novel-desk 被 git 忽略）

摘要取自舊章節索引的備註，只留第一段。舊索引不帶過去，否則等於替 skill 建好答案表。
另外埋兩個陷阱：水下卡和落選稿裡的假事實，用來測它們會不會被當成答案。
"""
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[3]
OLD = ROOT / "一世之尊"
NEW = ROOT.parent / "novel-desk" / "books" / "一世之尊-測試"

ALIASES = {"無退": ["血狂僧"], "孟奇": ["真定"]}

HIDDEN = """---
別名: [真慧]
---
測試用的假水下，不是原書設定。

真慧其實是玄藏安插在雜役院的眼線，和玄藏對話的暗號是「三更添油」。
"""

DRAFT = """（測試用的落選稿，不是原書內容。）

那一刀落下來，我的左手齊腕斷了。我看著那隻手在雪地裡滾了兩圈，才想起來要喊。
"""


def summaries():
    table = {}
    for line in (OLD / "chapters" / "_index.ai.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 7 and re.fullmatch(r"ch\d{4}", cells[1]):
            note = re.sub(r"\[\[|\]\]|\*\*", "", cells[7])
            table[cells[1]] = re.split(r"[；（]", note)[0].strip()[:60]
    return table


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def copy_cards(old_dir, new_dir):
    for src in sorted(old_dir.glob("*.md")):
        if src.name.endswith(".ai.md") or src.name.startswith("_"):
            continue
        text = src.read_text(encoding="utf-8")
        names = ALIASES.get(src.stem, [])
        write(new_dir / src.name, f"---\n別名: [{', '.join(names)}]\n---\n{text}")


def main():
    if NEW.exists():
        raise SystemExit(f"已存在，請先確認再處理：{NEW}")
    table = summaries()
    for src in sorted((OLD / "chapters").glob("ch*.md")):
        if src.name.endswith(".ai.md"):
            continue
        text = re.sub(r"<!--.*?-->\n*", "", src.read_text(encoding="utf-8"))
        head = f"---\n摘要: {table[src.stem]}\nPOV: 孟奇\n---\n\n"
        write(NEW / "chapters" / src.name, head + text)

    story = OLD / "story"
    copy_cards(story / "設定" / "角色", NEW / "cards" / "characters")
    copy_cards(story / "設定" / "世界觀", NEW / "cards" / "world")
    write(NEW / "摘要.md", (story / "00-摘要.md").read_text(encoding="utf-8"))
    write(NEW / "outline" / "總綱.md", (story / "01-大綱.md").read_text(encoding="utf-8"))
    for sub, dest in (("大綱", "outline"), ("幕綱", "beats")):
        for src in sorted((story / sub).glob("arc*.md")):
            (NEW / dest).mkdir(parents=True, exist_ok=True)
            shutil.copy(src, NEW / dest / src.name)

    write(NEW / "cards" / "hidden" / "真慧.md", HIDDEN)
    write(NEW / "drafts" / "ch0094" / "稿1.md", DRAFT)
    print(f"完成：{len(table)} 章 -> {NEW}")


if __name__ == "__main__":
    main()
