"""開對照表後分析：盲讀分數、確定性輔助、抄襲、刪句清單。
用法：python fix_analyze.py <key_path> [--cuts]
"""
import glob, json, pathlib, re, statistics as st, sys
import fix_lib as L

key = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
scores = json.loads((L.ROOT / "fix_blind_scores.json").read_text(encoding="utf-8"))
print("== 盲讀（問題總分越低越好 / 講故事越高越好）")
rows = sorted((key[k], sum(v["p"]), v["story"], v["p"]) for k, v in scores.items() if k in key)
for r in rows:
    print(f"{r[0]:14s} 問題={r[1]:2d} 講故事={r[2]} {r[3]}")


def metrics(t):
    body = re.sub(r"\s", "", t)
    n = max(len(body), 1)
    no_q = re.sub(r"「[^」]*」", "", t)
    paras = [p.strip() for p in re.split(r"\n+", t) if p.strip()]
    sents = [s for s in re.split(r"[。！？]", no_q) if s.strip()]
    closes = [re.split(r"[。！？]", p.rstrip("。！？」"))[-1] for p in paras]
    return {
        "chars": n,
        "narr_excl": no_q.count("！") / n * 1000,
        "dialogue": sum(len(q) for q in re.findall(r"「[^」]*」", t)) / n,
        "neg": len(re.findall(r"沒有|沒", t)) / n * 1000,
        "single": sum(1 for p in paras if len(re.findall(r"[。！？]", p)) <= 1) / max(len(paras), 1),
        "short_close": sum(1 for c in closes if len(c) <= 12) / max(len(closes), 1),
        "sent": st.median(len(s) for s in sents) if sents else 0,
    }


print("\n== 確定性輔助（各臂中位數，未刪稿）")
for m in "cq":
    for s in ("S1", "S2"):
        for a in ("B0", "V", "P"):
            ms = [metrics(pathlib.Path(f).read_text(encoding="utf-8")) for f in glob.glob(str(L.OUT / f"{m}_{s}_{a}_?.md"))]
            if ms:
                print(m, s, f"{a:2s} n={len(ms)}", {k: round(st.median(x[k] for x in ms), 2) for k in ms[0]})
h = next(k for k, v in key.items() if v == "HUMAN")
print("HUMAN", {k: round(v, 2) for k, v in metrics((pathlib.Path(sys.argv[1]).parent / "blind" / f"{h}.md").read_text(encoding="utf-8")).items()})


def lcs(a, b):
    best, prev = 0, [0] * (len(b) + 1)
    for ca in a:
        cur = [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


print("\n== 抄襲與走樣")
NAMES = {"S1": ["周明瑞", "克萊恩", "梅麗莎", "班森", "廷根", "魯恩"], "S2": ["陳莫白", "南宮玄玉", "丹霞", "元陽", "方寸書"]}
SIMP = set("这们说来时为会对么话头发边还里后经过见让门问从进没给")
for f in sorted(glob.glob(str(L.OUT / "*_V_?.md"))):
    t = pathlib.Path(f).read_text(encoding="utf-8")
    s = pathlib.Path(f).stem.split("_")[1]
    print(pathlib.Path(f).stem, "LCS", lcs(re.sub(r"\s", "", t), re.sub(r"\s", "", L.sample(s))), "專名", [n for n in NAMES[s] if n in t])
print("簡體字混入：", [(pathlib.Path(f).stem, sum(c in SIMP for c in pathlib.Path(f).read_text(encoding="utf-8"))) for f in sorted(glob.glob(str(L.OUT / "*.md"))) if ".cut" not in f and sum(c in SIMP for c in pathlib.Path(f).read_text(encoding="utf-8")) > 20])

print("\n== 刪句比例")
for f in sorted(glob.glob(str(L.OUT / "*.cut.json"))):
    stem = pathlib.Path(f).name[:-9]
    t = (L.OUT / f"{stem}.md").read_text(encoding="utf-8")
    d = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))["delete"]
    _, rem, tot = L.apply_cut(t, d)
    print(stem, f"{len(rem)}/{tot}")
    if "--cuts" in sys.argv and (stem.startswith("c_") or stem.endswith("_1")):
        for x in rem:
            print("   -", x)
