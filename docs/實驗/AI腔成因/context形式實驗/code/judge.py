"""逐句標注。一次看一篇，代號盲評，引句由程式核對。可重入。
用法：uv run --no-project --with opencc-python-reimplemented judge.py prepare
      python judge.py run <workers>
"""
import concurrent.futures as cf, json, os, pathlib, random, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
J = ROOT / "judgments"
PACK = J / "blind"
KEY = J / "blind_key.json"
CORPUS = ROOT.parent / "corpus"
CKEY = ROOT.parent / "corpus_key.json"

PROMPT = """你是資深中文小說編輯。下面是一段小說，請逐句讀，找出三類問題，每條都要逐字引用原文。

1. cut（斷裂）：相鄰兩句之間，讀者要自己補「誰、在哪、怎麼到這裡、視線落到哪」才接得上。刻意的場景切換、笑點省略不算。引用這兩句。
2. force（用力過猛）：動作或措辭被升級、搭配不自然，一般人寫會用平常的字；或硬拗成短促的對比句。引用該句。
3. tele（電報感）：該有的虛詞、主語、銜接被刪掉，讀起來像電報或筆記。引用該句。

有就標，沒有就不標，寧缺勿濫。每條引文必須是原文裡連續的文字，不要改字，不要加省略號。

另給 smooth（0–10）：讀者能不能在腦裡連續跟著畫面。10 是完全順，0 是不知道在寫什麼。

只輸出 JSON，不要其他文字：
{"cut":["引文",...],"force":["引文",...],"tele":["引文",...],"smooth":數字}

===== 小說 =====
"""


def prepare():
    from opencc import OpenCC
    cc = OpenCC("s2tw")
    PACK.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(OUT.glob("[cq]_S*_*_*.md")):
        t = cc.convert(p.read_text(encoding="utf-8")).replace("“", "「").replace("”", "」")
        items.append(({"group": "trial", "src": p.stem}, t))
    k = json.loads(CKEY.read_text(encoding="utf-8"))
    for bid, v in k.items():
        if v["group"] != "trial":
            items.append(({"group": v["group"], "src": v.get("src")}, (CORPUS / f"{bid}.txt").read_text(encoding="utf-8")))
    rnd = random.Random(20261101)
    rnd.shuffle(items)
    key = {}
    for i, (meta, t) in enumerate(items):
        bid = f"B{i:03d}"
        (PACK / f"{bid}.txt").write_text(t, encoding="utf-8")
        key[bid] = meta
    KEY.write_text(json.dumps(key, ensure_ascii=False, indent=0), encoding="utf-8")
    print(len(items), {g: sum(1 for m in key.values() if m["group"] == g) for g in {m["group"] for m in key.values()}})


EMPTY = pathlib.Path(os.environ.get("TEMP", ".")) / "claude-clean-exp"
CMD = ["claude", "-p", "--setting-sources", "", "--system-prompt", "你是資深中文小說編輯。", "--tools", "", "--model", "claude-sonnet-5-5",
       "--output-format", "json", "--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"]


def one(p):
    out = J / f"{p.stem}.json"
    if out.exists():
        return None
    r = subprocess.run(CMD, input=(PROMPT + p.read_text(encoding="utf-8")).encode("utf-8"), capture_output=True, cwd=EMPTY, timeout=900)
    d = json.loads(r.stdout.decode("utf-8"))
    txt = d["result"]
    m = re.search(r"\{.*\}", txt, re.S)
    res = json.loads(m.group(0))
    res["_cost"] = d.get("total_cost_usd")
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return f"{p.stem} {res.get('smooth')} {d.get('total_cost_usd')}"


def run(w):
    EMPTY.mkdir(exist_ok=True)
    files = sorted(PACK.glob("B*.txt"))
    with cf.ThreadPoolExecutor(w) as ex:
        futs = {ex.submit(one, p): p for p in files}
        for f in cf.as_completed(futs):
            try:
                m = f.result()
                if m:
                    print(m, flush=True)
            except Exception as e:
                print("FAIL", futs[f].stem, repr(e)[:200], flush=True)


if __name__ == "__main__":
    prepare() if sys.argv[1] == "prepare" else run(int(sys.argv[2]))
