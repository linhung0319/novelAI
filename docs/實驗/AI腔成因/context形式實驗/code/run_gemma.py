"""Gemma 4 12B 對照，只跑 M 臂，參數同 run_qwen.py。可重入。用法：python run_gemma.py <n>"""
import json, sys, time, urllib.request
from lib import OUT, SYS, prompt
from run_qwen import BASE, OPT

MODEL = "hf.co/unsloth/gemma-4-12b-it-GGUF:Q4_K_M"


def call(p, seed):
    body = {"model": MODEL, "stream": False, "keep_alive": "10m",
            "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": p}],
            "options": {**OPT, "seed": seed}}
    req = urllib.request.Request(BASE + "/api/chat", json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3000))


if __name__ == "__main__":
    for i in range(1, int(sys.argv[1]) + 1):
        for s in ("S2", "S1"):
            out = OUT / f"g_{s}_M_{i}.md"
            if out.exists():
                continue
            t = time.time()
            seed = 7000 * i + sum(map(ord, s + "M"))
            d = call(prompt(s, "M"), seed)
            txt = d["message"]["content"].strip()
            out.write_text(txt, encoding="utf-8")
            m = {"model": MODEL, "seed": seed, "options": OPT, "prompt_tokens": d.get("prompt_eval_count"), "output_tokens": d.get("eval_count"), "done": d.get("done_reason"), "secs": round(time.time() - t), "tok_s": round(d.get("eval_count", 0) / max(d.get("eval_duration", 1) / 1e9, 1e-9), 1)}
            out.with_suffix(".json").write_text(json.dumps(m), encoding="utf-8")
            print(out.name, len(txt), m["prompt_tokens"], m["output_tokens"], m["done"], m["secs"], m["tok_s"], flush=True)
