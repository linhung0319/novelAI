"""質性對照工作檔：每章一檔，原文＋4 篇稿，篇序打亂，只用隨機代號（判讀/texts.json 的 T 代號）。
python prep_qual.py    寫到 SCRATCH/qual/<章代號>.txt，對照存 判讀/質性/qual_key.json
"""
import random
from common import *

T = load_json(EXP_DIR / '判讀/texts.json')
SEED = 20261111


def main():
    rng = random.Random(SEED)
    chs = sorted({t['ch'] for t in T.values() if t['group'] == 'pair'})
    key = {}
    for n, ch in enumerate(chs, 1):
        tids = [tid for tid, t in T.items() if t['ch'] == ch]
        rng.shuffle(tids)
        evt, _ = event_text(ch)
        lines = ['# 事件清單（依發生順序）', '', evt, '', '---', '']
        for tid in tids:
            lines += [f'# 文本 {tid}', ''] + T[tid]['paras'] + ['', '---', '']
        code = f'Q{n}'
        p = SCRATCH / 'qual' / f'{code}.txt'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('\n'.join(lines), encoding='utf-8')
        key[code] = {'ch': ch, 'order': tids}
    dump_json(EXP_DIR / '判讀/質性/qual_key.json', key)
    print(key)


if __name__ == '__main__':
    main()
