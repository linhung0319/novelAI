"""收稿並打亂代號。稿件內容不修改。用法：python collect_blind.py <scratch 根目錄>"""
import json
import pathlib
import random
import shutil
import sys

from prepare import ROOT, SOURCES

scratch = pathlib.Path(sys.argv[1])
key = json.loads((scratch / "writer_key.json").read_text(encoding="utf-8"))
out = ROOT / "稿件"
for raw, name in key.items():
    shutil.copyfile(scratch / "w" / f"{raw}.md", out / f"{name}.md")

blind_key = {}
for ch in SOURCES:
    stems = [f"{m}_{ch}_{arm}_{n}" for m in "cq" for arm in ("I", "IE") for n in (1, 2)]
    random.SystemRandom().shuffle(stems)
    folder = scratch / "b" / ch
    folder.mkdir(parents=True, exist_ok=True)
    for i, stem in enumerate(stems):
        code = "ABCDEFGH"[i]
        shutil.copyfile(out / f"{stem}.md", folder / f"{code}.md")
        blind_key[f"{ch}-{code}"] = stem
(ROOT / "代號對照.json").write_text(json.dumps(blind_key, indent=1), encoding="utf-8")

for f in sorted(out.glob("*.md")):
    t = f.read_text(encoding="utf-8")
    print(f.stem, len("".join(t.split())))
