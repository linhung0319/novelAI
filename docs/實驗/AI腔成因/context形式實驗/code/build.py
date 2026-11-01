"""產生人類片段、前文與 S2 的 AI 前文。需要：uv run --no-project --with opencc-python-reimplemented build.py"""
import pathlib, re, subprocess, json, os
from opencc import OpenCC

ROOT = pathlib.Path(__file__).resolve().parents[1]
ST = ROOT / "stimuli"
OLD = ROOT.parent / "stimuli"
EX = ROOT.parents[3] / "examples"
CC = OpenCC("s2tw")


def clean(t):
    t = CC.convert(t).replace("“", "「").replace("”", "」").replace("‘", "『").replace("’", "』")
    return t.strip()


# V：S1 沿用修復實驗片段；S2 取同書較後章節的連續敘述
s1 = (EX / "詭秘之主" / "第003章_梅麗莎（第一更求推薦票）.txt").read_text(encoding="utf-8")
s1 = s1[s1.index("確定了計劃"):]
s1 = s1[:s1.index("砸出砰的一聲。") + 7]
(ST / "S1_V.txt").write_text(clean(s1), encoding="utf-8")

vol = EX / "一世之尊" / "卷一"
ch = next(p for p in vol.glob("*") if p.name.startswith("第047章"))
s2 = ch.read_text(encoding="utf-8")
s2 = s2[s2.index("看著茂密清淨" if "看著茂密清淨" in s2 else "看著茂密清凈"):]
s2 = "\n".join(s2.splitlines()[:14])
(ST / "S2_V.txt").write_text(clean(s2), encoding="utf-8")

# PH：原著第 1 章結尾
ch1 = next(p for p in vol.glob("*") if p.name.startswith("第001章")).read_text(encoding="utf-8")
(ST / "S2_PH.txt").write_text(clean(ch1[-520:].split("\n", 1)[-1]), encoding="utf-8")

# PA：S1 真實管線稿結尾
large = (OLD / "S1_large.txt").read_text(encoding="utf-8")
(ST / "S1_PA.txt").write_text(large[-520:].split("\n", 1)[-1].strip(), encoding="utf-8")

# PA：S2 由 Claude 寫一次，固定一份
if not (ST / "S2_PA.txt").exists():
    p = ("武俠仙俠小說《一世之尊》的第一章結尾。第三人稱，主角孟奇，現代大學生借屍還魂成了一個被送進少林的孩童。"
         "殿上執事玄苦手持戒尺依序問話。孟奇不敢多言，也不敢向帶他來的黃衣僧玄藏打聽。玄苦走到他面前，問他俗家姓名和為何入少林。"
         "孟奇靈光一閃，答「既入少林，俗名已忘」，心裡得意。玄苦看了他一會兒，判他：「機心太重，入雜役院，法號『真定』。」\n"
         "請寫出這段小說正文，約 500 字，繁體中文，以玄苦的這句判決結束。只輸出小說正文本身。")
    empty = pathlib.Path(os.environ["TEMP"]) / "claude-clean-exp"
    empty.mkdir(exist_ok=True)
    r = subprocess.run(["claude", "-p", "--setting-sources", "", "--system-prompt", "你是一位小說作者。", "--tools", "",
                        "--model", "claude-opus-5-5", "--effort", "high", "--output-format", "json",
                        "--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"],
                       input=p.encode("utf-8"), capture_output=True, cwd=empty, timeout=600)
    d = json.loads(r.stdout.decode("utf-8"))
    (ST / "S2_PA.txt").write_text(d["result"].strip(), encoding="utf-8")
    print("S2_PA cost", d.get("total_cost_usd"))

for n in ["S1_V", "S2_V", "S1_PA", "S2_PA", "S2_PH"]:
    print("=====", n, len((ST / f"{n}.txt").read_text(encoding="utf-8")))
    print((ST / f"{n}.txt").read_text(encoding="utf-8"))
