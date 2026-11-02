"""每題開一個新的 claude -p，從 novel-desk 根目錄觸發 /search，輸出存到 輸出/。

用法：python 跑題.py [題號 ...]   不給題號就跑全部；已有輸出的題不重跑。
答案不放在這裡，也不給受測的 claude 看。
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
BOOK = "一世之尊-測試"
TOOLS = "Read,Grep,Glob,Agent,Bash(python:*)"


def run(item):
    path = OUT / f"{item['id']}.jsonl"
    if path.exists():
        return item["id"], "已有"
    prompt = f"/search {BOOK} {item['q']}"
    try:
        done = subprocess.run(
            [shutil.which("claude"), "-p", prompt, "--output-format", "stream-json", "--verbose",
             "--allowedTools", TOOLS],
            cwd=DESK, capture_output=True, text=True, encoding="utf-8", timeout=1500,
        )
    except subprocess.TimeoutExpired:
        return item["id"], "逾時"
    path.write_text(done.stdout, encoding="utf-8")
    return item["id"], f"exit {done.returncode}"


def main():
    OUT.mkdir(exist_ok=True)
    items = json.loads((HERE / "題目.json").read_text(encoding="utf-8"))
    if sys.argv[1:]:
        items = [i for i in items if i["id"] in sys.argv[1:]]
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        for qid, status in pool.map(run, items):
            print(qid, status, flush=True)


if __name__ == "__main__":
    main()
