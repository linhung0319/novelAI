#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb-route 原型：門牌投影 + 收窄 + 載入量計算。

正式版讀各技法檔內嵌的門牌 blockquote；本原型讀 route.md（見該檔頂註）。
唯讀、零 LLM、可覆算。
"""
import sys, re, io, os, argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
# repo 根 = 本檔往上三層（05-原型 → 技法用法 → docs → repo）
KB = os.environ.get("KB_DIR", os.path.join(_HERE, "..", "..", "..", "技巧知識庫"))
ROUTE = os.path.join(_HERE, "門牌表.md")


def load_rows():
    rows = []
    cur_file = None
    with io.open(ROUTE, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("## "):
                cur_file = line[3:].strip()
                continue
            if "|" not in line or line.startswith("#") or line.startswith(">"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 6 or "#" not in parts[0]:
                continue
            addr, title, mode, sym, eat, spit = parts[:6]
            rows.append({
                "file": cur_file, "addr": addr, "title": title,
                "mode": mode, "sym": sym, "eat": eat, "spit": spit,
            })
    return rows


def section_sizes():
    """逐檔切 ## 節，按出現順序回傳 [(檔名, 節標題, bytes)]。"""
    out = {}
    for fn in sorted(os.listdir(KB)):
        if not fn.endswith(".md") or fn == "_index.md":
            continue
        name = fn[:-3]
        raw = io.open(os.path.join(KB, fn), encoding="utf-8").read()
        chunks = re.split(r"(?m)^## ", raw)
        secs = []
        for c in chunks[1:]:
            head = c.split("\n", 1)[0].strip()
            secs.append((head, len(("## " + c).encode("utf-8"))))
        out[name] = secs
    return out


def attach_sizes(rows):
    sizes = section_sizes()
    per_file = {}
    for r in rows:
        per_file.setdefault(r["file"], []).append(r)
    warn = []
    for fname, rs in per_file.items():
        secs = sizes.get(fname)
        if secs is None:
            warn.append("找不到技法檔: %s" % fname); continue
        if len(secs) != len(rs):
            warn.append("節數不符 %s: 門牌 %d vs 檔案 %d" % (fname, len(rs), len(secs)))
        for i, r in enumerate(rs):
            r["bytes"] = secs[i][1] if i < len(secs) else 0
            r["real_head"] = secs[i][0] if i < len(secs) else "?"
    return warn


def is_admin(r):
    return r["mode"] in ("—", "") and not r["sym"]


def fmt(r, show_bytes=True):
    b = "  %5dB" % r["bytes"] if show_bytes else ""
    return "%-34s｜%-9s｜%s%s" % (r["addr"], r["mode"], r["title"], b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true", help="投影全表")
    ap.add_argument("--symptom", help="症狀關鍵詞（可多個以空白分隔，OR）")
    ap.add_argument("--mode", help="用法模式")
    ap.add_argument("--eat", help="吃某型別")
    ap.add_argument("--spit", help="吐某型別")
    ap.add_argument("--stats", action="store_true", help="覆蓋率讀數")
    a = ap.parse_args()

    rows = load_rows()
    warn = attach_sizes(rows)
    for w in warn:
        print("⚠ " + w, file=sys.stderr)

    method = [r for r in rows if not is_admin(r)]
    admin = [r for r in rows if is_admin(r)]

    # E2：一律先印「我在這本知識庫上檢查了幾筆」，0 也印
    print("── kb-route：27 支技法檔／%d 節（方法節 %d、行政節 %d）；有症狀欄 %d、空門牌 %d"
          % (len(rows), len(method), len(admin),
             len([r for r in method if r["sym"]]),
             len([r for r in method if not r["sym"]])))

    if a.stats:
        from collections import Counter
        c = Counter()
        for r in method:
            for m in re.split(r"[／,]", r["mode"]):
                if m.strip():
                    c[m.strip()] += 1
        print("\n用法模式分佈（一節可多模式）：")
        for k, v in c.most_common():
            print("  %-6s %3d" % (k, v))
        tot = sum(r["bytes"] for r in rows)
        print("\n全庫 %d B；方法節平均 %d B/節；門牌表本身 %d B"
              % (tot, sum(r["bytes"] for r in method) // max(len(method), 1),
                 os.path.getsize(ROUTE)))
        return

    hits = method
    if a.symptom:
        kws = a.symptom.split()
        hits = [r for r in hits if any(k in r["sym"] or k in r["title"] for k in kws)]
    if a.mode:
        hits = [r for r in hits if a.mode in r["mode"]]
    if a.eat:
        hits = [r for r in hits if a.eat in r["eat"]]
    if a.spit:
        hits = [r for r in hits if a.spit in r["spit"]]

    if a.emit and not (a.symptom or a.mode or a.eat or a.spit):
        for r in method:
            print("%s｜%s｜%s｜吃:%s → 吐:%s" % (r["addr"], r["mode"], r["sym"], r["eat"], r["spit"]))
        return

    print("\n命中 %d 節，合計 %d B：" % (len(hits), sum(r["bytes"] for r in hits)))
    for r in hits:
        print("  " + fmt(r))
    if not hits:
        print("  （0 節命中——這不是錯誤，是讀數。請改用別的關鍵詞，或判定知識庫沒有這一格。）")


if __name__ == "__main__":
    main()
