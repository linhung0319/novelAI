"""寫稿工作檔：每篇一檔（前一章原文＋文體說明＋事件清單＋目標字數＋格式）。
python prep_write.py          寫到 SCRATCH/wr/<代號>.txt，對照存 稿件/write_key.json
python prep_write.py check    檢查 SCRATCH/wr/out_<代號>.txt 的字數，合格的複製到 稿件/
"""
import sys, random, re, shutil
from common import *
from prep_weight import event_lines, prev_text

SEL = load_json(EXP_DIR / 'code/selection.json')
W = load_json(EXP_DIR / '輕重/weights.json')['events']
SEED = 20261108
GENRE = {
    '詭秘之主': '西方奇幻背景的網路小說，繁體中文，敘述用第三人稱。這位作者刻意不用成語。',
    '一世之尊': '武俠仙俠網文，繁體中文，敘述用第三人稱。',
    '神秀之主': '仙俠網文，繁體中文，敘述用第三人稱。',
}
LV = {1: '輕', 2: '中', 3: '重'}


def target(rel):
    paras, _ = split_paras((EXAMPLES / rel).read_text(encoding='utf-8'), drop_title=True)
    return sum(cjk_len(p) for p in paras)


def build(k, arm):
    book, cur, prev = SEL['paired'][k]
    evs = event_lines(f'{k}.md')
    if arm == 'W':
        evs = [f'{l}（{LV[W[k][str(i + 1)]["rounded"]]}）' for i, l in enumerate(evs)]
    t = target(cur)
    lines = [
        '請接著下面這一章，寫出下一章的正文。', '',
        f'文體：{GENRE[book]}', '',
        '# 前一章', '', prev_text(prev), '', '---', '',
        '# 下一章要寫的事件', '',
        '依照順序寫完下面每一件事，不要跳過，也不要另外加入大的事件。',
    ]
    if arm == 'W':
        lines.append('每一條後面括號裡標的是這件事在本章的輕重。')
    lines += [''] + evs + ['',
              f'篇幅：大約 {t} 個漢字，上下不超過一成（{round(t * 0.9)}–{round(t * 1.1)} 字）。', '',
              '格式：一段一行。不寫章名或標題，不寫任何說明或附註，只寫正文。']
    return '\n'.join(lines) + '\n', t


def prep():
    jobs = [(k, arm, rep) for k in SEL['paired'] for arm in ('N', 'W') for rep in (1, 2)]
    rng = random.Random(SEED)
    codes = [f'D{n}' for n in rng.sample(range(100, 1000), len(jobs))]
    key = {}
    for code, (k, arm, rep) in zip(codes, jobs):
        body, t = build(k, arm)
        p = SCRATCH / 'wr' / f'{code}.txt'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding='utf-8')
        key[code] = {'ch': k, 'book': SEL['paired'][k][0], 'arm': arm, 'rep': rep, 'target': t}
    dump_json(EXP_DIR / '稿件/write_key.json', key)
    for c, v in key.items():
        print(c, v)


def check():
    key = load_json(EXP_DIR / '稿件/write_key.json')
    for c, v in key.items():
        p = SCRATCH / 'wr' / f'out_{c}.txt'
        if not p.exists():
            print(c, '缺'); continue
        n = cjk_len(p.read_text(encoding='utf-8'))
        r = n / v['target']
        flag = 'OK' if 0.75 <= r <= 1.25 else '超出±25%'
        print(c, v['ch'], v['arm'], v['rep'], n, v['target'], f'{r:.2f}', flag)
        shutil.copy(p, EXP_DIR / '稿件' / f'{v["ch"]}_{v["arm"]}_{v["rep"]}.txt')


if __name__ == '__main__':
    check() if len(sys.argv) > 1 and sys.argv[1] == 'check' else prep()
