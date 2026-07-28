"""`fact_projection` 這個套件裡幾個**跨模組共用**的 regex——每一個只有一份。

**為什麼要有這支檔（2026-07-28 功能 14，抉擇 1 D）。** 這個套件曾有三份同形的
伏筆標記 regex——`beats._MARK_RE`（不抓埋／收）／`objects._MARK_RE`（抓埋／收）／
`sources._FORESHADOW_RE`（不抓埋／收）——而它們在同一個 `import` 得得到的空間裡。

**跨套件的複製有政策在支持它**（所有 `tools/*/pyproject.toml` 皆 `dependencies = []`；
跨套件唯一真相是 `tools/foreshadow_project/src/foreshadow_project/scan.py:_MARK_RE`，
本檔仍然是它的複本）。**同一個套件內的複製沒有**——`derived_sync` 那一側已經實測出
這種複製會**語意分歧且分歧無人守**（功能 14 的 V4）。

schema 用半形冒號，這裡連全形一起收，錯字不靜默漏掉。
"""

from __future__ import annotations

import re

# **標記語法本身只寫一次**——下面每一個 regex 都由它組出來。
# 手寫第二遍的代價是實測過的：語法一旦鬆動（多一個可選空白、多一種冒號），
# 只有其中一份會跟上，而**不跟上的那一份只會少抓，輸出一切正常**。
_MARK = r"\[\[伏筆[:：]\s*([^\]]+?)\s*\]\]"

# 抓 (埋|收, 名字)
MARK_RE = re.compile(r"(埋|收)" + _MARK)
# 只抓名字（呼叫端不在乎埋還是收時用它——**同一條語法、同一份定義**）
NAME_RE = re.compile(r"(?:埋|收)" + _MARK)
# `揭示層級` 的水下層指向哪個收點（`物件.schema.md` 的唯一語法之一）
REVEAL_TARGET_RE = re.compile(r"^揭示於\s*收" + _MARK + r"$")

# 幕標題 `## 幕NNN`。**`beats` 與 `objects` 曾各有一份**（2026-07-28 功能 14
# 收成一份）：那兩份的 pattern 不同（一份抓幕號與標題、一份只問「有沒有」），
# 而**兩份會漂**——一個改了幕標題寫法的 schema 只會讓其中一份跟上。
BEAT_HEAD_RE = re.compile(r"^##\s*幕(\d+)\s*[·・]?\s*(.*)$")
