"""盲評標注：每篇獨立、看不到臂別。引句由程式核對。可重入。

用法：python judge.py <rater_tag> <workers> [model]
"""
import concurrent.futures as cf, json, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"
EMPTY = pathlib.Path(os.environ["TEMP"]) / "claude-clean-exp"
EMPTY.mkdir(exist_ok=True)

RUBRIC = """你是中文小說編輯。下面是一段中文小說文字。你不知道作者是誰。請逐句閱讀後，只做計數式標注，不要評價好壞。

四種標注：

J1 自解釋：敘述者（含第一人稱敘述者的旁白）把「前文已足以讓讀者推知」的含義、動機、意圖或意義明講出來。
  算：行動已經演完，接著一句告訴讀者這代表什麼、他為什麼這麼做、這件事的意義是什麼。
  不算：讀者無法從前文推知的新資訊（世界規則、背景事實、角色當下才產生的新念頭或吐槽、情節推進所需的交代）。不算角色對白。

J2 重述：同一個意思在 5 段以內，換句話又講一遍（含句式上的排比式再講、把前面的意思濃縮成短句金句）。
  標的是「後面重複的那一句」。有意的固定口頭禪（一字不差的複沓）不算。

J3 情節事件：場上真的發生、讓局面或人物處境改變的事件。一個事件用一句話概括。純心理活動、純描述不算。

J4 閒筆：對當前衝突沒有直接功能，純粹讓世界或人物更有活人感的細節、玩笑、小動作或對話。

只輸出 JSON，不要其他文字，格式：
{"J1":["逐字引句",...],"J2":["逐字引句",...],"J3":["事件概括",...],"J4":["逐字引句",...]}
J1、J2、J4 的引句必須從原文逐字複製，一條不超過 40 字，一條一句。沒有就給空陣列。

=== 文字開始 ===
"""


def squeeze(s):
    return re.sub(r"[\s「」『』，。！？、…—:：;；,.!?\"]", "", s)


def judge(job):
    tid, tag, model = job
    out = ROOT / f"judgments_{tag}" / f"{tid}.json"
    if out.exists():
        return f"skip {tid}"
    text = (CORPUS / f"{tid}.txt").read_text(encoding="utf-8")
    cmd = ["claude", "-p", "--setting-sources", "", "--system-prompt", "你是編輯。", "--tools", "", "--model", model,
           "--effort", "medium", "--output-format", "json", "--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"]
    for attempt in range(3):
        r = subprocess.run(cmd, input=(RUBRIC + text + "\n=== 文字結束 ===").encode("utf-8"), capture_output=True, cwd=EMPTY, timeout=900)
        try:
            d = json.loads(r.stdout.decode("utf-8"))
            m = re.search(r"\{.*\}", d["result"], re.S)
            j = json.loads(m.group(0))
            break
        except Exception as e:
            err = str(e)
            j = None
    if j is None:
        return f"FAIL {tid} {err}"
    src = squeeze(text)
    res = {"cost": d.get("total_cost_usd"), "J3": j.get("J3", [])}
    for k in ("J1", "J2", "J4"):
        items = j.get(k, [])
        ok = [q for q in items if squeeze(q) and squeeze(q) in src]
        # 同句去重
        seen, uniq = set(), []
        for q in ok:
            sq = squeeze(q)
            if sq not in seen:
                seen.add(sq)
                uniq.append(q)
        res[k] = uniq
        res[k + "_raw"] = len(items)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"ok {tid} J1={len(res['J1'])}/{res['J1_raw']} J2={len(res['J2'])}/{res['J2_raw']} J3={len(res['J3'])} J4={len(res['J4'])}"


if __name__ == "__main__":
    tag, w = sys.argv[1], int(sys.argv[2])
    model = sys.argv[3] if len(sys.argv) > 3 else "claude-sonnet-5-5"
    jobs = [(p.stem, tag, model) for p in sorted(CORPUS.glob("T*.txt"))]
    with cf.ThreadPoolExecutor(w) as ex:
        for m in ex.map(judge, jobs):
            print(m, flush=True)
