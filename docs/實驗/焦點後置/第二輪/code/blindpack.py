"""第 3 步：作者盲讀包。python blindpack.py
每章取同一段事件：原文一段、Claude 稿一段（固定 seed 從 4 篇抽 1）。段落範圍用兩個判者事件編號一致的段決定。
輸出 盲讀包/（給作者）與 盲讀包_對照鍵.json（放在盲讀包資料夾外）。
"""
import random, re
from common import *

SEED = 20261110
RANGES = {367: (3, 5), 400: (13, 17), 425: (15, 19)}
TEXTS = load_json(R2 / '判讀/texts.json')
A = load_json(R2 / '判讀/labels_j1.json')
B = load_json(R2 / '判讀/labels_j2.json')

# 統一標點與簡轉繁殘留，避免作者從字形認出來源
FIX = [('“', '「'), ('”', '」'), ('‘', '『'), ('’', '』'), ('么', '麼'), ('于', '於'), ('后', '後'),
       ('手里', '手裡'), ('心里', '心裡'), ('這里', '這裡'), ('那里', '那裡'), ('里面', '裡面'), ('屋里', '屋裡'), ('包廂里', '包廂裡'), ('死里', '死裡'), ('一只', '一隻'), ('鉆', '鑽'), ('余辜', '餘辜'), ('殘余', '殘餘'), ('震蕩', '震盪'), ('什么', '什麼')]


def norm(s):
    for a, b in FIX:
        s = s.replace(a, b)
    return s


def segment(tid, lo, hi):
    ps = TEXTS[tid]['paras']
    idx = []
    for i in range(len(ps)):
        ea, eb = set(A[f'{tid}#{i}']['events']), set(B[f'{tid}#{i}']['events'])
        ev = ea & eb
        if ev and all(lo <= e <= hi for e in ev):
            idx.append(i)
    s, e = min(idx), max(idx)
    return s, e, [norm(p) for p in ps[s:e + 1]]


def main():
    rng = random.Random(SEED)
    segs = []
    for ch, (lo, hi) in RANGES.items():
        drafts = sorted(k for k, t in TEXTS.items() if t.get('role') == 'claude' and t['ch'] == ch)
        pick = rng.choice(drafts)
        for tid in (f'O{ch}', pick):
            s, e, ps = segment(tid, lo, hi)
            segs.append({'ch': ch, 'tid': tid, 'from': s, 'to': e, 'paras': ps, 'chars': sum(cjk_len(p) for p in ps)})
    order = list(range(len(segs)))
    rng.shuffle(order)
    labels = '甲乙丙丁戊己'
    key = {}
    out = ['# 盲讀：六段節錄', '',
           '先讀 `填答說明.md`。六段的順序是打亂的，同一場戲的兩段不一定相鄰。', '']
    for lab, n in zip(labels, order):
        sg = segs[n]
        key[lab] = {k: sg[k] for k in ('ch', 'tid', 'from', 'to', 'chars')}
        out += [f'## {lab}', ''] + [p + '\n' for p in sg['paras']] + ['']
    pairs = {}
    for lab, v in key.items():
        pairs.setdefault(v['ch'], []).append(lab)
    pair_lines = [f'- 第 {i} 組：{"、".join(sorted(v, key=labels.index))}' for i, v in enumerate(sorted(pairs.values(), key=lambda x: labels.index(sorted(x, key=labels.index)[0])), 1)]
    guide = ['# 填答說明', '',
             '`節錄.md` 有六段小說節錄，兩兩是同一場戲的兩個版本：', ''] + pair_lines + ['',
             '請照平常讀網文的速度讀，不用刻意細讀。全部大約 15–20 分鐘。', '',
             '## 要做的兩件事', '',
             '1. **畫線**：讀到慢下來、回頭重讀、或抓不到這段在講什麼的地方，在 `節錄.md` 裡把那幾個字用 〖 〗 框起來。想加一句原因可以寫在後面，例如 〖……〗（回頭看了兩次）。沒有就不畫。',
             '2. **比較**：每組讀完後，在下面填哪一段讀起來比較累，可以加一句為什麼。', '']
    for i, v in enumerate(pair_lines, 1):
        guide += [f'### 第 {i} 組', '', '比較累的是：', '', '為什麼（選填）：', '']
    guide += ['## 注意', '', '- 請先不要打開別的檔案或問 Claude 這幾段的來源。',
              '- 標點和少數字形已統一（引號一律用「」『』），所以字形不能當線索。']
    d = R2 / '盲讀包'
    (d / '節錄.md').write_text('\n'.join(out), encoding='utf-8')
    (d / '填答說明.md').write_text('\n'.join(guide), encoding='utf-8')
    dump_json(R2 / '盲讀包_對照鍵.json', {'seed': SEED, 'ranges': RANGES, 'normalization': FIX, 'key': key})
    for lab, v in key.items():
        print(lab, v)
    print(pair_lines)


if __name__ == '__main__':
    main()
