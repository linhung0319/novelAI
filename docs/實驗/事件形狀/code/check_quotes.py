"""質性對照報告的引文核對：「」裡長度 ≥6 的字串是否出現在該章工作檔裡。結果寫 判讀/質性/quote_check.json。"""
import re, shutil
from common import *
res = {}
for n in range(1, 7):
    src = (SCRATCH / 'qual' / f'Q{n}.txt').read_text(encoding='utf-8')
    rep_p = SCRATCH / 'qual' / f'out_Q{n}.md'
    shutil.copy(rep_p, EXP_DIR / '判讀/質性' / f'out_Q{n}.md')
    rep = rep_p.read_text(encoding='utf-8')
    qs = [q for q in re.findall(r'「([^」]{6,}?)」', rep)]
    miss = [q for q in qs if q not in src and q.replace('……', '…') not in src]
    res[f'Q{n}'] = {'quotes': len(qs), 'not_found': miss}
    print(f'Q{n}', len(qs), '未命中', len(miss), miss[:4])
dump_json(EXP_DIR / '判讀/質性/quote_check.json', res)
