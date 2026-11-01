"""產生 Claude subagent 的代號工作檔（路徑與檔名不暴露實驗）。

用法：
  python fix_claude_packs.py write <workdir> <n>   → 寫稿任務
  python fix_claude_packs.py cut <workdir>         → 刪句任務（需已有草稿）
  python fix_claude_packs.py collect <workdir>     → 把結果收進 outputs_fix/
"""
import json, pathlib, random, sys
import fix_lib as L

mode, work = sys.argv[1], pathlib.Path(sys.argv[2])
work.mkdir(parents=True, exist_ok=True)
map_path = work / "_map.json"

if mode == "write":
    n = int(sys.argv[3])
    jobs = [(s, a, i) for s in ("S1", "S2") for a in ("B0", "V", "P") for i in range(1, n + 1)]
    random.Random(20261101).shuffle(jobs)
    m = {}
    for k, (s, a, i) in enumerate(jobs, 1):
        code = f"w{k:02d}"
        (work / f"{code}_task.txt").write_text(L.writer_prompt(s, a), encoding="utf-8")
        m[code] = f"c_{s}_{a}_{i}"
    map_path.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(" ".join(sorted(m)))
elif mode == "cut":
    m = json.loads(map_path.read_text(encoding="utf-8"))
    for code in sorted(k for k in m if k.startswith("w")):
        text = (work / f"{code}.md").read_text(encoding="utf-8")
        (work / f"e{code[1:]}_task.txt").write_text(L.cut_prompt(text), encoding="utf-8")
    print("ok")
elif mode == "collect":
    L.OUT.mkdir(exist_ok=True)
    m = json.loads(map_path.read_text(encoding="utf-8"))
    for code, stem in sorted(m.items()):
        src = work / f"{code}.md"
        if not src.exists():
            print("missing", code)
            continue
        text = src.read_text(encoding="utf-8").strip()
        (L.OUT / f"{stem}.md").write_text(text, encoding="utf-8")
        cut = work / f"e{code[1:]}.json"
        if cut.exists():
            dele = L.parse_delete(cut.read_text(encoding="utf-8"))
            (L.OUT / f"{stem}.cut.json").write_text(json.dumps({"delete": dele}), encoding="utf-8")
            new, removed, total = L.apply_cut(text, dele)
            (L.OUT / f"{stem}.cut.md").write_text(new, encoding="utf-8")
            print(stem, len(text), f"cut {len(removed)}/{total}")
        else:
            print(stem, len(text), "no cut")
