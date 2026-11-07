"""彙整判讀標籤。用法：python analyze.py [labels.json] [--key blind_key.json]"""
import json, sys, pathlib, collections
root = pathlib.Path(__file__).resolve().parent.parent
lab = json.loads((root / (sys.argv[1] if len(sys.argv) > 1 else 'my_labels.json')).read_text(encoding='utf-8'))
if '--key' in sys.argv:
    key = json.loads((root / sys.argv[sys.argv.index('--key') + 1]).read_text(encoding='utf-8'))
    lab = {key[k]: v for k, v in lab.items()}
chars = {}
for tag, rel in [('H', 'texts/人類原著_S2.txt'), ('C', 'texts/Claude_S2_A_1.txt')]:
    for l in (root / rel).read_text(encoding='utf-8').splitlines():
        if l.strip():
            pid, t = l.split('\t', 1); chars[pid] = len(t)
for tag, name in [('H', '人類'), ('C', 'Claude')]:
    rows = {k: v for k, v in lab.items() if k.startswith(tag)}
    n = len(rows); kc = sum(chars[k] for k in rows) / 1000
    foc = collections.Counter(v['focus'] for v in rows.values() if v['focus'])
    judged = sum(foc.values())
    late = sum(c for f, c in foc.items() if f.startswith('後'))
    fg = sum(len(v['foreground']) for v in rows.values())
    st = sum(v['stress'] for v in rows.values())
    adv = sum(v.get('advance', True) for v in rows.values())
    print(f'{name}: 段 {n}，字 {kc*1000:.0f}')
    print(f'  焦點（判 {judged} 段）：' + '、'.join(f'{f} {c}（{c/judged:.0%}）' for f, c in foc.most_common()) + f'；後合計 {late/judged:.0%}')
    print(f'  前景化 {fg} 處，每千字 {fg/kc:.2f}；重音段 {st}（{st/n:.0%}），每千字 {st/kc:.2f}；不推進段 {n-adv}（{(n-adv)/n:.0%}）')
