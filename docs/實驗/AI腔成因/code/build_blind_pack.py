"""作者盲讀包：每臂固定取第 1 篇（事先定死，避免挑稿），加對照文本，打亂。

S2 的對照是人類原著；S1 沒有人類版本，對照是 oh-story 實際產出的那一章。
對照表另存，讀完才開。需要先跑過 add_trials.py。
用法：uv run --with opencc-python-reimplemented build_blind_pack.py
"""
import json, pathlib, random, re
from opencc import OpenCC

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
PACK = ROOT / "盲讀包"
PACK.mkdir(exist_ok=True)
CC = OpenCC("s2twp")
ARMS = ["A", "B", "C", "D", "H", "QA", "QB", "QC"]
EXTRA = {
    "S2": ("人類原著", REPO / "examples/一世之尊/卷一/第002章_空門.txt"),
    "S1": ("oh-story 實際產出", next(pathlib.Path(r"C:\Users\user\Programming\oh-story-novel\典籍有誤\正文").glob("第006章*"))),
}
LETTERS = "ㄅㄆㄇㄈㄉㄊㄋㄌㄍ"


def clean(t):
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"^#.*$", "", t, flags=re.M)
    lines = [l.strip() for l in t.splitlines()]
    if lines and re.match(r"^第.{1,8}[章回].*$", lines[0]):
        lines = lines[1:]
    t = "\n".join(lines)
    t = CC.convert(t).replace("“", "「").replace("”", "」").replace("‘", "『").replace("’", "』")
    parts = t.split('"')
    if len(parts) > 1:
        t = "".join(p + ("「" if i % 2 == 0 else "」") if i < len(parts) - 1 else p for i, p in enumerate(parts))
    # 半形標點會洩漏來源（S1_A_1 整篇是半形逗號），一律轉全形
    t = re.sub(r"(?<=[\u4e00-\u9fff」]),", "，", t)
    t = re.sub(r"(?<=[\u4e00-\u9fff」])\?", "？", t)
    t = re.sub(r"(?<=[\u4e00-\u9fff」])!", "！", t)
    t = re.sub(r"(?<=[\u4e00-\u9fff」]):", "：", t)
    return re.sub(r"\n{2,}", "\n\n", re.sub(r"\n", "\n\n", re.sub(r"\n{2,}", "\n", t))).strip()


key = {}
for scene, seed in (("S2", 20261103), ("S1", 20261104)):
    items = []
    for arm in ARMS:
        p = ROOT / "outputs" / f"{scene}_{arm}_1.md"
        if p.exists():
            items.append((f"{scene}_{arm}_1", p))
    label, path = EXTRA[scene]
    items.append((label, path))
    random.Random(seed).shuffle(items)
    body = []
    key[scene] = {}
    for letter, (name, p) in zip(LETTERS, items):
        key[scene][letter] = name
        body.append(f"## 稿 {letter}\n\n{clean(p.read_text(encoding='utf-8'))}\n")
    sheet = "\n".join(f"| {l} |  |  |  |" for l in LETTERS[: len(items)])
    head = f"""# 盲讀包 {scene}

讀的時候不用想原因。憑語感填表，「覺得怪的句子」直接貼你最受不了的那一句（可空白）。

| 稿 | 怪不怪（1 很自然 – 5 很怪） | 想不想讀下去（1 不想 – 5 想） | 覺得怪的句子 |
|---|---|---|---|
{sheet}

---

"""
    (PACK / f"{scene}-盲讀.md").write_text(head + "\n---\n\n".join(body), encoding="utf-8")
(PACK / "_對照表_讀完才開.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
print({s: len(v) for s, v in key.items()})
