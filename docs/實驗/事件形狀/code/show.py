"""主持者讀稿用：印出切段後的章節（帶段號）。python show.py <檔案路徑> [--title]"""
import sys, pathlib
from common import split_paras, cjk_len

p = pathlib.Path(sys.argv[1])
paras, m = split_paras(p.read_text(encoding='utf-8'), drop_title='--title' in sys.argv)
print(f'# {p.name}  段={len(paras)} 字={sum(cjk_len(x) for x in paras)} 合併={m}')
for i, x in enumerate(paras):
    print(f'{i:03d} {x}')
