"""彙整確定性指標與盲評結果。"""
import json, pathlib, statistics as st, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from metrics import compute, hanzi

ROOT = pathlib.Path(__file__).resolve().parents[1]
KEY = json.load(open(ROOT / "corpus_key.json", encoding="utf-8"))
TAGS = [d.name.split("_", 1)[1] for d in sorted(ROOT.glob("judgments_*"))]
rows = []
for tid, l in KEY.items():
    text = (ROOT / "corpus" / f"{tid}.txt").read_text(encoding="utf-8")
    r = dict(l, id=tid, **compute(text))
    k = r["chars"] / 1000
    for f in ("J1", "J2", "J3", "J4"):
        vals = []
        for tag in TAGS:
            p = ROOT / f"judgments_{tag}" / f"{tid}.json"
            if p.exists():
                vals.append(len(json.load(open(p, encoding="utf-8")).get(f, [])) / k)
                r[f"{f}_{tag}"] = vals[-1]
        r[f] = st.mean(vals) if vals else None
    if r["J1"] is not None:
        r["SE"] = r["J1"] + r["J2"]
    rows.append(r)
(ROOT / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def group(r):
    if r["group"] == "trial":
        return f"{r['scene']}_{r['arm']}"
    if r["group"] == "human_scene":
        return "S2_HUMAN"
    if r["group"] == "human_base":
        return "HUMAN"
    return "OLD:" + r["book"]


gs = {}
for r in rows:
    gs.setdefault(group(r), []).append(r)
cols = ["chars", "SE", "J1", "J2", "J3", "J4", "neg_contrast", "explain_marker", "single_para", "short_close", "numeral", "negation_gesture", "dialogue_ratio", "sent_mean", "sent_cv", "para_mean", "he_ba"]
print("group".ljust(18), "n", *[c[:7].rjust(7) for c in cols])
for g in sorted(gs):
    line = []
    for c in cols:
        v = [x[c] for x in gs[g] if x.get(c) is not None]
        line.append(f"{st.median(v):7.2f}" if v else "      -")
    print(g.ljust(18), len(gs[g]), *line)
print("\nper-item SE by group")
for g in sorted(gs):
    print(g.ljust(18), [round(x.get("SE") or -1, 2) for x in gs[g]])
# 評分者一致性
if len(TAGS) >= 2:
    a, b = TAGS[0], TAGS[1]
    for f in ("J1", "J2", "J3", "J4"):
        pairs = [(r.get(f"{f}_{a}"), r.get(f"{f}_{b}")) for r in rows if r.get(f"{f}_{a}") is not None and r.get(f"{f}_{b}") is not None]
        if len(pairs) > 2 and len({p[0] for p in pairs}) > 1 and len({p[1] for p in pairs}) > 1:
            print(f, "pearson r1-r2", round(st.correlation([p[0] for p in pairs], [p[1] for p in pairs]), 3), "n", len(pairs))
