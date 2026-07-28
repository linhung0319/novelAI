from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path

AI_SUFFIX = ".ai.md"
_KV_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*(?:#.*)?$")


def canonical_text(text: str) -> str:
    """正規化後再 hash：統一換行、去每行尾空白、去檔尾多餘空行。
    使 CRLF/LF、尾隨空白這類無語意差異不會誤判 stale。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(lines).rstrip("\n") + "\n"


def content_hash(text: str) -> str:
    """正規化內容的 sha256 前 12 碼（人眼可比、碰撞機率可忽略）。"""
    return hashlib.sha256(canonical_text(text).encode("utf-8")).hexdigest()[:12]


def _is_source(p: Path) -> bool:
    return p.suffix == ".md" and not p.name.endswith(AI_SUFFIX)


def _is_rollup(p: Path) -> bool:
    return p.name.startswith("_") and p.name.endswith(AI_SUFFIX)


# **「宣告式綜合檔」這個檔類 2026-07-28（功能 11）整個廢除。**
#
# 它曾是 `(會不會被覆蓋) × (人能不能改)` 那張 2×2 表外的第三格：AI 寫、作者不手改，
# 卻**無單一上游源**可 hash 對映。實作是一個檔案級 predicate `_is_declarative`，讓
# `check` 報 `declarative`（不計入需處理數）、`stamp` 直接 raise、`validate_file`
# 早退三次（front-matter 必填鍵／裁決 blockquote／節枚舉）。
#
# 它死於**兩輪連續的實測**：
# - 功能 10 拆掉 `就緒儀表`（292,591 B、53.8% 是拍板日誌），並把判準升成
#   `設計原則.md` **A6**——「不許人改 ＋ 沒有 inbound 重算規則」是一個**必須解掉的
#   衝突，不是第三種身分**（「別改」的正當性完全來自「改了會被重生覆蓋」；沒有重算
#   規則，那個訊號是空的，而**空的訊號比沒有訊號更糟**）。
# - 功能 11 拆掉 `結構`，並發現這個豁免的**唯一支柱是一句沒人回頭檢查過的自述**：
#   `結構.schema.md` 寫「跨全書的綜合視圖、無單一源檔可 hash」，而實測它的對應表
#   **108/108 幕**都能從 `story/幕綱/arcNN.md` 的 `結構階段` 欄重算，選用公式那一半的
#   權威 `大綱.schema.md` 早就指定給 `## 選用結構公式`——**而多源 rollup digest 機制
#   （下面 `source_digest_for_derived` 的 `_is_rollup` 分支）早就存在且在跑**。
#   A6 第 1 條路因此同輪補上一句：**「沒有源」要當成一個待驗證的宣稱，不是前提。**
#
# 現在 `story/參照/` 底下只剩源檔（`就緒.md`／`裁決流.md`／`待裁決.md`），全部有 lint。
# **還帶著舊檔的書要被看見，不是靜靜地繼續豁免**：`結構.{md,ai.md}` 由
# `structure-project` 的第五節報（＋成長哨兵的體積那一項），`就緒儀表.{md,ai.md}` 由
# `readiness-lint` 第 7 項報。帶 `.ai.md` 而無源的檔從此照常報 `orphan`——**那是對的**。
#
# 連帶結清一筆 14 的欠債：`設計原則.md` E2 第七種形態（「豁免的射程比它的理由大」）
# 提的處方是「`_is_declarative` 該長成 `skip_hash(p)`」——**豁免整個消失，所以不必改
# 形狀了**。（那一條原則本身仍然成立，它只是少一個實例。）


_H1_RE = re.compile(r"^#\s+")


def lede(path: Path) -> str:
    """源檔 H1 之後第一個非空行（去掉開頭的 bullet 記號）。取不到回空字串。

    **2026-07-28 功能 12 抉擇 3 B 的機械來源。** `一行需求`／`一句話定位` 這兩個
    LLM 摘要欄廢除之後，「這個實體是什麼」改由源檔自己的第一段回答——它有作者維護、
    天生不會漂。

    **為什麼不印 H1**（抉擇 3 B 的字面）：實測一世之尊**角色 24/24、世界觀 4/4 的
    H1 就是檔名**（`# 修煉體系`），印它等於把 ID 欄抄第二遍。報告支持 3 B 的證據
    只取自 `大綱/_index.md` 的 `名稱` 欄（那一軸的 H1 是有資訊的標題），沒量這兩軸。
    「H1 之後第一段」在這兩軸實測 100% 非空、中位 29／104 字元、**0 支超過 400**。

    **它仍是純機械來源**：位置固定、零 LLM。與 08 抉擇 4 C 被駁回的「從自由源抽
    基調那一句」不同——那一格抽的是**一個具名語意欄**（位置假設承載語意宣稱），
    這一格抽的是**檔的開頭**（位置不承載語意），而且投影只印、不取值。
    依 E1 配守衛：`char-lint` 第 9 項／`world-lint` 第 7 項驗「H1 之後要有非空行」。
    """
    if not path.is_file():
        return ""
    seen_h1 = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s:
            continue
        if not seen_h1 and _H1_RE.match(s):
            seen_h1 = True
            continue
        return re.sub(r"^[-*]\s*", "", s)
    return ""


def _split_frontmatter(text: str) -> tuple[list[str] | None, str]:
    """回傳 (front-matter 行清單, 本體)；無合法 front-matter 時 (None, 全文)。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1 :])
    return None, text  # 未封閉 → 視為無 front-matter


def _dir_digest(d: Path) -> tuple[str, int]:
    """一個**目錄形態源**的 digest：其下所有 `*.md` 的『檔名:內容hash』排序後再 hash。

    回傳 (digest, 切面數)。與 rollup 的取法**刻意是同一個**——「一組檔當成一個源」
    在這個系統裡只有一種算法，兩份會漂移。

    **2026-07-27（功能 06）新增。** 在此之前 `角色.schema.md` 寫著「rollup 的
    digest 對目錄形態取其下所有切面檔的集合」，而那是一條**零實作的承諾**：
    `<名>/` 底下的切面檔既不在非 rollup 那一支的 `d / f"{stem}.md"` 裡，也不在
    rollup 那一支的 `d.glob("*.md")`（不遞迴）裡。實測後果是目錄形態**整個是壞的**
    ——`check` 把 `<名>.ai.md` 報成 `orphan`、`stamp` 直接 raise、改動某個切面
    不會讓 rollup 變 stale。0/24 實測所以從沒撞到；功能 06 把升級改成哨兵驅動
    （並讓「有秘密就開 `水下.md`」與大小脫鉤）之後，第一支升級的角色就會撞上。
    """
    parts = [
        f"{src.name}:{content_hash(src.read_text(encoding='utf-8'))}"
        for src in sorted(d.glob("*.md"))
        if _is_source(src)
    ]
    return content_hash("\n".join(parts)), len(parts)


def source_digest_for_derived(derived: Path) -> tuple[str, str]:
    """回傳 (digest, 來源描述)。
    _*.ai.md 為 rollup：digest = 同層所有源（`X.md` 與**目錄形態** `X/`）的
    『名稱:內容hash』排序後再 hash。
    其餘 X.ai.md：源 = 同層 `X.md`，或**目錄形態** `X/` 的切面集合；
    兩者皆缺回傳 ("", 說明)。"""
    d = derived.parent
    if _is_rollup(derived):
        # (排序鍵, 那一行)。**排序鍵是名稱**，不是整行——用整行排會讓
        # digest 依賴 hash 值的字典序，那是無語意的差異（既有書的 digest
        # 也會因此變動）。既有行為＝按檔名排，這裡照舊。
        entries: list[tuple[str, str]] = [
            (src.name, f"{src.name}:{content_hash(src.read_text(encoding='utf-8'))}")
            for src in sorted(d.glob("*.md"))
            if _is_source(src)
        ]
        # 目錄形態的源也是這一層的源（角色升級成 `<名>/<切面>.md` 之後）。
        # 漏掉它 ＝ 升級一個角色、或改動它的某個切面，rollup 都不會變 stale
        # ——而 rollup 的那一列正是要從它重生的。
        dirs = 0
        for sub in sorted(d.iterdir()):
            if not sub.is_dir() or sub.name.startswith("_"):
                continue
            sub_digest, facets = _dir_digest(sub)
            if not facets:
                continue
            entries.append((f"{sub.name}/", f"{sub.name}/:{sub_digest}"))
            dirs += 1
        parts = [line for _, line in sorted(entries, key=lambda kv: kv[0])]
        desc = f"（rollup：{len(parts)} 個同層源"
        desc += f"，含 {dirs} 個目錄形態）" if dirs else "檔）"
        return content_hash("\n".join(parts)), desc
    stem = derived.name[: -len(AI_SUFFIX)]
    src = d / f"{stem}.md"
    if src.exists():
        return content_hash(src.read_text(encoding="utf-8")), src.name
    src_dir = d / stem
    if src_dir.is_dir():
        digest, facets = _dir_digest(src_dir)
        if facets:
            return digest, f"{stem}/（目錄形態：{facets} 個切面）"
        return "", f"（目錄形態 {stem}/ 底下沒有任何切面 .md）"
    return "", f"（找不到源檔 {src.name}，也沒有目錄形態 {stem}/）"


def read_generated_from(derived: Path) -> str | None:
    fm, _ = _split_frontmatter(derived.read_text(encoding="utf-8"))
    if fm is None:
        return None
    for line in fm:
        m = _KV_RE.match(line)
        if m and m.group(1) == "generated-from":
            return m.group(2).strip()
    return None


def _set_kv(fm: list[str], key: str, value: str) -> list[str]:
    out, replaced = [], False
    for line in fm:
        m = _KV_RE.match(line)
        if m and m.group(1) == key:
            out.append(f"{key}: {value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.insert(0, f"{key}: {value}")
    return out


def stamp(derived: Path, on: str | None = None) -> str:
    """算出 derived 的源 digest，寫回其 front-matter 的 generated-from/generated-at。
    回傳蓋上的 digest。skill 重生 .ai.md 後呼叫此函式封章（別手算 hash）。"""
    digest, _ = source_digest_for_derived(derived)
    if not digest and not _is_rollup(derived):
        raise ValueError(f"無法為 {derived.name} 計算源 digest（源檔缺失？）")
    on = on or _date.today().isoformat()
    fm, body = _split_frontmatter(derived.read_text(encoding="utf-8"))
    if fm is None:
        fm, body = [], body.lstrip("\n")
    fm = _set_kv(fm, "generated-at", on)
    fm = _set_kv(fm, "generated-from", digest)  # insert 後在最前
    new = "---\n" + "\n".join(fm) + "\n---\n" + body.lstrip("\n")
    derived.write_text(canonical_text(new), encoding="utf-8")
    return digest


@dataclass(frozen=True)
class DerivedStatus:
    derived: Path
    source: str
    status: str  # fresh | stale | unstamped | orphan


def check_book(book: Path) -> list[DerivedStatus]:
    """掃 book 下所有 *.ai.md，回報每個相對於其源檔的新鮮度。

    **沒有豁免**（2026-07-28 功能 11：`declarative` 那一格廢除，見檔頭）：帶 `.ai.md`
    而指不出源的檔一律報 `orphan`。**那是對的**——依 `設計原則.md` A6，「不許人改 ＋
    沒有 inbound 重算規則」是一個要解掉的衝突，不是一種可以永遠豁免的身分。
    """
    results: list[DerivedStatus] = []
    for derived in sorted(book.rglob(f"*{AI_SUFFIX}")):
        digest, desc = source_digest_for_derived(derived)
        if not digest and not _is_rollup(derived):
            results.append(DerivedStatus(derived, desc, "orphan"))
            continue
        recorded = read_generated_from(derived)
        if recorded is None:
            status = "unstamped"
        elif recorded == digest:
            status = "fresh"
        else:
            status = "stale"
        results.append(DerivedStatus(derived, desc, status))
    return results
