"""判者一：claude -p，一條候選一個請求，可重入。

用法：python judge_cli.py <workers> [limit]
"""
import concurrent.futures as cf, json, os, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from rubric import LABELS, RUBRIC, SINGLE_OUT, render

HERE = pathlib.Path(__file__).resolve().parents[1]
OUT = HERE / "judgments_j1"
OUT.mkdir(exist_ok=True)
EMPTY = pathlib.Path(os.environ["TEMP"]) / "claude-clean-exp"
EMPTY.mkdir(exist_ok=True)
MODEL = "claude-sonnet-5-5"
CMD = ["claude", "-p", "--setting-sources", "", "--system-prompt", "你是編輯。", "--tools", "", "--model", MODEL,
       "--effort", "medium", "--output-format", "json", "--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"]


def ask(prompt):
    r = subprocess.run(CMD, input=prompt.encode("utf-8"), capture_output=True, cwd=EMPTY, timeout=600)
    d = json.loads(r.stdout.decode("utf-8"))
    return d, d.get("result", "")


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None, ""
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None, ""
    lab = str(j.get("label", "")).strip()
    return (lab if lab in LABELS else None), str(j.get("reason", ""))


def judge(c):
    out = OUT / f"{c['id']}.json"
    if out.exists():
        return None
    prompt = RUBRIC + "\n" + render(c) + "\n" + SINGLE_OUT
    rec = {"id": c["id"], "cost": 0.0, "format_errors": 0, "raw": []}
    for attempt in range(2):  # 格式錯誤重跑一次
        try:
            d, text = ask(prompt)
        except Exception as e:  # CLI 本身失敗（非格式錯誤）：不落盤，下次重入再跑
            return f"CLI-FAIL {c['id']} {e}"
        rec["cost"] += d.get("total_cost_usd") or 0
        rec["raw"].append(text[:300])
        lab, reason = parse(text)
        if lab:
            break
        rec["format_errors"] += 1
    rec["label"] = lab or "無法判斷"
    rec["reason"] = reason if lab else ""
    rec["forced"] = lab is None
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return None if lab else f"FORMAT {c['id']}"


if __name__ == "__main__":
    w = int(sys.argv[1])
    cands = json.load(open(HERE / "candidates.json", encoding="utf-8"))
    if len(sys.argv) > 2:
        cands = cands[: int(sys.argv[2])]
    done = 0
    with cf.ThreadPoolExecutor(w) as ex:
        for m in ex.map(judge, cands):
            done += 1
            if m:
                print(m, flush=True)
            if done % 100 == 0:
                print("progress", done, len(list(OUT.glob("*.json"))), flush=True)
    print("done", len(list(OUT.glob("*.json"))), "/", len(json.load(open(HERE / "candidates.json", encoding="utf-8"))))
