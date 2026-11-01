"""透過 llama-server 跑 Qwen。可重入。用法：python run_qwen.py <base_url> <n>"""
import json, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
ST = ROOT / "stimuli"
OUT = ROOT / "outputs"
WRAP = (ST / "wrapper.txt").read_text(encoding="utf-8")
SYS = "你是一位小說作者。"


def prompt(scene, cell):
    brief = {"QA": "A", "QB": "B", "QC": "A"}[cell]
    b = (ST / f"{scene}_{brief}.txt").read_text(encoding="utf-8")
    if cell == "QC":
        return "以下是本書的資料與寫作規範：\n" + (ST / f"{scene}_large_q.txt").read_text(encoding="utf-8") + "\n\n===== 本章任務 =====\n" + b + "\n" + WRAP
    return b + "\n" + WRAP


def call(base, p, seed):
    body = {
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": p}],
        "temperature": 0.8, "top_p": 0.95, "max_tokens": 7000, "seed": seed, "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(base + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3000))


if __name__ == "__main__":
    base, n = sys.argv[1], int(sys.argv[2])
    for i in range(1, n + 1):
        for cell in ("QA", "QB", "QC"):
            for scene in ("S1", "S2"):
                out = OUT / f"{scene}_{cell}_{i}.md"
                if out.exists():
                    continue
                t = time.time()
                d = call(base, prompt(scene, cell), 1000 * i + sum(map(ord, cell + scene)))
                txt = d["choices"][0]["message"]["content"]
                txt = txt.split("</think>")[-1].strip()
                out.write_text(txt, encoding="utf-8")
                print(out.name, len(txt), d.get("usage"), d["choices"][0].get("finish_reason"), f"{time.time()-t:.0f}s", flush=True)
