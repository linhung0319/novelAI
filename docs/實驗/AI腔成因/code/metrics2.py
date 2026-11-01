"""事後探索指標（讀稿後提出，非預註冊）。發現與驗證用的是同一批文本，只能當線索，不算證據。

只量「敘述」時先把「」內對白剝掉，否則對白多的文本會被算成敘述活潑。
"""
import collections, json, pathlib, re, statistics as st, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from metrics import NUM, hanzi

ROOT = pathlib.Path(__file__).resolve().parents[1]
QUOTE = re.compile(r"「[^「」]*」")
PATTERNS = {
    "simile": r"像|彷彿|彷佛|如同|宛如|似的|好像|一般地",
    "narr_excl": r"！",
    "narr_ques": r"？",
    "silent_gesture": r"沒說話|沒有說話|什麼也沒說|沒再說|沒多說|沒作聲|不作聲|一言不發|沒抬頭|沒有抬頭|頭也不抬|沒回頭|沒有回頭|沒應|沒答|沒有回答|沒吭聲|沒看|沒有看",
    "num_gt1": r"(?:\d+|[二兩三四五六七八九十百千萬]+)(?:個|次|下|步|塊|道|天|夜|刻|口|聲|趟|分|度|筆|頁|張|行|字|人|隻|根|圈|層|年|月|尺|寸|息|遍|眼|秒|時辰|炷香|盞|排|條|把)",
    "yi_quant": r"一(?:個|次|下|步|塊|道|刻|口|聲|趟|分|筆|頁|張|行|字|人|隻|根|圈|層|尺|寸|息|遍|眼|秒|盞|排|條|把)",
    "speech_tag": r"(?:地|說|笑|冷冷|問|答)道[：，]|道：「",
}


def compute2(t):
    narr = QUOTE.sub("", t)
    k = max(hanzi(t), 1) / 1000
    kn = max(hanzi(narr), 1) / 1000
    out = {}
    for name, p in PATTERNS.items():
        scope = t if name == "speech_tag" else narr
        out[name] = len(re.findall(p, scope)) / (k if name == "speech_tag" else kn)
    return out


def auc(a, b):
    return sum((x > y) + 0.5 * (x == y) for x in a for y in b) / (len(a) * len(b))


if __name__ == "__main__":
    KEY = json.load(open(ROOT / "corpus_key.json", encoding="utf-8"))
    rows = []
    numc = {"human": collections.Counter(), "old": collections.Counter(), "S2_trial": collections.Counter()}
    for tid, l in KEY.items():
        t = (ROOT / "corpus" / f"{tid}.txt").read_text(encoding="utf-8")
        rows.append(dict(l, **compute2(t)))
        bucket = "human" if l["group"].startswith("human") else "old" if l["group"] == "old_ai" else ("S2_trial" if l.get("scene") == "S2" else None)
        if bucket:
            numc[bucket].update(m.group(0) for m in NUM.finditer(t))
    for b, c in numc.items():
        print(b, "top數量詞", c.most_common(14))
    H = [r for r in rows if r["group"].startswith("human")]
    O = [r for r in rows if r["group"] == "old_ai"]
    names = list(PATTERNS)
    print("\nmetric".ljust(17), "人類".rjust(7), "舊AI".rjust(7), "AUC".rjust(6))
    for m in names:
        print(m.ljust(16), f"{st.median(r[m] for r in H):7.2f}{st.median(r[m] for r in O):7.2f}{auc([r[m] for r in O], [r[m] for r in H]):6.2f}")
    print()
    print("arm".ljust(14), "n", *[n[:9].rjust(9) for n in names])
    arms = sorted({(r["scene"], r["arm"]) for r in rows if r["group"] == "trial"})
    for s, a in arms:
        g = [r for r in rows if r["group"] == "trial" and r["scene"] == s and r["arm"] == a]
        print(f"{s}_{a}".ljust(14), len(g), *[f"{st.median(r[n] for r in g):9.2f}" for n in names])
    g = [r for r in rows if r["group"] == "human_scene"]
    print("S2_HUMAN".ljust(14), len(g), *[f"{st.median(r[n] for r in g):9.2f}" for n in names])
