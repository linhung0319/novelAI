# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""下載參照小說片段到 examples/<書名>/（對照分析用，見 examples/README.md）。

用法（於 repo 根目錄）：
    uv run examples/download.py --list            # dry-run：只印範圍→章號對映，不下載
    uv run examples/download.py                   # 下載全部
    uv run examples/download.py --only 從紅月開始   # 只下載一本

來源：黃金屋中文 tw.hjwzw.com（5 本，繁體 UTF-8）；詭秘之主已從黃金屋下架，
改用飄天文學 piaotia.com（簡體 GBK）。細節與版權聲明見 README.md。
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
import time
from pathlib import Path

import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
DELAY = 1.5          # 章與章之間的禮貌延遲（秒）
RETRIES = 3
TIMEOUT = 30.0
EXAMPLES_DIR = Path(__file__).resolve().parent

# ── 抓取設定（作者已拍板的書目與範圍）───────────────────────────────
# mode="opening": 取開頭 → 前導引子/序章 + 第1章…第{end}章（遇卷內章號重置即停，避免跨卷誤抓）
# mode="mid":     取中段 → 第{start}章…第{end}章（連續一段）
# mode="volumes": 取整卷 → 依「章號重置回 1」偵測卷界，抓 volumes 指定的卷（ord 由 1 起），
#                 各卷寫入 <書名>/<dir>/ 子資料夾（章號各卷重置，故必須分夾避免撞名）。
BOOKS = [
    {"name": "詭秘之主", "author": "愛潛水的烏賊", "source": "piaotia", "id": "9/9459",
     "mode": "opening", "end": 40},
    {"name": "一世之尊", "author": "愛潛水的烏賊", "source": "hjwzw", "id": "35150",
     "mode": "volumes",
     # 卷界經目錄核對：卷一 第一章 機心→第八十三章 處罰（第73章來源拆兩頁）、
     # 卷二 第一章 瀚海邊緣→第六十五章 人榜、卷三 第一章 仗劍江湖閑散意→第三百五十二章 仰天大笑出門去。
     "volumes": [{"ord": 1, "dir": "卷一"}, {"ord": 2, "dir": "卷二"}, {"ord": 3, "dir": "卷三"}]},
    {"name": "極道天魔", "author": "滾開", "source": "hjwzw", "id": "36213",
     "mode": "opening", "end": 40},
    {"name": "我有一個修仙世界", "author": "純九蓮寶燈", "source": "hjwzw", "id": "48754",
     "mode": "mid", "start": 794, "end": 806},
    {"name": "神秀之主", "author": "文抄公", "source": "hjwzw", "id": "45213",
     "mode": "mid", "start": 364, "end": 461},
    {"name": "從紅月開始", "author": "黑山老鬼", "source": "hjwzw", "id": "45229",
     "mode": "opening", "end": 57},
]

# ── 中文數字 → int（支援到千；本專案範圍最大 806）──────────────────
_CN_DIG = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "两": 2, "三": 3, "四": 4,
           "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn2int(s: str) -> int:
    total = section = num = 0
    for ch in s:
        if ch in _CN_DIG:
            num = _CN_DIG[ch]
        elif ch in _CN_UNIT:
            u = _CN_UNIT[ch]
            if num == 0:
                num = 1
            section += num * u
            num = 0
    return total + section + num


def chapter_number(title: str) -> int | None:
    """從章名解析章號，支援阿拉伯（神秀「第364章」）與中文（「第七百九十四章」）。"""
    m = re.search(r"第\s*(\d+)\s*章", title)
    if m:
        return int(m.group(1))
    m = re.search(r"第([零〇一二兩两三四五六七八九十百千]+)章", title)
    if m:
        return cn2int(m.group(1))
    return None


_PROLOGUE_KEYS = ("引子", "序章", "楔子", "序幕", "前言")


def is_prologue(title: str) -> bool:
    return any(k in title for k in _PROLOGUE_KEYS)


# ── HTTP ─────────────────────────────────────────────────────────────
def fetch(client: httpx.Client, url: str, encoding: str) -> str:
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = client.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return r.content.decode(encoding, errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"抓取失敗 {url}: {last}")


# ── 各來源：目錄解析 + 章節正文解析 ─────────────────────────────────
def toc_hjwzw(client, book):
    url = f"https://tw.hjwzw.com/Book/Chapter/{book['id']}"
    h = fetch(client, url, "utf-8")
    pairs = re.findall(rf'href="/Book/Read/{book["id"]},(\d+)"[^>]*>([^<]+)<', h)
    items = []
    for cid, title in pairs:
        title = _html.unescape(title).strip()
        items.append({"cid": cid,
                      "url": f"https://tw.hjwzw.com/Book/Read/{book['id']},{cid}",
                      "title": title, "num": chapter_number(title)})
    return items


def body_hjwzw(raw: str, book_name: str) -> str:
    i = raw.find("text-indent: 2em")
    if i < 0:
        return ""
    start = raw.find(">", i) + 1
    end = raw.find("</div>", start)
    block = raw[start:end if end > 0 else None]
    return _clean_paragraphs(re.split(r"<p\s*/?>", block, flags=re.I), book_name)


def toc_piaotia(client, book):
    base = f"https://www.piaotia.com/html/{book['id']}/"
    h = fetch(client, base, "gbk")
    pairs = re.findall(r'<a href="(\d+\.html)">([^<]+)</a>', h)
    items = []
    for href, title in pairs:
        title = _html.unescape(title).strip()
        items.append({"cid": href.replace(".html", ""),
                      "url": base + href,
                      "title": title, "num": chapter_number(title)})
    return items


def body_piaotia(raw: str, book_name: str) -> str:
    end = raw.find("<!-- 翻页上AD")
    if end < 0:
        end = raw.find("bottomlink")
    start = raw.rfind("</table>", 0, end)
    block = raw[(start + len("</table>")) if start >= 0 else 0:end if end > 0 else None]
    return _clean_paragraphs(re.split(r"<br\s*/?>", block, flags=re.I), book_name)


_JUNK_MARKERS = ("標記章節", "标记章节", "黃金屋", "黄金屋", "hjwzw", "piaotia", "飄天",
                 "飘天", "上一章", "下一章", "返回目", "加入書", "加入书", "本章未完",
                 "www.", "重要聲明", "重要声明", "Copyright")


def _clean_paragraphs(parts, book_name) -> str:
    out = []
    for p in parts:
        txt = re.sub(r"<[^>]+>", "", p)
        txt = _html.unescape(txt).replace("\xa0", " ").replace("　", " ").strip()
        if not txt:
            continue
        if any(m in txt for m in _JUNK_MARKERS):
            continue
        if txt.startswith(book_name):          # 書名連結 + 章名 的頁首行
            continue
        out.append(txt)
    return "\n".join(out)


SOURCES = {
    "hjwzw": (toc_hjwzw, body_hjwzw, "utf-8"),
    "piaotia": (toc_piaotia, body_piaotia, "gbk"),
}


# ── 選章 ─────────────────────────────────────────────────────────────
def select_opening(items, end):
    """前導 prologue + 第1章…第end章；遇章號回退（跨卷重置）或超過 end 即停。"""
    res, i = [], 0
    while i < len(items) and items[i]["num"] is None and is_prologue(items[i]["title"]):
        res.append(items[i]); i += 1
    while i < len(items) and items[i]["num"] != 1:
        i += 1
    prev = 0
    while i < len(items):
        n = items[i]["num"]
        if n is None:
            i += 1; continue
        if n <= prev or n > end:
            break
        res.append(items[i]); prev = n; i += 1
    return res


def select_mid(items, start, end):
    """第start章…第end章 連續一段（以第一個 num==start 為起點，遇回退/超界即停）。"""
    res, i = [], 0
    while i < len(items) and items[i]["num"] != start:
        i += 1
    prev = start - 1
    while i < len(items):
        n = items[i]["num"]
        if n is None:
            i += 1; continue
        if n < prev or n > end:
            break
        res.append(items[i]); prev = n; i += 1
    return res


def select_volumes(items):
    """依「章號重置回 1」切卷：每遇 num==1 起新卷，其後（含 num 為 None 的附頁）併入該卷。
    第一個 num==1 之前的項目（若有前導 recent 區塊或無章號雜項）一律丟棄。"""
    vols, cur = [], None
    for it in items:
        if it["num"] == 1:
            cur = [it]
            vols.append(cur)
        elif cur is not None:
            cur.append(it)
    return vols


def select(book, items):
    if book["mode"] == "opening":
        return select_opening(items, book["end"])
    return select_mid(items, book["start"], book["end"])


# ── 檔名 ─────────────────────────────────────────────────────────────
_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def chapter_filename(item) -> str:
    num = item["num"] if item["num"] is not None else 0
    name = re.sub(r"^.*?第[\d零〇一二兩两三四五六七八九十百千]+章", "", item["title"])
    name = _ILLEGAL.sub("", name).strip().replace(" ", "_")
    if not name:                       # prologue（引子/序章…）沒有「第X章」
        name = _ILLEGAL.sub("", item["title"]).strip().replace(" ", "_") or "無題"
    return f"第{num:03d}章_{name}.txt"


# ── 主流程 ───────────────────────────────────────────────────────────
def _write_chapters(out_dir, picked, client, body_fn, enc, book_name, do_download):
    """抓 picked 各章寫入 out_dir，回傳 (manifest_chapters, short_count)。
    同名檔（來源把一章拆多頁、標題重複）：內容相同則略過，不同則加 _2/_3 後綴各留一檔。"""
    written: dict[str, str] = {}     # fname → text，用於撞名去重／區分
    chapters, short = [], 0
    for k, it in enumerate(picked, 1):
        raw = fetch(client, it["url"], enc)
        text = body_fn(raw, book_name)
        base = chapter_filename(it)
        fname = base
        if base in written:
            if written[base] == text:
                print(f"  [{k}/{len(picked)}] {base}  ← 內容重複，略過")
                continue
            stem, i = base[:-4], 2
            while f"{stem}_{i}.txt" in written and written[f"{stem}_{i}.txt"] != text:
                i += 1
            if f"{stem}_{i}.txt" in written:   # 已有相同內容的後綴檔
                print(f"  [{k}/{len(picked)}] {base}  ← 內容重複，略過")
                continue
            fname = f"{stem}_{i}.txt"
        (out_dir / fname).write_text(it["title"] + "\n\n" + text + "\n", encoding="utf-8")
        written[fname] = text
        chapters.append({"number": it["num"], "title": it["title"],
                         "cid": it["cid"], "file": fname, "url": it["url"]})
        flag = ""
        if len(text) < 200:
            short += 1; flag = "  ⚠ 正文過短"
        print(f"  [{k}/{len(picked)}] {fname}  ({len(text)} 字){flag}")
        time.sleep(DELAY)
    return chapters, short


def run_book_volumes(client, book, do_download):
    toc_fn, body_fn, enc = SOURCES[book["source"]]
    items = toc_fn(client, book)
    vols = select_volumes(items)
    wanted = book["volumes"]
    print(f"\n=== {book['name']}（{book['author']}）｜{book['source']}｜"
          f"卷 {[w['ord'] for w in wanted]}｜目錄 {len(items)} 章，偵測 {len(vols)} 卷 ===")
    base_dir = EXAMPLES_DIR / book["name"]
    manifest = {"title": book["name"], "author": book["author"], "source": book["source"],
                "id": book["id"], "fetched": time.strftime("%Y-%m-%d"), "volumes": []}
    for w in wanted:
        idx = w["ord"] - 1
        if idx < 0 or idx >= len(vols):
            print(f"  !! 卷{w['ord']} 不存在（僅偵測 {len(vols)} 卷）")
            continue
        picked = vols[idx]
        print(f"\n  ── {w['dir']}（卷{w['ord']}）：{len(picked)} 章"
              f"｜首：{picked[0]['title']}｜尾：{picked[-1]['title']}")
        if not do_download:
            preview = (picked[:3] + [None] + picked[-3:]) if len(picked) > 6 else picked
            for it in preview:
                if it is None:
                    print("        …"); continue
                print(f"        第{(it['num'] or 0):03d}章  {it['title']}  → {w['dir']}/{chapter_filename(it)}")
            continue
        out_dir = base_dir / w["dir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        chapters, short = _write_chapters(out_dir, picked, client, body_fn, enc,
                                          book["name"], do_download)
        manifest["volumes"].append({"volume": w["ord"], "dir": w["dir"],
                                    "first": picked[0]["title"], "last": picked[-1]["title"],
                                    "chapters": chapters})
        print(f"  完成 {w['dir']} {len(chapters)} 章 → {out_dir}"
              + (f"（{short} 章正文過短，請抽查）" if short else ""))
    if do_download and manifest["volumes"]:
        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        total = sum(len(v["chapters"]) for v in manifest["volumes"])
        print(f"\n  {book['name']} 共 {len(manifest['volumes'])} 卷 {total} 章 → {base_dir}/manifest.json")


def run_book(client, book, do_download):
    if book["mode"] == "volumes":
        return run_book_volumes(client, book, do_download)
    toc_fn, body_fn, enc = SOURCES[book["source"]]
    items = toc_fn(client, book)
    picked = select(book, items)
    rng = f"ch1–{book['end']}" if book["mode"] == "opening" else f"ch{book['start']}–{book['end']}"
    print(f"\n=== {book['name']}（{book['author']}）｜{book['source']}｜{rng}｜"
          f"目錄 {len(items)} 章，選中 {len(picked)} 章 ===")
    if not picked:
        print("  !! 選中 0 章——請檢查目錄解析或章號範圍")
        return
    print(f"  首：{picked[0]['title']}")
    print(f"  尾：{picked[-1]['title']}")

    if not do_download:
        if len(picked) > 6:
            preview = picked[:3] + [None] + picked[-3:]
        else:
            preview = picked
        for it in preview:
            if it is None:
                print("      …"); continue
            print(f"      第{(it['num'] or 0):03d}章  {it['title']}  → {chapter_filename(it)}")
        return

    out_dir = EXAMPLES_DIR / book["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"title": book["name"], "author": book["author"], "source": book["source"],
                "id": book["id"], "range": rng, "fetched": time.strftime("%Y-%m-%d"),
                "chapters": []}
    short = 0
    for k, it in enumerate(picked, 1):
        raw = fetch(client, it["url"], enc)
        text = body_fn(raw, book["name"])
        fname = chapter_filename(it)
        (out_dir / fname).write_text(it["title"] + "\n\n" + text + "\n", encoding="utf-8")
        manifest["chapters"].append({"number": it["num"], "title": it["title"],
                                     "cid": it["cid"], "file": fname, "url": it["url"]})
        flag = ""
        if len(text) < 200:
            short += 1; flag = "  ⚠ 正文過短"
        print(f"  [{k}/{len(picked)}] {fname}  ({len(text)} 字){flag}")
        time.sleep(DELAY)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  完成 {len(picked)} 章 → {out_dir}"
          + (f"（{short} 章正文過短，請抽查）" if short else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="dry-run：只印範圍→章號對映")
    ap.add_argument("--only", metavar="書名", help="只處理指定一本")
    args = ap.parse_args()

    books = BOOKS if not args.only else [b for b in BOOKS if b["name"] == args.only]
    if not books:
        sys.exit(f"找不到書：{args.only}（可選：{'、'.join(b['name'] for b in BOOKS)}）")

    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True) as client:
        for b in books:
            try:
                run_book(client, b, do_download=not args.list)
            except Exception as e:  # noqa: BLE001
                print(f"  !! {b['name']} 失敗：{e}")


if __name__ == "__main__":
    main()
