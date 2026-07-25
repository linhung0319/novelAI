import statistics
from pathlib import Path

import pytest
from prose_metrics.metrics import Chapter, load_book_chapters, load_plain_chapters
from prose_metrics.rhythm import (
    DASH_CAP,
    ECHO_CAP,
    JOLT_CAP,
    SPP_CAP,
    combine,
    detect_rhythm,
    scan_rhythm,
    summarize_rhythm,
)

REPO = Path(__file__).resolve().parents[3]


def _ch(tmp_path, text, name="ch0001", group="arc01", drop_title=False):
    p = tmp_path / f"{name}.md"
    p.write_text(text, encoding="utf-8")
    return scan_rhythm(Chapter(label=name, group=group, path=p), drop_title=drop_title)


def _paras(*items):
    return "\n\n".join(items)


LONG = "他推開門走進院子把油壺擱在石階上抬頭看了看天色院裡的雪還沒化乾淨牆根下堆著半人高的柴他數了數又數了一遍" * 2


# ---------------------------------------------------------------- 破折號

def test_consecutive_dash_counts_once(tmp_path):
    """`——` 記 1 不記 2——否則中文的標準用法會被算成兩倍。"""
    assert _ch(tmp_path, "他站住了——沒有回頭。").dashes == 1


def test_dash_variants_and_single_hyphen(tmp_path):
    """三種橫線與 `--` 都算；單個 `-` 是連字號，不算。"""
    assert _ch(tmp_path, "甲—乙─丙―丁--戊").dashes == 4
    assert _ch(tmp_path, "他叫 A-1 號。").dashes == 0


# ---------------------------------------------------------------- 顛簸

def test_jolt_needs_a_long_neighbour(tmp_path):
    """短段本身不是病，短段**緊鄰長段**才是——那是一次完全煞車。"""
    assert _ch(tmp_path, _paras(LONG, "他站住了。", LONG)).jolts == 1
    assert _ch(tmp_path, _paras("他站住了。", "他抬起頭。", "他走了。")).jolts == 0


def test_dialogue_and_lead_in_are_not_jolts(tmp_path):
    """台詞短是正常的；`某某冷笑道：` 是版式不是節拍（見 _LEAD_IN 的實測理由）。"""
    assert _ch(tmp_path, _paras(LONG, "「你來了。」", LONG)).jolts == 0
    assert _ch(tmp_path, _paras(LONG, "老周冷笑道：", LONG)).jolts == 0


def test_zero_cjk_paragraph_is_not_a_jolt(tmp_path):
    """`……` 分隔行與作者按語不是斷片段，是排版（從紅月開始 0.36→0.15 的差額）。"""
    assert _ch(tmp_path, _paras(LONG, "……", LONG)).jolts == 0


# ---------------------------------------------------------------- 回聲斷片

def test_echo_needs_every_chunk_in_the_previous_paragraphs(tmp_path):
    """整段每一塊都在前文出現過＝把剛說過的話複製成一個無資訊的重拍。"""
    prev = "老奴給您討碗熱薑湯，二少爺您忍忍，前頭拐過山就到了。"
    assert _ch(tmp_path, _paras(prev, "薑湯。二少爺。老奴。")).echoes == 1
    assert _ch(tmp_path, _paras(prev, "薑湯。二少爺。馬車。")).echoes == 0


def test_exclamation_and_question_fragments_are_exempt(tmp_path):
    """擬聲與驚呼帶新的語氣行為；病徵是平述句的重述。少了這條指標就廢掉。"""
    prev = "轟隆一道閃電劈落，盡數附于刀身，地面電光亂閃，雪花消融騰起白霧。"
    assert _ch(tmp_path, _paras(prev, "轟隆！")).echoes == 0
    assert _ch(tmp_path, _paras(prev, "轟隆。")).echoes == 1


def test_single_char_chunk_does_not_count(tmp_path):
    assert _ch(tmp_path, _paras("他走了很久很久。", "他。")).echoes == 0


def test_echo_lookback_is_three_paragraphs(tmp_path):
    far = _paras("他討了碗薑湯。", LONG, LONG, LONG, "薑湯。")
    near = _paras("他討了碗薑湯。", LONG, LONG, "薑湯。")
    assert _ch(tmp_path, far).echoes == 0
    assert _ch(tmp_path, near).echoes == 1


# ---------------------------------------------------------------- 前處理

def test_scaffolding_not_counted(tmp_path):
    """幕錨點與標題不是散文——不計漢字、不當段落。"""
    r = _ch(tmp_path, "# ch0001 · 標題\n\n<!-- 幕001 -->\n\n他推開門。")
    assert r.cjk == len("他推開門")
    assert r.dashes == 0


def test_drop_title_only_for_plain_corpus(tmp_path):
    """`examples/*.txt` 首行是章名、沒有 `#`，strip_scaffolding 去不掉。"""
    text = _paras("第001章 機心", LONG, "他站住了。", LONG)
    assert _ch(tmp_path, text, drop_title=False).cjk > _ch(tmp_path, text, drop_title=True).cjk


# ---------------------------------------------------------------- 輔助量

def test_sentence_split_keeps_closing_quote_with_its_sentence(tmp_path):
    """句末標點後若接收尾引號，不切——否則每句台詞都會被算成兩句，句長中位失真。"""
    assert len(_ch(tmp_path, "「你來了。」他說。").sent_lens) == 1
    assert len(_ch(tmp_path, "他來了。他說。").sent_lens) == 2


def test_long_sentence_share_is_by_character_not_by_sentence(tmp_path):
    """問的是「多少字活在長句裡」——原著六成，生成版倒過來。"""
    r = _ch(tmp_path, _paras("短。", "短。", "他" * 60 + "。"))
    assert r.sent_lens.count(1) == 2
    stat = combine([r], "x")
    assert stat.long_sent_share > 0.9


# ---------------------------------------------------------------- detect

def _stat(group, cjk=10_000, dashes=0, jolts=0, echoes=0, short=100, sents=0, paras=300):
    from prose_metrics.rhythm import RhythmStat

    return RhythmStat(
        group=group, chapters=5, cjk=cjk, paras=paras, dashes=dashes, jolts=jolts,
        echoes=echoes, short_paras=short, sent_lens=(10,) * sents, clause_lens=(),
        commas=0, periods=0,
    )


def test_clean_stat_has_no_finding():
    assert detect_rhythm([_stat("arc01", dashes=3, jolts=2, echoes=1)]) == []


def test_each_threshold_fires_independently():
    assert [f.metric for f in detect_rhythm([_stat("a", dashes=60)])] == ["破折號密度"]
    assert [f.metric for f in detect_rhythm([_stat("a", jolts=40)])] == ["顛簸指數"]
    assert [f.metric for f in detect_rhythm([_stat("a", echoes=5)])] == ["回聲斷片"]
    assert [f.metric for f in detect_rhythm([_stat("a", sents=600)])] == ["句/段"]


def test_echo_share_is_suppressed_on_thin_samples():
    """短段本來就少的書分母極小，一兩條就衝破門檻——樣本不足時不報。"""
    assert detect_rhythm([_stat("a", echoes=3, short=5)]) == []
    assert len(detect_rhythm([_stat("a", echoes=12, short=20)])) == 1


def test_thresholds_are_absolute_not_relative():
    """與 drift.detect 的分工：這三項不需要基準分組，單一分段就能判。"""
    assert len(detect_rhythm([_stat("only", dashes=60)])) == 1


# ---------------------------------------------------------------- 三組語料回歸
#
# 這些數字是 P8 的立論基礎，刻意釘死。日後若有人放寬 `_is_beat` 或 `_ECHO_EXEMPT_END`，
# known-good 會先在這裡爆掉——那兩條的實測理由寫在 rhythm.py，別繞過去。

_CORPUS = REPO / "examples"
_KNOWN_BAD = REPO / "一世之尊"
_CONTROL = REPO / "芯片巫師"
_SIX = ["一世之尊", "詭秘之主", "極道天魔", "神秀之主", "從紅月開始", "我有一個修仙世界"]

needs_corpora = pytest.mark.skipif(
    not (_CORPUS.is_dir() and _KNOWN_BAD.is_dir() and _CONTROL.is_dir()),
    reason="回歸語料不在（本測試需要 repo 內的凍結 fixture）",
)


def _corpus_stats(book):
    rows = [scan_rhythm(c, drop_title=True) for c in load_plain_chapters(_CORPUS / book)]
    return summarize_rhythm(rows)


def _book_stats(path):
    return summarize_rhythm([scan_rhythm(c) for c in load_book_chapters(path)])


@needs_corpora
@pytest.mark.parametrize("book", _SIX)
def test_known_good_corpora_stay_clean(book):
    """六本橫跨四個文類的好讀網文，三項簽名全部落在門檻內——這就是「普世地板」的證據。"""
    assert detect_rhythm(_corpus_stats(book)) == []


@needs_corpora
def test_known_good_band_is_narrow():
    stats = [s for b in _SIX for s in _corpus_stats(b)]
    assert max(s.dash_density for s in stats) <= 0.40
    assert max(s.jolt_index for s in stats) <= 0.25
    assert max(s.echo_share for s in stats) <= 0.01


@needs_corpora
def test_known_bad_is_reported_on_every_arc():
    stats = _book_stats(_KNOWN_BAD)
    findings = detect_rhythm(stats)
    assert {f.group for f in findings} == {s.group for s in stats}  # 11 個 arc 無一倖免
    assert min(s.dash_density for s in stats) > 6.0  # 語料 max 的 15 倍以上
    assert min(s.jolt_index for s in stats) > 1.8


@needs_corpora
def test_control_book_shows_the_same_signature():
    """另一本書、另一份風格檔、另一個文類，簽名一模一樣——所以病因不在風格檔。"""
    stats = _book_stats(_CONTROL)
    assert {f.group for f in detect_rhythm(stats)} == {s.group for s in stats}
    assert min(s.dash_density for s in stats) > 6.0
    assert min(s.jolt_index for s in stats) > 1.5


@needs_corpora
def test_one_sentence_per_paragraph_is_the_corpus_norm():
    """句/段：六本 ≈1（段落就是句子），生成書 1.41–2.33——**第四項絕對門檻**。

    生成版的形狀是「多句擠成的密集長段 ＋ 夾在中間的斷片段」，長短在段落級擺盪；
    語料通篇同一顆粒度，沒有可擺盪的空間。第一輪從語料反推得到（診斷03 未載），
    第二輪升為門檻——它是三項簽名之外唯一還有零重疊的量。
    """
    good = [s for b in _SIX for s in _corpus_stats(b)]
    gen = _book_stats(_KNOWN_BAD) + _book_stats(_CONTROL)
    assert max(s.sent_per_para for s in good) < SPP_CAP
    assert min(s.sent_per_para for s in gen) > SPP_CAP


@needs_corpora
@pytest.mark.parametrize("book", _SIX)
def test_paragraph_density_never_fires_on_known_good(book):
    """第四項門檻的餘裕比前三項窄（上緣 1.08×），所以逐本釘死而不只看合計。"""
    assert not [f for f in detect_rhythm(_corpus_stats(book)) if f.metric == "句/段"]


@needs_corpora
def test_paragraph_density_fires_on_every_generated_group():
    for book in (_KNOWN_BAD, _CONTROL):
        stats = _book_stats(book)
        fired = {f.group for f in detect_rhythm(stats) if f.metric == "句/段"}
        assert fired == {s.group for s in stats}


@needs_corpora
def test_sentence_length_dispersion_does_not_separate():
    """**釘死一個負面結果**：「該長的地方沒放長」做不成第五項門檻。

    第二輪問過能不能用長句佔比或句長離散度抓「通篇均勻的中等長度」。答案是不能。
    這四個量都得做成**下限**（「至少要有這麼多長句／這麼大變異」），而實測顯示
    **每一個生成分段都不低於 known-good 的下緣**——任何抓得到生成書的下限，都會
    先誤傷《極道天魔》。六本自己的長句字數佔比就從 17% 到 54%，這是文類自由的量。

    這個測試存在的唯一理由，是防止日後有人重試「長句下限」——那會誤傷極道型，
    也會把 `行文節奏與呼吸.md` 誤讀成「寫長一點」。真正的抓手是 句/段（見上一個
    測試）：段落裡的材料本來就夠，只是在句號那一級被切開了。
    """
    def dispersion(s):
        lens = sorted(s.sent_lens)
        med = statistics.median(lens)
        total = sum(lens)
        return {
            "≥40字句字數佔比": s.long_sent_share,
            "≥1.5×中位字數佔比": sum(n for n in lens if n >= 1.5 * med) / total,
            "變異係數": statistics.pstdev(lens) / statistics.mean(lens),
            "p90/中位": lens[int(len(lens) * 0.90)] / med,
        }

    good = [dispersion(s) for b in _SIX for s in _corpus_stats(b)]
    gen = [dispersion(s) for s in _book_stats(_KNOWN_BAD) + _book_stats(_CONTROL)]
    for axis in good[0]:
        floor = min(g[axis] for g in good)  # 不誤傷語料的下限最多只能訂到這裡
        assert min(x[axis] for x in gen) >= floor, f"{axis} 竟然分得開，回頭看檔頭那張表"


@needs_corpora
def test_no_overlap_between_good_and_generated():
    """兩組之間沒有重疊區——絕對門檻因此成立，這是它與 drift.py 相對判準的分野。"""
    good = [s for b in _SIX for s in _corpus_stats(b)]
    bad = _book_stats(_KNOWN_BAD) + _book_stats(_CONTROL)
    assert max(s.dash_density for s in good) < min(s.dash_density for s in bad)
    assert max(s.jolt_index for s in good) < min(s.jolt_index for s in bad)


@needs_corpora
def test_short_is_not_the_crime():
    """《極道天魔》比生成版更短更碎，卻在 known-good 名單裡。

    判準不是「句子要長」——這個測試存在的唯一理由，就是防止日後有人把本檔誤讀成那樣。
    """
    ji = _corpus_stats("極道天魔")[0]
    ysz = _book_stats(_KNOWN_BAD)
    six = [s for b in _SIX for s in _corpus_stats(b)]
    # 六本裡最短的一本：句長中位與長句字數佔比雙雙墊底
    assert ji.sent_median == min(s.sent_median for s in six)
    assert ji.long_sent_share == min(s.long_sent_share for s in six)
    # 而且比**每一個**生成 arc 還少字活在長句裡、句長中位落在生成版的區間內
    assert ji.long_sent_share < min(s.long_sent_share for s in ysz)
    assert ji.sent_median <= max(s.sent_median for s in ysz)
    assert detect_rhythm([ji]) == []  # 四項簽名仍全清（含 句/段 1.17）


@needs_corpora
def test_the_difference_is_punctuation_level_not_phrase_length():
    """分句長度兩邊接近，句長差一倍——差別在該用逗號的地方用了句號。"""
    orig = _corpus_stats("一世之尊")
    gen = _book_stats(_KNOWN_BAD)
    o_clause = sum(s.clause_mean for s in orig) / len(orig)
    g_clause = sum(s.clause_mean for s in gen) / len(gen)
    assert abs(o_clause - g_clause) < 2.0  # 分句層接近
    assert min(s.sent_median for s in orig) > max(s.sent_median for s in gen)  # 句層差一倍
    assert min(s.comma_period for s in orig) > 1.8 * max(s.comma_period for s in gen)


@needs_corpora
def test_thresholds_sit_in_the_gap():
    """門檻不是拍腦袋：四項都落在 known-good max 與生成 min 之間。

    句/段 的縫最窄（1.25 → 1.35 → 1.41，上下各只有 1.08×／1.04×），這是接受它
    當門檻時就知道的取捨，理由寫在 `SPP_CAP` 上。
    """
    good = [s for b in _SIX for s in _corpus_stats(b)]
    bad = _book_stats(_KNOWN_BAD)
    assert max(s.dash_density for s in good) < DASH_CAP < min(s.dash_density for s in bad)
    assert max(s.jolt_index for s in good) < JOLT_CAP < min(s.jolt_index for s in bad)
    assert max(s.sent_per_para for s in good) < SPP_CAP < min(s.sent_per_para for s in bad)
    assert max(s.echo_share for s in good) < ECHO_CAP
