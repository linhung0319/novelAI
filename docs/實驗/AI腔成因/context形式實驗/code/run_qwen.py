"""Qwen 臂。可重入。用法：python run_qwen.py <n>"""
import json, sys, time, urllib.request
from lib import OUT, SYS, jobs, prompt

BASE = "http://localhost:11434"
MODEL = "qwen3.5:9b"
OPT = {"temperature": 0.8, "top_p": 0.95, "top_k": 20, "repeat_penalty": 1.0, "presence_penalty": 0, "num_predict": 7000, "num_ctx": 32768}


def call(p, seed):
    body = {"model": MODEL, "stream": False, "think": False, "keep_alive": "30m",
            "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": p}],
            "options": {**OPT, "seed": seed}}
    req = urllib.request.Request(BASE + "/api/chat", json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3000))


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for s, a, i in jobs(int(sys.argv[1])):
        out = OUT / f"q_{s}_{a}_{i}.md"
        if out.exists():
            continue
        t = time.time()
        seed = 7000 * i + sum(map(ord, s + a))
        d = call(prompt(s, a), seed)
        txt = d["message"]["content"].split("</think>")[-1].strip()
        out.write_text(txt, encoding="utf-8")
        m = {"model": MODEL, "seed": seed, "options": OPT, "prompt_tokens": d.get("prompt_eval_count"), "output_tokens": d.get("eval_count"), "done": d.get("done_reason"), "secs": round(time.time() - t)}
        out.with_suffix(".json").write_text(json.dumps(m), encoding="utf-8")
        print(out.name, len(txt), m["prompt_tokens"], m["output_tokens"], m["done"], m["secs"], flush=True)
