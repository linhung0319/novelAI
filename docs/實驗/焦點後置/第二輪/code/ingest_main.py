"""驗證第 1 步判者輸出並落盤。
python ingest_main.py            檢查全部批次，合格的寫進 判讀/<j>/<b>.json，列出不合格或缺的批次
python ingest_main.py merge      合併成 判讀/labels_<j>.json（鍵 tid#idx），格式錯誤批次記在 判讀/format_errors.json
"""
import sys
from common import *

B = load_json(R2 / '判讀/batches.json')
KEY = load_json(R2 / '判讀/key.json')
JUDGES = ('j1', 'j2')


def check():
    bad = []
    for j in JUDGES:
        for b, info in B.items():
            dst = R2 / '判讀' / j / f'{b}.json'
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
                dump_json(dst, obj)
    for x in bad:
        print(*x)
    print('不合格／缺：', len(bad))
    return bad


def merge():
    errors = {}
    for j in JUDGES:
        out = {}
        for b in B:
            p = R2 / '判讀' / j / f'{b}.json'
            if not p.exists():
                errors.setdefault(j, []).append(b); continue
            for pid, v in load_json(p).items():
                k = KEY[pid]
                out[f'{k["tid"]}#{k["idx"]}'] = v
        dump_json(R2 / f'判讀/labels_{j}.json', out)
        print(j, len(out), '段')
    dump_json(R2 / '判讀/format_errors.json', errors)
    print('格式錯誤批次：', errors)


if __name__ == '__main__':
    merge() if len(sys.argv) > 1 and sys.argv[1] == 'merge' else check()
