import json, os, random, re
base = r'C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Programming-novelAI\2f45c7c4-7743-45cf-9201-2b5c117db62c\scratchpad\tests\v2'
repo = r'C:\Users\user\Programming\novelAI'
cards_dir = os.path.join(repo, 'docs', '新技巧知識庫', 'cards')
S = json.load(open(os.path.join(base, 'situations.json'), encoding='utf-8'))


def excerpt(ref):
    m = re.match(r'(.+?):(\d+)-(\d+)$', ref)
    path, a, b = (m.group(1), int(m.group(2)), int(m.group(3))) if m else (ref.split(':')[0], 1, 60)
    p = os.path.join(repo, path)
    if not os.path.exists(p):
        return f'[{ref}：檔案不存在]'
    lines = open(p, encoding='utf-8').read().split('\n')
    return f'[{ref}]\n' + '\n'.join(lines[a - 1:b][:60])


def skeleton(body):
    """招名、適用、吐；拿掉做、例、限界。"""
    title = body.split('\n')[0]
    fit = re.search(r'^適用：.*$', body, re.M).group(0)
    out = re.search(r'^吐：.*$', body, re.M).group(0)
    return f'{title}\n\n{fit}\n{out}'


random.seed(20261102)
random.shuffle(S)
n = 9
missing = []
for b in range(n):
    items = S[b::n]
    for arm in ('full', 'skel'):
        chunks = []
        for it in items:
            p = os.path.join(cards_dir, it['card'] + '.md')
            if not os.path.exists(p):
                missing.append(it['card']); continue
            body = open(p, encoding='utf-8').read().strip()
            card = body if arm == 'full' else skeleton(body)
            mats = '\n\n'.join(excerpt(r) for r in it.get('material', [])) or '（沒有現成素材，只有作者這句話）'
            chunks.append(f"===== 題：{it['card']} =====\n書：{it['book']}\n作者說：{it['complaint']}\n\n----- 素材 -----\n{mats}\n\n----- 招卡 -----\n{card}\n")
        open(os.path.join(base, f'batch-{b}-{arm}.txt'), 'w', encoding='utf-8').write('\n'.join(chunks))
print('batches', n, 'sizes', [len(S[b::n]) for b in range(n)], 'missing', missing)
print('chars', [os.path.getsize(os.path.join(base, f'batch-{b}-full.txt')) for b in range(n)])
