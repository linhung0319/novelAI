"""跑 Claude 臂。可重入：已存在的輸出會跳過。"""
import json,pathlib,subprocess,concurrent.futures as cf,sys,time,os
ROOT=pathlib.Path(__file__).resolve().parents[1]; ST=ROOT/"stimuli"; OUT=ROOT/"outputs"; OUT.mkdir(exist_ok=True)
REPO=ROOT.parents[2]
EMPTY=pathlib.Path(os.environ["TEMP"])/"claude-clean-exp"; EMPTY.mkdir(exist_ok=True)
MODEL="claude-opus-5-5"
WRAP=(ST/"wrapper.txt").read_text(encoding="utf-8")
SYS="你是一位小說作者。"
def prompt(scene,cell):
    brief={"A":"A","B":"B","C":"A","D":"B","H":"A"}[cell]
    b=(ST/f"{scene}_{brief}.txt").read_text(encoding="utf-8")
    if cell in "CD":
        return "以下是本書的資料與寫作規範：\n"+(ST/f"{scene}_large.txt").read_text(encoding="utf-8")+"\n\n===== 本章任務 =====\n"+b+"\n"+WRAP
    return b+"\n"+WRAP
def run(job):
    scene,cell,i=job
    out=OUT/f"{scene}_{cell}_{i}.md"; meta=OUT/f"{scene}_{cell}_{i}.json"
    if out.exists(): return f"skip {out.name}"
    if cell=="H":
        cmd=["claude","-p","--model",MODEL,"--effort","high","--output-format","json","--no-session-persistence","--disallowedTools","Write,Edit,NotebookEdit,Bash,PowerShell"]
        cwd=REPO
    else:
        cmd=["claude","-p","--setting-sources","","--system-prompt",SYS,"--tools","","--model",MODEL,"--effort","high","--output-format","json","--no-session-persistence","--strict-mcp-config","--disable-slash-commands"]
        cwd=EMPTY
    exe=subprocess.list2cmdline(cmd) if False else None
    t=time.time()
    r=subprocess.run(cmd,input=prompt(scene,cell).encode("utf-8"),capture_output=True,cwd=cwd,timeout=1500,shell=False)
    try: d=json.loads(r.stdout.decode("utf-8"))
    except Exception: return f"FAIL {out.name} rc={r.returncode} {r.stdout[:300]!r} {r.stderr[:300]!r}"
    if d.get("is_error"): return f"ERR {out.name} {d.get('result')}"
    out.write_text(d["result"],encoding="utf-8")
    u=d.get("usage",{})
    meta.write_text(json.dumps({"cost":d.get("total_cost_usd"),"in":u.get("input_tokens",0)+u.get("cache_creation_input_tokens",0)+u.get("cache_read_input_tokens",0),"out":u.get("output_tokens"),"sec":time.time()-t,"session_cwd":str(cwd)}),encoding="utf-8")
    return f"ok {out.name} chars={len(d['result'])} in={u.get('input_tokens',0)+u.get('cache_creation_input_tokens',0)+u.get('cache_read_input_tokens',0)} cost={d.get('total_cost_usd')} {time.time()-t:.0f}s"
if __name__=="__main__":
    cells=sys.argv[1]; n=int(sys.argv[2]); w=int(sys.argv[3])
    jobs=[(s,c,i) for i in range(1,n+1) for c in cells for s in ("S1","S2")]
    with cf.ThreadPoolExecutor(w) as ex:
        for m in ex.map(run,jobs): print(m,flush=True)
