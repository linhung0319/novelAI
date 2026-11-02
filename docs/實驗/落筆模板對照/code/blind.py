"""把 15 稿打亂成盲讀檔。對照表寫到 _對照表_讀完才開.json，不印到畫面。"""
import json
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
BLIND = ROOT / "盲讀"
BLIND.mkdir(exist_ok=True)

files = sorted(OUT.glob("*.md"))
assert len(files) == 15, len(files)
random.SystemRandom().shuffle(files)
key = {}
for n, f in enumerate(files, 1):
    code = f"稿{n:02d}"
    (BLIND / f"{code}.md").write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    key[code] = f.stem
(ROOT / "_對照表_讀完才開.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
print("blinded", len(key))
