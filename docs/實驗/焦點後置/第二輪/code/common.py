"""第二輪共用：路徑、讀段落、批次檔輸出、判讀 JSON 驗證。"""
import json, pathlib, re

R2 = pathlib.Path(__file__).resolve().parent.parent          # 第二輪/
R1 = R2.parent                                               # 焦點後置/
EXP = R1.parent                                              # docs/實驗/
REPO = EXP.parent.parent
SCRATCH = pathlib.Path(r'C:\Users\user\AppData\Local\Temp\claude\b6246c08fb6c85bc\82aaf56e-25cf-47d4-b9d1-9db1c3c6d049\scratchpad\work')

TYPES = {'對白', '混合', '敘述'}
FOCI = {'前', '後舊', '後新', '平', '不判'}
FIELDS = ['type', 'focus', 'foreground', 'cliche', 'inference', 'stress', 'setup', 'events']

WATERMARK = re.compile(r'的?72文學網[A-Za-z0-9./:]*')
CJK = re.compile(r'[\u4e00-\u9fff]')


def cjk_len(s):
    return len(CJK.findall(s))


def paras_from_text(text):
    """以換行切段，去空行；刪浮水印。"""
    out = []
    for line in text.splitlines():
        line = WATERMARK.sub('', line).strip()
        if line:
            out.append(line)
    return out


def write_batch(path, items, events_text=None):
    """items: [{'pid','prev','cur','next'}]"""
    lines = []
    if events_text:
        lines += ['# 事件清單', '', events_text.strip(), '', '---', '']
    else:
        lines += ['# 本批沒有事件清單（events 一律給 []）', '', '---', '']
    for it in items:
        lines += [f'## {it["pid"]}', f'前段：{it["prev"]}', f'本段：{it["cur"]}', f'後段：{it["next"]}', '']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')


def validate(obj, pids, max_event=None):
    """回傳錯誤清單；空清單表示合格。"""
    errs = []
    if not isinstance(obj, dict):
        return ['頂層不是物件']
    missing = set(pids) - set(obj)
    extra = set(obj) - set(pids)
    if missing:
        errs.append(f'缺 {len(missing)} 段：{sorted(missing)[:5]}')
    if extra:
        errs.append(f'多 {len(extra)} 段：{sorted(extra)[:5]}')
    for pid in pids:
        v = obj.get(pid)
        if v is None:
            continue
        if not isinstance(v, dict):
            errs.append(f'{pid} 不是物件'); continue
        for f in FIELDS:
            if f not in v:
                errs.append(f'{pid} 缺欄位 {f}')
        if v.get('type') not in TYPES:
            errs.append(f'{pid} type={v.get("type")!r}')
        if v.get('focus') not in FOCI:
            errs.append(f'{pid} focus={v.get("focus")!r}')
        for f in ('foreground', 'cliche'):
            x = v.get(f)
            if not isinstance(x, list) or not all(isinstance(s, str) for s in x):
                errs.append(f'{pid} {f} 不是字串陣列')
        inf = v.get('inference')
        if not isinstance(inf, list) or not all(isinstance(d, dict) and 'text' in d for d in inf):
            errs.append(f'{pid} inference 格式錯')
        for f in ('stress', 'setup'):
            if not isinstance(v.get(f), bool):
                errs.append(f'{pid} {f} 不是布林')
        ev = v.get('events')
        if not isinstance(ev, list) or not all(isinstance(e, int) and not isinstance(e, bool) for e in ev):
            errs.append(f'{pid} events 不是整數陣列')
        elif max_event is not None and any(e < 1 or e > max_event for e in ev):
            errs.append(f'{pid} events 超出範圍 {ev}')
        elif max_event is None and ev:
            errs.append(f'{pid} 沒有清單卻填了 events {ev}')
    return errs


def load_json(p):
    return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))


def dump_json(p, obj):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')
