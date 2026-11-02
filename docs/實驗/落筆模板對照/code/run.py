"""跑 A–E 各 n 稿。可重入：已存在的輸出會跳過。用法：python run.py 3 5"""
import concurrent.futures as cf
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
ST = ROOT / "stimuli"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
EMPTY = pathlib.Path(os.environ["TEMP"]) / "claude-clean-exp-loubi"
EMPTY.mkdir(exist_ok=True)
MODEL = "claude-opus-5-5"
SYS = "你是一位小說作者。"
CMD = ["claude", "-p", "--setting-sources", "", "--system-prompt", SYS, "--tools", "",
       "--model", MODEL, "--effort", "high", "--output-format", "json",
       "--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"]


def run(job):
    arm, i = job
    out = OUT / f"{arm}_{i}.md"
    if out.exists():
        return f"skip {out.name}"
    t = time.time()
    prompt = (ST / f"{arm}.txt").read_text(encoding="utf-8")
    r = subprocess.run(CMD, input=prompt.encode("utf-8"), capture_output=True, cwd=EMPTY, timeout=1500)
    try:
        d = json.loads(r.stdout.decode("utf-8"))
    except Exception:
        return f"FAIL {out.name} rc={r.returncode} {r.stdout[:300]!r} {r.stderr[:300]!r}"
    if d.get("is_error"):
        return f"ERR {out.name} {d.get('result')}"
    out.write_text(d["result"], encoding="utf-8")
    (OUT / f"{arm}_{i}.json").write_text(json.dumps(
        {"cost": d.get("total_cost_usd"), "usage": d.get("usage"), "sec": time.time() - t}), encoding="utf-8")
    return f"ok {out.name} chars={len(d['result'])} cost={d.get('total_cost_usd')} {time.time() - t:.0f}s"


if __name__ == "__main__":
    n, w = int(sys.argv[1]), int(sys.argv[2])
    jobs = [(a, i) for i in range(1, n + 1) for a in "ABCDE"]
    with cf.ThreadPoolExecutor(w) as ex:
        for m in ex.map(run, jobs):
            print(m, flush=True)
