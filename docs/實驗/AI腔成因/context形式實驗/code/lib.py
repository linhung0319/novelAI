"""組 prompt。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
ST = ROOT / "stimuli"
OLD = ROOT.parent / "stimuli"
OUT = ROOT / "outputs"
WRAP = (OLD / "wrapper.txt").read_text(encoding="utf-8").strip()
SYS = "你是一位小說作者。"
ARMS = {"S1": ["M", "MP", "S", "N", "R", "V", "PA"], "S2": ["M", "MP", "S", "N", "R", "V", "PA", "PH"]}


def rd(p):
    return p.read_text(encoding="utf-8").strip()


def context_parts(scene, arm):
    """此臂額外給的文字，用於核對照抄。"""
    a = rd(OLD / f"{scene}_A.txt")
    mp = rd(ST / f"{scene}_MP.txt")
    return {
        "M": [a], "MP": [mp],
        "S": [a, rd(ST / f"{scene}_spec.txt")],
        "N": [mp, rd(ST / f"{scene}_prose.txt")],
        "R": [a, rd(ST / "rule.txt")],
        "V": [a, rd(ST / f"{scene}_V.txt")],
        "PA": [a, rd(ST / f"{scene}_PA.txt")],
        "PH": [a, rd(ST / f"{scene}_PH.txt")] if scene == "S2" else [],
    }[arm]


def prompt(scene, arm):
    a = rd(OLD / f"{scene}_A.txt")
    if arm == "M":
        return f"{a}\n\n{WRAP}"
    if arm == "MP":
        return f"{rd(ST / f'{scene}_MP.txt')}\n\n{WRAP}"
    if arm == "S":
        return f"以下是本書資料：\n{rd(ST / f'{scene}_spec.txt')}\n\n本章任務：\n{a}\n\n{WRAP}"
    if arm == "N":
        return f"以下是本書背景：\n{rd(ST / f'{scene}_prose.txt')}\n\n{rd(ST / f'{scene}_MP.txt')}\n\n{WRAP}"
    if arm == "R":
        return f"{a}\n\n{rd(ST / 'rule.txt')}\n\n{WRAP}"
    if arm == "V":
        return f"{a}\n\n下面是別的章節的一段文字，只參考它敘述的聲音和句子之間的銜接，不要用它的情節和人物：\n{rd(ST / f'{scene}_V.txt')}\n\n{WRAP}"
    if arm in ("PA", "PH"):
        return f"上一章的結尾：\n{rd(ST / f'{scene}_{arm}.txt')}\n\n{a}\n\n{WRAP}"
    raise ValueError(arm)


def jobs(n):
    return [(s, a, i) for i in range(1, n + 1) for s in ARMS for a in ARMS[s]]
