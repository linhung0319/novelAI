"""洩漏檢查：事件清單和原文之間長度 ≥8 的共同片段（只比漢字與數字，去標點）。
python check_leak.py        檢查全部清單，結果寫 事件清單/leak_report.json
"""
import re
from common import *

SEL = load_json(EXP_DIR / 'code/selection.json')
MINLEN = 8
KEEP = re.compile(r'[一-鿿0-9A-Za-z]')


def norm(s):
    return ''.join(KEEP.findall(s))


def common_substrings(a, b, n):
    """a 裡長度 ≥n 且出現在 b 的最長片段（不重疊、取最大）。"""
    out, i = [], 0
    while i <= len(a) - n:
        if a[i:i + n] in b:
            j = i + n
            while j < len(a) and a[i:j + 1] in b:
                j += 1
            out.append(a[i:j]); i = j
        else:
            i += 1
    return out


def sources():
    for k, v in SEL['paired'].items():
        yield k, v[1]
    for k, v in SEL['human'].items():
        num = re.search(r'第(\d+)章', v[1]).group(1)
        yield f'{k}{int(num)}', v[1]
    for k, v in SEL['calib'].items():
        yield k, v[1]


def main():
    rep = {}
    for key, rel in sources():
        orig = norm((EXAMPLES / rel).read_text(encoding='utf-8'))
        lines = [l for l in (EXP_DIR / '事件清單' / f'{key}.md').read_text(encoding='utf-8').splitlines() if l.strip()]
        hits = {}
        for l in lines:
            m = re.match(r'(\d+)\.\s*(.*)', l)
            cs = common_substrings(norm(m.group(2)), orig, MINLEN)
            if cs:
                hits[m.group(1)] = cs
        rep[key] = hits
        print(key, hits if hits else '無')
    dump_json(EXP_DIR / '事件清單/leak_report.json', rep)


if __name__ == '__main__':
    main()
