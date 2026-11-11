"""每張卡開 2 個全新的 claude -p，只給交接文件規定的那段話，回答原樣存到 輸出/。

從一個空資料夾啟動，所以它看不到 novelAI 或 novel-desk 的 CLAUDE.md 和記憶。

用法：python 跑測試.py 改前            （跑全部）
      python 跑測試.py 改後 卡名 卡名…  （只跑指定的卡）
"""
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "輸出"
CARDS = Path(r"C:\Users\user\Programming\novel-desk\knowledge\cards")
DRAFT = Path(r"C:\Users\user\Programming\novelAI\docs\實驗\排章測試\02-稿件\CB27.md")

# (卡名, 是不是正文類)
PICKS = [
    ("是不是多說了", True),
    ("換個管道", True),
    ("情緒換成行為", True),
    ("設定怎麼帶出來", False),
    ("故事設定健檢", False),
    ("阻礙不夠力", False),
    ("旁帶", True),
    ("重音放哪", True),
    ("動力檢查", False),
    ("抽掉就垮", False),
    # 以下 7 張是清單「不確定」區，只有改後
    ("一件東西頂一段描寫", True),
    ("該演還是帶過", True),
    ("話中有話", True),
    ("對白旁邊寫什麼", True),
    ("爽點與節奏", False),
    ("角色分層放", False),
    ("留一塊不說破", False),
]

ONE = ("一、對卡上「做」這一欄的每一個問句或每一句話，用你自己的話說它在問什麼，"
       "然後各編一個「照這句會被判成有問題」和一個「照這句會被判成沒問題」的短例子（兩三句小說文字）。")


def prompt(card: str, prose: bool) -> str:
    head = f"讀 `{CARDS / (card + '.md')}`。\n\n{ONE}\n\n"
    if prose:
        return (head + f"二、照這張卡檢查 `{DRAFT}` 的全文。每一處寫：原句、你用了卡上哪一個問句、"
                "你的判斷和理由。不要給改法。\n\n只讀這兩個檔，不要讀其他檔。")
    return head + "只讀這個檔，不要讀其他檔。"


def run(job):
    tag, card, prose, n, cwd = job
    path = OUT / f"{tag}-{card}-{n}.md"
    if path.exists() and path.stat().st_size > 200:
        return f"略過 {path.name}"
    cmd = [shutil.which("claude"), "-p", prompt(card, prose), "--output-format", "json",
           "--allowedTools", "Read", "--add-dir", str(CARDS), str(DRAFT.parent)]
    try:
        done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              stdin=subprocess.DEVNULL, timeout=1500)
    except subprocess.TimeoutExpired:
        return f"逾時 {path.name}"
    try:
        data = json.loads(done.stdout)
        text = data.get("result") or ""
        models = ", ".join((data.get("modelUsage") or {}).keys())
    except json.JSONDecodeError:
        return f"失敗 {path.name}: {done.stdout[:200]} {done.stderr[:200]}"
    if not text:
        return f"空白 {path.name}: {done.stdout[:300]}"
    path.write_text(f"<!-- 卡：{card}　第 {n} 次　{tag}　模型：{models} -->\n\n{text}\n", encoding="utf-8")
    return f"完成 {path.name}"


def main():
    tag = sys.argv[1]
    only = set(sys.argv[2:])
    OUT.mkdir(exist_ok=True)
    cwd = tempfile.mkdtemp(prefix="card-test-")
    jobs = [(tag, c, p, n, cwd) for c, p in PICKS if not only or c in only for n in (1, 2)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        for line in pool.map(run, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
