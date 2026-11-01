"""透過 ollama 跑本地模型（取代 run_qwen.py 的 llama-server 路徑）。可重入。

用法：python run_ollama.py <model> <n> [--smoke]

明確設定的參數，因為 ollama 的預設會污染實驗：
- num_ctx：預設值會靜默截斷長 prompt，QC 臂就等於沒有長 context。每篇都記 prompt_eval_count 供核對。
- repeat_penalty=1.0：預設的重複懲罰會直接壓低「重述」這項被量的東西。
- think=False：只比較正文，不讓推理佔掉輸出額度。
"""
import json, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
ST = ROOT / "stimuli"
OUT = ROOT / "outputs"
WRAP = (ST / "wrapper.txt").read_text(encoding="utf-8")
SYS = "你是一位小說作者。"
BASE = "http://localhost:11434"
NUM_CTX = 32768


def prompt(scene, cell):
    brief = {"QA": "A", "QB": "B", "QC": "A"}[cell]
    b = (ST / f"{scene}_{brief}.txt").read_text(encoding="utf-8")
    if cell == "QC":
        large = (ST / f"{scene}_large_q.txt").read_text(encoding="utf-8")
        return "以下是本書的資料與寫作規範：\n" + large + "\n\n===== 本章任務 =====\n" + b + "\n" + WRAP
    return b + "\n" + WRAP


def call(model, p, seed, num_predict=7000):
    body = {
        "model": model,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": p}],
        "options": {"temperature": 0.8, "top_p": 0.95, "num_predict": num_predict, "seed": seed, "num_ctx": NUM_CTX, "repeat_penalty": 1.0},
    }
    req = urllib.request.Request(BASE + "/api/chat", json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3000))


if __name__ == "__main__":
    model, n = sys.argv[1], int(sys.argv[2])
    if "--smoke" in sys.argv:
        d = call(model, prompt("S2", "QC"), 1, num_predict=200)
        print("prompt_tokens", d.get("prompt_eval_count"), "output_tokens", d.get("eval_count"), "done", d.get("done_reason"))
        print("tok/s", round(d["eval_count"] / (d["eval_duration"] / 1e9), 1))
        print(d["message"]["content"][:300])
        ps = json.load(urllib.request.urlopen(BASE + "/api/ps"))
        print(json.dumps(ps, ensure_ascii=False)[:500])
        sys.exit()
    for i in range(1, n + 1):
        for cell in ("QA", "QB", "QC"):
            for scene in ("S1", "S2"):
                out = OUT / f"{scene}_{cell}_{i}.md"
                if out.exists():
                    continue
                t = time.time()
                d = call(model, prompt(scene, cell), 1000 * i + sum(map(ord, cell + scene)))
                txt = d["message"]["content"].split("</think>")[-1].strip()
                out.write_text(txt, encoding="utf-8")
                meta = {"model": model, "prompt_tokens": d.get("prompt_eval_count"), "output_tokens": d.get("eval_count"), "done": d.get("done_reason"), "secs": round(time.time() - t)}
                out.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
                print(out.name, len(txt), meta, flush=True)
