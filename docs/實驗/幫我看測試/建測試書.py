"""複製 一世之尊-測試 成 幫我看-測試，埋入三處問題，並 git init（不 commit）。

原書不動，/search 的測試書才不會被汙染。埋的內容都不是原書設定。
用法：python 建測試書.py   已存在就中止。
"""
import pathlib
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
BOOKS = pathlib.Path(__file__).resolve().parents[4] / "novel-desk" / "books"
SRC = BOOKS / "一世之尊-測試"
DST = BOOKS / "幫我看-測試"

PLANTS = [
    # 走樣：孟奇一路藏秘密，這裡卻主動對真慧全盤托出
    ("ch0004", "不知道還崇不崇拜。\n",
     "不知道還崇不崇拜。\n\n我左右看了看，把他拉近些，壓低聲音：「跟你說個秘密。我根本不是這身子原來的人，我是從別的世界過來的，身上這塊玉佛也不知道打哪兒來。你別告訴別人就是了。」\n\n真慧眨了眨眼，點點頭。\n"),
    # 前後矛盾：ch0043 砍的是左肩
    ("ch0047", "他左肩上那道口子沒有裹。", "他右肩上那道口子沒有裹。"),
    # 多說＋視角滑出第一人稱＋預告後事
    ("ch0012", "被一條落單的漏網黑影，平平常常地，捅死了。\n",
     "被一條落單的漏網黑影，平平常常地，捅死了。\n\n這一幕告訴我們，生命的無常正在於此：人越是以為平安將至，死亡越是悄然而來。清景的死，也成了孟奇日後一切算計的起點，他將用一生記住這個教訓。\n"),
]


def main():
    if DST.exists():
        sys.exit(f"已存在：{DST}")
    shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns(".git"))
    for ch, old, new in PLANTS:
        path = DST / "chapters" / f"{ch}.md"
        text = path.read_bytes().decode("utf-8")
        if text.count(old) != 1:
            sys.exit(f"{ch} 找不到唯一的埋設位置：{old}")
        path.write_bytes(text.replace(old, new).encode("utf-8"))
    subprocess.run(["git", "init", "-q"], cwd=DST, check=True)
    print("完成", DST)


if __name__ == "__main__":
    main()
