from derived_sync.sentinel import (
    beat_sheet_density,
    long_lines,
    oversized_sources,
    run,
)


def _beats(n: int, filler: int) -> str:
    out = ["# arcNN\n"]
    for i in range(1, n + 1):
        out.append(f"## 幕{i:03d} · x\n- 角色：少年\n- 行動：{'字' * filler}\n")
    return "\n".join(out)


def _book(tmp_path):
    book = tmp_path / "book"
    (book / "story" / "幕綱").mkdir(parents=True)
    (book / "story" / "設定" / "角色").mkdir(parents=True)
    (book / "story" / "參照").mkdir(parents=True)
    return book


def test_lean_beat_sheet_is_clean(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc01.md").write_text(_beats(10, 100), encoding="utf-8")
    assert beat_sheet_density(book) == []


def test_bloated_beat_sheet_fires(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc09.md").write_text(_beats(10, 3000), encoding="utf-8")
    findings = beat_sheet_density(book)
    assert len(findings) == 1 and findings[0].kind == "幕綱肥大"


def test_non_arc_files_in_beat_dir_ignored(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "_index.md").write_text("巨" * 50000, encoding="utf-8")
    assert beat_sheet_density(book) == []


def test_oversized_source_uses_absolute_not_median(tmp_path):
    """承重角色本來就該比路人厚——中位數比值會把主角每次都報出來，那是雜訊。"""
    book = _book(tmp_path)
    d = book / "story" / "設定" / "角色"
    for name in ("路人甲", "路人乙", "路人丙"):
        (d / f"{name}.md").write_text("短", encoding="utf-8")
    (d / "主角.md").write_text("字" * 5000, encoding="utf-8")  # 15KB，遠高於中位數但合理
    assert oversized_sources(book) == []
    (d / "超巨.md").write_text("字" * 10000, encoding="utf-8")  # 30KB，過絕對門檻
    assert [f.path.stem for f in oversized_sources(book)] == ["超巨"]


def test_derived_and_index_files_not_checked_as_sources(tmp_path):
    book = _book(tmp_path)
    d = book / "story" / "設定" / "角色"
    (d / "某角.ai.md").write_text("字" * 20000, encoding="utf-8")
    (d / "_index.ai.md").write_text("字" * 20000, encoding="utf-8")
    assert oversized_sources(book) == []


def test_long_line_fires_on_status_cell(tmp_path):
    book = _book(tmp_path)
    p = book / "story" / "參照" / "就緒儀表.md"
    p.write_text("| 主線 | " + "沿" * 3000 + " |\n短短一行\n", encoding="utf-8")
    findings = long_lines(book)
    assert len(findings) == 1 and "3000" in findings[0].detail or findings[0].detail


def test_append_log_with_short_lines_is_clean(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "參照" / "狀態事件流.md").write_text(
        "\n".join(f"- 幕{i:03d}（arc01）· 少年 · 持有：東西{i}" for i in range(500)),
        encoding="utf-8",
    )
    assert long_lines(book) == []


def test_run_aggregates(tmp_path):
    book = _book(tmp_path)
    (book / "story" / "幕綱" / "arc09.md").write_text(_beats(5, 3000), encoding="utf-8")
    (book / "story" / "參照" / "結構.md").write_text("巨" * 5000 + "\n", encoding="utf-8")
    kinds = {f.kind for f in run(book)}
    assert kinds == {"幕綱肥大", "狀態格過長"}


def test_missing_dirs_do_not_crash(tmp_path):
    assert run(tmp_path / "nonexistent") == []
