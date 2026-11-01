"""產生 Claude 盲讀集：每場景每模型每臂第 1 篇未刪稿，加 S2 人類原著。對照表另存，不印出。
用法：python fix_blind.py <blind_dir> <key_path>
"""
import json, pathlib, random, sys
import fix_lib as L

blind, key_path = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
blind.mkdir(parents=True, exist_ok=True)
items = [f"{m}_{s}_{a}_1" for m in "cq" for s in ("S1", "S2") for a in ("B0", "V", "P")]
ck = json.loads((L.ROOT / "corpus_key.json").read_text(encoding="utf-8"))
human = [k for k, v in ck.items() if v.get("group") == "human_scene"]
assert len(human) == 1
items.append("HUMAN")
random.SystemRandom().shuffle(items)
key = {}
for k, stem in enumerate(items, 1):
    code = f"X{k:02d}"
    src = L.ROOT / "corpus" / f"{human[0]}.txt" if stem == "HUMAN" else L.OUT / f"{stem}.md"
    (blind / f"{code}.md").write_text(src.read_text(encoding="utf-8").replace("“", "「").replace("”", "」"), encoding="utf-8")
    key[code] = stem
key_path.write_text(json.dumps(key, indent=1), encoding="utf-8")
print(len(items), "files")
