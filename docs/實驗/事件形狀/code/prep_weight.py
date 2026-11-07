"""輕重判定的工作檔：每章一檔，只有前一章原文＋本章事件清單（看不到本章原文）。
python prep_weight.py      寫到 SCRATCH/wt/，代號對應存 輕重/wt_key.json
python prep_weight.py ingest   驗證 SCRATCH/wt/out_j1.json、out_j2.json，落盤並算平均與加權 kappa
"""
import sys, random, re
from common import *

SEL = load_json(EXP_DIR / 'code/selection.json')
SEED = 20261107


def chapters():
    """[(實驗代號, 書, 本章rel, 前章rel, 清單檔名)]"""
    out = []
    for k, (book, cur, prev) in SEL['paired'].items():
        out.append((k, book, cur, prev, f'{k}.md'))
    for k, (book, cur, prev) in SEL['human'].items():
        num = int(re.search(r'第(\d+)章', cur).group(1))
        out.append((f'{k}{num}', book, cur, prev, f'{k}{num}.md'))
    return out


def event_lines(fname):
    t = (EXP_DIR / '事件清單' / fname).read_text(encoding='utf-8')
    return [l.strip() for l in t.splitlines() if re.match(r'\d+\.', l.strip())]


def prev_text(rel):
    paras, _ = split_paras((EXAMPLES / rel).read_text(encoding='utf-8'), drop_title=True)
    return '\n'.join(paras)


def prep():
    chs = chapters()
    rng = random.Random(SEED)
    codes = [f'W{n}' for n in rng.sample(range(10, 100), len(chs))]
    key = {}
    for code, (k, book, cur, prev, fn) in zip(codes, chs):
        body = ['# 前一章', '', prev_text(prev), '', '---', '', '# 本章的事件清單（依發生順序）', '']
        body += event_lines(fn)
        p = SCRATCH / 'wt' / f'{code}.txt'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('\n'.join(body) + '\n', encoding='utf-8')
        key[code] = k
    dump_json(EXP_DIR / '輕重/wt_key.json', key)
    print(key)


def wkappa(a, b, cats=(1, 2, 3)):
    """線性加權 Cohen kappa。"""
    n = len(a); k = len(cats); idx = {c: i for i, c in enumerate(cats)}
    w = [[1 - abs(i - j) / (k - 1) for j in range(k)] for i in range(k)]
    O = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        O[idx[x]][idx[y]] += 1
    ra = [sum(O[i]) / n for i in range(k)]; rb = [sum(O[i][j] for i in range(k)) / n for j in range(k)]
    po = sum(w[i][j] * O[i][j] / n for i in range(k) for j in range(k))
    pe = sum(w[i][j] * ra[i] * rb[j] for i in range(k) for j in range(k))
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')


def ingest():
    key = load_json(EXP_DIR / '輕重/wt_key.json')
    nev = {k: len(event_lines(fn)) for k, _, _, _, fn in chapters()}
    J = {}
    for j in ('j1', 'j2'):
        obj = load_json(SCRATCH / 'wt' / f'out_{j}.json')
        errs = []
        for code, k in key.items():
            v = obj.get(code)
            if not isinstance(v, dict) or sorted(v) != sorted(str(i) for i in range(1, nev[k] + 1)) \
                    or any(x not in (1, 2, 3) for x in v.values()):
                errs.append(code)
        print(j, '合格' if not errs else f'不合格 {errs}')
        if errs:
            return
        J[j] = {key[c]: {int(e): s for e, s in v.items()} for c, v in obj.items() if c in key}
        dump_json(EXP_DIR / f'輕重/{j}.json', J[j])
    a, b, res = [], [], {}
    for k in sorted(J['j1']):
        res[k] = {}
        for e in sorted(J['j1'][k]):
            x, y = J['j1'][k][e], J['j2'][k][e]
            a.append(x); b.append(y)
            m = (x + y) / 2
            res[k][e] = {'j1': x, 'j2': y, 'mean': m, 'rounded': int(m + 0.5),
                         'heavy_strict': x == 3 and y == 3}
    kw = wkappa(a, b)
    agree = sum(x == y for x, y in zip(a, b)) / len(a)
    out = {'weighted_kappa_linear': round(kw, 3), 'exact_agreement': round(agree, 3), 'n_events': len(a),
           'mode': 'three_level' if kw >= 0.4 else 'heavy_vs_nonheavy', 'events': res}
    dump_json(EXP_DIR / '輕重/weights.json', out)
    print('weighted kappa', round(kw, 3), 'agree', round(agree, 3), 'mode', out['mode'])
    for k, v in res.items():
        print(k, ' '.join(f'{e}:{d["j1"]}/{d["j2"]}' for e, d in v.items()))


if __name__ == '__main__':
    ingest() if len(sys.argv) > 1 and sys.argv[1] == 'ingest' else prep()
