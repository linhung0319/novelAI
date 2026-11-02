import json, collections, glob, os, sys, re
s = sys.argv[1]
base = r'C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Programming-novelAI\2f45c7c4-7743-45cf-9201-2b5c117db62c\scratchpad\tests'
root = r'C:\Users\user\Programming\novelAI\docs\新技巧知識庫'
A = json.load(open(os.path.join(base, f'set-{s}.json'), encoding='utf-8'))
r1 = {x['id']: x for x in json.load(open(os.path.join(base, f'route-{s}-1.json'), encoding='utf-8'))}
r2 = {x['id']: x for x in json.load(open(os.path.join(base, f'route-{s}-2.json'), encoding='utf-8'))}
cards = {os.path.basename(f)[:-3] for f in glob.glob(os.path.join(root, 'cards', '*.md'))}
out = []
cnt = collections.Counter(); ov = 0; neg = neg_ok = 0; empties = []; conf = collections.Counter(); pair = collections.Counter()
for x in A:
    i = x['id']; a = set(r1[i]['picks']); b = set(r2[i]['picks'])
    for c in a | b:
        cnt[c] += 1
        if c not in cards: out.append(f'BAD NAME {i} {c}')
    isneg = 'NEG' in x['note']
    if isneg:
        neg += 1; neg_ok += (not a and not b)
    elif not a or not b:
        empties.append(i)
    agree = bool(a & b) or (not a and not b)
    ov += agree
    conf[r1[i]['conf']] += 1; conf[r2[i]['conf']] += 1
    if not agree and a and b:
        for p in a:
            for q in b:
                pair[tuple(sorted((p, q)))] += 1
    for alt, picks in ((r1[i]['alt'], a), (r2[i]['alt'], b)):
        if alt:
            for p in picks:
                pair[tuple(sorted((p, alt)))] += 1
    mark = 'OK ' if agree else 'DIFF'
    out.append(f"{mark} {i} {x['mode']} {'NEG' if isneg else ''} {x['complaint'][:40]} | {sorted(a)} {r1[i]['conf']} | {sorted(b)} {r2[i]['conf']} | alt:{r1[i]['alt']}/{r2[i]['alt']}")
out.append(f'agree {ov}/{len(A)}; NEG both zero {neg_ok}/{neg}; non-NEG with an empty pick: {empties}')
out.append(f'conf {dict(conf)}')
out.append(f'distinct cards hit {len(cnt)} of {len(cards)}')
out.append(f'top {cnt.most_common(15)}')
out.append(f'confusable pairs {pair.most_common(25)}')
open(os.path.join(base, f'compare-{s}.txt'), 'w', encoding='utf-8').write('\n'.join(out))
