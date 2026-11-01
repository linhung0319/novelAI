"""把 Claude 的工作檔寫到路徑不含實驗資訊的資料夾。用法：python make_claude_tasks.py <工作資料夾>"""
import json
import pathlib
import random
import sys

from prepare import SOURCES, prompt

work = pathlib.Path(sys.argv[1])
work.mkdir(parents=True, exist_ok=True)
cells = [(ch, arm, n) for ch in SOURCES for arm in ("I", "IE") for n in (1, 2)]
random.SystemRandom().shuffle(cells)
key = {}
for i, (ch, arm, n) in enumerate(cells, 1):
    (work / f"t{i:02d}.txt").write_text(prompt(ch, arm), encoding="utf-8")
    key[f"o{i:02d}"] = f"c_{ch}_{arm}_{n}"
(work.parent / "writer_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
print(len(key))
