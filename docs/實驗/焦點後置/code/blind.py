"""打亂兩份稿的段落，產生盲判包與對照鍵。用法：python blind.py"""
import json, random, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = [('H', 'texts/人類原著_S2.txt'), ('C', 'texts/Claude_S2_A_1.txt')]
items = []
for tag, rel in SRC:
    paras = [l.split('\t', 1)[1].rstrip('\n') for l in (ROOT / rel).read_text(encoding='utf-8').splitlines() if l.strip()]
    for i, p in enumerate(paras):
        items.append({'src': f'{tag}{i+1:02d}', 'prev': paras[i-1] if i else '', 'cur': p,
                      'next': paras[i+1] if i + 1 < len(paras) else ''})
random.Random(20261107).shuffle(items)
key, lines = {}, ['# 盲判包', '']
for n, it in enumerate(items, 1):
    bid = f'B{n:03d}'
    key[bid] = it['src']
    lines += [f'## {bid}', f'前段：{it["prev"]}', f'**本段：{it["cur"]}**', f'後段：{it["next"]}', '']
(ROOT / 'blind_pack.md').write_text('\n'.join(lines), encoding='utf-8')
(ROOT / 'blind_key.json').write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding='utf-8')
print(len(items), 'items')
