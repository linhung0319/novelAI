"""把主持者的校準標籤（host_calib_spec.txt）展開成 校準/host_labels.json，並檢查段數。"""
import collections
from common import *
SEL = load_json(EXP_DIR / 'code/selection.json')
spec, cur = collections.defaultdict(list), None
for line in (EXP_DIR / 'code/host_calib_spec.txt').read_text(encoding='utf-8').splitlines():
    if line.startswith('## '):
        cur = line[3:].strip()
    elif line.strip():
        spec[cur].append(line.split())
L = {}
for k, rows in spec.items():
    n = len(split_paras((EXAMPLES / SEL['calib'][k][1]).read_text(encoding='utf-8'), drop_title=True)[0])
    seen = set()
    for r, e, f in rows:
        a, b = (r.split('-') + [r])[:2]
        for i in range(int(a), int(b) + 1):
            assert i not in seen; seen.add(i)
            L[f'{k}#{i}'] = {'event': int(e), 'func': f}
    assert seen == set(range(n)), (k, n, sorted(set(range(n)) ^ seen))
    print(k, n)
dump_json(EXP_DIR / '校準/host_labels.json', L)
print(collections.Counter(v['func'] for v in L.values()))
