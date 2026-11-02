"""獨立查證：從工具紀錄和 subagent 紀錄核對，並把回答印到 輸出/彙整.md 供親讀。

用法：
  python 查證.py --snapshot   跑題前記錄測試書的檔案雜湊
  python 查證.py              查所有輸出，並比對雜湊
"""
import hashlib
import json
import os
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
BOOKS = HERE.parents[3] / "novel-desk" / "books"
NAMES = ["局部操作-測試", "一世之尊-測試"]
SNAP = HERE / "輸出" / "雜湊.json"
SESSIONS = pathlib.Path(os.path.expanduser("~/.claude/projects/C--Users-user-Programming-novel-desk"))
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
SHEN = ["血書", "韓家長子", "韓家派", "徹底廢掉", "逼林硯"]
BANNED = {"P01": ["三更添油", "眼線"], "P02": SHEN, "P03": SHEN, "P04": SHEN, "P05b": SHEN, "P06b": SHEN,
          "P07b": SHEN, "P08a": SHEN, "P12": SHEN, "P13": SHEN, "P15": SHEN, "P16": SHEN}
NO_FORK = {"P05a", "P06a", "P06b", "P06c", "P07a", "P08b", "P09", "P09h", "P14"}
LATER_THAN = {"P01": 4}


def hashes():
    table = {}
    for name in NAMES:
        for p in sorted((BOOKS / name).rglob("*")):
            if p.is_file() and ".git" not in p.parts:
                table[str(p.relative_to(BOOKS))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return table


def parse(path):
    global fork_saw_hidden
    fork_saw_hidden = False
    main_calls, fork_calls, fork_prompt, result, cost, sid = [], [], "", "", None, None
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            result, cost, sid = ev.get("result", ""), ev.get("total_cost_usd"), ev.get("session_id")
        msg = ev.get("message")
        if not (isinstance(msg, dict) and isinstance(msg.get("content"), list)):
            continue
        forked = str(ev.get("parent_tool_use_id") or "").startswith("forked-command")
        for b in msg["content"]:
            if not isinstance(b, dict):
                continue
            if forked and b.get("type") == "tool_result" and re.search(r"cards[\/]+hidden", json.dumps(b.get("content"), ensure_ascii=False)):
                fork_saw_hidden = True
            if b.get("type") == "tool_use":
                (fork_calls if forked else main_calls).append((b["name"], b["input"]))
            elif b.get("type") == "text" and forked and ev.get("type") == "user" and not fork_prompt:
                fork_prompt = b["text"]
    return main_calls, fork_calls, fork_prompt, result, cost, sid


def fork_final(sid):
    """subagent 紀錄裡，每個 fork 最後一段回覆。"""
    texts = []
    for p in sorted((SESSIONS / str(sid) / "subagents").glob("*.jsonl")) if sid else []:
        last = ""
        for raw in p.read_text(encoding="utf-8").splitlines():
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg = ev.get("message")
            if ev.get("type") == "assistant" and isinstance(msg, dict) and isinstance(msg.get("content"), list):
                joined = "".join(b.get("text", "") for b in msg["content"] if isinstance(b, dict) and b.get("type") == "text")
                last = joined or last
        texts.append(last)
    return texts


def fork_leak(sid):
    """整份 subagent 紀錄裡有沒有水下的字，比回答和 prompt 更嚴。"""
    words = SHEN + ["三更添油", "眼線"]
    text = "".join(p.read_text(encoding="utf-8") for p in (SESSIONS / str(sid) / "subagents").glob("*.jsonl"))
    return [w for w in words if w in text]


def path_of(tool, i):
    if tool == "Read":
        return i.get("file_path", "")
    if tool in ("Grep", "Glob"):
        return f"{i.get('path', '<cwd>')} pat={i.get('pattern')} glob={i.get('glob')}"
    if tool in ("Bash", "PowerShell"):
        return i.get("command", "")
    return ""


def norm(text):
    return re.sub(r"\s+", "", text)


def main():
    if "--snapshot" in sys.argv:
        SNAP.parent.mkdir(exist_ok=True)
        SNAP.write_text(json.dumps(hashes(), ensure_ascii=False), encoding="utf-8")
        print("已記錄", len(hashes()), "檔")
        return
    items = json.loads((HERE / "題目.json").read_text(encoding="utf-8"))
    report, total_cost = ["# 回答彙整\n"], 0
    for item in items:
        qid = item["id"]
        path = HERE / "輸出" / f"{qid}.jsonl"
        if not path.exists():
            print(f"== {qid} 沒有輸出")
            continue
        main_calls, fork_calls, fork_prompt, result, cost, sid = parse(path)
        total_cost += cost or 0
        fork_reads = [i.get("file_path", "") for n, i in fork_calls if n == "Read"]
        fork_all = [path_of(n, i) for n, i in fork_calls]
        fork_reads_all = [p for p in fork_all if p]
        sensitive = [p for p in fork_reads if re.search(r"hidden|drafts", p)]
        fork_search_sensitive = [p for n, i in fork_calls if n in ("Grep", "Glob") for p in [path_of(n, i)] if re.search(r"hidden|drafts", p)]
        shells = [path_of(n, i)[:200] for n, i in fork_calls if n in ("Bash", "PowerShell")]
        knowledge = [pathlib.Path(p).stem for p in fork_reads if "knowledge" in p]
        chapters = sorted({int(m) for p in fork_reads for m in re.findall(r"ch(\d{4})", p)})
        later = [c for c in chapters if qid in LATER_THAN and c > LATER_THAN[qid]]
        main_writes = [(n, i.get("file_path")) for n, i in main_calls if n in WRITE_TOOLS]
        fork_writes = [(n, i.get("file_path")) for n, i in fork_calls if n in WRITE_TOOLS]
        main_reads = [i.get("file_path", "") for n, i in main_calls if n == "Read"]
        banned = [w for w in BANNED.get(qid, []) if w in result]
        prompt_hit = [w for w in SHEN + ["三更添油", "眼線"] if w in fork_prompt]
        finals = fork_final(sid) if fork_calls or fork_prompt else []
        relay = None
        if finals:
            relay = norm(finals[-1]) == norm(result)
        print(f"== {qid} ${None if cost is None else round(cost, 2)} fork={'是' if fork_prompt else '否'} fork讀章={chapters} 招卡={knowledge} 轉交逐字={relay}")
        for label, value in [("主對話讀", [p for p in main_reads if re.search('hidden|drafts|knowledge', p)]),
                             ("主對話寫", main_writes), ("fork 寫", fork_writes),
                             ("fork 讀敏感", sensitive), ("fork 搜尋提到敏感", fork_search_sensitive),
                             ("fork 看到水下檔名", ["是"] if fork_saw_hidden else []),
                             ("fork 紀錄有水下字", fork_leak(sid) if fork_prompt else []),
                             ("fork shell", shells), ("讀了之後的章", later),
                             ("fork prompt 有水下字", prompt_hit), ("禁用字", banned),
                             ("該走 fork 沒走", [] if fork_prompt or qid in NO_FORK else ["未走 fork"]),
                             ("不該走 fork 卻走", ["走了 fork"] if fork_prompt and qid in NO_FORK else [])]:
            if value:
                print(f"   {label}：{value}")
        report += [f"\n## {qid}\n", f"> {item['prompt']}\n\n", result, "\n"]
        if relay is False:
            report += ["\n### fork 原始回覆（和上面不同）\n\n", finals[-1], "\n"]
    print(f"\n總成本 ${total_cost:.2f}")
    if SNAP.exists():
        before, after = json.loads(SNAP.read_text(encoding="utf-8")), hashes()
        print("書檔有變動：", [k for k in set(before) | set(after) if before.get(k) != after.get(k)] or "無")
    (HERE / "輸出" / "彙整.md").write_text("".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
