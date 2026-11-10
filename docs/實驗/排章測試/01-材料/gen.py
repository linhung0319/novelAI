"""生成稿件。照 novel-desk `.claude/skills/draft/scripts/send.py` 的參數：空資料夾、無工具、無設定、opus、effort high。
用法：python -X utf8 gen.py <prompt 檔> <輸出檔> [<輸出檔> ...]
每個輸出檔一稿，平行送出；已存在的輸出檔不覆蓋。
"""
import concurrent.futures as cf
import json
import pathlib
import subprocess
import sys
import tempfile

SYSTEM = "你是一位小說作者。"   # 同 send.py


def generate(prompt, out, cwd):
    cmd = ["claude", "-p", "--setting-sources", "", "--system-prompt", SYSTEM, "--tools", "",
           "--model", "opus", "--effort", "high", "--output-format", "json",
           "--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"]
    r = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True, cwd=cwd, timeout=1500)
    try:
        d = json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        return f"{out.name} 失敗：{r.stderr.decode('utf-8', 'replace')[:300]}"
    if d.get("is_error"):
        return f"{out.name} 失敗：{d.get('result')}"
    out.write_text(d["result"], encoding="utf-8")
    return f"{out.name} 完成，{len(d['result'])} 字，model={list((d.get('modelUsage') or {}).keys())}"


def main():
    prompt = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    outs = [pathlib.Path(p) for p in sys.argv[2:]]
    for o in outs:
        if o.exists():
            sys.exit(f"{o} 已存在，不覆蓋")
    with tempfile.TemporaryDirectory() as cwd, cf.ThreadPoolExecutor(len(outs)) as ex:
        for line in ex.map(lambda o: generate(prompt, o, cwd), outs):
            print(line)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
