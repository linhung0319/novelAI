"""組兩組 prompt。用法：python -X utf8 build.py

照 novel-desk `.claude/skills/draft/templates/prompt.md` 的段落順序組；修正段從 novel-desk 的 `templates/修正段.md` 分隔線以下原樣取。
兩組只差「這一章要發生的事」那段（{ch}-事件段-{組}.md）和篇幅那一句（PACE）。
輸出 prompts/{ch}-{組}.md。
"""
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
DESK = pathlib.Path(r'C:\Users\user\Programming\novel-desk\.claude\skills\draft\templates')

CH = {
    'S403': dict(done='第四百零二章', next='第四百零三章', lens='這一章的鏡頭跟著鐘神秀。',
                 prev=REPO / 'examples/神秀之主/第402章_飛劍.txt', cut='晴簫子也不管'),
    'Y17': dict(done='第十六章', next='第十七章', lens='這一章的鏡頭先跟著孟奇，再依序切到齊正言、張遠山、羅勝衣和云霆鋒。',
                prev=REPO / 'examples/一世之尊/卷二/第016章_簡單粗暴.txt', cut='“真定，你在看什么？”'),
}
PACE = {
    ('S403', '甲'): '篇幅大約兩千字。',
    ('Y17', '甲'): '篇幅大約三千一百字。',
    # 乙組照排章表提的範圍，見 {ch}-排章.md
    ('S403', '乙'): None,
    ('Y17', '乙'): None,
}
PACE_FILE = HERE / '乙組篇幅.txt'   # 每行：章代號<TAB>篇幅句


def section(text, name):
    m = re.search(rf'^## {name}\n\n(.*?)(?=^## |\Z)', text, re.S | re.M)
    return m.group(1).strip()


def ending(c):
    t = c['prev'].read_text(encoding='utf-8')
    t = t[t.index(c['cut']):].strip()
    t = re.sub(r'rs$', '', t).strip()          # 浮水印
    return '\n\n'.join(l.strip() for l in t.splitlines() if l.strip())


def fix_block():
    t = (DESK / '修正段.md').read_text(encoding='utf-8')
    return t.split('\n---\n', 1)[1].strip()


def build(ch, group):
    c = CH[ch]
    cp = (HERE / f'{ch}-角色與前情.md').read_text(encoding='utf-8')
    events = (HERE / f'{ch}-事件段-{group}.md').read_text(encoding='utf-8').strip()
    pace = PACE[(ch, group)]
    if pace is None:
        pace = dict(l.split('\t') for l in PACE_FILE.read_text(encoding='utf-8').splitlines() if l.strip())[ch]
    parts = [
        f'我們正在合寫一部長篇小說，目前寫到{c["done"]}。這次請你寫{c["next"]}。下面依序是會出場的人物、到目前為止的故事、這一章要發生的事，最後附上上一章的結尾。',
        '先介紹這一章會出場的人。',
        section(cp, '角色'),
        '故事到目前為止是這樣的：',
        section(cp, '前情'),
        '這一章要發生的事：',
        events,
        c['lens'] + pace,
        fix_block(),
        '以下是上一章的結尾：',
        ending(c),
        f'請從這裡接著寫{c["next"]}，直接開始正文。',
    ]
    return '\n\n'.join(parts) + '\n'


def main():
    out = HERE / 'prompts'
    out.mkdir(exist_ok=True)
    for ch in CH:
        for g in ('甲', '乙'):
            if (HERE / f'{ch}-事件段-{g}.md').exists():
                p = out / f'{ch}-{g}.md'
                p.write_text(build(ch, g), encoding='utf-8')
                print(p.name, len(p.read_text(encoding='utf-8')))


if __name__ == '__main__':
    main()
