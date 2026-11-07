"""主持者讀稿用：印出某章某事件在原文和指定稿裡的段落（依判者一的事件編號），附功能標籤。
python evshow.py <章> <事件> [臂篇 ...]   例：python evshow.py S403 2 N1 W1
"""
import sys
from common import *
T = load_json(EXP_DIR / '判讀/texts.json')
L = load_json(EXP_DIR / '判讀/labels_j1.json')
ch, e = sys.argv[1], int(sys.argv[2])
want = ['O0'] + sys.argv[3:]
for tid, t in T.items():
    tag = f"{t['arm']}{t['rep']}"
    if t['ch'] != ch or tag not in want:
        continue
    rows = [(i, p, L[f'{tid}#{i}']['func']) for i, p in enumerate(t['paras']) if L[f'{tid}#{i}']['event'] == e]
    print(f'=== {ch} 事件{e} {tag} ({tid})  {len(rows)} 段 {sum(cjk_len(p) for _, p, _ in rows)} 字')
    for i, p, f in rows:
        print(f'{i:03d} [{f}] {p}')
