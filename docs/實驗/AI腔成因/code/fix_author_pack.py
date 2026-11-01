"""作者盲讀包。每場景：Claude B0／V／P 第 1 篇、Qwen P 第 1 篇；S2 加人類原著。
用法：uv run --with opencc-python-reimplemented code/fix_author_pack.py
"""
import json, random
import opencc
import fix_lib as L

cc = opencc.OpenCC("s2twp")
PACK = L.ROOT / "盲讀包"
ck = json.loads((L.ROOT / "corpus_key.json").read_text(encoding="utf-8"))
human = next(k for k, v in ck.items() if v.get("group") == "human_scene")
key = {}
FORM = "\n\n**整體喜歡程度（1–5）：**\n\n**讀到哪一句開始覺得怪（貼句子）：**\n\n**哪一句最像活人（貼句子）：**\n"
for scene in ("S1", "S2"):
    stems = [f"c_{scene}_B0_1", f"c_{scene}_V_1", f"c_{scene}_P_1", f"q_{scene}_P_1"] + (["HUMAN"] if scene == "S2" else [])
    random.SystemRandom().shuffle(stems)
    out = [f"# 修復實驗盲讀 {scene}\n\n同一份事件大綱寫出的不同版本。讀完每篇就填，全部填完才開 `_修復對照表_讀完才開.json`。\n"]
    for i, stem in enumerate(stems):
        code = f"{scene}-{'甲乙丙丁戊'[i]}"
        src = L.ROOT / "corpus" / f"{human}.txt" if stem == "HUMAN" else L.OUT / f"{stem}.md"
        text = cc.convert(src.read_text(encoding="utf-8")).replace("“", "「").replace("”", "」")
        out.append(f"\n---\n\n## {code}\n\n{text}{FORM}")
        key[code] = stem
    (PACK / f"修復-{scene}-盲讀.md").write_text("".join(out), encoding="utf-8")
(PACK / "_修復對照表_讀完才開.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
print("ok", len(key))
