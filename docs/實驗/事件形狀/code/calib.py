"""第 0 步校準。
python calib.py prep <round>     切批到 SCRATCH/calib<round>/
python calib.py ingest <round>   驗證輸出、落盤 校準/r<round>_<j>.json
python calib.py kappa <round> [steps]   算 kappa（steps=1/2/3：段落功能合併規則的步數）
"""
import sys, random, collections
from common import *

SEL = load_json(EXP_DIR / 'code/selection.json')
SEED = 20261109
NB = {'cG16': 2, 'cY336': 1, 'cS395': 1}
JUDGES = ('j1', 'j2')


def batches():
    rng = random.Random(SEED)
    out, key, n = {}, {}, 0
    for k, (book, rel) in SEL['calib'].items():
        paras, _ = split_paras((EXAMPLES / rel).read_text(encoding='utf-8'), drop_title=True)
        its = items_of(k, paras)
        rng.shuffle(its)
        size = len(its) / NB[k]
        for b in range(NB[k]):
            chunk = its[round(b * size):round((b + 1) * size)]
            name = f'c{len(out) + 1:02d}'
            for it in chunk:
                n += 1
                it['pid'] = f'Q{n:04d}'
                key[it['pid']] = f'{k}#{it["idx"]}'
            chunk.sort(key=lambda x: x['pid'])
            out[name] = {'ch': k, 'items': chunk}
    return out, key


def prep(rnd):
    out, key = batches()
    for name, b in out.items():
        evt, _ = event_text(b['ch'])
        write_batch(SCRATCH / f'calib{rnd}' / f'{name}.txt', b['items'], evt)
    dump_json(EXP_DIR / '校準/calib_key.json', key)
    dump_json(EXP_DIR / '校準/calib_batches.json',
              {n: {'ch': b['ch'], 'pids': [i['pid'] for i in b['items']]} for n, b in out.items()})
    print({n: (b['ch'], len(b['items'])) for n, b in out.items()})


def ingest(rnd):
    key = load_json(EXP_DIR / '校準/calib_key.json')
    B = load_json(EXP_DIR / '校準/calib_batches.json')
    for j in JUDGES:
        merged, ok = {}, True
        for name, b in B.items():
            p = SCRATCH / f'calib{rnd}' / f'out_{j}_{name}.json'
            try:
                obj = load_json(p)
            except Exception as e:
                print(j, name, '讀取失敗', e); ok = False; continue
            errs = validate(obj, b['pids'], event_text(b['ch'])[1])
            print(j, name, '合格' if not errs else errs[:6])
            ok &= not errs
            merged.update({key[k]: v for k, v in obj.items() if k in key})
        if ok:
            dump_json(EXP_DIR / f'校準/r{rnd}_{j}.json', merged)


MERGE = [{'反應': '拖尾', '評語': '拖尾', '描寫': '拖尾'},
         {'預告': '預告音效', '音效': '預告音效'},
         {'動作': '推進', '對白': '推進'}]


def fmap(steps):
    m = {}
    for s in MERGE[:steps]:
        m.update(s)
    return lambda f: m.get(f, f)


def kap(rnd, steps=0):
    H = load_json(EXP_DIR / '校準/host_labels.json')
    J = {j: load_json(EXP_DIR / f'校準/r{rnd}_{j}.json') for j in JUDGES}
    ids = sorted(H)
    fm = fmap(steps)
    res = {}
    for f in ('event', 'func'):
        g = (lambda v: fm(v['func'])) if f == 'func' else (lambda v: v['event'])
        h = [g(H[i]) for i in ids]
        a = [g(J['j1'][i]) for i in ids]
        b = [g(J['j2'][i]) for i in ids]
        k1, k2 = kappa(h, a), kappa(h, b)
        res[f] = {'j1_vs_host': round(k1, 3), 'j2_vs_host': round(k2, 3), 'mean_vs_host': round((k1 + k2) / 2, 3),
                  'j1_vs_j2': round(kappa(a, b), 3), 'pass': (k1 + k2) / 2 >= 0.6}
    for f in FEEL:
        a = [J['j1'][i][f] for i in ids]
        b = [J['j2'][i][f] for i in ids]
        k = kappa(a, b)
        res[f] = {'j1_vs_j2': round(k, 3), 'pass': k >= 0.4,
                  'j1_dist': {v: a.count(v) for v in FEEL[f]}, 'j2_dist': {v: b.count(v) for v in FEEL[f]}}
    conf = collections.Counter()
    for j in JUDGES:
        for i in ids:
            conf[(fm(H[i]['func']), fm(J[j][i]['func']))] += 1
    res['_func_confusion_host_to_judge'] = {f'{a}->{b}': c for (a, b), c in
                                            sorted(conf.items(), key=lambda x: -x[1]) if a != b}
    dump_json(EXP_DIR / f'校準/r{rnd}_kappa{"_m" + str(steps) if steps else ""}.json', res)
    for k, v in res.items():
        print(k, v)


if __name__ == '__main__':
    cmd, rnd = sys.argv[1], sys.argv[2]
    if cmd == 'kappa':
        kap(rnd, int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    else:
        {'prep': prep, 'ingest': ingest}[cmd](rnd)
