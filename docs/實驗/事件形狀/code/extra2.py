"""補充（不進判定）：各組輕／中／重事件裡，反應、評語、描寫、背景、內心段的比例。寫 判讀/extra2.json。"""
import collections
from common import *
T = load_json(EXP_DIR / '判讀/texts.json')
R = load_json(EXP_DIR / '判讀/results.json')
out = {}
for j in ('j1', 'j2'):
    acc = collections.defaultdict(collections.Counter)
    for t, p in R['per_text'][j].items():
        g = T[t]['book'] + '|' + T[t]['arm']
        for e in p['events'].values():
            acc[(g, e['cls'])].update(e['funcs'])
    res = {}
    for (g, cl), c in sorted(acc.items()):
        n = sum(c.values())
        res[f'{g}|{cl}'] = {'n': n, 'tail(反應+評語+描寫)': round((c['反應'] + c['評語'] + c['描寫']) / n, 3),
                           '反應': round(c['反應'] / n, 3), '評語': round(c['評語'] / n, 3), '描寫': round(c['描寫'] / n, 3),
                           '背景': round(c['背景'] / n, 3), '內心': round(c['內心'] / n, 3), '結果': round(c['結果'] / n, 3)}
    out[j] = res
dump_json(EXP_DIR / '判讀/extra2.json', out)
for k in out['j1']:
    if k.split('|')[2] in ('light', 'heavy'):
        a, b = out['j1'][k], out['j2'][k]
        print(k, 'n', a['n'], 'tail', a['tail(反應+評語+描寫)'], '/', b['tail(反應+評語+描寫)'], ' 反應', a['反應'], '/', b['反應'], ' 評語', a['評語'], '/', b['評語'], ' 描寫', a['描寫'], '/', b['描寫'])
