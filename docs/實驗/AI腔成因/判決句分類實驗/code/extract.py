"""抽候選句。輸出 ../candidates.json（給判者的內容）、../candidates_key.json（編號→來源）、../texts.json（每篇敘述字數與候選數）。

用法：python extract.py
"""
import json, pathlib, random, re

HERE = pathlib.Path(__file__).resolve().parents[1]
EXP1 = HERE.parent
KEY = json.load(open(EXP1 / "corpus_key.json", encoding="utf-8"))
CAP = 80
SEED = 20261107

MARKERS = ["其實", "原來", "意思是", "也就是說", "換句話說", "這就是", "那就是", "這才是", "這意味", "意味著", "代表著",
           "之所以", "正因為", "說到底", "歸根結底", "要的就是", "要的正是", "無非", "不過是",
           "他知道", "她知道", "我知道", "他清楚", "她清楚", "我清楚", "他明白", "她明白", "我明白", "他懂", "她懂",
           "他很清楚", "她很清楚", "心裡清楚", "心裡明白", "終於明白", "才明白", "意識到"]
MARK_RE = re.compile("|".join("(?:^|(?<=[，,。！？：；、—…]))原來" if m == "原來" else m for m in sorted(MARKERS, key=len, reverse=True)))
WATERMARK = re.compile(r"的?72文學網[A-Za-z0-9./:]*")
TERMINAL = set("。！？!?…」』”’）)—：:")
END = set("。！？!?…")
CLOSE = set("」』”’）)")
OPEN_Q, CLOSE_Q = set("「『"), set("」』")
BR = chr(10)
QUOTED = re.compile(r"「[^「」]*」|『[^『』]*』")


def hanzi(t):
    return len(re.findall(r"[一-鿿]", t))


def split_sents(p):
    out, buf, depth, i = [], "", 0, 0
    while i < len(p):
        ch = p[i]
        buf += ch
        if ch in OPEN_Q:
            depth += 1
        elif ch in CLOSE_Q:
            depth = max(depth - 1, 0)
        if ch in END and depth == 0:
            while i + 1 < len(p) and (p[i + 1] in END or p[i + 1] in CLOSE):
                i += 1
                buf += p[i]
            out.append(buf.strip())
            buf = ""
        i += 1
    if buf.strip():
        out.append(buf.strip())
    return [s for s in out if hanzi(s) > 0]


def is_narr(s):
    return not any(q in s for q in "「」『』") and hanzi(s) >= 2 and s[-1] not in "：:"


def paragraphs(t):
    """去網站浮水印；段落結尾沒有句末標點的視為斷行，與下一段合併。"""
    raw = [x.strip() for x in WATERMARK.sub("", t).split(BR) if hanzi(x) > 0]
    out, buf = [], ""
    for x in raw:
        buf += x
        if buf[-1] in TERMINAL:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def narrative_chars(t):
    return hanzi(t) - sum(hanzi(q) for q in QUOTED.findall(t))


def build():
    cands, texts = [], {}
    for tid in sorted(KEY):
        t = WATERMARK.sub("", (EXP1 / "corpus" / f"{tid}.txt").read_text(encoding="utf-8"))
        flat = []  # (para_idx, sent)
        for pi, p in enumerate(paragraphs(t)):
            for s in split_sents(p):
                flat.append((pi, s))
        mine = []
        for k, (pi, s) in enumerate(flat):
            if not is_narr(s):
                continue
            last = k + 1 == len(flat) or flat[k + 1][0] != pi
            first = k == 0 or flat[k - 1][0] != pi
            kinds = []
            if last:
                kinds.append("段尾")
            if last and first:
                kinds.append("單句成段")
            m = MARK_RE.search(s)
            if m:
                kinds.append("標記")
            if not kinds:
                continue
            prev = flat[k - 1][1] + (" ¶" if flat[k - 1][0] != pi else "") if k > 0 else ""
            nxt = ("¶ " if flat[k + 1][0] != pi else "") + flat[k + 1][1] if k + 1 < len(flat) else ""
            mine.append(dict(tid=tid, pos=k, kinds=kinds, marker=m.group(0) if m else None, prev=prev, target=s, next=nxt))
        n = len(mine)
        sample = [mine[i * n // CAP] for i in range(CAP)] if n > CAP else mine
        texts[tid] = dict(KEY[tid], narr_chars=narrative_chars(t), chars=hanzi(t), n_sents=len(flat), n_cand=n, n_sample=len(sample),
                          kinds={k: sum(k in c["kinds"] for c in mine) for k in ("段尾", "單句成段", "標記")})
        cands += sample
    random.Random(SEED).shuffle(cands)
    pub, key = [], {}
    for i, c in enumerate(cands):
        cid = f"C{i:04d}"
        pub.append(dict(id=cid, prev=c["prev"], target=c["target"], next=c["next"]))
        key[cid] = dict(tid=c["tid"], pos=c["pos"], kinds=c["kinds"], marker=c["marker"])
    for name, obj in (("candidates.json", pub), ("candidates_key.json", key), ("texts.json", texts)):
        (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    print("候選（抽樣後）", len(pub), "篇", len(texts), "被截的篇數", sum(v["n_cand"] > CAP for v in texts.values()))


if __name__ == "__main__":
    build()
