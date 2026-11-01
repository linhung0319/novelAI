"""事後輔助（非預註冊）：升級動詞、而是句、Qwen 重複段。"""
import glob, os, re, statistics as st, collections
HV = re.compile(r"砸|釘|撞|碾|劈|剁|摔|扎進|刺進|壓過|灌|轟|炸|撕|咬進|掐|鑿|砍")
g = collections.defaultdict(list); dup = {}
for f in glob.glob("[cq]_S*_*_*.md"):
    t = open(f, encoding="utf-8").read(); m, s, a, i = os.path.basename(f)[:-3].split("_")
    k = max(len(re.findall(r"[一-鿿]", t)), 1) / 1000
    g[(m, s, a)].append((len(HV.findall(t)) / k, len(re.findall(r"而是", t)) / k))
    ps = [p.strip() for p in t.split("\n") if len(p.strip()) > 12]
    d = len(ps) - len(set(ps))
    if d >= 3: dup[os.path.basename(f)] = d
for k in sorted(g):
    if k[0] == "c": print(*k, "重動詞/千字", round(st.median(x[0] for x in g[k]), 2), [round(x[0], 1) for x in g[k]], "而是", round(st.median(x[1] for x in g[k]), 2))
print("Qwen 重複段≥3", dup)
