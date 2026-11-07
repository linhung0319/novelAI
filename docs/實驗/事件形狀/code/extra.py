"""補充統計：判者一致性、事件最小段數、缺事件、每組功能分布與每事件段數。寫 判讀/extra.json。"""
import collections, statistics
from common import *
T = load_json(EXP_DIR / '判讀/texts.json')
R = load_json(EXP_DIR / '判讀/results.json')
L = {j: load_json(EXP_DIR / f'判讀/labels_{j}.json') for j in ('j1', 'j2')}
ids = sorted(L['j1'])
out = {'kappa_j1_j2': {}}
for f in FIELDS:
    a = [L['j1'][i][f] for i in ids]; b = [L['j2'][i][f] for i in ids]
    out['kappa_j1_j2'][f] = round(kappa(a, b), 3)
print('kappa', out['kappa_j1_j2'])
grp = lambda t: {'O': '原文', 'N': 'N', 'W': 'W', 'H': '人類範圍'}[t['arm']]
for j in L:
    pt = R['per_text'][j]
    mins = [min((e['n'] for e in p['events'].values() if e['n'] > 0), default=0) for p in pt.values()]
    miss = {t: p['missing_events'] for t, p in pt.items() if p['missing_events']}
    print(j, 'min event paras per text', sorted(mins)[:6], 'missing', {f"{T[t]['ch']}_{T[t]['arm']}{T[t]['rep']}": m for t, m in miss.items()})
    out[f'missing_{j}'] = {t: m for t, m in miss.items()}
    fd = collections.defaultdict(collections.Counter)
    ep = collections.defaultdict(list)
    for t, p in pt.items():
        g = (T[t]['book'], grp(T[t]))
        for e in p['events'].values():
            fd[g].update(e['funcs'])
            if e['n']:
                ep[(g, e['cls'])].append(e['n'])
    out[f'func_{j}'] = {f'{b}|{g}': {k: round(v / sum(c.values()), 3) for k, v in c.most_common()} for (b, g), c in fd.items()}
    out[f'paras_per_event_{j}'] = {f'{b}|{g}|{cl}': round(statistics.mean(v), 2) for ((b, g), cl), v in sorted(ep.items())}
dump_json(EXP_DIR / '判讀/extra.json', out)
for j in L:
    print('==', j)
    for k, v in out[f'paras_per_event_{j}'].items():
        print(' ', k, v)
for k, v in out['func_j1'].items():
    print(k, dict(list(v.items())[:7]))
