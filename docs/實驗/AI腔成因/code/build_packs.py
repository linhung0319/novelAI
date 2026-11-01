"""組長 context 包。只收兩個專案真的會餵給寫作者的檔。"""
import pathlib,sys
R=pathlib.Path(r"C:\Users\user\Programming\novelAI"); O=pathlib.Path(r"C:\Users\user\Programming\oh-story-novel")
ST=R/"docs/實驗/AI腔成因/stimuli"
def collect(paths):
    out=[]
    for p in paths:
        p=pathlib.Path(p)
        if p.is_dir(): fs=sorted(x for x in p.rglob("*.md"))
        else: fs=[p]
        for f in fs: out.append(f)
    return out
B=O/"典籍有誤"; SK=O/".claude"
s1=[O/"CLAUDE.md",SK/"agents/narrative-writer.md",SK/"rules",SK/"skills/story-long-write/SKILL.md",
    SK/"skills/story-long-write/references/anti-ai-writing.md",SK/"skills/story-long-write/references/banned-words.md",
    B/"设定",B/"大纲/大纲.md",B/"大纲/卷纲_第一卷.md"]+[next((B/"正文").glob(f"第00{i}章*")) for i in range(1,6)]
Y=R/"一世之尊/story"; KB=R/"技巧知識庫"
s2=[R/"CLAUDE.md",R/".claude/skills/write/SKILL.md",
    Y/"00-摘要.md",Y/"00-摘要.ai.md",Y/"01-大綱.md",Y/"設定/風格",Y/"設定/世界觀/修煉體系.md",Y/"設定/世界觀/少林.md",Y/"設定/世界觀/少林.ai.md",
    Y/"設定/角色/孟奇.md",Y/"設定/角色/孟奇.ai.md"]+[KB/f"{n}.md" for n in ["展示而非講述與五感描寫","敘事距離與DeepPOV","對白","字詞句法與抗生硬","場景與情節推進"]]+[R/"一世之尊/chapters/ch0001.md"]
def build(name,paths,limit=None):
    txt=[];n=0
    for f in collect(paths):
        if not f.exists(): print("MISSING",f,file=sys.stderr); continue
        t=f.read_text(encoding="utf-8",errors="replace")
        rel=f.name if limit else str(f).split("\\",4)[-1]
        block=f"\n===== 檔案：{rel} =====\n{t}\n"
        if limit and n+len(block.encode())>limit: continue
        txt.append(block); n+=len(block.encode())
    (ST/f"{name}.txt").write_text("".join(txt),encoding="utf-8")
    print(name,n,"B",len(txt),"files")
build("S1_large",s1); build("S2_large",s2)
# Qwen 版：規則與短設定優先、總量 ≈40 KB
build("S1_large_q",[SK/"rules",B/"设定/核心设定.md",B/"设定/世界观",B/"大纲/卷纲_第一卷.md"]+[next((B/"正文").glob(f"第00{i}章*")) for i in (3,4,5)],limit=40000)
build("S2_large_q",[Y/"00-摘要.md",Y/"設定/世界觀/少林.md",Y/"設定/角色/孟奇.md",KB/"展示而非講述與五感描寫.md",R/"一世之尊/chapters/ch0001.md"],limit=40000)
