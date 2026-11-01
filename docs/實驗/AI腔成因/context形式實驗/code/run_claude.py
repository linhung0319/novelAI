"""Claude 臂，路徑同第一輪 A 臂。可重入。用法：python run_claude.py <n> <workers>"""
import concurrent.futures as cf, json, os, pathlib, subprocess, sys, time
from lib import OUT, SYS, jobs, prompt

EMPTY = pathlib.Path(os.environ["TEMP"]) / "claude-clean-exp"
EMPTY.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)
CMD = ["claude", "-p", "--setting-sources", "", "--system-prompt", SYS, "--tools", "", "--model", "claude-opus-5-5",
       "--effort", "high", "--output-format", "json", "--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"]


def run(job):
    s, a, i = job
    out = OUT / f"c_{s}_{a}_{i}.md"
    if out.exists():
        return f"skip {out.name}"
    t = time.time()
    r = subprocess.run(CMD, input=prompt(s, a).encode("utf-8"), capture_output=True, cwd=EMPTY, timeout=1500)
    try:
        d = json.loads(r.stdout.decode("utf-8"))
    except Exception:
        return f"FAIL {out.name} rc={r.returncode} {r.stderr[:300]!r}"
    if d.get("is_error"):
        return f"ERR {out.name} {d.get('result')}"
    out.write_text(d["result"], encoding="utf-8")
    u = d.get("usage", {})
    m = {"cost": d.get("total_cost_usd"), "in": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0), "out": u.get("output_tokens"), "sec": round(time.time() - t)}
    out.with_suffix(".json").write_text(json.dumps(m), encoding="utf-8")
    return f"ok {out.name} {len(d['result'])} {m}"


if __name__ == "__main__":
    n, w = int(sys.argv[1]), int(sys.argv[2])
    with cf.ThreadPoolExecutor(w) as ex:
        for m in ex.map(run, jobs(n)):
            print(m, flush=True)
