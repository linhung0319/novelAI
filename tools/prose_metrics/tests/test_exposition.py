from pathlib import Path

import pytest
from prose_metrics.exposition import (
    ExpoStat,
    detect_exposition,
    scan_chapter,
    summarize_exposition,
)
from prose_metrics.metrics import Chapter, load_book_chapters, load_plain_chapters

REPO = Path(__file__).resolve().parents[3]


def _ch(tmp_path, text, name="ch0001", group="arc01"):
    p = tmp_path / f"{name}.md"
    p.write_text(text, encoding="utf-8")
    return scan_chapter(Chapter(label=name, group=group, path=p))


# ---------------------------------------------------------------- 段級命中

def test_m1_hits(tmp_path):
    """「這句是留的活話」＝回指剛才那句話 ＋ 宣告它的用途。"""
    r = _ch(tmp_path, "——這句是留的活話。既解釋了他為什麼像個木頭，又給日後留了個由頭。")
    assert [c.kinds for c in r.paragraph] == [("自指回述",)]


def test_m2_hits(tmp_path):
    r = _ch(tmp_path, "他把這兩樣擺清楚，得出一個乾乾淨淨的結論：他沒有性命之危。")
    assert [c.kinds for c in r.paragraph] == [("元認知結算",)]


def test_plain_action_paragraph_is_not_a_candidate(tmp_path):
    r = _ch(tmp_path, "他推開門，走進院子，把油壺擱在石階上，抬頭看了看天色。")
    assert r.paragraph == ()


def test_dialogue_paragraph_excluded_for_all_three_quote_styles(tmp_path):
    """原著用彎引號、芯片巫師用【】、生成版用「」——只寫「」會讓 known-good 誤報。"""
    body = "他把這兩樣擺清楚，得出一個乾乾淨淨的結論。"
    for open_q, close_q in (("「", "」"), ("“", "”"), ("【", "】")):
        r = _ch(tmp_path, f"{open_q}我早就跟你說過了{close_q}他說。{body}")
        assert r.paragraph == (), f"{open_q}{close_q} 未被當成對白排除"


def test_short_quoted_word_is_not_dialogue(tmp_path):
    """「想不起事」是引用詞不是對白——不該讓整段逃掉。"""
    r = _ch(tmp_path, "——這句是留的活話，既解釋了他，又給日後「想不起事」留了個由頭。")
    assert len(r.paragraph) == 1


def test_short_paragraph_excluded(tmp_path):
    assert _ch(tmp_path, "他盤算著。").paragraph == ()


def test_scaffolding_not_scanned(tmp_path):
    """幕錨點與標題不是散文，不該計入字數，也不該被掃。"""
    r = _ch(tmp_path, "# ch0001 · 這句是留的活話的一手\n\n<!-- 幕001 -->\n\n他推開門。")
    assert r.paragraph == ()
    assert r.chars == len("他推開門。")


# ---------------------------------------------------------------- 句級（低產出）

def test_reflex_only_counts_at_paragraph_end(tmp_path):
    tail = _ch(tmp_path, "他望著那扇門，看了很久很久。他終於明白了。")
    mid = _ch(tmp_path, "他終於明白了，於是抬手推開門，走進滿是灰塵的院子裡去。")
    assert len(tail.sentence) == 1
    assert mid.sentence == ()


def test_bare_finally_plus_physical_action_is_not_reflex(tmp_path):
    """裸的「他終於」會誤中物理動作——頓悟動詞必須是認知動詞。"""
    assert _ch(tmp_path, "他站在原地等了半晌，他終於轉過頭。").sentence == ()


# ---------------------------------------------------------------- 密度與漂移

def _stat(group, hits, chars=10_000):
    return ExpoStat(group=group, chapters=5, chars=chars, paragraph_hits=hits, sentence_hits=0)


def test_density_is_normalised_by_length():
    """篇幅腰斬時絕對數會騙人：一樣 3 條候選，半本篇幅＝兩倍密度。"""
    assert _stat("a", 3, chars=10_000).density == pytest.approx(0.3)
    assert _stat("a", 3, chars=5_000).density == pytest.approx(0.6)


def test_flat_density_has_no_finding():
    stats = [_stat(g, 3) for g in ("arc01", "arc02", "arc03", "arc04")]
    findings, base = detect_exposition(stats)
    assert findings == [] and base == pytest.approx(0.3)


def test_doubled_density_fires():
    stats = [_stat(g, 3) for g in ("arc01", "arc02", "arc03")] + [_stat("arc04", 7)]
    findings, _ = detect_exposition(stats)
    assert [f.group for f in findings] == ["arc04"]
    assert "2.3 倍" in findings[0].detail


def test_below_floor_does_not_fire_even_at_high_ratio():
    """基準 0.00 時倍率無意義——樓地板是唯一擋得住雜訊的東西（原著卷一＝0）。"""
    stats = [_stat(g, 0) for g in ("卷一", "卷二")] + [_stat("卷三", 1, chars=100_000)]
    findings, base = detect_exposition(stats)
    assert base == 0.0 and findings == []


def test_zero_baseline_still_fires_above_floor():
    stats = [_stat(g, 0) for g in ("卷一", "卷二")] + [_stat("卷三", 5)]
    findings, _ = detect_exposition(stats)
    assert [f.group for f in findings] == ["卷三"]
    assert "基準 0.00" in findings[0].detail


def test_too_few_groups_means_no_baseline():
    findings, base = detect_exposition([_stat("a", 1), _stat("b", 9)])
    assert findings == [] and base is None


def test_summarize_preserves_group_order(tmp_path):
    rows = [_ch(tmp_path, "他推開門。", name=n, group=g)
            for n, g in (("c1", "arc02"), ("c2", "arc01"), ("c3", "arc02"))]
    stats = summarize_exposition(rows)
    assert [s.group for s in stats] == ["arc02", "arc01"]
    assert stats[0].chapters == 2


# ---------------------------------------------------------------- 三組語料回歸
#
# 這幾個數字是 R4 的立論基礎，刻意釘死：段級規則分離度 44 倍，而舊的句級詞表
# 是**反相關**的。日後若有人想把句級詞表升回主訊號，這裡會擋下來。

_KNOWN_GOOD = REPO / "examples" / "一世之尊"
_KNOWN_BAD = REPO / "一世之尊"
_CONTROL = REPO / "芯片巫師"

needs_corpora = pytest.mark.skipif(
    not (_KNOWN_GOOD.is_dir() and _KNOWN_BAD.is_dir() and _CONTROL.is_dir()),
    reason="回歸語料不在（本測試需要 repo 內的凍結 fixture）",
)


def _scan(chapters):
    rows = [scan_chapter(c) for c in chapters]
    stats = summarize_exposition(rows)
    return rows, stats, detect_exposition(stats)[0]


@needs_corpora
def test_known_good_stays_clean():
    _, stats, findings = _scan(load_plain_chapters(_KNOWN_GOOD))
    assert findings == []
    assert max(s.density for s in stats) <= 0.01


@needs_corpora
def test_known_bad_is_reported():
    rows, stats, findings = _scan(load_book_chapters(_KNOWN_BAD))
    assert {f.group for f in findings} == {"arc06", "arc10", "arc11"}
    total = sum(s.paragraph_hits for s in stats) * 1000 / sum(s.chars for s in stats)
    assert total > 0.3  # 原著 0.008 的 40 倍以上
    hits = {(c.label, c.text) for r in rows for c in r.paragraph}
    assert any(l == "ch0001" and "這句是留的活話" in t for l, t in hits)
    assert any(l == "ch0080" and "擺清楚" in t for l, t in hits)


@needs_corpora
def test_control_group_not_falsely_reported():
    _, stats, findings = _scan(load_book_chapters(_CONTROL))
    assert findings == []
    assert [round(s.density, 2) for s in stats] == sorted(
        (round(s.density, 2) for s in stats), reverse=True
    )  # 遞減，不是漂移


@needs_corpora
def test_sentence_level_wordlist_is_anticorrelated():
    """句級詞表在健康語料上比病態語料上響得更多——這就是 R4 的論點。"""
    _, good, _ = _scan(load_plain_chapters(_KNOWN_GOOD))
    _, bad, _ = _scan(load_book_chapters(_KNOWN_BAD))
    good_density = sum(s.sentence_hits for s in good) * 1000 / sum(s.chars for s in good)
    bad_density = sum(s.sentence_hits for s in bad) * 1000 / sum(s.chars for s in bad)
    assert good_density > bad_density
    # 對照：同一組語料上，段級規則的方向是相反的
    good_para = sum(s.paragraph_hits for s in good) * 1000 / sum(s.chars for s in good)
    bad_para = sum(s.paragraph_hits for s in bad) * 1000 / sum(s.chars for s in bad)
    assert bad_para > good_para * 20
