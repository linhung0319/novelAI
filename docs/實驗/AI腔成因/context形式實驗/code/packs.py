"""盲讀分包：讀者一、二（Claude 第 1、2 篇），讀者三（Qwen 第 1 篇），作者包（Claude 第 1 篇）。對照表另存。"""
import json, pathlib, random, sys
from opencc import OpenCC
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
SCR = pathlib.Path(sys.argv[1])
CC = OpenCC("s2tw")
EX = ROOT.parents[3] / "examples" / "一世之尊" / "卷一" / "第002章_空門.txt"
ARMS = {"S1": ["M","MP","S","N","R","V","PA"], "S2": ["M","MP","S","N","R","V","PA","PH"]}
def n(t): return CC.convert(t).replace("“","「").replace("”","」").strip()
hum = "\n".join(EX.read_text(encoding="utf-8").splitlines()[1:])
rnd = random.Random(1101)
key = {}
for name, mod, i in (("r1","c",1),("r2","c",2),("r3","q",1)):
    d = SCR / name; d.mkdir(parents=True, exist_ok=True)
    for s in ARMS:
        its = [(a, n((OUT/f"{mod}_{s}_{a}_{i}.md").read_text(encoding="utf-8"))) for a in ARMS[s]]
        if s == "S2": its.append(("HUMAN", n(hum)))
        rnd.shuffle(its)
        for j,(a,t) in enumerate(its):
            cid = f"{s}-{rnd.randint(100,999)}{j}"
            (d/f"{cid}.txt").write_text(t, encoding="utf-8")
            key[f"{name}/{cid}"] = a
(SCR/"key.json").write_text(json.dumps(key,ensure_ascii=False,indent=0),encoding="utf-8")
PACK = ROOT/"盲讀包"; PACK.mkdir(exist_ok=True); akey={}
for s in ARMS:
    its = [(a, n((OUT/f"c_{s}_{a}_1.md").read_text(encoding="utf-8"))) for a in ARMS[s]]
    if s == "S2": its.append(("HUMAN", n(hum)))
    rnd.shuffle(its)
    L = [f"# {s} 盲讀\n\n每篇讀完填兩項：**順暢 0–10**（能不能在腦裡連續跟著畫面）、**哪裡卡**（貼一兩句）。對照表讀完才開。\n"]
    for j,(a,t) in enumerate(its):
        code = chr(65+j); akey[f"{s}-{code}"]=a
        L.append(f"\n---\n\n## 稿 {code}\n\n順暢：＿＿　哪裡卡：＿＿\n\n{t}\n")
    (PACK/f"{s}-盲讀.md").write_text("".join(L),encoding="utf-8")
(PACK/"_對照表_讀完才開.json").write_text(json.dumps(akey,ensure_ascii=False,indent=0),encoding="utf-8")
print(len(key),len(akey))
