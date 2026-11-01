"""正規化所有文本到 corpus/<blind_id>.txt，對照表存 corpus_key.json。

blind_id 由固定種子打亂。評分者只看得到 blind_id 與內文。
需要 opencc（在 uv 暫存環境跑）：uv run --with opencc-python-reimplemented build_corpus.py
"""
import json, pathlib, random, re
from opencc import OpenCC

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
OH = pathlib.Path(r"C:\Users\user\Programming\oh-story-novel\典籍有誤\正文")
EX = REPO / "examples"
CC = OpenCC("s2twp")
TARGET = 3500  # 長篇基準語料截到這個字數，只取前段落邊界


def norm(t):
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"^#.*$", "", t, flags=re.M)
    lines = t.splitlines()
    # 人類語料第一行是章名
    if lines and re.match(r"^\s*第.{1,8}[章回].*$", lines[0]):
        lines = lines[1:]
    t = "\n".join(l.strip() for l in lines)
    t = re.sub(r"^\s*第.{1,8}章[^\n]*$", "", t, count=1, flags=re.M)
    t = CC.convert(t)
    t = t.replace("“", "「").replace("”", "」").replace("‘", "『").replace("’", "』")
    t = t.replace('"', "\0")
    # 直引號成對換
    parts = t.split("\0")
    if len(parts) > 1:
        t = "".join(p + ("「" if i % 2 == 0 else "」") if i < len(parts) - 1 else p for i, p in enumerate(parts))
    t = re.sub(r"\n{2,}", "\n", t).strip()
    return t


def clip(t, n=TARGET):
    out, c = [], 0
    for p in t.split("\n"):
        out.append(p)
        c += len(re.findall(r"[\u4e00-\u9fff]", p))
        if c >= n:
            break
    return "\n".join(out)


items = []  # (label dict, text)
# 受測稿
for f in sorted((ROOT / "outputs").glob("S?_*_?.md")):
    scene, arm, i = f.stem.split("_")
    items.append(({"group": "trial", "scene": scene, "arm": arm, "rep": int(i), "src": f.name}, norm(f.read_text(encoding="utf-8"))))
# S2 人類原文
s2h = EX / "一世之尊/卷一/第002章_空門.txt"
items.append(({"group": "human_scene", "scene": "S2", "arm": "HUMAN", "rep": 1, "src": s2h.name}, norm(s2h.read_text(encoding="utf-8"))))
# 人類基準：每本 2 段（固定挑選）
rng = random.Random(20261101)
for book in ["一世之尊", "詭秘之主", "極道天魔", "從紅月開始", "神秀之主", "我有一個修仙世界"]:
    fs = sorted(p for p in (EX / book).rglob("*.txt") if p.name != s2h.name)
    if book == "一世之尊":
        fs = [p for p in fs if "卷三" in str(p)]
    elif len(fs) > 15:
        fs = fs[10:]  # 避開開篇
    for p in rng.sample(fs, 2):
        items.append(({"group": "human_base", "book": book, "src": p.name}, clip(norm(p.read_text(encoding="utf-8")))))
# 舊 AI 稿
for name, fs in {
    "repo_一世之尊": [REPO / f"一世之尊/chapters/ch{n:04d}.md" for n in (2, 40, 70)],
    "repo_消失的密室": [REPO / f"消失的密室/chapters/ch{n:04d}.md" for n in (1, 4)],
    "oh_典籍有誤": [next(OH.glob(f"第{n:03d}章*")) for n in (1, 6, 12)],
}.items():
    for p in fs:
        items.append(({"group": "old_ai", "book": name, "src": p.name}, clip(norm(p.read_text(encoding="utf-8")))))

rng2 = random.Random(77)
ids = rng2.sample(range(1000, 9999), len(items))
out = ROOT / "corpus"
out.mkdir(exist_ok=True)
for old in out.glob("*.txt"):
    old.unlink()
key = {}
for (label, text), bid in zip(items, ids):
    (out / f"T{bid}.txt").write_text(text, encoding="utf-8")
    key[f"T{bid}"] = label
(ROOT / "corpus_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(items), "items")
