"""驗證第 1 步判者輸出並落盤。
python ingest_main.py          檢查全部批次，合格的寫進 判讀/<j>/<b>.json，列出不合格或缺的
python ingest_main.py merge    合併成 判讀/labels_<j>.json（鍵 tid#idx），格式錯誤批次記在 判讀/format_errors.json
python ingest_main.py groups   印出 subagent 分組（每組 3 批）
"""
import sys
from common import *

B = load_json(EXP_DIR / '判讀/batches.json')
KEY = load_json(EXP_DIR / '判讀/key.json')
JUDGES = ('j1', 'j2')


def check():
    bad = []
    for j in JUDGES:
        for b, info in B.items():
            src = None
            for cand in (SCRATCH / 'main' / f'out_{j}_{b}_retry.json', SCRATCH / 'main' / f'out_{j}_{b}.json'):
                if cand.exists():
                    src = cand; break
            if src is None:
                bad.append((j, b, '缺檔')); continue
            try:
                obj = load_json(src)
            except Exception as e:
                bad.append((j, b, f'JSON 解析失敗 {e}')); continue
            errs = validate(obj, info['pids'], info['max_event'])
            if errs:
                bad.append((j, b, f'{src.name}: ' + '; '.join(errs[:6])))
            else:
                dump_json(EXP_DIR / '判讀' / j / f'{b}.json', obj)
    for x in bad:
        print(*x)
    print('不合格／缺：', len(bad))


def merge():
    errors = {}
    for j in JUDGES:
        out = {}
        for b in B:
            p = EXP_DIR / '判讀' / j / f'{b}.json'
            if not p.exists():
                errors.setdefault(j, []).append(b); continue
            for pid, v in load_json(p).items():
                k = KEY[pid]
                out[f'{k["tid"]}#{k["idx"]}'] = v
        dump_json(EXP_DIR / f'判讀/labels_{j}.json', out)
        print(j, len(out), '段')
    dump_json(EXP_DIR / '判讀/format_errors.json', errors)
    print('格式錯誤批次：', errors)


def groups():
    names = sorted(B)
    gs = [names[i:i + 3] for i in range(0, len(names), 3)]
    for n, g in enumerate(gs, 1):
        print(n, g)


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else 'check'
    {'check': check, 'merge': merge, 'groups': groups}[arg]()
