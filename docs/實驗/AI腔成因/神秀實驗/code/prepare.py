"""組出提示；核對指示沒有洩漏該章原句。只核對事實，不評品質。"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOK = ROOT.parents[3] / "examples" / "神秀之主"
SOURCES = {"367": "第367章_談笑殺人.txt", "400": "第400章_賄賂.txt", "425": "第425章_一劍挑了.txt"}
EXCERPTS = [("第408章_除夕.txt", 45, 64), ("第444章_比劍(1200加).txt", 34, 79)]


def lines(name, first, last):
    text = (BOOK / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(text[first - 1:last])


def excerpt_block():
    parts = [lines(n, a, b) for n, a, b in EXCERPTS]
    joined = "\n\n（另一章）\n\n".join(parts)
    return (
        "下面是同一本書其他章節的原文片段，情節和這一章無關。"
        "學它怎麼講故事、怎麼分段、怎麼讓人物在心裡說話。"
        "不要抄它的句子，也不要用它的情節。\n\n<片段>\n" + joined + "\n</片段>\n\n"
    )


def prompt(ch, arm):
    body = (ROOT / "指示" / f"ch{ch}.md").read_text(encoding="utf-8")
    style = (ROOT / "指示" / "寫法.md").read_text(encoding="utf-8")
    return (excerpt_block() if arm == "IE" else "") + body + "\n" + style


def longest_shared(a, b):
    best, where, prev = 0, "", [0] * (len(b) + 1)
    for ca in a:
        cur = [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best, where = cur[j], b[j - cur[j]:j]
        prev = cur
    return best, where


def norm(text):
    table = str.maketrans({"里": "裡", "么": "麼", "于": "於", "后": "後", "鉆": "鑽", "鍾": "鐘"})
    return re.sub(r"[\s“”‘’「」『』，。！？、：；…—《》（）()0-9]", "", text.translate(table))


if __name__ == "__main__":
    for ch, name in SOURCES.items():
        human = norm((BOOK / name).read_text(encoding="utf-8"))
        brief = norm((ROOT / "指示" / f"ch{ch}.md").read_text(encoding="utf-8"))
        print(ch, "原文字數", len(human), "與指示最長共同字串", longest_shared(brief, human))
    print("片段字數", len(excerpt_block()))
