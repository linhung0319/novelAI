import pytest
from prose_metrics.drift import Finding, detect, summarize
from prose_metrics.metrics import (
    Chapter,
    MetricsError,
    chapter_metrics,
    group_sort_key,
    load_book_chapters,
    load_vocab,
    strip_scaffolding,
)

VOCAB = ["少年", "老僕", "同伴"]


def _ch(tmp_path, name, text, group="arc01"):
    p = tmp_path / f"{name}.md"
    p.write_text(text, encoding="utf-8")
    return Chapter(label=name, group=group, path=p)


def test_strips_scaffolding_from_char_count(tmp_path):
    body = "少年推門。\n\n老僕在。"
    ch = _ch(tmp_path, "ch0001", f"# ch0001 · 標題\n\n<!-- 幕001 -->\n\n{body}\n")
    m = chapter_metrics(ch, VOCAB)
    assert m.chars == len("少年推門。") + len("老僕在。")
    assert m.paragraphs == 2


def test_strips_old_style_inline_metadata(tmp_path):
    """舊版把 metadata 內嵌在 .md，不去掉會灌水字數、也會誤算角色。"""
    text = "# ch01 · x\n\n- 對應幕：[[幕001]]\n- 所屬 arc：arc01\n- POV：少年\n\n少年走了。\n"
    m = chapter_metrics(_ch(tmp_path, "ch01", text), VOCAB)
    assert m.chars == len("少年走了。")
    assert m.cast == 1  # POV 那行的「少年」不算


def test_counts_both_quote_conventions(tmp_path):
    ch = _ch(tmp_path, "c", "「甲」他說。\n“乙”她說。\n")
    assert chapter_metrics(ch, VOCAB).quotes == 2


def test_solo_chapter_detection(tmp_path):
    solo = _ch(tmp_path, "a", "少年一個人坐著，想了很久。")
    duo = _ch(tmp_path, "b", "少年看著老僕。")
    assert chapter_metrics(solo, VOCAB).solo is True
    assert chapter_metrics(duo, VOCAB).solo is False


def test_quote_density_normalises_by_length(tmp_path):
    short = chapter_metrics(_ch(tmp_path, "s", "「甲」" + "字" * 97), VOCAB)
    long = chapter_metrics(_ch(tmp_path, "l", "「甲」" + "字" * 997), VOCAB)
    assert short.quote_density > long.quote_density


@pytest.mark.parametrize(
    "names,expected",
    [
        (["卷一", "卷二", "卷三"], ["卷一", "卷二", "卷三"]),
        (["卷十", "卷二", "卷一"], ["卷一", "卷二", "卷十"]),
        (["part2", "part10", "part1"], ["part1", "part2", "part10"]),
    ],
)
def test_group_sort_handles_cjk_numerals(names, expected):
    """`三`(U+4E09) < `二`(U+4E8C)，中文數字不能用字典序排。"""
    assert sorted(names, key=group_sort_key) == expected


# ---------------------------------------------------------------- 漂移

def _stats(chars_per_group, quotes=10.0, cast=4.0, solo=0.1):
    rows = []
    for g, chars in chars_per_group.items():
        for i in range(4):
            rows.append(
                type(
                    "M",
                    (),
                    {
                        "group": g,
                        "chars": chars,
                        "quote_density": quotes,
                        "cast": cast,
                        "solo": i == 0 and solo > 0.2,
                        "label": f"{g}-{i}",
                    },
                )()
            )
    return summarize(rows)


def test_flat_book_has_no_drift():
    stats = _stats({"arc01": 3000, "arc02": 3000, "arc03": 2900, "arc04": 3100})
    findings, base = detect(stats)
    assert findings == [] and base is not None


def test_halved_length_fires():
    stats = _stats({"arc01": 3000, "arc02": 3000, "arc03": 3000, "arc04": 1200})
    findings, _ = detect(stats)
    assert any(f.metric == "篇幅" and f.group == "arc04" for f in findings)


def test_too_few_groups_means_no_baseline():
    findings, base = detect(_stats({"arc01": 3000, "arc02": 1000}))
    assert findings == [] and base is None


def test_cast_metrics_suppressed_when_vocab_absent():
    """詞彙表沒建時 cast 恆為 0、獨白章恆為 100%——報出來全是假的。"""
    stats = _stats({"a": 3000, "b": 3000, "c": 3000, "d": 3000}, cast=0.0)
    findings, _ = detect(stats)
    assert not any(f.metric in ("在場角色", "獨白章佔比") for f in findings)


def test_cast_metrics_suppressed_when_borrowed():
    stats = _stats({"a": 3000, "b": 3000, "c": 3000, "d": 3000}, cast=4.0)
    stats[-1] = stats[-1].__class__(**{**stats[-1].__dict__, "cast": 0.5})
    assert any(f.metric == "在場角色" for f in detect(stats)[0])
    assert not any(f.metric == "在場角色" for f in detect(stats, cast_metrics=False)[0])


# ---------------------------------------------------------------- 載入

def test_load_book_chapters_maps_arc_from_ai_md(tmp_path):
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "chapters" / "ch0001.md").write_text("正文", encoding="utf-8")
    (book / "chapters" / "ch0001.ai.md").write_text(
        "---\ngenerated-from: x\n所屬arc: arc07\n---\n", encoding="utf-8"
    )
    assert load_book_chapters(book)[0].group == "arc07"


def test_load_book_chapters_falls_back_to_inline_arc(tmp_path):
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "chapters" / "ch01.md").write_text("- 所屬 arc：arc03\n\n正文", encoding="utf-8")
    assert load_book_chapters(book)[0].group == "arc03"


def test_missing_chapters_dir_raises(tmp_path):
    with pytest.raises(MetricsError):
        load_book_chapters(tmp_path / "nope")


def test_vocab_skips_derived_and_index(tmp_path):
    book = tmp_path / "book"
    d = book / "story" / "設定" / "角色"
    d.mkdir(parents=True)
    (d / "少年.md").write_text("x", encoding="utf-8")
    (d / "少年.ai.md").write_text("x", encoding="utf-8")
    (d / "_index.ai.md").write_text("x", encoding="utf-8")
    assert load_vocab(book) == ["少年"]
