"""洩漏檢查：每份 prompt 和本章原文之間 ≥8 字的共同片段。沿用 docs/實驗/事件形狀/code/check_leak.py 的 norm 和 common_substrings。
用法：python -X utf8 check_prompts.py   結果寫 leak_report.json
"""
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / '事件形狀' / 'code'))
from check_leak import norm, common_substrings, MINLEN, EXAMPLES

ORIG = {'S403': '神秀之主/第403章_捏死了.txt', 'Y17': '一世之尊/卷二/第017章_擊殺.txt'}
rep = {}
for p in sorted((HERE / 'prompts').glob('*.md')):
    ch = p.stem.split('-')[0]
    orig = norm((EXAMPLES / ORIG[ch]).read_text(encoding='utf-8'))
    hits = common_substrings(norm(p.read_text(encoding='utf-8')), orig, MINLEN)
    rep[p.name] = hits
    print(p.name, hits if hits else '無')
(HERE / 'leak_report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
