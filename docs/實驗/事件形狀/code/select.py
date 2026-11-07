"""語料選定：配對組章節（主持者讀稿後選定）、校準章、人類範圍組（seed 抽）。
python select.py   印出並寫 code/selection.json
"""
import random
from common import *

SEED = 20261107

# 配對組：key -> (書, 本章路徑, 前一章路徑)
PAIRED = {
    'G13': ('詭秘之主', '詭秘之主/第013章_值夜者.txt', '詭秘之主/第012章_再次上門.txt'),
    'G32': ('詭秘之主', '詭秘之主/第032章_靈視.txt', '詭秘之主/第031章_魔藥.txt'),
    'Y17': ('一世之尊', '一世之尊/卷二/第017章_擊殺.txt', '一世之尊/卷二/第016章_簡單粗暴.txt'),
    'Y20': ('一世之尊', '一世之尊/卷二/第020章_提醒.txt', '一世之尊/卷二/第019章_四大封印之兵.txt'),
    'S403': ('神秀之主', '神秀之主/第403章_捏死了.txt', '神秀之主/第402章_飛劍.txt'),
    'S424': ('神秀之主', '神秀之主/第424章_翻臉.txt', '神秀之主/第423章_講道.txt'),
}
# 校準章：不是實驗章，也不是實驗章的前一章
CALIB = {
    'cG16': ('詭秘之主', '詭秘之主/第016章_狗拿耗子.txt'),
    'cY336': ('一世之尊', '一世之尊/卷三/第036章_弄巧成拙.txt'),
    'cS395': ('神秀之主', '神秀之主/第395章_官話.txt'),
}


def human_range():
    rng = random.Random(SEED)
    out = {}
    for key, book in (('H紅', '從紅月開始'), ('H極', '極道天魔')):
        fs = sorted((EXAMPLES / book).glob('*.txt'))
        cands = [f for f in fs if int(f.name[1:4]) >= 11]
        pick = rng.choice(cands)
        i = fs.index(pick)
        out[key] = (book, f'{book}/{pick.name}', f'{book}/{fs[i - 1].name}')
    return out


if __name__ == '__main__':
    sel = {'paired': PAIRED, 'calib': CALIB, 'human': human_range(), 'seed': SEED}
    dump_json(EXP_DIR / 'code/selection.json', sel)
    for k, v in sel.items():
        print(k, v)
