"""修復實驗共用：組 prompt、切句、套用刪句。"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
ST = ROOT / "stimuli"
FIX = ST / "fix"
OUT = ROOT / "outputs_fix"
EX = ROOT.parents[2] / "examples"
WRAP = "請寫出這一章的小說正文，約 3000 字，繁體中文。只輸出小說正文本身，不要任何說明、標題或後記。"

SAMPLE_SRC = {
    "S1": (EX / "詭秘之主" / "第003章_梅麗莎（第一更求推薦票）.txt", "確定了計劃", "砸出砰的一聲。"),
    "S2": (EX / "我有一個修仙世界" / "第796章_真寒.txt", "陳莫白安排了家里", "附上了一個自己施展劍意的視頻。"),
}
FIXES = {"家里": "家裡", "相當于": "相當於", "過于": "過於", "這里": "這裡", "那里": "那裡", "哪里": "哪裡", "之后": "之後", "后面": "後面", "最后": "最後", "關系": "關係", "由于": "由於", "對于": "對於", "屬于": "屬於", "在于": "在於", "于元陽": "於元陽", "之上": "之上", "“": "「", "”": "」"}

CARD = {
    "S1": "奧倫十六歲，窮，記仇，手上忙的時候嘴也不閒，老在心裡跟自己和死去的父親抬槓。數字記得牢，算錯了會罵自己。整章的敘述緊貼他，像他事後跟一個信得過的人講這三天的事：想到哪講到哪，該交代的隨手交代，氣了就罵，得意了也藏不住。旁人跟他說話，他多半會回嘴。",
    "S2": "孟奇二十出頭，現代大學生，嘴快，愛吐槽，怕死又好面子，常常話出口了才後悔。整章的敘述緊貼他，像他當晚跟最熟的朋友講今天的遭遇：想到哪講到哪，該交代的隨手交代，覺得好笑就笑，被嚇到就叫出來。寺裡這些人也都有話就當面說，會頂嘴，也會講廢話。",
}

CUT_PROMPT = """下面是一章小說草稿，每句前有編號。你是編輯，只能整句刪除，不能改字。

挑出刪掉之後讀者不會少知道任何事的句子：前面已經演出來、又講一遍意思的句子；替讀者下結論的句子；作者探頭出來總結的句子。

故事事件、對白、笑點和單純交代事情的句子都留著。不確定就留。

只輸出 JSON：{"delete":[編號,...]}

"""


def sample(scene):
    path, start, end = SAMPLE_SRC[scene]
    text = path.read_text(encoding="utf-8")
    text = text[text.index(start):]
    text = text[:text.index(end) + len(end)]
    for a, b in FIXES.items():
        text = text.replace(a, b)
    return text


def writer_prompt(scene, arm):
    brief = (ST / f"{scene}_A.txt").read_text(encoding="utf-8").strip()
    if arm == "B0":
        return f"{brief}\n\n{WRAP}"
    if arm == "V":
        return f"下面是另一本書的片段，和這一章的情節無關。只學它的敘述聲音：怎麼交代事情、主角怎麼在心裡說話。不要用它的人名、設定和句子。\n\n<片段>\n{sample(scene)}\n</片段>\n\n{brief}\n\n{WRAP}"
    if arm == "P":
        return f"{brief}\n\n這一章的敘述者：{CARD[scene]}\n\n{WRAP}"
    raise ValueError(arm)


def split_sentences(text):
    """回傳 [(段號, 句子)]。引號內不切，整段對白算一句。"""
    out = []
    for pi, para in enumerate(p.strip() for p in re.split(r"\n+", text) if p.strip()):
        buf, depth = "", 0
        chars = list(para)
        for i, c in enumerate(chars):
            buf += c
            if c in "「『":
                depth += 1
            elif c in "」』":
                depth = max(0, depth - 1)
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if depth == 0 and c in "。！？…」" and nxt not in "。！？…」』，、；：":
                if c == "」" and nxt and nxt not in "「":
                    continue
                out.append((pi, buf))
                buf = ""
        if buf:
            out.append((pi, buf))
    return out


def numbered(text):
    return "\n".join(f"[{i}] {s}" for i, (_, s) in enumerate(split_sentences(text), 1))


def cut_prompt(text):
    return CUT_PROMPT + numbered(text)


def apply_cut(text, delete):
    sents = split_sentences(text)
    dele = {int(d) for d in delete}
    paras, removed = {}, []
    for i, (p, s) in enumerate(sents, 1):
        if i in dele:
            removed.append(s)
        else:
            paras[p] = paras.get(p, "") + s
    return "\n\n".join(paras[k] for k in sorted(paras)), removed, len(sents)


def parse_delete(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0))["delete"]
