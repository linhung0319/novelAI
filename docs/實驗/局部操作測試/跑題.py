"""每題開一個新的 claude -p，從 novel-desk 根目錄跑，輸出存到 輸出/。

用法：python 跑題.py [題號 ...]   不給題號就跑全部；已有輸出的題不重跑。
resume 接在前一題的 session 後面；fork_from 也接在後面，但另開分支，不影響原 session。
要用 Python 呼叫：從 Git Bash 直接打 claude，/passage 會被轉成 Windows 路徑。
"""
import concurrent.futures
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
DESK = HERE.parents[3] / "novel-desk"
OUT = HERE / "輸出"
TOOLS = "Read,Grep,Glob,Agent,Skill,Bash(python:*)"


def session_of(qid):
    for raw in (OUT / f"{qid}.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            return ev["session_id"]
    raise SystemExit(f"{qid} 沒有 result")


def run(item):
    path = OUT / f"{item['id']}.jsonl"
    if path.exists():
        return item["id"], "已有"
    cmd = [shutil.which("claude"), "-p", item["prompt"], "--output-format", "stream-json", "--verbose",
           "--allowedTools", TOOLS]
    if "resume" in item:
        cmd += ["--resume", session_of(item["resume"])]
    if "fork_from" in item:
        cmd += ["--resume", session_of(item["fork_from"]), "--fork-session"]
    try:
        done = subprocess.run(cmd, cwd=DESK, capture_output=True, text=True, encoding="utf-8",
                              stdin=subprocess.DEVNULL, timeout=1500)
    except subprocess.TimeoutExpired:
        return item["id"], "逾時"
    path.write_text(done.stdout, encoding="utf-8")
    return item["id"], f"exit {done.returncode}"


def main():
    OUT.mkdir(exist_ok=True)
    items = json.loads((HERE / "題目.json").read_text(encoding="utf-8"))
    if sys.argv[1:]:
        items = [i for i in items if i["id"] in sys.argv[1:]]
    first = [i for i in items if "resume" not in i and "fork_from" not in i]
    later = [i for i in items if "resume" in i or "fork_from" in i]
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        for qid, status in pool.map(run, first):
            print(qid, status, flush=True)
    for item in later:
        print(*run(item), flush=True)


if __name__ == "__main__":
    main()
