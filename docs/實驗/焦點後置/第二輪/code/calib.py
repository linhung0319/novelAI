"""第 0 步校準。
python calib.py prep <round>      切批（round=1 或 2，判據改版時用 2）
python calib.py ingest <round>    驗證 scratch 裡兩個判者的輸出，落盤到 校準/
python calib.py kappa <round>     算 kappa
"""
import sys, json, random, collections
from common import *

SRC = [('H', R1 / 'texts/人類原著_S2.txt'), ('C', R1 / 'texts/Claude_S2_A_1.txt')]
SEED = 20261108


def load_items():
    items = []
    for tag, p in SRC:
        rows = [l.split('\t', 1) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
        paras = [(a, b.strip()) for a, b in rows]
        for i, (sid, t) in enumerate(paras):
            items.append({'src': sid, 'prev': paras[i - 1][1] if i else '', 'cur': t,
                          'next': paras[i + 1][1] if i + 1 < len(paras) else ''})
    return items


def prep(rnd):
    items = load_items()
    random.Random(SEED).shuffle(items)
    key = {}
    for n, it in enumerate(items, 1):
        it['pid'] = f'P{n:04d}'
        key[it['pid']] = it['src']
    half = (len(items) + 1) // 2
    d = SCRATCH / f'calib{rnd}'
    write_batch(d / 'b01.txt', items[:half])
    write_batch(d / 'b02.txt', items[half:])
    dump_json(R2 / '校準/calib_key.json', key)
    print(len(items), 'items ->', d)


def ingest(rnd):
    key = load_json(R2 / '校準/calib_key.json')
    pids_by_b = {}
    pids = sorted(key)
    half = (len(pids) + 1) // 2
    pids_by_b = {'b01': pids[:half], 'b02': pids[half:]}
    for j in ('j1', 'j2'):
        merged, ok = {}, True
        for b, ps in pids_by_b.items():
            p = SCRATCH / f'calib{rnd}' / f'out_{j}_{b}.json'
            if not p.exists():
                print(j, b, '缺檔'); ok = False; continue
            try:
                obj = load_json(p)
            except Exception as e:
                print(j, b, 'JSON 解析失敗', e); ok = False; continue
            errs = validate(obj, ps, None)
            print(j, b, '合格' if not errs else errs[:8])
            ok &= not errs
            merged.update({key[k]: v for k, v in obj.items() if k in key})
        if ok:
            dump_json(R2 / f'校準/r{rnd}_{j}.json', merged)


def kappa2(a, b):
    n = len(a)
    if n == 0:
        return float('nan')
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')


BIN = {
    '類型：對白 vs 非': lambda v: v['type'] == '對白',
    '焦點：後新 vs 非': lambda v: v['focus'] == '後新',
    '焦點：後(舊+新) vs 非': lambda v: (v['focus'] or '').startswith('後'),
    '前景化：有 vs 無': lambda v: len(v['foreground']) > 0,
    '重音': lambda v: bool(v['stress']),
}
BIN_JJ = {
    '套語：有 vs 無': lambda v: len(v['cliche']) > 0,
    '推論：有 vs 無': lambda v: len(v['inference']) > 0,
    '預告段': lambda v: bool(v['setup']),
}


def norm_mine(v):
    return {'type': v['type'], 'focus': v['focus'] or '不判', 'foreground': v['foreground'], 'stress': v['stress']}


def kappa(rnd):
    mine = {k: norm_mine(v) for k, v in load_json(R1 / 'my_labels.json').items()}
    J = {j: load_json(R2 / f'校準/r{rnd}_{j}.json') for j in ('j1', 'j2')}
    ids = sorted(mine)
    res = {}
    for name, f in BIN.items():
        m = [f(mine[i]) for i in ids]
        k1 = kappa2(m, [f(J['j1'][i]) for i in ids])
        k2 = kappa2(m, [f(J['j2'][i]) for i in ids])
        kj = kappa2([f(J['j1'][i]) for i in ids], [f(J['j2'][i]) for i in ids])
        res[name] = {'j1_vs_me': round(k1, 3), 'j2_vs_me': round(k2, 3), 'mean_vs_me': round((k1 + k2) / 2, 3),
                     'j1_vs_j2': round(kj, 3), 'me_rate': round(sum(m) / len(m), 3),
                     'j1_rate': round(sum(f(J['j1'][i]) for i in ids) / len(ids), 3),
                     'j2_rate': round(sum(f(J['j2'][i]) for i in ids) / len(ids), 3)}
    for name, f in BIN_JJ.items():
        a = [f(J['j1'][i]) for i in ids]; b = [f(J['j2'][i]) for i in ids]
        res[name] = {'j1_vs_j2': round(kappa2(a, b), 3), 'j1_rate': round(sum(a) / len(a), 3), 'j2_rate': round(sum(b) / len(b), 3)}
    # 焦點五類混淆（參考）
    conf = {j: collections.Counter((mine[i]['focus'], J[j][i]['focus']) for i in ids) for j in J}
    res['_focus_confusion'] = {j: {f'{a}->{b}': c for (a, b), c in sorted(conf[j].items())} for j in conf}
    dump_json(R2 / f'校準/r{rnd}_kappa.json', res)
    for k, v in res.items():
        if not k.startswith('_'):
            print(k, v)


if __name__ == '__main__':
    cmd, rnd = sys.argv[1], sys.argv[2]
    {'prep': prep, 'ingest': ingest, 'kappa': kappa}[cmd](rnd)
