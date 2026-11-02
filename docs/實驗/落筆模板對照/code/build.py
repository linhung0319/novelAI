"""從模板的填好範例組出 A–E 五臂 prompt。每個替換都斷言只命中一次。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXP = ROOT.parent
TPL = EXP / "多模型實測" / "AI 小說章節生成：規則與 Prompt 模板.md"
CORPUS = EXP / "AI腔成因" / "corpus"
ST = ROOT / "stimuli"
ST.mkdir(exist_ok=True)


def base():
    text = TPL.read_text(encoding="utf-8").replace("\r\n", "\n")
    head = "## 填好的範例：可直接測試"
    section = text[text.index(head):]
    start = section.index("```\n") + 4
    return section[start:section.index("\n```", start)]


def sub(s, old, new):
    assert s.count(old) == 1, (s.count(old), old)
    return s.replace(old, new)


def lines(name, a, b):
    ls = (CORPUS / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(ls[a - 1:b])


GUIMI = lines("T9826.txt", 55, 80)
YISHI = lines("T4278.txt", 2, 21)

INTRO_OLD = "以及一些寫法上的想法，最後附上上一章的結尾。"
OLD_WRITING_HEAD = "關於寫法，我的想法是這樣的：\n\n"
OLD_TAIL = "上一章的文字語感是我想要的，請延續它的句子節奏和銜接方式。以下是上一章的結尾：\n"
MIN_WRITING = "這一章的鏡頭跟著林硯。篇幅大約三千字，寧可多一點。\n\n"
SAMPLE_INTRO = "下面這段文字是參考語感用的，內容與這部小說無關，不要借用它的情節或人物：\n\n"
MEANING = [
    "這一章開始前，林硯心裡最放不下的，是他越來越想相信沈舟，而五年前，他也是這樣相信過一個人。\n\n",
    "這一章的情緒重心，是林硯的懷疑一點一點長出來，以及他不願意讓它長出來的那種拉扯。",
]


def build(minimal, strip_meaning, sample):
    s = base()
    if minimal:
        i = s.index(OLD_WRITING_HEAD)
        j = s.index(OLD_TAIL)
        block = MIN_WRITING
        if sample:
            block += SAMPLE_INTRO + sample + "\n\n"
        s = s[:i] + block + "以下是上一章的結尾：\n" + s[j + len(OLD_TAIL):]
        intro = "最後附上參考文字和上一章的結尾。" if sample else "最後附上上一章的結尾。"
        s = sub(s, INTRO_OLD, intro)
    if strip_meaning:
        for m in MEANING:
            s = sub(s, m, "")
    return s


ARMS = {
    "A": build(False, False, None),
    "B": build(True, False, None),
    "C": build(True, False, GUIMI),
    "D": build(True, True, GUIMI),
    "E": build(True, True, YISHI),
}

for k, v in ARMS.items():
    (ST / f"{k}.txt").write_text(v, encoding="utf-8")
    print(k, len(v))
(ST / "範文_詭秘.txt").write_text(GUIMI, encoding="utf-8")
(ST / "範文_一世.txt").write_text(YISHI, encoding="utf-8")
print("guimi", len(GUIMI), "yishi", len(YISHI))
