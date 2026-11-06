"""彙整兩個判者的結果，輸出 ../results.json、../人類下判決句.json，並印出摘要。

用法：python analyze.py
"""
import collections, json, pathlib, random, statistics as st, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from rubric import LABELS

HERE = pathlib.Path(__file__).resolve().parents[1]
EXP1 = HERE.parent
TEXTS = json.load(open(HERE / "texts.json", encoding="utf-8"))
CKEY = json.load(open(HERE / "candidates_key.json", encoding="utf-8"))
CANDS = {c["id"]: c for c in json.load(open(HERE / "candidates.json", encoding="utf-8"))}
R1 = {r["id"]: r for r in json.load(open(EXP1 / "results.json", encoding="utf-8"))}  # 第一輪


def load(tag):
    d = {}
    for p in (HERE / f"judgments_{tag}").glob("C*.json"):
        r = json.load(open(p, encoding="utf-8"))
        d[r["id"]] = r
    return d


J = {"j1": load("j1"), "j2": load("j2")}


def group(v):
    if v["group"] == "trial":
        return f"{v['scene']}_{v['arm']}"
    return {"human_base": "人類基準", "old_ai": "舊AI", "human_scene": "S2原著"}[v["group"]]


def per_text(tag):
    by = collections.defaultdict(list)
    for cid, r in J[tag].items():
        by[CKEY[cid]["tid"]].append(r["label"])
    out = {}
    for tid, v in TEXTS.items():
        labs = by.get(tid, [])
        if len(labs) < v["n_sample"]:
            out[tid] = None  # 尚未判完
            continue
        scale = v["n_cand"] / v["n_sample"] if v["n_sample"] else 0
        k = v["narr_chars"] / 1000
        c = collections.Counter(labs)
        out[tid] = {lab: c[lab] * scale / k for lab in LABELS}
        out[tid]["n"] = len(labs)
        out[tid]["share"] = {lab: c[lab] / max(len(labs), 1) for lab in LABELS}
    return out


def kappa(a, b, cats):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[c] * cb[c] for c in cats) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def med(xs):
    return st.median(xs) if xs else None


def main():
    res = {"per_text": {}, "groups": {}, "gate": {}, "kappa": {}, "dist": {}, "format": {}}
    pt = {tag: per_text(tag) for tag in J}
    for tid, v in TEXTS.items():
        res["per_text"][tid] = dict(group=group(v), narr_chars=v["narr_chars"], n_cand=v["n_cand"], n_sample=v["n_sample"],
                                    SE_round1=R1[tid].get("SE"),
                                    **{tag: pt[tag][tid] for tag in J})
    groups = collections.defaultdict(list)
    for tid, v in TEXTS.items():
        groups[group(v)].append(tid)
    for g, tids in sorted(groups.items()):
        gi = {"n": len(tids), "SE_round1_median": med([R1[t]["SE"] for t in tids if R1[t].get("SE") is not None])}
        for tag in J:
            vals = [pt[tag][t]["下判決"] for t in tids if pt[tag][t]]
            fact = [pt[tag][t]["交代事實"] for t in tids if pt[tag][t]]
            rest = [pt[tag][t]["重述"] for t in tids if pt[tag][t]]
            gi[tag] = dict(n_done=len(vals), verdict_median=med(vals), verdict_min=min(vals) if vals else None, verdict_max=max(vals) if vals else None,
                           verdict_values=[round(x, 2) for x in vals], fact_median=med(fact), restate_median=med(rest))
        res["groups"][g] = gi
    for tag in J:
        h, o = res["groups"]["人類基準"][tag]["verdict_median"], res["groups"]["舊AI"][tag]["verdict_median"]
        if h is not None and o is not None:
            res["gate"][tag] = dict(human=h, old_ai=o, ratio=h / o if o else None, passed=h <= o / 2)
    common = sorted(set(J["j1"]) & set(J["j2"]))
    if common:
        a = [J["j1"][i]["label"] for i in common]
        b = [J["j2"][i]["label"] for i in common]
        bin_a = ["下判決" if x == "下判決" else "非" for x in a]
        bin_b = ["下判決" if x == "下判決" else "非" for x in b]
        res["kappa"] = dict(n=len(common), binary=kappa(bin_a, bin_b, ["下判決", "非"]), five=kappa(a, b, LABELS),
                            agree_binary=sum(x == y for x, y in zip(bin_a, bin_b)) / len(common),
                            confusion={f"{x}→{y}": c for (x, y), c in collections.Counter(zip(a, b)).most_common()})
    for tag in J:
        dist = collections.defaultdict(collections.Counter)
        for cid, r in J[tag].items():
            dist[group(TEXTS[CKEY[cid]["tid"]])][r["label"]] += 1
            dist["全部"][r["label"]] += 1
        res["dist"][tag] = {g: dict(c) for g, c in dist.items()}
        res["format"][tag] = dict(format_errors=sum(r.get("format_errors", 0) for r in J[tag].values()),
                                  forced=sum(bool(r.get("forced")) for r in J[tag].values()))
    res["cost_j1_usd"] = sum(r.get("cost", 0) for r in J["j1"].values())
    # 依候選類別看下判決比例（描述用）
    kinds = collections.defaultdict(collections.Counter)
    for cid, r in J["j1"].items():
        g = "人類" if TEXTS[CKEY[cid]["tid"]]["group"].startswith("human") else "AI"
        for k in CKEY[cid]["kinds"]:
            kinds[f"{g}_{k}"][r["label"] == "下判決"] += 1
    res["verdict_share_by_kind_j1"] = {k: dict(n=c[True] + c[False], share=c[True] / max(c[True] + c[False], 1)) for k, c in sorted(kinds.items())}
    (HERE / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    # 人類語料中被標下判決的句子（任一判者）
    hv = []
    for cid, k in CKEY.items():
        v = TEXTS[k["tid"]]
        if not v["group"].startswith("human"):
            continue
        tags = [t for t in J if J[t].get(cid, {}).get("label") == "下判決"]
        if tags:
            hv.append(dict(id=cid, tid=k["tid"], group=group(v), book=v.get("book"), judges=tags, kinds=k["kinds"],
                           prev=CANDS[cid]["prev"], target=CANDS[cid]["target"], next=CANDS[cid]["next"],
                           reasons={t: J[t][cid].get("reason") for t in tags},
                           other={t: J[t].get(cid, {}).get("label") for t in J}))
    hv.sort(key=lambda x: (x["group"], x["tid"], CKEY[x["id"]]["pos"]))
    (HERE / "人類下判決句.json").write_text(json.dumps(hv, ensure_ascii=False, indent=1), encoding="utf-8")

    # 作者核對 20 句：判者一標「下判決」者，受測稿 10、人類（基準＋S2 原著）10，打亂，不標來源
    if len(J["j1"]) == len(CANDS):
        rng = random.Random(20261107)
        pools = {"trial": [], "human": []}
        for cid, r in sorted(J["j1"].items()):
            if r["label"] != "下判決":
                continue
            g = TEXTS[CKEY[cid]["tid"]]["group"]
            if g == "trial":
                pools["trial"].append(cid)
            elif g.startswith("human"):
                pools["human"].append(cid)
        pick = rng.sample(pools["trial"], 10) + rng.sample(pools["human"], min(10, len(pools["human"])))
        rng.shuffle(pick)
        key = {}
        lines = ["# 作者核對 20 句", "",
                 "下面 20 句都被判者標為「下判決」：把前文已演出的行動或情境的含義、動機、意義、情緒直接寫出來，替讀者做了判斷。",
                 "來源混合 AI 稿與人類網文，各半，已打亂。請憑語感填「是」或「不是」：這句讀起來是不是在替你下判決、多餘或刺眼。不用全部填。", "",
                 "| # | 句子 | 是／不是 |", "|---|---|---|"]
        for n, cid in enumerate(pick, 1):
            lines.append(f"| {n} | {CANDS[cid]['target'].replace('|', '｜')} |  |")
            key[n] = dict(id=cid, tid=CKEY[cid]["tid"], group=group(TEXTS[CKEY[cid]['tid']]))
        lines += ["", "## 需要上下文時看這裡", ""]
        for n, cid in enumerate(pick, 1):
            c = CANDS[cid]
            lines.append(f"{n}. 前：{c['prev'] or '（無）'}　**本句**：{c['target']}　後：{c['next'] or '（無）'}")
        (HERE / "作者核對20句.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (HERE / "作者核對20句_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")

    # 摘要
    print("gate", json.dumps(res["gate"], ensure_ascii=False))
    print("kappa", {k: v for k, v in res["kappa"].items() if k != "confusion"})
    print("format", res["format"], "cost_j1", round(res["cost_j1_usd"], 2))
    for g, gi in res["groups"].items():
        print(g.ljust(8), gi["n"], "SE1", None if gi["SE_round1_median"] is None else round(gi["SE_round1_median"], 2),
              *[f"{t}: med={gi[t]['verdict_median'] and round(gi[t]['verdict_median'], 2)} vals={gi[t]['verdict_values']}" for t in J])
    print("human verdict sentences", len(hv))


if __name__ == "__main__":
    main()
