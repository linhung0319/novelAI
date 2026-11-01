"""確定性輔助與標注彙整，寫 results.json 並印表。用 uv＋opencc 跑。"""
import json, pathlib, re, statistics as st, sys
from difflib import SequenceMatcher
from opencc import OpenCC

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "code"))
from metrics import compute, hanzi  # noqa
from lib import context_parts  # noqa

OUT = ROOT / "outputs"
J = ROOT / "judgments"
OLD = ROOT.parent / "outputs"
CC = OpenCC("s2tw")
FUNC = re.compile(r"[了著過便卻還就又也才而但可再都]")
QUOTE = re.compile(r"「[^「」]*」")
EVENTS = {"S1": ["呵", "霜", "七塊", "平石", "凹地", "賽拉斯", "十七", "炭", "三十頁", "鼻血", "米蘭達"],
          "S2": ["玄藏", "玄苦", "煩惱落盡", "雜役院", "戒律", "玄心", "鐵面鬼", "真應", "真觀", "真慧", "玉佩", "晚膳"]}


def norm(t):
    return CC.convert(t).replace("“", "「").replace("”", "」")


def func_rate(t):
    narr = QUOTE.sub("", t)
    return len(FUNC.findall(narr)) / max(hanzi(narr), 1) * 1000


def lcs(a, b):
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return m.size, a[m.a:m.a + m.size]


def row(t):
    m = compute(t)
    return {"chars": m["chars"], "func": func_rate(t), "sent_med": st.median([hanzi(s) for s in re.findall(r"[^。！？!?…\n]+[。！？!?…」]*", t) if hanzi(s)]), "single": m["single_para"], "neg": m["neg_contrast"], "dlg": m["dialogue_ratio"]}


def summarize(rows, keys):
    return {k: round(st.median(r[k] for r in rows), 2) for k in keys}


def judged():
    key = json.loads((J / "blind_key.json").read_text(encoding="utf-8")) if (J / "blind_key.json").exists() else {}
    res = {}
    for bid, meta in key.items():
        f = J / f"{bid}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        t = re.sub(r"\s", "", (J / "blind" / f"{bid}.txt").read_text(encoding="utf-8"))
        k = max(hanzi(t), 1) / 1000
        c = {}
        total = 0
        for n in ("cut", "force", "tele"):
            ok = [q for q in d.get(n, []) if re.sub(r"\s", "", q) in t]
            c[n] = len(ok) / k
            c[n + "_bad"] = len(d.get(n, [])) - len(ok)
            total += len(ok)
        c["total"] = total / k
        c["smooth"] = d.get("smooth")
        res[bid] = {**meta, **c}
    return res


if __name__ == "__main__":
    rows = {}
    for p in sorted(OUT.glob("[cq]_S*_*_*.md")):
        mod, s, a, i = p.stem.split("_")
        t = norm(p.read_text(encoding="utf-8"))
        r = row(t)
        parts = context_parts(s, a)
        r["lcs"], r["lcs_s"] = max((lcs(t, norm(c)) for c in parts), key=lambda x: x[0])
        r["miss"] = [e for e in EVENTS[s] if e not in t]
        rows.setdefault((mod, s, a), []).append(r)
    keys = ["chars", "func", "sent_med", "single", "neg", "dlg", "lcs"]
    out = {}
    print("模型 場景 臂 n", *keys, "漏事件")
    for k in sorted(rows):
        s = summarize(rows[k], keys)
        out["_".join(k)] = {**s, "miss": [r["miss"] for r in rows[k]], "lcs_s": [r["lcs_s"] for r in rows[k]], "n": len(rows[k])}
        print(*k, len(rows[k]), *[s[x] for x in keys], sum(len(r["miss"]) for r in rows[k]))
    base = {}
    for s in ("S1", "S2"):
        rs = [row(norm((OLD / f"{s}_A_{i}.md").read_text(encoding="utf-8"))) for i in (1, 2, 3)]
        base[s] = summarize(rs, keys[:-1])
        print("第一輪A", s, base[s])
    res = judged()
    groups = {}
    for bid, m in res.items():
        if m["group"] == "trial":
            mod, s, a, i = m["src"].split("_")
            g = (mod, s, a)
        else:
            g = (m["group"],)
        groups.setdefault(g, []).append(m)
    jout = {}
    print("標注：組 n 斷裂 用力 電報 合計 順暢 查無引句")
    for g in sorted(groups):
        v = groups[g]
        row_ = {n: round(st.median(x[n] for x in v), 2) for n in ("cut", "force", "tele", "total", "smooth")}
        bad = sum(x["cut_bad"] + x["force_bad"] + x["tele_bad"] for x in v)
        jout["_".join(g)] = {**row_, "n": len(v), "bad": bad}
        print(*g, len(v), *row_.values(), bad)
    (ROOT / "results.json").write_text(json.dumps({"det": out, "base": base, "judge": jout}, ensure_ascii=False, indent=1), encoding="utf-8")
