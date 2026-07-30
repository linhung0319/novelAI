"""`beat-lint` 的正反例。

每一項檢查都要有**反例會報、正例不報**兩個方向——只測「壞的會報」的檢查器，
無法分辨「它在守」與「它把全部東西都報成壞的」。

fixture 一律自造：一世之尊只有 15 個問題、涵蓋不到多數檢查（它的幕號 0 重複、
前因 0 懸空——那正是它作為乾淨基準的價值）。真實語料的回歸走 `test_golden_一世之尊.py`。
"""

from __future__ import annotations

import pytest

from beat_metrics.lint import lint_report
from beat_metrics.scan import ScanError

# **spine 與索引 2026-07-28（功能 12 抉擇 2 A）分家**：`全書順序：` 是 A1 源（作者
# 的創作決定），住 `_順序.md`；索引是視圖（`beat-lint` 驗它 ≡ 資料夾），住 `_index.md`。
# 在此之前兩者同居一檔，而這份 fixture 只有 spine 那一行——那正是被補上的那個縫：
# `_index.md` 的 11,647 字元裡只有一行被驗過。
SPINE = "# 幕綱順序\n\n- 全書順序：arc01 → arc02\n"

# 索引要**列出每一支 arc 檔**並宣告幕號範圍；`選用結構公式：` 只准指路
# （權威在大綱的 `## 選用結構公式`，`outline-lint` 第 12 項守）。
INDEX = (
    "# 幕綱索引\n\n"
    "- 選用結構公式：見 `story/01-大綱.md` 的 `## 選用結構公式`\n"
    "- arc01：幕001–幕002（號段 001–100）\n"
    "- arc02：幕101–幕101（號段 101–200）\n"
)

ARC01 = """# arc01 · 起

## 本 arc 承諾

- 節奏檔位：開頭段
- 不得發生：
  - 反派不登場
  - 不跨階

## 幕001 · 開場
- 角色：林小凡
- 時空：老宅／清晨
- 行動：翻遍藥典找解毒法
- 衝突：藥石罔效
- 結果：確認無解
- 前因：—
- 伏筆：埋[[伏筆:血玉墜]]
- 結構階段：平凡失衡

## 幕002 · 立誓
- 角色：林小凡、母親
- 時空：老宅／夜
- 行動：向母親發誓親自去取寒髓
- 衝突：取者無人生還
- 結果：立誓獨力奪髓
- 前因：[[幕001]]（醫術無解逼出這條路）
- 伏筆：—
- 結構階段：召喚衝突
"""

ARC02 = """# arc02 · 承

## 本 arc 承諾

- 節奏檔位：常態段

## 幕101 · 奪髓
- 角色：林小凡、血衣老者
- 時空：北域冰原／第三夜
- 行動：闖禁地取寒髓
- 衝突：老者出手阻攔
- 結果：奪得寒髓，左臂遭封脈
- 前因：[[幕002]]（立誓獨力奪髓）
- 伏筆：收[[伏筆:血玉墜]]
- 結構階段：磨練成長
"""


def _book(tmp_path, index=None, spine=SPINE, **arcs):
    """`index=` 給索引檔，`spine=` 給順序檔；**傳 None ＝不建那一支**。

    - `spine=None` → 測**新落點不在**（2026-07-30 起舊落點不再回退）。
    - `index=None`（**預設**）→ 索引檔廢除之後的正常狀態（功能 12 抉擇 1 A：
      五支 rollup 廢除，全書視圖改跑 `beat-lint --emit`）。傳 `INDEX` 進來就是在
      造一本**還留著已廢除 rollup 的舊書**，那本身就是一筆問題（2026-07-30 起）。
    """
    d = tmp_path / "story" / "幕綱"
    d.mkdir(parents=True)
    if index is not None:
        (d / "_index.md").write_text(index, encoding="utf-8")
    if spine is not None:
        (d / "_順序.md").write_text(spine, encoding="utf-8")
    for name, text in arcs.items():
        (d / f"{name}.md").write_text(text, encoding="utf-8")
    # 索引的 `選用結構公式：` 只准指路，而**指路本身要指得到**——`_check_destinations`
    # 會驗這一筆（E1：箭頭指向空氣，而箭頭本身格式完全合法）。兩項守衛的交互是刻意的。
    (tmp_path / "story" / "01-大綱.md").write_text(
        "# 大綱\n\n## 選用結構公式\n\n- 起承轉合\n", encoding="utf-8"
    )
    return tmp_path


def _only(problems, needle):
    return [p for p in problems if needle in p]


# --------------------------------------------------------------- 正例

def test_clean_book_reports_nothing(tmp_path):
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert problems == []
    assert (stats.arcs, stats.beats, stats.refs) == (2, 3, 2)
    assert (stats.marks, stats.mark_names) == (2, 1)
    assert stats.promise_sections == 2
    assert stats.exclusions == 2


def test_coverage_line_prints_zeroes(tmp_path):
    """**0 也要印。** 「我檢查了 0 筆」本身就是最有用的那一筆訊息。"""
    _, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    line = stats.render()
    assert "2 支 arc／3 幕／2 條前因" in line
    assert "0 列狀態表" in line and "0 支物件檔" in line and "跳過 0 支骨架" in line


# --------------------------------------------------------------- 反例

def test_duplicate_beat_number(tmp_path):
    dup = ARC02.replace("## 幕101 ·", "## 幕001 ·").replace(
        "- 前因：[[幕002]]（立誓獨力奪髓）", "- 前因：[[幕002]]"
    )
    dup = dup.replace("- 全書順序", "- 全書順序")
    problems, _ = lint_report(
        _book(tmp_path, arc01=ARC01, arc02=dup.replace("幕001", "幕002"))
    )
    assert _only(problems, "重複"), problems


def test_beat_number_outside_allocated_block(tmp_path):
    """arc02 的幕號該落在 幕101–幕200；寫成 幕999 要報。"""
    off = ARC02.replace("## 幕101 ·", "## 幕999 ·")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=off))
    assert _only(problems, "預配號段"), problems


def test_dangling_beat_reference(tmp_path):
    """V3：schema 與 beat-test 都稱它是「機械事實」，2026-07-27 前卻無工具在做。"""
    bad = ARC02.replace("[[幕002]]", "[[幕777]]")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=bad))
    hits = _only(problems, "指向不存在的幕")
    assert len(hits) == 1 and "幕777" in hits[0], problems


def test_missing_field(tmp_path):
    bad = ARC02.replace("- 結果：奪得寒髓，左臂遭封脈\n", "")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=bad))
    assert _only(problems, "缺欄位 結果"), problems


def test_blank_field(tmp_path):
    bad = ARC02.replace("- 衝突：老者出手阻攔", "- 衝突：—")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=bad))
    assert _only(problems, "「衝突」欄留白"), problems


def test_blank_antecedent_and_foreshadow_are_legal(tmp_path):
    """`前因：—`＝首幕；`伏筆：—`＝本幕無伏筆。**都不是格式問題。**

    非首幕卻沒有前因是「孤兒幕」，屬因果連續性（`beat-test` 測試1 的語意判斷），
    不歸本閘門——實測 `驗證範例` 幕005 正是刻意留著的那個缺陷樣本。
    """
    loose = ARC02.replace("- 前因：[[幕002]]（立誓獨力奪髓）", "- 前因：—")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=loose))
    assert _only(problems, "留白") == []


def test_missing_promise_section(tmp_path):
    bad = ARC02.replace("## 本 arc 承諾\n\n- 節奏檔位：常態段\n", "")
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=bad))
    assert _only(problems, "缺「## 本 arc 承諾」分區"), problems


# --------------------------------------------------------------- spine

def test_spine_missing_arc(tmp_path):
    problems, _ = lint_report(
        _book(tmp_path, spine="- 全書順序：arc01\n", arc01=ARC01, arc02=ARC02)
    )
    assert _only(problems, "未涵蓋 arc02"), problems


def test_spine_lists_nonexistent_arc(tmp_path):
    problems, _ = lint_report(
        _book(tmp_path, spine="- 全書順序：arc01 → arc02 → arc03\n", arc01=ARC01, arc02=ARC02)
    )
    assert _only(problems, "沒有對應的 arc03.md"), problems


def test_spine_duplicate_entry(tmp_path):
    problems, _ = lint_report(
        _book(tmp_path, spine="- 全書順序：arc01 → arc02 → arc01\n", arc01=ARC01, arc02=ARC02)
    )
    assert _only(problems, "重複列出 arc01"), problems


def test_spine_unparseable(tmp_path):
    problems, _ = lint_report(
        _book(tmp_path, spine="# 幕綱順序\n\n（還沒填）\n", arc01=ARC01, arc02=ARC02)
    )
    assert _only(problems, "全書順序"), problems


# ------------------------------------------- spine 的落點（功能 12 抉擇 2 A）
#
# `全書順序：` 是 A1 源（arc 的故事先後是創作決定，沒有任何檔算得出來），2026-07-28
# 從索引檔搬進同層的 `_順序.md`——它原本與一支被驗成「視圖 ≡ 資料夾」的索引同居
# 一檔（六問 Q0；`設計原則.md` A1 同輪補的那句就是這件事）。


def test_spine_lives_in_its_own_file(tmp_path):
    """正例：spine 在 `_順序.md`，覆蓋率行說出它讀的是新落點。"""
    _, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert (stats.spine_file, stats.spine_legacy) == ("_順序.md", False)
    assert "spine 讀自 `_順序.md`" in stats.render()
    assert "（舊落點已不在）" in stats.render()  # **0 也印**


def test_the_legacy_spine_location_is_no_longer_read(tmp_path):
    """**舊落點 `_index.md` 的回退 2026-07-30 移除**（驗證輪階段 1c）。

    2026-07-28 那一輪的處置是「不拒絕回退，讓它可見」，問題訊息裡寫著
    「別讓它一直是提醒」。實測**提醒發了兩天、唯一走回退的書一個字沒動**，
    而四份回退實作照樣活著（`beat_metrics`／`fact_projection`／
    `decision_projection`／`foreshadow_project`）。活用戶只有 `一世之尊`。

    現在舊落點**不讀**，於是這本書降級成「被回報的問題」——**不是 traceback**
    （階段 1c 硬驗收條件 1），而訊息指得出舊檔在哪、怎麼搬。
    """
    legacy_index = INDEX + "- 全書順序：arc01 → arc02\n"
    problems, stats = lint_report(
        _book(tmp_path, index=legacy_index, spine=None, arc01=ARC01, arc02=ARC02)
    )
    assert stats.spine_legacy is True  # 墓碑：舊檔還在
    assert "舊落點 `_index.md` 仍在·2026-07-30 起不讀" in stats.render()
    hits = _only(problems, "不存在")
    assert len(hits) == 1
    assert "_順序.md" in hits[0] and "不讀它" in hits[0] and "git mv" in hits[0]


def test_both_spine_locations_present_reads_only_the_new_one(tmp_path):
    """兩支都在時只讀新的，**並報舊的那一支**——兩份定序漂移是下一個病。"""
    legacy_index = INDEX + "- 全書順序：arc02 → arc01\n"  # 刻意與 SPINE 逆序
    problems, stats = lint_report(
        _book(tmp_path, index=legacy_index, arc01=ARC01, arc02=ARC02)
    )
    assert (stats.spine_file, stats.spine_legacy) == ("_順序.md", True)
    assert len(_only(problems, "已廢除的 rollup 還在")) == 1


def test_missing_spine_points_at_the_new_home(tmp_path):
    """兩個落點都沒有時，錯誤訊息要指向**該建的那一支**，不是舊的。

    這也是**索引檔廢除之後的形狀**（抉擇 1 A）：新書沒有 `_index.md`，所以
    `spine_path` 只剩一個候選，而視圖比對那一項直接跳過（沒有檔就沒有視圖）。
    """
    problems, stats = lint_report(
        _book(tmp_path, index=None, spine=None, arc01=ARC01, arc02=ARC02)
    )
    assert stats.spine_file == ""  # 沒讀到就不寫「讀自」——那一句會是假的
    hits = _only(problems, "不存在")
    assert len(hits) == 1 and "幕綱/_順序.md" in hits[0]


def test_index_absent_is_not_a_problem(tmp_path):
    """**索引檔廢除之後不該報它不見了**（抉擇 1 A）：全書視圖跑 `beat-lint --emit`，
    spine 住 `_順序.md`——兩件事都不需要那支檔。"""
    problems, stats = lint_report(_book(tmp_path, index=None, arc01=ARC01, arc02=ARC02))
    assert problems == []
    assert stats.index_retired is False
    assert "已廢除的 `_index.md`：已不在" in stats.render()  # **0 也印**
    assert (stats.spine_file, stats.spine_legacy) == ("_順序.md", False)


def test_spine_failure_is_loud_not_silent():
    """V4：`parse_spine` 讀不到就 raise，與其餘三支工具一致。

    舊版回 `{}` 退檔名排序、印 exit 0——同一個壞法，看你先跑哪支工具決定你會不會發現。
    """
    from beat_metrics.scan import parse_spine

    with pytest.raises(ScanError):
        parse_spine("# 幕綱索引\n- 選用結構公式：編劇九階段\n")
    assert parse_spine("- 全書順序：arc03 → arc01\n") == {"arc03": 0, "arc01": 1}


# --------------------------------------------------------------- 近似名／目的地

def test_near_duplicate_foreshadow_name(tmp_path):
    """V10：狀態表造出 `X（Y）`，而標記寫的是 `X`——兩個名字、一條伏筆。"""
    arc = ARC02 + (
        "\n## 本 arc 伏筆狀態\n"
        "| 伏筆 | 埋設幕 | 收回 | 備註 |\n"
        "|------|--------|------|------|\n"
        "| 血玉墜（母親給的） | 幕001 | 幕101 | 括號變體 |\n"
    )
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert _only(problems, "疑似同一條伏筆的兩個名字"), problems
    assert stats.status_rows == 1


def test_prose_continuation_rows_are_counted_not_reported(tmp_path):
    """抉擇 2 B：續行刻意不立 token，**不報成問題**，但要在覆蓋率行誠實計數。"""
    arc = ARC02 + (
        "\n## 本 arc 伏筆狀態\n"
        "| 伏筆 | 埋設幕 | 收回 | 備註 |\n"
        "|------|--------|------|------|\n"
        "| 母愛護盾 | arc01（未拆） | 未收 | 全書無標記的散文續行 |\n"
    )
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert problems == []
    assert (stats.status_rows, stats.status_prose_rows) == (1, 1)
    assert "其中 1 列的伏筆名全書無標記" in stats.render()


def test_design_note_without_destination(tmp_path):
    """E1 新推論：遷移承諾的終點要有守衛。箭頭指向空氣，而箭頭本身格式合法。"""
    arc = ARC02 + "\n## 設計註（下游不抄）\n\n母題論證：這一段的骨是對帳。\n"
    book = _book(tmp_path, arc01=ARC01, arc02=arc)
    problems, _ = lint_report(book)
    assert _only(problems, "裁決流.md` 不存在"), problems

    # **舊名 `裁決流.co.md` 2026-07-30 起不算目的地**（驗證輪階段 1c）：E1 要的是
    # 「目的地存在」，不是「有個叫這名字的檔存在」——`.co.md` 拿不到 `decision-lint`，
    # 讓它冒充目的地，等於把箭頭指向一支沒有守衛的檔。
    ref = book / "story" / "參照"
    ref.mkdir(parents=True)
    (ref / "裁決流.co.md").write_text("# 裁決流\n", encoding="utf-8")
    assert _only(lint_report(book)[0], "裁決流.md` 不存在")
    (ref / "裁決流.md").write_text("# 裁決流\n", encoding="utf-8")
    assert _only(lint_report(book)[0], "裁決流") == []


def test_legacy_decision_log_name_also_counts(tmp_path):
    """`裁決流.schema.md:6`：2026-07-27 前的書可能仍是舊名 `裁決流.md`。"""
    arc = ARC02 + "\n## 設計註\n\n理由。\n"
    book = _book(tmp_path, arc01=ARC01, arc02=arc)
    ref = book / "story" / "參照"
    ref.mkdir(parents=True)
    (ref / "裁決流.md").write_text("# 裁決流\n", encoding="utf-8")
    assert _only(lint_report(book)[0], "裁決流") == []


# --------------------------------------------------------------- 骨架／提示

def test_skeleton_is_skipped_but_counted(tmp_path):
    """跳過幾支要印出來，否則就是另一個「守衛報平安」。"""
    skeleton = "# arc02\n\n> ⚠️ **尚未產出**——本檔是空骨架。\n\n## 幕101 · （幕名）\n- 角色：\n"
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=skeleton))
    assert problems == []
    assert (stats.arcs, stats.skeletons) == (1, 1)
    assert "跳過 1 支骨架" in stats.render()


def test_tail_hook_is_a_hint_not_a_problem(tmp_path):
    """`幕尾鉤` 是 schema 未定義的第九欄（實測 79/108 幕）。本輪只提示、不裁歸屬。"""
    arc = ARC02.replace(
        "- 結構階段：磨練成長", "- 結構階段：磨練成長\n- 幕尾鉤：斷在老者抬眼那一下"
    )
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert problems == []
    assert any("幕尾鉤" in h for h in stats.hints)


def test_unregistered_foreshadow_names_are_hints(tmp_path):
    """`物件.schema.md`：沒有物件檔的 ID 是合法的，所以是提示不是問題。"""
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert problems == []
    assert any("沒有 `story/物件/" in h for h in stats.hints)


def test_registered_names_drop_out_of_the_hint(tmp_path):
    book = _book(tmp_path, arc01=ARC01, arc02=ARC02)
    objects = book / "story" / "物件"
    objects.mkdir(parents=True)
    (objects / "血玉墜.md").write_text("---\n型別: 伏筆\n---\n", encoding="utf-8")
    _, stats = lint_report(book)
    assert stats.object_files == 1
    assert not any("沒有 `story/物件/" in h for h in stats.hints)


def test_unknown_section_is_a_hint(tmp_path):
    arc = ARC02 + "\n## ⚠️ 措辭硬約束（全域）\n\n某某一律不以「手」字指稱。\n"
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert problems == []
    assert any("未定義的 `##` 分區" in h for h in stats.hints)


# --------------------------------------------------------------- 測試執行紀錄（功能 10）

def test_beat_test_record_is_optional(tmp_path):
    """**缺席合法、不計入問題數**——沒測過是真實狀態，報它就是把非門檻變成門檻。

    缺幾支由覆蓋率行說（`0/2 支 arc`），**0 也印**。
    """
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=ARC02))
    assert problems == []
    assert (stats.test_records, stats.test_records_bad) == (0, 0)
    assert "0/2 支 arc 有 `beat-test` 紀錄" in stats.render()


def test_beat_test_record_well_formed(tmp_path):
    arc = ARC01.replace("# arc01 · 起", "# arc01 · 起\nbeat-test: 2026-07-24·0高3中3低")
    problems, stats = lint_report(_book(tmp_path, arc01=arc, arc02=ARC02))
    assert problems == []
    assert (stats.test_records, stats.test_records_bad) == (1, 0)


def test_beat_test_record_rejects_prose(tmp_path):
    """判準是**結構**：日期 ＋ 阿拉伯數字。中文數字與散文一律不算。"""
    arc = ARC01.replace("# arc01 · 起", "# arc01 · 起\nbeat-test: 七月底跑過，結構沒問題")
    problems, stats = lint_report(_book(tmp_path, arc01=arc, arc02=ARC02))
    assert _only(problems, "不合形狀")
    assert stats.test_records_bad == 1


def test_beat_test_record_only_read_from_the_header(tmp_path):
    """位置判準：設計註裡談 `beat-test:` 的散文不算紀錄（全檔掃會撈到它）。"""
    arc = ARC02 + "\n## 設計註\n\nbeat-test: 這一輪先不跑，等 arc03 一起\n"
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert not _only(problems, "不合形狀")
    assert stats.test_records == 0


# ------------------------------------------------- 幕綱索引的視圖（功能 12 步驟 3）
#
# 形狀照抄 `outline-lint` 第 3 項，**多一件事**：幕綱的索引列宣告了一個可機械核對的
# 區間（`幕001–幕009`），而大綱的索引列只有名稱與狀態。這同時是 `beat-lint --emit`
# 的核心——為了比對而算出來的那一份，就是要印的那一份。


def test_a_retired_rollup_is_reported_by_existence_not_compared(tmp_path):
    """**2026-07-30（驗證輪階段 1c／1d）：從「照舊比對」改成存在性檢查。**

    功能 12 廢除五支 rollup，並把兩支 `.md` 的殘留偵測交給本 lint 與 `outline-lint`
    ——而實作出來的是「照舊比對」（`功能報告/15` 明文交回這一筆）。
    照舊比對的後果是**工具叫作者去把一支已廢除的檔修好，而修好就等於讓它永久合法**
    （`設計原則.md` A5，與 `ABOLISHED_ROLLUPS` 檔頭是同一句話，只是那裡守的是
    `.ai.md`、這裡漏了 `.md`）。
    """
    problems, stats = lint_report(_book(tmp_path, index=INDEX, arc01=ARC01, arc02=ARC02))
    assert stats.index_retired is True
    assert "已廢除的 `_index.md`：**仍在**" in stats.render()
    hits = _only(problems, "已廢除的 rollup 還在")
    assert len(hits) == 1
    assert "beat-lint --emit" in hits[0] and "_順序.md" in hits[0]


def test_a_retired_rollup_is_not_compared_against_the_folder(tmp_path):
    """**內容不再被看**：漏列、幽靈列、幕號範圍不符、列序逆序——一律不報。

    這些曾是四個獨立的問題（`test_index_missing_a_row_fires` 等），而它們問的都是
    「這支已廢除的檔跟資料夾對不對得上」。那個問題不該再被問：唯一的答案是刪掉它。
    那份重算沒有消失，它在 `beat-lint --emit`（功能 12 抉擇 4 C 給它的家）。
    """
    broken = "\n".join(
        [
            "# 幕綱索引",
            "",
            "- 選用結構公式：卷一整體＝起承轉合",       # 沒指路（舊第 4 項）
            "- 全書順序：arc02 → arc01",
            "- arc02：幕101–幕101（號段 101–200）",     # 列序逆序（舊第 3 項）
            "- arc03：幕201–幕205（號段 201–300）",     # 幽靈列（舊第 1 項）
            "",
        ]
    )  # 且完全沒有 arc01 那一列（漏列）
    problems, _ = lint_report(_book(tmp_path, index=broken, arc01=ARC01, arc02=ARC02))
    for gone in ("沒有列", "指向不存在的 arc 檔", "列序非遞增", "沒有指向大綱層的路徑指標"):
        assert not _only(problems, gone), f"{gone} 不該再被報——那支檔已廢除"
    assert len(_only(problems, "已廢除的 rollup 還在")) == 1


def test_the_recomputation_moved_to_emit_not_away(tmp_path):
    """**射程非空**：拿掉比對不等於拿掉那份重算。

    「視圖 ≡ 資料夾」還在跑，只是改成**輸出**而不是**比對**——`beat-lint --emit`
    印的就是原本為了比對而算出來的那一份。這一支釘住它真的還印得出 arc 列，
    否則這一輪就是把一個守衛換成一句空話。
    """
    from beat_metrics.emit import emit_beats

    book = _book(tmp_path, index=None, arc01=ARC01, arc02=ARC02)
    text, _ = emit_beats(book)
    assert "arc01" in text and "arc02" in text


# --------------------------------------- 檔內書內路徑的目的地存在（功能 12 步驟 2）
#
# E1「目的地承諾」推論的第 7 個實例。射程＝`story/幕綱/*.md`，**含 `_index.md`**
# ——實測一世之尊那支檔的檔頭逐字寫著「arc 概覽同步自 `參照/結構.md`」，而該檔
# 2026-07-28（功能 11）已廢除，**零守衛**。


def test_dangling_book_path_in_the_index_fires(tmp_path):
    index = INDEX + "\n> arc 概覽同步自 `story/參照/結構.md`。\n"
    problems, stats = lint_report(_book(tmp_path, index, arc01=ARC01, arc02=ARC02))
    assert _only(problems, "`story/參照/結構.md`")
    assert stats.path_missing == 1


def test_dangling_book_path_in_an_arc_file_fires(tmp_path):
    arc = ARC02 + "\n## 設計註\n\n見 `story/設定/角色/不存在的人.md`。\n"
    problems, _ = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert _only(problems, "不存在的人.md")


def test_schema_and_placeholder_paths_are_not_destinations(tmp_path):
    """射程刻意窄（同 `outline-lint` 第 9 項）：不排除的話，一支完全合法的幕綱會
    因為引用了自己的 schema 而被報成目的地不存在。"""
    arc = ARC02 + (
        "\n> 依 `結構定義/幕綱.schema.md` 填寫；每個 arc 一支 `story/幕綱/arcNN.md`。\n"
    )
    problems, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert problems == []
    assert stats.path_missing == 0


def test_existing_book_paths_are_counted_not_reported(tmp_path):
    """覆蓋率行要能回答「我檢查了幾筆」——0 個問題不等於 0 筆檢查。"""
    arc = ARC02 + "\n> 見 `story/01-大綱.md`。\n"
    _, stats = lint_report(_book(tmp_path, arc01=ARC01, arc02=arc))
    assert stats.path_refs >= 1 and stats.path_missing == 0
