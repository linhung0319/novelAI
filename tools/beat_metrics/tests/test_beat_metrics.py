"""回歸案例。

`tests/fixtures/` 是一世之尊 **2026-07-26 遷移前**的 arc01（known-good）與 arc11
（known-bad）原樣複本。診斷01／02 的病例現場凍結在這裡——書內檔之後會依新 schema
被遷移，這兩份不跟著動，否則「改好了」與「量壞了」就分不出來。

比照 `prose_metrics/tests/test_rhythm.py` 把《極道天魔》釘死的用意：**防止日後有人
把判準往任一邊調到失去鑑別力**。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from beat_metrics.motif import detect, measure
from beat_metrics.playability import HOLLOW_SHARE_CAP, analyse
from beat_metrics.scan import MOTIF_FIELDS, PROSE_FIELDS, load_pov, scan_arc

FIX = Path(__file__).parent / "fixtures"
POV = "孟奇"


@pytest.fixture
def good():
    return scan_arc(FIX / "arc01_known_good.md", "arc01")


@pytest.fixture
def bad():
    return scan_arc(FIX / "arc11_known_bad.md", "arc11")


# ------------------------------------------------------------------ scan

def test_scan_reads_all_eight_fields(good):
    assert len(good.beats) == 9
    b = good.beats[0]
    assert b.number == 1
    assert "馬臉管家" in b.fields["角色"]
    assert "二少爺" in b.fields["行動"]
    assert b.fields["結構階段"].startswith("起")


def test_scan_skips_non_beat_sections(bad):
    """「## 本 arc 伏筆狀態」等小節不是幕，其表格列不得混進欄位。"""
    assert len(bad.beats) == 11
    assert all(1001 <= b.number <= 1011 for b in bad.beats)


def test_prose_excludes_link_fields(bad):
    """`前因`／`伏筆` 是結構化連結欄，不進任何母體（見 scan.PROSE_FIELDS）。"""
    assert "前因" not in PROSE_FIELDS and "伏筆" not in PROSE_FIELDS
    beat = next(b for b in bad.beats if b.number == 1011)
    assert "[[幕1009]]" in beat.fields["前因"]
    assert "[[幕1009]]" not in beat.prose


def test_motif_body_also_excludes_cast(bad):
    """`角色` 是名單不是散文：主角每幕都要列，那是 schema 樣板不是母題迴圈。

    未排除時 arc11 重複前五名有兩名是角色欄樣板（「心裡不在場」「孟奇真定妙音」）。
    """
    assert "角色" in PROSE_FIELDS and "角色" not in MOTIF_FIELDS
    beat = next(b for b in bad.beats if b.number == 1002)
    assert "妙音" in beat.fields["角色"]
    assert beat.fields["角色"] not in beat.motif_body


# ------------------------------------------------- playability (可演性)

def test_known_good_arc_has_no_hollow_beats(good):
    """arc01 有 2 幕主角獨處，但兩幕都有鏡頭拍得到的行為＝不是空洞幕。

    這正是「(b) 純內在幕單獨判會誤傷」的證據——診斷02 §3 手數成 0/9，實際是 2/9。
    """
    p = analyse(good, POV)
    assert len(p.solo_beats) == 2
    assert p.hollow_beats == []
    assert p.hollow_share == 0.0
    assert p.hollow_runs == []


def test_known_bad_arc_lights_up(bad):
    p = analyse(bad, POV)
    assert len(p.solo_beats) == 6  # 與診斷01／02 手數的 6/11 一致
    assert p.hollow_beats == [1001, 1007, 1008, 1010, 1011]
    assert p.hollow_share > HOLLOW_SHARE_CAP
    assert [(r[0], r[-1]) for r in p.hollow_runs] == [(1007, 1008), (1010, 1011)]


def test_hollow_needs_both_conditions(bad):
    """空洞＝獨處 ∧ 行動欄命中禁止詞。少任一個都不算。"""
    flags = {f.beat: f for f in analyse(bad, POV).flags}
    assert flags[1009].banned and not flags[1009].solo  # 有對手在場 → 不空洞
    assert not flags[1009].hollow
    assert flags[1011].solo and flags[1011].banned and flags[1011].hollow


def test_absent_markers_do_not_hide_present_opponents():
    """`（帶隊執事·因故不在場／被調開；背景：無退步步進逼）`——分號子群要逐一判，
    整組丟掉會把還在場的對手一起丟掉。"""
    from beat_metrics.playability import _others

    cast = "孟奇（真定）、（帶隊執事·因故不在場／被調開；背景：無退步步進逼）"
    assert _others(cast, POV) != []


def test_solo_needs_pov_and_never_guesses(bad):
    """讀不到主角時一律不判空洞，不猜。"""
    p = analyse(bad, None)
    assert p.solo_beats == [] and p.hollow_beats == []


def test_meta_hygiene_ignores_narrative_arc_hooks(good, bad):
    """`結果` 欄的「接 arc02 輪回世界啟動」是故事事實；「與 arcNN 刻意成對比」才是設計理由。

    裸 `arc\\d` 會把 known-good 的 arc01 也報進去，分區衛生因此失去鑑別力。
    """
    assert analyse(good, POV).meta_beats == []
    assert len(analyse(bad, POV).meta_beats) == 4


# ------------------------------------------------------- motif (P10)

def test_motif_repeat_separates_good_from_bad(good, bad):
    g = measure(good, analyse(good, POV).action_mean)
    b = measure(bad, analyse(bad, POV).action_mean)
    assert g.repeat_rate == pytest.approx(4.6, abs=0.5)
    assert b.repeat_rate == pytest.approx(87.7, abs=1.0)
    assert b.repeat_rate > g.repeat_rate * 10  # 11 倍量級，別讓判準退化到分不開


def test_action_column_inflation(good, bad):
    assert analyse(good, POV).action_mean == pytest.approx(76, abs=3)
    assert analyse(bad, POV).action_mean == pytest.approx(355, abs=5)


def test_detect_is_relative_and_needs_a_baseline(good, bad):
    """判準相對本書前段（同 prose_metrics/drift.py）；arc 數不足時不談漂移。"""
    g = measure(good, 76.0)
    b = measure(bad, 355.0)
    assert detect([g, b]) == ([], None)  # 只有兩個 arc → 沒有基準可比

    findings, base = detect([g, g, b])
    assert base is not None
    metrics = {f.metric for f in findings}
    assert metrics == {"母題重複率", "行動欄長度"}
    assert all(f.arc == "arc11" for f in findings)


def test_hot_grams_surface_the_actual_motif(bad):
    """熱詞要指得出是哪個母題在迴圈，而不是「見伏筆狀態表」這種格式殘渣。"""
    hot = "".join(g for _, g in measure(bad, 355.0).hot)
    assert "伏筆狀態" not in hot


# ------------------------------------------------------------- load_pov

def test_load_pov_reads_summary_front_matter():
    """**找不到書就 fail，不 skip。**

    2026-07-27 前這裡是 `pytest.skip("需要書資料夾")`——而一個會自己 skip 掉的測試，
    正是功能 02 這一輪要修掉的那一類守衛：它跑了、它報綠燈、而它什麼都沒檢查
    （`設計原則.md` E2 第五格）。病例書是這支測試的全部語料，不在就是真的壞了。
    """
    book = Path(__file__).resolve().parents[3] / "一世之尊"
    summary = book / "story" / "00-摘要.ai.md"
    assert summary.is_file(), f"病例書的摘要不在 {summary}——它是這支測試的全部語料"
    assert load_pov(book) == POV


def test_load_pov_returns_none_when_absent(tmp_path):
    assert load_pov(tmp_path) is None
