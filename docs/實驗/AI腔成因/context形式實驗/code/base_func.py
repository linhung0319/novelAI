import json, pathlib, statistics as st, sys, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "code"))
from metrics import hanzi
FUNC = re.compile(r"[了著過便卻還就又也才而但可再都]"); Q = re.compile(r"「[^「」]*」")
J = ROOT/"judgments"; key=json.loads((J/"blind_key.json").read_text(encoding="utf-8"))
g={}
for b,m in key.items():
    t=(J/"blind"/f"{b}.txt").read_text(encoding="utf-8"); n=Q.sub("",t)
    s=[hanzi(x) for x in re.findall(r"[^。！？!?…\n]+[。！？!?…」]*",t) if hanzi(x)]
    if m["group"]!="trial": g.setdefault(m["group"],[]).append((len(FUNC.findall(n))/max(hanzi(n),1)*1000,st.median(s),m.get("src")))
for k,v in g.items():
    print(k,len(v),"func med",round(st.median(x[0] for x in v),1),"range",round(min(x[0] for x in v),1),round(max(x[0] for x in v),1),"sent med",st.median(x[1] for x in v))
    if k!="human_base": print(v)
