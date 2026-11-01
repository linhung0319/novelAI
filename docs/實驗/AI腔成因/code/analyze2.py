"""探索性分析（事後，非預註冊）：哪些指標真的分得開人類與舊 AI 稿；各臂落在哪。

不依賴會被洗牌的 corpus id 以外的東西；只讀 results.json，先跑 analyze.py。
"""
import json, pathlib, statistics as st

ROOT = pathlib.Path(__file__).resolve().parents[1]
rows = json.load(open(ROOT / "results.json", encoding="utf-8"))
HUMAN = [r for r in rows if r["group"] in ("human_base", "human_scene")]
OLD = [r for r in rows if r["group"] == "old_ai"]
METRICS = ["SE", "J1", "J2", "J3", "J4", "neg_contrast", "explain_marker", "single_para", "short_close", "numeral", "negation_gesture", "dialogue_ratio", "sent_mean", "sent_cv", "para_mean", "he_ba"]


def auc(a, b):
    """P(a 隨機一篇 > b 隨機一篇)，0.5 = 完全分不開。"""
    wins = sum((x > y) + 0.5 * (x == y) for x in a for y in b)
    return wins / (len(a) * len(b))


print(f"人類 n={len(HUMAN)}  舊AI n={len(OLD)}")
print("metric".ljust(18), "人類中位".rjust(8), "舊AI中位".rjust(8), "AUC".rjust(6), "分離度".rjust(6))
ranked = []
for m in METRICS:
    h = [r[m] for r in HUMAN if r.get(m) is not None]
    o = [r[m] for r in OLD if r.get(m) is not None]
    a = auc(o, h)
    ranked.append((abs(a - 0.5), m, st.median(h), st.median(o), a))
for sep, m, hm, om, a in sorted(ranked, reverse=True):
    print(m.ljust(18), f"{hm:8.2f}{om:8.2f}{a:6.2f}{sep * 2:6.2f}")

ARMS = ["A", "B", "C", "D", "H", "QA", "QB", "QC"]
SHOW = ["SE", "numeral", "negation_gesture", "dialogue_ratio", "sent_mean", "single_para", "short_close", "he_ba", "chars"]
for scene in ("S1", "S2"):
    print(f"\n[{scene}] 各臂中位數")
    print("arm".ljust(8), "n", *[c[:8].rjust(8) for c in SHOW])
    groups = [(a, [r for r in rows if r["group"] == "trial" and r["scene"] == scene and r["arm"] == a]) for a in ARMS]
    if scene == "S2":
        groups.append(("HUMAN", [r for r in rows if r["group"] == "human_scene"]))
    groups.append(("人類基準", HUMAN))
    groups.append(("舊AI", OLD))
    for name, g in groups:
        if not g:
            continue
        vals = []
        for c in SHOW:
            v = [x[c] for x in g if x.get(c) is not None]
            vals.append(f"{st.median(v):8.2f}" if v else "       -")
        print(name.ljust(8), len(g), *vals)

# 預註冊判定（V 不過時僅供記錄）
h_se = sorted(r["SE"] for r in HUMAN if r.get("SE") is not None)
print("\n人類 SE 中位", round(st.median(h_se), 2), "P75", round(st.quantiles(h_se, n=4)[2], 2), "範圍", round(h_se[0], 2), round(h_se[-1], 2))
o_se = [r["SE"] for r in OLD]
print("舊AI SE 中位", round(st.median(o_se), 2), "倍率", round(st.median(o_se) / st.median(h_se), 2), "（V 要求 ≥2）")


def med(scene, arm, m="SE"):
    v = [r[m] for r in rows if r["group"] == "trial" and r["scene"] == scene and r["arm"] == arm and r.get(m) is not None]
    return st.median(v) if v else None


for scene in ("S1", "S2"):
    a, b, c, d, hh = (med(scene, x) for x in "ABCDH")
    print(scene, f"C/A={c/a:.2f} D/B={d/b:.2f} | B/A={b/a:.2f} D/C={d/c:.2f} | H/A={hh/a:.2f}", end="")
    qa = med(scene, "QA")
    if qa:
        print(f" | QA={qa:.2f} A={a:.2f} QB/QA={med(scene,'QB')/qa:.2f} QC/QA={med(scene,'QC')/qa:.2f}")
    else:
        print()
