"""第 1 步指標。python analyze.py  → 判讀/results.json，並印出主要表格。
定義照 00-凍結.md。
"""
import json, collections, statistics
from common import *

TURNING = {367: {3, 5, 6, 8}, 400: {6, 13, 16, 17}, 425: {7, 11, 13, 16, 18}}
NEVENTS = {367: 10, 400: 17, 425: 19}
# 負擔用的欄位（凍結時依校準結果決定）
BURDEN = {'foreground': True, 'inference': True, 'late_new': True, 'stress': True}
DROPPED = set()  # 從主分析拿掉的欄位名

TEXTS = load_json(R2 / '判讀/texts.json')
LAB = {j: load_json(R2 / f'判讀/labels_{j}.json') for j in ('j1', 'j2')}


def burden(v):
    b = 0
    if BURDEN['foreground']: b += len(v['foreground'])
    if BURDEN['inference']: b += len(v['inference'])
    if BURDEN['late_new']: b += v['focus'] == '後新'
    if BURDEN['stress']: b += bool(v['stress'])
    return b


def rows(j, tid):
    t = TEXTS[tid]
    out = []
    for i, p in enumerate(t['paras']):
        v = LAB[j].get(f'{tid}#{i}')
        if v is not None:
            out.append((i, p, v))
    return out


def para_metrics(rs):
    n = len(rs)
    chars = sum(cjk_len(p) for _, p, _ in rs)
    kc = chars / 1000
    judged = [v for _, _, v in rs if v['focus'] != '不判']
    late_new = sum(v['focus'] == '後新' for v in judged)
    late_old = sum(v['focus'] == '後舊' for v in judged)
    fg = sum(len(v['foreground']) for _, _, v in rs)
    cl = sum(len(v['cliche']) for _, _, v in rs)
    inf = sum(len(v['inference']) for _, _, v in rs)
    st = sum(bool(v['stress']) for _, _, v in rs)
    su = sum(bool(v['setup']) for _, _, v in rs)
    bs = [burden(v) for _, _, v in rs]
    run = best = 0
    for b in bs:
        run = run + 1 if b >= 2 else 0
        best = max(best, run)
    return {'n': n, 'chars': chars,
            'late_new_rate': late_new / len(judged) if judged else None,
            'late_old_rate': late_old / len(judged) if judged else None,
            'focus_judged': len(judged),
            'fg_per_k': fg / kc, 'cliche_per_k': cl / kc, 'inf_per_k': inf / kc,
            'stress_rate': st / n, 'setup_n': su, 'setup_per_k': su / kc,
            'burden_mean': sum(bs) / n, 'rest_rate': sum(b == 0 for b in bs) / n, 'max_high_run': best}


def event_metrics(rs, ch):
    """M2、M3、M4 的事件部分。rs 是單一文本的段。"""
    turn = TURNING[ch]
    bt = [burden(v) for _, _, v in rs if set(v['events']) & turn]
    bo = [burden(v) for _, _, v in rs if not (set(v['events']) & turn)]
    chars_ev = collections.Counter()
    pos = collections.defaultdict(list)
    for i, p, v in rs:
        ev = [e for e in v['events'] if 1 <= e <= NEVENTS[ch]]
        for e in ev:
            chars_ev[e] += cjk_len(p) / len(ev)
            pos[e].append(i)
    allev = range(1, NEVENTS[ch] + 1)
    t_chars = [chars_ev[e] for e in allev if e in turn]
    o_chars = [chars_ev[e] for e in allev if e not in turn]
    charmap = {i: cjk_len(p) for i, p, _ in rs}
    spans, spans_c, spans_t = [], [], []
    for e, ps in pos.items():
        s = max(ps) - min(ps) + 1
        spans.append(s)
        spans_c.append(sum(charmap.get(k, 0) for k in range(min(ps), max(ps) + 1)))
        if e in turn:
            spans_t.append(s)
    return {'bt_sum': sum(bt), 'bt_n': len(bt), 'bo_sum': sum(bo), 'bo_n': len(bo),
            'M2': (sum(bt) / len(bt)) / (sum(bo) / len(bo)) if bt and bo and sum(bo) else None,
            'turn_chars_mean': statistics.mean(t_chars), 'other_chars_mean': statistics.mean(o_chars),
            'M3': statistics.mean(t_chars) / statistics.mean(o_chars) if statistics.mean(o_chars) else None,
            'events_covered': len(pos), 'span_mean': statistics.mean(spans) if spans else None,
            'span_chars_mean': statistics.mean(spans_c) if spans_c else None,
            'turn_span_mean': statistics.mean(spans_t) if spans_t else None,
            'chars_by_event': {e: round(chars_ev[e]) for e in allev},
            'unassigned_rate': sum(1 for _, _, v in rs if not v['events']) / len(rs)}


def pooled(j, tids):
    rs = []
    for tid in tids:
        rs += [(f'{tid}#{i}', p, v) for i, p, v in rows(j, tid)]
    return rs


def pooled_event(j, tids, ch):
    """配對組 Claude 四篇合併：M2 用合併段落；M3 用每事件字數的四篇平均；跨段用四篇平均。"""
    ems = [event_metrics(rows(j, t), ch) for t in tids]
    bt = sum(e['bt_sum'] for e in ems); btn = sum(e['bt_n'] for e in ems)
    bo = sum(e['bo_sum'] for e in ems); bon = sum(e['bo_n'] for e in ems)
    tc = statistics.mean(e['turn_chars_mean'] for e in ems)
    oc = statistics.mean(e['other_chars_mean'] for e in ems)
    return {'M2': (bt / btn) / (bo / bon) if btn and bon and bo else None,
            'turn_chars_mean': tc, 'other_chars_mean': oc, 'M3': tc / oc if oc else None,
            'span_mean': statistics.mean(e['span_mean'] for e in ems),
            'turn_span_mean': statistics.mean(e['turn_span_mean'] for e in ems if e['turn_span_mean']),
            'span_chars_mean': statistics.mean(e['span_chars_mean'] for e in ems),
            'unassigned_rate': statistics.mean(e['unassigned_rate'] for e in ems)}


def kappa2(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')


def agreement():
    keys = sorted(set(LAB['j1']) & set(LAB['j2']))
    a, b = LAB['j1'], LAB['j2']
    tests = {
        '類型 對白': lambda v: v['type'] == '對白',
        '焦點 後新': lambda v: v['focus'] == '後新',
        '焦點 後(舊+新)': lambda v: v['focus'].startswith('後'),
        '前景化 有': lambda v: bool(v['foreground']),
        '套語 有': lambda v: bool(v['cliche']),
        '推論 有': lambda v: bool(v['inference']),
        '重音': lambda v: v['stress'],
        '預告段': lambda v: v['setup'],
        '負擔≥2': lambda v: burden(v) >= 2,
    }
    res = {name: round(kappa2([f(a[k]) for k in keys], [f(b[k]) for k in keys]), 3) for name, f in tests.items()}
    foc = sum(a[k]['focus'] == b[k]['focus'] for k in keys) / len(keys)
    res['焦點五類一致率'] = round(foc, 3)
    pk = [k for k in keys if TEXTS[k.split('#')[0]]['group'] == 'pair']
    res['事件 完全相同'] = round(sum(sorted(a[k]['events']) == sorted(b[k]['events']) for k in pk) / len(pk), 3)
    res['事件 有交集或皆空'] = round(sum(bool((set(a[k]['events']) & set(b[k]['events'])) or (not a[k]['events'] and not b[k]['events'])) for k in pk) / len(pk), 3)
    def isturn(k, v):
        ch = TEXTS[k.split('#')[0]]['ch']; return bool(set(v['events']) & TURNING[ch])
    res['轉折段 kappa'] = round(kappa2([isturn(k, a[k]) for k in pk], [isturn(k, b[k]) for k in pk]), 3)
    res['n'] = len(keys)
    return res


def main():
    R = {'per_text': {}, 'per_chapter': {}, 'groups': {}, 'agreement': agreement()}
    for j in ('j1', 'j2'):
        for tid, t in TEXTS.items():
            rs = rows(j, tid)
            m = para_metrics(rs)
            if t['group'] == 'pair':
                m.update(event_metrics(rs, t['ch']))
            R['per_text'].setdefault(tid, {})[j] = m
        for ch in (367, 400, 425):
            cl = [k for k, t in TEXTS.items() if t.get('role') == 'claude' and t['ch'] == ch]
            o = para_metrics(rows(j, f'O{ch}')); o.update(event_metrics(rows(j, f'O{ch}'), ch))
            c = para_metrics(pooled(j, cl)); c.update(pooled_event(j, cl, ch))
            R['per_chapter'].setdefault(str(ch), {})[j] = {'orig': o, 'claude': c}
        groups = {'原文': [k for k, t in TEXTS.items() if t.get('role') == 'orig'],
                  'Claude': [k for k, t in TEXTS.items() if t.get('role') == 'claude'],
                  '人類範圍': [k for k, t in TEXTS.items() if t['group'] == 'human']}
        for g, ts in groups.items():
            R['groups'].setdefault(g, {})[j] = para_metrics(pooled(j, ts))
    # 預測
    P = {}
    for j in ('j1', 'j2'):
        pc = R['per_chapter']
        def cnt(f):
            return sum(f(pc[c][j]['orig'], pc[c][j]['claude']) for c in pc)
        P[j] = {
            'P1': cnt(lambda o, c: c['late_new_rate'] > o['late_new_rate']),
            'P2': cnt(lambda o, c: c['fg_per_k'] >= 2 * o['fg_per_k']),
            'P3': cnt(lambda o, c: c['stress_rate'] > o['stress_rate']),
            'P4': cnt(lambda o, c: (o['M2'] or 0) > (c['M2'] or 0)),
            'P5': cnt(lambda o, c: (o['M3'] or 0) > (c['M3'] or 0)),
        }
    need = {'P1': 2, 'P2': 3, 'P3': 2, 'P4': 2, 'P5': 2}
    R['predictions'] = {p: {'j1': P['j1'][p], 'j2': P['j2'][p], 'need': need[p],
                            'verdict': ('成立' if P['j1'][p] >= need[p] and P['j2'][p] >= need[p]
                                        else '只有一個判者成立' if (P['j1'][p] >= need[p]) != (P['j2'][p] >= need[p])
                                        else '不成立')} for p in need}
    # 人類範圍：前景化密度
    hr = {}
    for j in ('j1', 'j2'):
        others = [R['per_text'][k][j]['fg_per_k'] for k, t in TEXTS.items() if t['group'] == 'human' and t['book'] != '一世之尊']
        lo, hi = min(others), max(others)
        ysz = [R['per_text'][k][j]['fg_per_k'] for k, t in TEXTS.items() if t.get('book') == '一世之尊'][0]
        sx = R['groups']['原文'][j]['fg_per_k']
        sx_each = [R['per_text'][f'O{c}'][j]['fg_per_k'] for c in (367, 400, 425)]
        hr[j] = {'others_range': [lo, hi], '一世之尊': ysz, '神秀之主_合併': sx, '神秀之主_各章': sx_each,
                 '一世之尊_在範圍內': lo <= ysz <= hi, '神秀之主_在範圍內': lo <= sx <= hi}
    R['human_range'] = hr
    dump_json(R2 / '判讀/results.json', R)
    report(R)


def f(x, d=2, pct=False):
    if x is None: return '—'
    return f'{x:.0%}' if pct else f'{x:.{d}f}'


def report(R):
    for j in ('j1', 'j2'):
        print(f'\n=== {j} 每章')
        print('章|組|段|字|後新|後舊|前景化/k|套語/k|推論/k|重音|預告/k|喘息|最長高負擔|M2|M3|事件跨段|轉折跨段|未歸事件')
        for c, d in R['per_chapter'].items():
            for g in ('orig', 'claude'):
                m = d[j][g]
                print('|'.join([c, g, str(m['n']), str(m['chars']), f(m['late_new_rate'], pct=True), f(m['late_old_rate'], pct=True),
                                f(m['fg_per_k']), f(m['cliche_per_k']), f(m['inf_per_k']), f(m['stress_rate'], pct=True),
                                f(m['setup_per_k']), f(m['rest_rate'], pct=True), str(m['max_high_run']), f(m['M2']), f(m['M3']),
                                f(m['span_mean'], 1), f(m['turn_span_mean'], 1), f(m['unassigned_rate'], pct=True)]))
        print(f'--- {j} 每篇')
        for tid, d in R['per_text'].items():
            m = d[j]
            print('|'.join([tid, TEXTS[tid].get('book', ''), str(m['n']), f(m['late_new_rate'], pct=True), f(m['fg_per_k']), f(m['cliche_per_k']),
                            f(m['inf_per_k']), f(m['stress_rate'], pct=True), f(m['setup_per_k']), f(m['rest_rate'], pct=True),
                            str(m['max_high_run']), f(m.get('M2')), f(m.get('M3'))]))
        print(f'--- {j} 每組')
        for g, d in R['groups'].items():
            m = d[j]
            print(g, m['n'], m['chars'], f(m['late_new_rate'], pct=True), f(m['fg_per_k']), f(m['cliche_per_k']), f(m['inf_per_k']),
                  f(m['stress_rate'], pct=True), f(m['setup_per_k']), f(m['rest_rate'], pct=True), m['max_high_run'])
    print('\n一致性', R['agreement'])
    print('預測', json.dumps(R['predictions'], ensure_ascii=False))
    print('人類範圍', json.dumps(R['human_range'], ensure_ascii=False))


if __name__ == '__main__':
    main()
