"""獨立查證：不信回答的自述，從工具紀錄和原文核對，並把回答印到 輸出/彙整.md 供親讀。

用法：
  python 查證.py --snapshot   跑題前記錄兩本書的檔案雜湊
  python 查證.py              查所有輸出，並比對雜湊
"""
import hashlib
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
BOOKS = HERE.parents[3] / "novel-desk" / "books"
NAMES = ["幫我看-測試", "雁門鏢-測試"]
SNAP = HERE / "輸出" / "雜湊.json"
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
BANNED = {
    "Q08": ["三更添油", "眼線"], "Q10": ["齊腕斷了"], "Q11": ["血書", "韓家長子", "韓家派"],
    "Q12": ["血書", "韓家長子", "韓家派"], "Q13": ["血書", "韓家長子", "韓家派"],
    "Q14": ["清景"],
}


def hashes():
    table = {}
    for name in NAMES:
        for p in sorted((BOOKS / name).rglob("*")):
            if p.is_file() and ".git" not in p.parts:
                table[str(p.relative_to(BOOKS))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return table


def norm(text):
    return re.sub(r"\s+", "", text)


def parse(path):
    calls, result, cost, denied = [], "", None, []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            result, cost = ev.get("result", ""), ev.get("total_cost_usd")
            denied = ev.get("permission_denials", [])
        msg = ev.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("content"), list):
            for b in msg["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    calls.append((b["name"], b["input"]))
    return calls, result, cost, denied


def book_for(qid, items):
    return "雁門鏢-測試" if any(i["id"] == qid and "雁門鏢" in i["prompt"] for i in items) else "幫我看-測試"


def quote_hits(result, book):
    """回答裡「標章號或路徑：「引文」」的引文，逐字比對；回傳 (總數, 對不上的)。"""
    total, bad = 0, []
    for line in result.splitlines():
        for src, quote in re.findall(r"(ch\d{4}|[\w./\-一-鿿]+\.md)[^「\n]{0,12}「([^」\n]{6,})」", line):
            if src.startswith("ch"):
                p = BOOKS / book / "chapters" / f"{src}.md"
            else:
                p = next(iter((BOOKS / book).rglob(pathlib.Path(src).name)), None)
            total += 1
            if not p or not p.is_file() or norm(quote.rstrip("…")) not in norm(p.read_text(encoding="utf-8")):
                bad.append(f"{src}「{quote}」")
    return total, bad


def main():
    if "--snapshot" in sys.argv:
        SNAP.parent.mkdir(exist_ok=True)
        SNAP.write_text(json.dumps(hashes(), ensure_ascii=False), encoding="utf-8")
        print("已記錄", len(hashes()), "檔")
        return
    items = json.loads((HERE / "題目.json").read_text(encoding="utf-8"))
    order = [i["id"] for i in items]
    report, total_cost = ["# 回答彙整\n"], 0
    for qid in order:
        path = HERE / "輸出" / f"{qid}.jsonl"
        if not path.exists():
            print(f"== {qid} 沒有輸出")
            continue
        calls, result, cost, denied = parse(path)
        total_cost += cost or 0
        book = book_for(qid, items)
        reads = [i.get("file_path", "") for n, i in calls if n == "Read"]
        searches = [f"{i.get('path', '<cwd>')} pat={i.get('pattern')} glob={i.get('glob')}" for n, i in calls if n in ("Grep", "Glob")]
        shells = [i.get("command", "") for n, i in calls if n in ("Bash", "PowerShell")]
        agents = [i.get("prompt", "") for n, i in calls if n == "Agent"]
        skill = [i.get("skill") for n, i in calls if n == "Skill"]
        writes = [n for n, _ in calls if n in WRITE_TOOLS]
        sensitive = [x for x in reads + searches if re.search(r"hidden|drafts", x)]
        shell_sensitive = [x[:200] for x in shells if "check_quotes" not in x and re.search(r"hidden|drafts", x)]
        cards = [pathlib.Path(r).stem for r in reads if re.search(r"knowledge[\\/]cards", r)]
        index = any("索引" in r for r in reads)
        chapters = sorted({m for r in reads for m in re.findall(r"ch\d{4}", r)})
        wide = [s for s in searches if s.startswith("<cwd>") or re.search(r"測試[\\/]?\s+pat", s)]
        checked = sum("check_quotes" in s for s in shells)
        total, bad = quote_hits(result, book)
        banned = [w for w in BANNED.get(qid, []) if w in result]
        print(f"== {qid} ${cost if cost is None else round(cost, 2)} skill={skill} 索引={index} 卡={cards} 章={chapters[:6]}{'…' if len(chapters) > 6 else ''}（{len(chapters)}）核對腳本={checked} 引文={total}")
        for label, value in [("寫入工具", writes), ("被拒", [d.get("tool_name") for d in denied]), ("敏感路徑", sensitive), ("shell 提到敏感路徑（親查是列檔名還是讀內容）", shell_sensitive),
                             ("搜整本或未指定", wide), ("引文對不上", bad), ("禁用字", banned)]:
            if value:
                print(f"   {label}：{value}")
        if agents:
            print(f"   subagent {len(agents)} 個；subagent 內部的讀取不在主紀錄，說明要親讀")
            for a in agents:
                print("     ", a[:300].replace("\n", " "))
        report += [f"\n## {qid}\n", f"> {next(i['prompt'] for i in items if i['id'] == qid)}\n\n", result, "\n"]
    print(f"\n總成本 ${total_cost:.2f}")
    if SNAP.exists():
        before, after = json.loads(SNAP.read_text(encoding="utf-8")), hashes()
        changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
        print("書檔有變動：", changed or "無")
    (HERE / "輸出" / "彙整.md").write_text("".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
