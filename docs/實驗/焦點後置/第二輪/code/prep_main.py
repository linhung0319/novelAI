"""第 1 步：讀語料、切段、打散、切批。
python prep_main.py          產生 判讀/texts.json、判讀/key.json、判讀/batches.json，批次檔寫到 scratch/main/
"""
import json, random, re, collections
from common import *

SEED = 20261109
TARGET = 70  # 每批目標段數
CORPUS = EXP / 'AI腔成因/corpus'
CKEY = load_json(EXP / 'AI腔成因/corpus_key.json')
ORIG = {367: '第367章_談笑殺人.txt', 400: '第400章_賄賂.txt', 425: '第425章_一劍挑了.txt'}
DRAFTS = EXP / 'AI腔成因/神秀實驗/稿件'
INSTR = EXP / 'AI腔成因/神秀實驗/指示'
END = tuple('。！？!?…」』”’）)—：:~～')


def merge_broken(paras):
    """段落結尾不是句末標點時與下一段合併（判決句實驗的同一條規則）。"""
    out, buf, merges = [], '', 0
    for p in paras:
        buf = buf + p if buf else p
        if buf.endswith(END):
            out.append(buf); buf = ''
        else:
            merges += 1
    if buf:
        out.append(buf)
    return out, merges


def event_list(ch):
    t = (INSTR / f'ch{ch}.md').read_text(encoding='utf-8')
    sec = t.split('## 這一章發生什麼', 1)[1]
    sec = re.split(r'\n## ', sec, 1)[0]
    lines = sec.splitlines()[1:]
    keep = [l for l in lines if not l.startswith('這章的重點')]
    body = '\n'.join(keep).strip()
    n = max(int(m) for m in re.findall(r'^(\d+)\.', body, re.M))
    return body, n


def human_range():
    """human_base 每本書一章（神秀之主除外），兩章中用固定 seed 選一章。"""
    by_book = collections.defaultdict(list)
    for tid, v in CKEY.items():
        if v['group'] == 'human_base' and v['book'] != '神秀之主':
            by_book[v['book']].append(tid)
    rng = random.Random(SEED)
    pick = {b: rng.choice(sorted(ts)) for b, ts in sorted(by_book.items())}
    return pick


def build_texts():
    texts = {}
    for ch, fn in ORIG.items():
        raw = (REPO / 'examples/神秀之主' / fn).read_text(encoding='utf-8')
        paras = paras_from_text(raw)[1:]  # 去標題行
        paras, m = merge_broken(paras)
        texts[f'O{ch}'] = {'group': 'pair', 'role': 'orig', 'ch': ch, 'src': f'examples/神秀之主/{fn}', 'paras': paras, 'merges': m}
    for p in sorted(DRAFTS.glob('c_*.md')):
        _, ch, arm, rep = p.stem.split('_')
        paras, m = merge_broken(paras_from_text(p.read_text(encoding='utf-8')))
        texts[p.stem] = {'group': 'pair', 'role': 'claude', 'ch': int(ch), 'arm': arm, 'rep': int(rep),
                         'src': f'AI腔成因/神秀實驗/稿件/{p.name}', 'paras': paras, 'merges': m}
    for book, tid in human_range().items():
        paras, m = merge_broken(paras_from_text((CORPUS / f'{tid}.txt').read_text(encoding='utf-8')))
        texts[tid] = {'group': 'human', 'role': 'human', 'book': book, 'src': f'AI腔成因/corpus/{tid}.txt',
                      'orig_file': CKEY[tid]['src'], 'paras': paras, 'merges': m}
    return texts


def main():
    texts = build_texts()
    items = []
    for tid, t in texts.items():
        ps = t['paras']
        for i, p in enumerate(ps):
            items.append({'tid': tid, 'idx': i, 'prev': ps[i - 1] if i else '', 'cur': p,
                          'next': ps[i + 1] if i + 1 < len(ps) else ''})
    rng = random.Random(SEED)
    rng.shuffle(items)
    for n, it in enumerate(items, 1):
        it['pid'] = f'P{n:05d}'
    pair = collections.defaultdict(list)
    human = []
    for it in items:
        t = texts[it['tid']]
        (pair[t['ch']] if t['group'] == 'pair' else human).append(it)
    # 人類範圍段按配對池大小比例分給三章的批次（判者看不出哪些是人類範圍組）
    total = sum(len(v) for v in pair.values())
    shares, start = {}, 0
    chs = sorted(pair)
    for k, ch in enumerate(chs):
        cnt = len(human) - start if k == len(chs) - 1 else round(len(human) * len(pair[ch]) / total)
        shares[ch] = human[start:start + cnt]; start += cnt
    batches = {}
    bno = 0
    for ch in chs:
        pool = pair[ch] + shares[ch]
        rng.shuffle(pool)
        nb = max(1, round(len(pool) / TARGET))
        size = len(pool) / nb
        evtext, nev = event_list(ch)
        for b in range(nb):
            bno += 1
            chunk = pool[round(b * size):round((b + 1) * size)]
            chunk.sort(key=lambda x: x['pid'])
            name = f'b{bno:03d}'
            write_batch(SCRATCH / 'main' / f'{name}.txt', chunk, evtext)
            batches[name] = {'ch': ch, 'max_event': nev, 'pids': [c['pid'] for c in chunk]}
    key = {it['pid']: {'tid': it['tid'], 'idx': it['idx']} for it in items}
    dump_json(R2 / '判讀/texts.json', texts)
    dump_json(R2 / '判讀/key.json', key)
    dump_json(R2 / '判讀/batches.json', batches)
    print('texts', len(texts), 'items', len(items), 'batches', len(batches))
    for tid, t in texts.items():
        print(tid, t.get('book', ''), len(t['paras']), sum(cjk_len(p) for p in t['paras']), 'merges', t['merges'])
    print({b: len(v['pids']) for b, v in batches.items()})


if __name__ == '__main__':
    main()
