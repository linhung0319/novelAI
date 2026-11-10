"""字數核對：每稿總字數、各場景字數、幾個指定節拍的字數（不含空白）。行號是稿件檔的行號，由主持者讀稿後標出。
用法：python -X utf8 count.py > 字數.md
"""
import json, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
D = HERE.parent / '02-稿件'
M = json.loads((HERE / '代號對照.json').read_text(encoding='utf-8'))
N = {'S403': 2000, 'Y17': 3100}
SCENES = {  # 場景起訖行（含）
 'CB27': [(1,15),(17,35),(37,43),(45,51)], 'MT53': [(1,9),(11,27),(29,35),(37,45)],
 'WB85': [(1,15),(17,25),(27,31),(33,37)], 'JG64': [(1,15),(17,25),(27,31),(33,37)],
 'PC21': [(1,25),(27,33),(35,43),(45,55)], 'XZ93': [(1,19),(21,25),(27,33),(35,39)],
 'DS24': [(1,15),(17,21),(23,27),(29,33)], 'BD13': [(1,15),(17,23),(25,35),(37,45)],
}
BEATS = {
 'S403': {'請老祖到笑容停住（高點前延後＋高點）': {'CB27':(17,23),'MT53':(11,17),'WB85':(17,19),'JG64':(17,19)},
          '金丹比較那一段': {'CB27':(25,25),'MT53':(19,19),'WB85':(21,21),'JG64':(21,21)}},
 'Y17': {'唐的回憶（乙組標一句帶過）': {'PC21':(7,7),'XZ93':(7,7),'DS24':(7,7),'BD13':(7,7)},
         '齊正言盤算功法（乙組標一句帶過）': {'PC21':(33,33),'XZ93':(25,25),'DS24':(21,21),'BD13':(23,23)}},
}
def n(lines, a, b): return len(re.sub(r'\s', '', ''.join(lines[a-1:b])))
out = ['# 字數核對', '', '不含空白。只核對事實，不評好壞。', '']
for ch in N:
    out += [f'## {ch}（N={N[ch]}）', '', '| 代號 | 組 | 總字數 | 對 N | 場景1 | 場景2 | 場景3 | 場景4 |', '|---|---|---|---|---|---|---|---|']
    codes = sorted([c for c, v in M.items() if v['章'] == ch], key=lambda c: (M[c]['組'], c))
    for c in codes:
        L = (D / f'{c}.md').read_text(encoding='utf-8').splitlines()
        tot = n(L, 1, len(L))
        out.append(f"| {c} | {M[c]['組']} | {tot} | {tot/N[ch]-1:+.0%} | " + ' | '.join(str(n(L, a, b)) for a, b in SCENES[c]) + ' |')
    out += ['', '| 節拍 | ' + ' | '.join(f"{c}（{M[c]['組']}）" for c in codes) + ' |', '|---|' + '---|' * len(codes)]
    for name, r in BEATS[ch].items():
        row = []
        for c in codes:
            L = (D / f'{c}.md').read_text(encoding='utf-8').splitlines(); row.append(str(n(L, *r[c])))
        out.append(f'| {name} | ' + ' | '.join(row) + ' |')
    out.append('')
print('\n'.join(out))
