"""判者二：Claude Code subagent（model: sonnet）批次判讀。本腳本只負責切批、驗證、落盤；呼叫 subagent 由主會話用 Agent 工具執行。

用法：
  python judge_agent.py prep <workdir> [size]   切批，寫 <workdir>/batches/bNNN.txt（判據＋候選，無來源資訊）
  python judge_agent.py ingest <workdir>        驗證 <workdir>/out/bNNN.json，合格者寫 judgments_j2/<id>.json；
                                                不合格的候選（缺漏、標籤不在五個之內）若是第一次就寫進重跑批 rNNN.txt，
                                                重跑後仍不合格記「無法判斷」並標 forced
  python judge_agent.py status <workdir>
"""
import json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from rubric import LABELS, RUBRIC, BATCH_OUT, render

HERE = pathlib.Path(__file__).resolve().parents[1]
OUT = HERE / "judgments_j2"
CANDS = {c["id"]: c for c in json.load(open(HERE / "candidates.json", encoding="utf-8"))}


def batch_text(ids):
    body = "\n\n".join(f"### {i}\n{render(CANDS[i])}" for i in ids)
    return RUBRIC + BATCH_OUT + "\n=== 候選開始 ===\n\n" + body + "\n\n=== 候選結束 ===\n"


def prep(wd, size):
    (wd / "batches").mkdir(parents=True, exist_ok=True)
    (wd / "out").mkdir(exist_ok=True)
    ids = list(CANDS)  # candidates.json 已是打亂後的順序，同批候選來自不同篇
    n = -(-len(ids) // size)
    manifest = {}
    for b in range(n):
        part = ids[b * len(ids) // n:(b + 1) * len(ids) // n]
        name = f"b{b:03d}"
        (wd / "batches" / f"{name}.txt").write_text(batch_text(part), encoding="utf-8")
        manifest[name] = part
    (wd / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    print("batches", n, "sizes", min(map(len, manifest.values())), max(map(len, manifest.values())))


def load_out(p):
    t = p.read_text(encoding="utf-8")
    m = re.search(r"\[.*\]", t, re.S)
    try:
        arr = json.loads(m.group(0)) if m else []
    except Exception:
        arr = []
    return {str(x.get("id")): x for x in arr if isinstance(x, dict)}


def ingest(wd):
    OUT.mkdir(exist_ok=True)
    manifest = json.load(open(wd / "manifest.json", encoding="utf-8"))
    log = {"ok": 0, "format_err_first": 0, "forced": 0}
    for name, ids in manifest.items():
        p = wd / "out" / f"{name}.json"
        if not p.exists():
            continue
        got = load_out(p)
        retry = name.startswith("r")
        bad = []
        for i in ids:
            if (OUT / f"{i}.json").exists():
                continue
            x = got.get(i)
            lab = str(x.get("label", "")).strip() if x else ""
            if lab in LABELS:
                rec = {"id": i, "label": lab, "reason": str(x.get("reason", "")), "batch": name, "format_errors": 1 if retry else 0, "forced": False}
            elif retry:
                rec = {"id": i, "label": "無法判斷", "reason": "", "batch": name, "format_errors": 2, "forced": True, "bad": str(x)[:200]}
                log["forced"] += 1
            else:
                bad.append(i)
                continue
            (OUT / f"{i}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            log["ok"] += 1
        if bad:
            log["format_err_first"] += len(bad)
            rname = "r" + name[1:]
            if rname not in manifest:
                manifest[rname] = bad
                (wd / "batches" / f"{rname}.txt").write_text(batch_text(bad), encoding="utf-8")
                print("retry batch", rname, len(bad))
    (wd / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    print(log, "total in judgments_j2:", len(list(OUT.glob("*.json"))), "/", len(CANDS))


def status(wd):
    manifest = json.load(open(wd / "manifest.json", encoding="utf-8"))
    pending = [n for n in manifest if not (wd / "out" / f"{n}.json").exists()]
    print("pending", len(pending), pending)


if __name__ == "__main__":
    cmd, wd = sys.argv[1], pathlib.Path(sys.argv[2])
    if cmd == "prep":
        prep(wd, int(sys.argv[3]) if len(sys.argv) > 3 else 50)
    elif cmd == "ingest":
        ingest(wd)
    else:
        status(wd)
