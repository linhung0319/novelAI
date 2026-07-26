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


# 宣告式綜合檔：AI 寫、作者不手改，但**無單一上游源**可 hash 對映（跨全書的
# 綜合視圖）。過去為了避免被誤報 orphan 而刻意不叫 `.ai.md`——那是讓工具的
# 實作細節決定命名慣例，方向反了：後綴是給作者看的「這個別改」訊號。
# 2026-07-26 起改由本 predicate 承擔，命名回歸語意（見 共同約定.md 二）。
DECLARATIVE_STEMS = frozenset({"就緒儀表", "結構"})


def _is_declarative(p: Path) -> bool:
    if not p.name.endswith(AI_SUFFIX) or p.parent.name != "參照":
        return False
    return p.name[: -len(AI_SUFFIX)] in DECLARATIVE_STEMS


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


def source_digest_for_derived(derived: Path) -> tuple[str, str]:
    """回傳 (digest, 來源描述)。
    _*.ai.md 為 rollup：digest = 同層所有源 *.md 的『檔名:內容hash』排序後再 hash。
    其餘 X.ai.md：源 = 同層 X.md，digest = 該源內容 hash；源缺失回傳 ("", 說明)。"""
    d = derived.parent
    if _is_declarative(derived):
        return "", "（宣告式綜合檔·無單一源·不走 hash）"
    if _is_rollup(derived):
        parts = [
            f"{src.name}:{content_hash(src.read_text(encoding='utf-8'))}"
            for src in sorted(d.glob("*.md"))
            if _is_source(src)
        ]
        return content_hash("\n".join(parts)), f"（rollup：{len(parts)} 個同層源檔）"
    stem = derived.name[: -len(AI_SUFFIX)]
    src = d / f"{stem}.md"
    if not src.exists():
        return "", f"（找不到源檔 {src.name}）"
    return content_hash(src.read_text(encoding="utf-8")), src.name


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
    if _is_declarative(derived):
        raise ValueError(
            f"{derived.name} 是宣告式綜合檔（無單一源、不走 hash），不必也不能封章；"
            "它的過期由 sync 做語意比對"
        )
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
    status: str  # fresh | stale | unstamped | orphan | declarative


def check_book(book: Path) -> list[DerivedStatus]:
    """掃 book 下所有 *.ai.md，回報每個相對於其源檔的新鮮度。"""
    results: list[DerivedStatus] = []
    for derived in sorted(book.rglob(f"*{AI_SUFFIX}")):
        if _is_declarative(derived):
            # 不走 hash：沒有源可比，過期與否交 sync 語意比對。不計入需處理數。
            results.append(
                DerivedStatus(derived, "（宣告式綜合檔·不走 hash）", "declarative")
            )
            continue
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
