"""獨立查證：不信回答的自述，從工具紀錄和原文核對。

1. 每題實際讀或搜了哪些路徑，有沒有真的碰 cards/hidden、drafts。
2. 截至題有沒有讀超出範圍的章。
3. 回答裡每句引文重新比對原文。
"""
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
BOOK = HERE.parents[3] / "novel-desk" / "books" / "一世之尊-測試"
LIMIT = {"Q06": 72, "Q07": 40}


def norm(text):
    return re.sub(r"\s+", "", text)


def body(path):
    return norm(re.sub(r"\A---\n.*?\n---\n", "", path.read_text(encoding="utf-8"), flags=re.S))


CHAPTERS = {p.stem: body(p) for p in (BOOK / "chapters").glob("ch*.md")}
total = bad = 0
for path in sorted((HERE / "輸出").glob("Q*.jsonl")):
    qid = path.stem
    reads, greps, result = [], [], ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            result = ev.get("result", "")
        msg = ev.get("message")
        if not (isinstance(msg, dict) and isinstance(msg.get("content"), list)):
            continue
        for b in msg["content"]:
            if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                continue
            i = b["input"]
            if b["name"] == "Read":
                reads.append(i.get("file_path", ""))
            elif b["name"] in ("Grep", "Glob"):
                greps.append(f"{i.get('path', '<cwd>')} glob={i.get('glob')}")
            elif b["name"] in ("Bash", "PowerShell") and "check_quotes" not in i.get("command", ""):
                greps.append("SHELL " + i.get("command", "")[:150])
    chs = sorted({m for r in reads for m in re.findall(r"ch\d{4}", r)})
    sensitive = [x for x in reads + greps if re.search(r"hidden|drafts", x)]
    wide = [g for g in greps if re.search(r"測試(?:[\\/\"']?\s*glob|\s+glob)|<cwd>", g)]
    print(f"== {qid} 讀 {len(reads)} 檔，章 {chs[:6]}{'…' if len(chs) > 6 else ''}（{len(chs)} 章）")
    if sensitive:
        print("   碰敏感路徑：", sensitive)
    if wide:
        print("   搜整本或未指定路徑：", wide[:4])
    if qid in LIMIT:
        print("   超出範圍的讀取：", [c for c in chs if int(c[2:]) > LIMIT[qid]] or "無")
        print("   回答提到超出範圍的章：", [c for c in set(re.findall(r"ch\d{4}", result)) if int(c[2:]) > LIMIT[qid]] or "無")
    for line in result.splitlines():
        m = re.search(r"(ch\d{4})[^：「\n]*：「(.*)", line)
        if not m:
            continue
        quote = re.sub(r"」?[^」]*$", "", m.group(2)) or m.group(2)
        total += 1
        if norm(quote) not in CHAPTERS[m.group(1)]:
            bad += 1
            print(f"   引文對不上 {m.group(1)}：{quote}")
print(f"\n引文 {total} 句，對不上 {bad} 句")

print("\n-- 其他事實核對 --")
for label, ch, word in [
    ("Q03 ch0046 有妙音二字", "ch0046", "妙音"), ("Q13 ch0005 有玄恩", "ch0005", "玄恩"),
    ("Q13 ch0005 有左手", "ch0005", "左手"), ("Q13 ch0005 有傷", "ch0005", "傷"),
]:
    print(label, word in CHAPTERS[ch])
for word in ("玄藏", "紫檀", "十來年前", "馬蜂窩", "第七塊"):
    hit = sorted(c for c, t in CHAPTERS.items() if word in t)
    print(word, "最後", hit[-1] if hit else None, "共", len(hit), "章")
for ch in ("ch0074", "ch0075"):
    t = (BOOK / "chapters" / f"{ch}.md").read_text(encoding="utf-8")
    for line in t.splitlines():
        if re.search(r"曉得，是誰在給|連真觀自己都不知道", line):
            print(ch, line[:160])
