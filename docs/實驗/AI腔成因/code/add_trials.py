"""把新稿併入 corpus，保留既有 blind id（build_corpus.py 會全部洗牌，使既有盲評對不上，所以不能重跑）。

用法：uv run --with opencc-python-reimplemented add_trials.py
"""
import json, pathlib, random, re
from opencc import OpenCC

ROOT = pathlib.Path(__file__).resolve().parents[1]
CC = OpenCC("s2twp")


def norm(t):
    """與 build_corpus.norm 相同的受測稿路徑。"""
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"^#.*$", "", t, flags=re.M)
    lines = t.splitlines()
    if lines and re.match(r"^\s*第.{1,8}[章回].*$", lines[0]):
        lines = lines[1:]
    t = "\n".join(l.strip() for l in lines)
    t = re.sub(r"^\s*第.{1,8}章[^\n]*$", "", t, count=1, flags=re.M)
    t = CC.convert(t)
    t = t.replace("“", "「").replace("”", "」").replace("‘", "『").replace("’", "』")
    t = t.replace('"', "\0")
    parts = t.split("\0")
    if len(parts) > 1:
        t = "".join(p + ("「" if i % 2 == 0 else "」") if i < len(parts) - 1 else p for i, p in enumerate(parts))
    return re.sub(r"\n{2,}", "\n", t).strip()


KP = ROOT / "corpus_key.json"
key = json.load(open(KP, encoding="utf-8"))
have = {v["src"] for v in key.values() if v["group"] == "trial"}
used = {int(k[1:]) for k in key}
new = [f for f in sorted((ROOT / "outputs").glob("S?_*_?.md")) if f.name not in have]
rng = random.Random(20261102)
pool = [i for i in range(1000, 9999) if i not in used]
for f, bid in zip(new, rng.sample(pool, len(new))):
    scene, arm, i = f.stem.split("_")
    (ROOT / "corpus" / f"T{bid}.txt").write_text(norm(f.read_text(encoding="utf-8")), encoding="utf-8")
    key[f"T{bid}"] = {"group": "trial", "scene": scene, "arm": arm, "rep": int(i), "src": f.name}
KP.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
print("added", len(new), "total", len(key))
