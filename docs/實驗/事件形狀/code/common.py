"""事件形狀實驗共用：路徑、切段、讀章、JSON 存取。"""
import json, pathlib, re

EXP_DIR = pathlib.Path(__file__).resolve().parent.parent      # docs/實驗/事件形狀/
REPO = EXP_DIR.parent.parent.parent
EXAMPLES = REPO / 'examples'
SCRATCH = pathlib.Path(r'C:\Users\user\AppData\Local\Temp\claude\b6246c08fb6c85bc\b3188b15-2a22-48ef-af12-9ed772a4b7d5\scratchpad\w')

CJK = re.compile(r'[\u4e00-\u9fff]')
WATERMARK = re.compile(
    r'的?72文學網[A-Za-z0-9./:]*'
    r'|天才一秒鐘就記住：\(72文學'
    r'|看書領紅包關注公\.\.眾號書友大本營，看書抽最高888現金紅包！'
    r'|看最新最全'
    r'|;長;風;文學'
    r'|<－》'
    r'|rs$'
)
NOTE_LINE = re.compile(r'^(ps|PS|ＰＳ)\d*[：:]')   # 作者附言整行刪除
END = tuple('。！？!?…」』”’）)—：:~～')


def cjk_len(s):
    return len(CJK.findall(s))


def split_paras(text, drop_title=False):
    """以換行切段、去空行、去浮水印；段尾不是句末標點時和下一段合併。回傳 (段落, 合併次數)。"""
    lines = []
    for line in text.splitlines():
        line = WATERMARK.sub('', line.strip()).strip()
        if line and not NOTE_LINE.match(line):
            lines.append(line)
    if drop_title and lines:
        lines = lines[1:]
    out, buf, merges = [], '', 0
    for p in lines:
        buf = buf + p if buf else p
        if buf.endswith(END):
            out.append(buf); buf = ''
        else:
            merges += 1
    if buf:
        out.append(buf)
    return out, merges


def chapter_files(book):
    """回傳 [(章代號, 路徑)]，依檔名順序。一世之尊分卷。"""
    root = EXAMPLES / book
    if book == '一世之尊':
        res = []
        for vol in ('卷二', '卷三'):
            for p in sorted((root / vol).glob('*.txt')):
                res.append((f'{vol}/{p.stem}', p))
        return res
    return [(p.stem, p) for p in sorted(root.glob('*.txt'))]


def load_json(p):
    return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))


def dump_json(p, obj):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')


FUNCS = ['預告', '動作', '對白', '結果', '反應', '評語', '內心', '背景', '描寫', '音效']
FEEL = {
    'speed': ['快', '中', '慢', '停'],
    'attention': ['盯住', '一般', '可略'],
    'tension': ['升', '持平', '降', '懸著'],
    'involve': ['自己看到', '被告知'],
    'load': ['省力', '一般', '費力'],
}
FIELDS = ['event', 'func'] + list(FEEL)


def write_batch(path, items, events_text):
    """items: [{'pid','prev','cur','next'}]"""
    lines = ['# 事件清單', '', events_text.strip(), '', '---', '']
    for it in items:
        lines += [f'## {it["pid"]}', '前段：' + (it['prev'] or '（無，這是第一段）'), '本段：' + it['cur'],
                  '後段：' + (it['next'] or '（無，這是最後一段）'), '']
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')


def validate(obj, pids, max_event):
    errs = []
    if not isinstance(obj, dict):
        return ['頂層不是物件']
    miss, extra = set(pids) - set(obj), set(obj) - set(pids)
    if miss:
        errs.append(f'缺 {len(miss)} 段 {sorted(miss)[:4]}')
    if extra:
        errs.append(f'多 {len(extra)} 段 {sorted(extra)[:4]}')
    for pid in pids:
        v = obj.get(pid)
        if v is None:
            continue
        if not isinstance(v, dict):
            errs.append(f'{pid} 不是物件'); continue
        e = v.get('event')
        if not isinstance(e, int) or isinstance(e, bool) or not 0 <= e <= max_event:
            errs.append(f'{pid} event={e!r}')
        if v.get('func') not in FUNCS:
            errs.append(f'{pid} func={v.get("func")!r}')
        for f, vals in FEEL.items():
            if v.get(f) not in vals:
                errs.append(f'{pid} {f}={v.get(f)!r}')
    return errs


def items_of(tid, paras):
    return [{'tid': tid, 'idx': i, 'prev': paras[i - 1] if i else '', 'cur': p,
             'next': paras[i + 1] if i + 1 < len(paras) else ''} for i, p in enumerate(paras)]


def event_text(key):
    t = (EXP_DIR / '事件清單' / f'{key}.md').read_text(encoding='utf-8')
    lines = [l.strip() for l in t.splitlines() if re.match(r'\d+\.', l.strip())]
    return '\n'.join(lines), len(lines)


def kappa(a, b):
    """未加權 Cohen kappa（名目）。"""
    n = len(a)
    cats = sorted(set(a) | set(b), key=str)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')
