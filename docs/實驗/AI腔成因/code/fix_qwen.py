"""Qwen 臂：寫稿與刪句。可重入。用法：python fix_qwen.py <n>"""
import json, sys, time, urllib.request
import fix_lib as L

MODEL = "qwen3.5:9b"
BASE = "http://localhost:11434"


def call(sys_msg, user, seed, num_predict, fmt=None):
    body = {
        "model": MODEL, "stream": False, "think": False, "keep_alive": "30m",
        "messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}],
        "options": {"temperature": 0.8, "top_p": 0.95, "num_predict": num_predict, "seed": seed, "num_ctx": 32768, "repeat_penalty": 1.0},
    }
    if fmt:
        body["format"] = fmt
    req = urllib.request.Request(BASE + "/api/chat", json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3000))


if __name__ == "__main__":
    n = int(sys.argv[1])
    L.OUT.mkdir(exist_ok=True)
    for i in range(1, n + 1):
        for arm in ("B0", "V", "P"):
            for scene in ("S1", "S2"):
                stem = f"q_{scene}_{arm}_{i}"
                out = L.OUT / f"{stem}.md"
                if not out.exists():
                    t = time.time()
                    d = call("你是一位小說作者。", L.writer_prompt(scene, arm), 7000 + 100 * i + sum(map(ord, arm + scene)), 7000)
                    out.write_text(d["message"]["content"].split("</think>")[-1].strip(), encoding="utf-8")
                    (L.OUT / f"{stem}.json").write_text(json.dumps({"prompt_tokens": d.get("prompt_eval_count"), "output_tokens": d.get("eval_count"), "done": d.get("done_reason"), "secs": round(time.time() - t)}), encoding="utf-8")
                    print(out.name, len(out.read_text(encoding="utf-8")), flush=True)
                cut = L.OUT / f"{stem}.cut.json"
                if not cut.exists():
                    text = out.read_text(encoding="utf-8")
                    d = call("你是一位小說編輯。", L.cut_prompt(text), 9000 + i, 1500, "json")
                    try:
                        dele = L.parse_delete(d["message"]["content"])
                    except Exception as e:
                        print("CUT FAIL", stem, e, d["message"]["content"][:200], flush=True)
                        continue
                    cut.write_text(json.dumps({"delete": dele}), encoding="utf-8")
                    new, removed, total = L.apply_cut(text, dele)
                    (L.OUT / f"{stem}.cut.md").write_text(new, encoding="utf-8")
                    print(cut.name, f"{len(removed)}/{total}", flush=True)
