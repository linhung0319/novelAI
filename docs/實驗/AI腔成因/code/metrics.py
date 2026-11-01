"""確定性指標。輸入已正規化（繁體、「」）的純文字。"""
import re, statistics

NEG = re.compile(r"(?:不是|並非|不像是?)[^，。！？「」\n]{1,24}[，,、]?(?:而是|是|而)[^，。！？\n]{1,}")
EXPL = re.compile(r"意思是|這就是|那就是|換句話說|其實|原來|也就是說|他知道|他清楚|他明白|他懂|他很清楚|他心裡清楚|我知道|我清楚|我明白|這意味|意味著|代表著|之所以|正因為|說到底|歸根結底|這才是|不是因為")
NUM = re.compile(r"(?:\d+|[一二兩三四五六七八九十百千萬半]+)(?:個|次|下|步|塊|道|天|夜|刻|口|聲|趟|分|度|筆|頁|張|行|字|人|隻|根|圈|層|年|月|尺|寸|息|遍|眼|秒|時辰|炷香|盞|排|條|把)")
NEGG = re.compile(r"沒有|沒|未曾|不曾")
HE_BA = re.compile(r"(?:^|[。！？\n])\s*(?:他|她|我)把")
SENT = re.compile(r"[^。！？!?…\n]+[。！？!?…」]*")
QUOTE = re.compile(r"「[^「」]*」")


def hanzi(t):
    return len(re.findall(r"[一-鿿]", t))


def sentences(t):
    return [s.strip() for s in SENT.findall(t) if hanzi(s) > 0]


def paragraphs(t):
    return [p.strip() for p in t.split("\n") if hanzi(p) > 0]


def compute(t):
    k = max(hanzi(t), 1) / 1000
    ss = sentences(t)
    ps = paragraphs(t)
    lens = [hanzi(s) for s in ss] or [0]
    single = sum(1 for p in ps if len(sentences(p)) == 1)
    close = 0
    for p in ps:
        sp = sentences(p)
        if sp and hanzi(sp[-1]) <= 12 and not sp[-1].endswith("」"):
            close += 1
    plens = [hanzi(p) for p in ps] or [0]
    return {
        "chars": hanzi(t),
        "neg_contrast": len(NEG.findall(t)) / k,
        "explain_marker": len(EXPL.findall(t)) / k,
        "single_para": single / max(len(ps), 1),
        "short_close": close / max(len(ps), 1),
        "numeral": len(NUM.findall(t)) / k,
        "negation_gesture": len(NEGG.findall(t)) / k,
        "dialogue_ratio": sum(hanzi(q) for q in QUOTE.findall(t)) / max(hanzi(t), 1),
        "sent_cv": statistics.pstdev(lens) / max(statistics.mean(lens), 1),
        "sent_mean": statistics.mean(lens),
        "para_mean": statistics.mean(plens),
        "he_ba": len(HE_BA.findall(t)) / k,
    }
