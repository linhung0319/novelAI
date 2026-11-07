"""第 1 步：切段、給隨機代號、打散、切批。
python prep_main.py    寫 判讀/texts.json、判讀/key.json、判讀/batches.json、代號對照.json；批次檔到 SCRATCH/main/
"""
import random, collections
from common import *

SEL = load_json(EXP_DIR / 'code/selection.json')
WK = load_json(EXP_DIR / '稿件/write_key.json')
SEED = 20261110
TARGET = 70
HUMAN_LIST = {'H紅': 'H紅47', 'H極': 'H極32'}


def build_texts():
    raw = []
    for k, (book, cur, prev) in SEL['paired'].items():
        raw.append({'group': 'pair', 'role': 'orig', 'ch': k, 'book': book, 'arm': 'O', 'rep': 0,
                    'src': f'examples/{cur}', 'text': (EXAMPLES / cur).read_text(encoding='utf-8'), 'title': True})
    for code, v in WK.items():
        p = EXP_DIR / '稿件' / f'{v["ch"]}_{v["arm"]}_{v["rep"]}.txt'
        raw.append({'group': 'pair', 'role': 'claude', 'ch': v['ch'], 'book': v['book'], 'arm': v['arm'],
                    'rep': v['rep'], 'src': f'稿件/{p.name}', 'text': p.read_text(encoding='utf-8'), 'title': False,
                    'writer_code': code})
    for k, (book, cur, prev) in SEL['human'].items():
        raw.append({'group': 'human', 'role': 'human', 'ch': HUMAN_LIST[k], 'book': book, 'arm': 'H', 'rep': 0,
                    'src': f'examples/{cur}', 'text': (EXAMPLES / cur).read_text(encoding='utf-8'), 'title': True})
    rng = random.Random(SEED)
    codes = [f'T{n}' for n in rng.sample(range(1000, 10000), len(raw))]
    texts = {}
    for code, r in zip(codes, raw):
        paras, m = split_paras(r.pop('text'), drop_title=r.pop('title'))
        texts[code] = {**r, 'paras': paras, 'merges': m, 'chars': sum(cjk_len(p) for p in paras)}
    return texts


def main():
    texts = build_texts()
    items = []
    for tid, t in texts.items():
        items += items_of(tid, t['paras'])
    rng = random.Random(SEED)
    rng.shuffle(items)
    for n, it in enumerate(items, 1):
        it['pid'] = f'P{n:05d}'
    pools = collections.defaultdict(list)
    for it in items:
        pools[texts[it['tid']]['ch']].append(it)
    batches, bno = {}, 0
    for ch in sorted(pools):
        pool = pools[ch]
        rng.shuffle(pool)
        nb = max(1, round(len(pool) / TARGET))
        size = len(pool) / nb
        evt, nev = event_text(ch)
        for b in range(nb):
            bno += 1
            chunk = sorted(pool[round(b * size):round((b + 1) * size)], key=lambda x: x['pid'])
            name = f'b{bno:03d}'
            write_batch(SCRATCH / 'main' / f'{name}.txt', chunk, evt)
            batches[name] = {'ch': ch, 'max_event': nev, 'pids': [c['pid'] for c in chunk]}
    key = {it['pid']: {'tid': it['tid'], 'idx': it['idx']} for it in items}
    dump_json(EXP_DIR / '判讀/texts.json', texts)
    dump_json(EXP_DIR / '判讀/key.json', key)
    dump_json(EXP_DIR / '判讀/batches.json', batches)
    dump_json(EXP_DIR / '代號對照.json', {c: {k: t[k] for k in ('group', 'role', 'book', 'ch', 'arm', 'rep', 'src')}
                                          for c, t in texts.items()})
    print('texts', len(texts), 'paras', len(items), 'batches', len(batches))
    sizes = [len(b['pids']) for b in batches.values()]
    print('batch size', min(sizes), max(sizes))
    for c, t in sorted(texts.items(), key=lambda x: (x[1]['ch'], x[1]['arm'], x[1]['rep'])):
        print(c, t['ch'], t['arm'], t['rep'], len(t['paras']), t['chars'], 'merges', t['merges'])


if __name__ == '__main__':
    main()
