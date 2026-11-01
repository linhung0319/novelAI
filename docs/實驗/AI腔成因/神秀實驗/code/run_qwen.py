"""本機 Qwen 產稿。輸出原樣保存，不做任何修改。"""
import json
import pathlib
import urllib.request

from prepare import ROOT, SOURCES, prompt

OUT = ROOT / "稿件"
OUT.mkdir(exist_ok=True)

for ch in SOURCES:
    for arm in ("I", "IE"):
        for n in (1, 2):
            path = OUT / f"q_{ch}_{arm}_{n}.md"
            if path.exists():
                continue
            payload = {
                "model": "qwen3.5:9b",
                "messages": [{"role": "user", "content": prompt(ch, arm)}],
                "stream": False,
                "think": False,
                "options": {"num_ctx": 16384, "num_predict": 6000},
            }
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=1800) as resp:
                result = json.load(resp)
            text = result["message"]["content"]
            path.write_text(text, encoding="utf-8")
            print(path.name, len(text), result.get("done_reason"), flush=True)
