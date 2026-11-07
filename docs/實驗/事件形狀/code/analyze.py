"""算 H1–H5 與人類範圍。python analyze.py   → 判讀/results.json，並印出表格。
定義見 01-凍結.md 第六節。
"""
import math, statistics, collections, itertools
from common import *

TEXTS = load_json(EXP_DIR / '判讀/texts.json')
WTS = load_json(EXP_DIR / '輕重/weights.json')
MODE = WTS['mode']
SPEED = {'快': 1, '中': 2, '慢': 3, '停': 4}
TAIL = {'反應', '評語', '描寫'}
BOOKS = ['詭秘之主', '一世之尊', '神秀之主']
TH = {'H1': 1.5, 'H2': 0.05, 'H3': 0.5, 'H4': 0.3}


def wclass(ch, e):
    d = WTS['events'][ch][str(e)]
    if MODE == 'three_level':
        return {3: 'heavy', 2: 'mid', 1: 'light'}[d['rounded']]
    return 'heavy' if d['heavy_strict'] else 'non'


LIGHT = 'light' if MODE == 'three_level' else 'non'


def per_text(tid, labels):
    t = TEXTS[tid]
    paras = t['paras']
    rows = []
    for i, p in enumerate(paras):
        v = labels.get(f'{tid}#{i}')
        rows.append(None if v is None else {**v, 'chars': cjk_len(p), 'i': i})
    total = sum(cjk_len(p) for p in paras)
    nev = len(WTS['events'][t['ch']])
    ev = {}
    for e in range(1, nev + 1):
        rs = [r for r in rows if r and r['event'] == e]
        funcs = collections.Counter(r['func'] for r in rs)
        # 拖尾：第一個「結果」段之後，同一事件的 反應／評語／描寫 段數
        res_pos = [r['i'] for r in rs if r['func'] == '結果']
        tail = None
        if res_pos:
            tail = sum(1 for r in rs if r['i'] > res_pos[0] and r['func'] in TAIL)
        sp = [SPEED[r['speed']] for r in rs]
        ev[e] = {'cls': wclass(t['ch'], e), 'n': len(rs), 'share': sum(r['chars'] for r in rs) / total,
                 'funcs': dict(funcs), 'tail': tail, 'speed': statistics.mean(sp) if sp else None,
                 'tens_hi': sum(1 for r in rs if r['tension'] in ('升', '懸著'))}
    present = [e for e in ev if ev[e]['n'] > 0]

    def jsd(p, q):
        def kl(a, b):
            return sum(a[k] * math.log2(a[k] / b[k]) for k in a if a[k] > 0)
        m = {k: (p[k] + q[k]) / 2 for k in FUNCS}
        return (kl(p, m) + kl(q, m)) / 2

    def dist(e):
        n = ev[e]['n']
        return {k: ev[e]['funcs'].get(k, 0) / n for k in FUNCS}

    def mean_jsd(es):
        pairs = list(itertools.combinations(es, 2))
        return statistics.mean(jsd(dist(a), dist(b)) for a, b in pairs) if pairs else None

    sps = [ev[e]['speed'] for e in present]
    n_lab = sum(1 for r in rows if r)
    heavy_paras = sum(ev[e]['n'] for e in ev if ev[e]['cls'] == 'heavy')
    tens_all = sum(ev[e]['tens_hi'] for e in ev) + sum(
        1 for r in rows if r and r['event'] == 0 and r['tension'] in ('升', '懸著'))
    tens_heavy = sum(ev[e]['tens_hi'] for e in ev if ev[e]['cls'] == 'heavy')
    conc = None
    if tens_all and heavy_paras and n_lab:
        conc = (tens_heavy / tens_all) / (heavy_paras / n_lab)
    return {'events': ev, 'H2': mean_jsd(present), 'H2_ge3': mean_jsd([e for e in present if ev[e]['n'] >= 3]),
            'H4': statistics.pstdev(sps) if len(sps) > 1 else None, 'tension_conc': conc,
            'n_paras': len(paras), 'n_labeled': n_lab, 'chars': total,
            'missing_events': [e for e in ev if ev[e]['n'] == 0],
            'event0_paras': sum(1 for r in rows if r and r['event'] == 0)}


def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def pooled(pts):
    """pts: per_text 結果的清單（同一組）。"""
    evs = [e for p in pts for e in p['events'].values()]
    hv = [e for e in evs if e['cls'] == 'heavy']
    lt = [e for e in evs if e['cls'] == LIGHT]
    out = {}
    if hv and lt:
        ms, ml = statistics.mean(e['share'] for e in hv), statistics.mean(e['share'] for e in lt)
        out['H1'] = ms / ml if ml else None
        nl = statistics.mean(e['n'] for e in lt)
        out['H1_paras'] = statistics.mean(e['n'] for e in hv) / nl if nl else None
    else:
        out['H1'] = out['H1_paras'] = None
    out['heavy_share'] = mean_or_none([e['share'] for e in hv])
    out['light_share'] = mean_or_none([e['share'] for e in lt])
    out['H2'] = mean_or_none([p['H2'] for p in pts])
    out['H2_ge3'] = mean_or_none([p['H2_ge3'] for p in pts])
    out['H3_light'] = mean_or_none([e['tail'] for e in lt])
    out['H3_heavy'] = mean_or_none([e['tail'] for e in hv])
    out['H3_light_n'] = sum(1 for e in lt if e['tail'] is not None)
    out['H3_light_all0'] = mean_or_none([e['tail'] or 0 for e in lt])
    out['H4'] = mean_or_none([p['H4'] for p in pts])
    out['tension_conc'] = mean_or_none([p['tension_conc'] for p in pts])
    out['n_heavy'] = len(hv); out['n_light'] = len(lt); out['n_texts'] = len(pts)
    return out


def diff_ok(h, o, n):
    """預測方向的差，及是否過門檻。h=H1..H4，o=原文值，n=N 臂值。"""
    if o is None or n is None:
        return None, None
    if h == 'H1':
        d = o / n if n else None
        return d, d is not None and d >= TH['H1']
    if h == 'H3':
        d = n - o
    else:
        d = o - n
    return d, d >= TH[h]


def main():
    res = {}
    for j in ('j1', 'j2'):
        L = load_json(EXP_DIR / f'判讀/labels_{j}.json')
        PT = {tid: per_text(tid, L) for tid in TEXTS}
        R = {'per_text': PT, 'books': {}, 'human': {}}
        for b in BOOKS:
            g = {}
            for arm in ('O', 'N', 'W'):
                g[arm] = pooled([PT[t] for t in TEXTS if TEXTS[t]['book'] == b and TEXTS[t]['arm'] == arm])
            R['books'][b] = g
        for t, v in TEXTS.items():
            if v['group'] == 'human':
                R['human'][v['book']] = pooled([PT[t]])
        res[j] = R
    # 判定
    verdict = {}
    for h, key in (('H1', 'H1'), ('H2', 'H2'), ('H3', 'H3_light'), ('H4', 'H4')):
        verdict[h] = {}
        for b in BOOKS:
            per = {}
            for j in res:
                g = res[j]['books'][b]
                per[j] = diff_ok(h, g['O'][key], g['N'][key])
            ok = all(v[1] for v in per.values()) if all(v[1] is not None for v in per.values()) else None
            verdict[h][b] = {'diffs': {j: per[j][0] for j in per}, 'pass_each': {j: per[j][1] for j in per},
                             'book_holds': ok}
        n_ok = sum(1 for b in BOOKS if verdict[h][b]['book_holds'])
        verdict[h]['_summary'] = {'books_holding': n_ok,
                                  'result': '成立' if n_ok >= 2 else ('這位作者' if n_ok == 1 else '不成立')}
    # 人類範圍：某本配對書的原文值落在其他四篇／組人類值之外
    hr = {}
    for h, key in (('H1', 'H1'), ('H2', 'H2'), ('H3', 'H3_light'), ('H4', 'H4')):
        hr[h] = {}
        for b in BOOKS:
            per = {}
            for j in res:
                me = res[j]['books'][b]['O'][key]
                others = [res[j]['books'][o]['O'][key] for o in BOOKS if o != b] + \
                         [res[j]['human'][x][key] for x in res[j]['human']]
                others = [x for x in others if x is not None]
                out = None if me is None or not others else not (min(others) <= me <= max(others))
                per[j] = {'value': me, 'range': [min(others), max(others)] if others else None, 'outside': out}
            hr[h][b] = {**per, 'demote': any(per[j]['outside'] for j in per)}
    # H5：W 對 N
    h5 = {}
    for h, key in (('H1', 'H1'), ('H2', 'H2'), ('H3', 'H3_light'), ('H4', 'H4')):
        h5[h] = {}
        for b in BOOKS:
            per = {}
            for j in res:
                n, w = res[j]['books'][b]['N'][key], res[j]['books'][b]['W'][key]
                if n is None or w is None:
                    per[j] = None; continue
                if h == 'H1':
                    per[j] = {'W_over_N': w / n if n else None, 'up': w > n}
                elif h == 'H3':
                    per[j] = {'N_minus_W': n - w, 'improved': n - w >= TH['H3'], 'direction_better': w < n}
                else:
                    per[j] = {'W_minus_N': w - n, 'improved': w - n >= TH[h], 'direction_better': w > n}
            h5[h][b] = per
    def cnt(h, f):
        return sum(1 for b in BOOKS if all(h5[h][b][j] and h5[h][b][j][f] for j in res))
    h5['_summary'] = {'H1_up_books': cnt('H1', 'up'), 'H2_improved_books': cnt('H2', 'improved'),
                      'H3_improved_books': cnt('H3', 'improved'), 'H4_improved_books': cnt('H4', 'improved'),
                      'H2_dir_better_books': cnt('H2', 'direction_better'),
                      'H3_dir_better_books': cnt('H3', 'direction_better'),
                      'H4_dir_better_books': cnt('H4', 'direction_better')}
    s = h5['_summary']
    s['prediction_holds'] = s['H1_up_books'] >= 2 and s['H2_improved_books'] < 2 and s['H3_improved_books'] < 2
    out = {'mode': MODE, 'thresholds': TH, 'judges': {j: {'books': res[j]['books'], 'human': res[j]['human']} for j in res},
           'per_text': {j: {t: {k: v for k, v in p.items()} for t, p in res[j]['per_text'].items()} for j in res},
           'verdict': verdict, 'human_range': hr, 'H5': h5}
    dump_json(EXP_DIR / '判讀/results.json', out)
    for j in res:
        print('==', j)
        for b in BOOKS:
            for arm in ('O', 'N', 'W'):
                g = res[j]['books'][b][arm]
                print(b, arm, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in g.items()})
        for x, g in res[j]['human'].items():
            print(x, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in g.items()})
    print('verdict', {h: verdict[h]['_summary'] for h in verdict})
    for h in verdict:
        for b in BOOKS:
            print(h, b, verdict[h][b])
    print('human range', {h: {b: hr[h][b]['demote'] for b in BOOKS} for h in hr})
    print('H5', h5['_summary'])


if __name__ == '__main__':
    main()
