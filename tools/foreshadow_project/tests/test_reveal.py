"""揭示層級（原 🧊 水下）：單一語法、四種結果、以及「我掃到幾處」。

**這支測試檔在 2026-07-27 之前不存在**，那正是那個 bug 能活下來的原因：🧊 這條路
一行測試都沒有，於是「schema 授權三種語法而工具只認一種」沒有任何東西會發現，而
`foreshadow-project` 對 92 次出現印「0 條為可疑點」exit 0。
"""

import pytest
from foreshadow_project.cli import format_report
from foreshadow_project.project import build

INDEX = "# 幕綱索引\n- 全書順序：arc01 → arc02\n"

ARC01 = """\
# arc01

## 幕001 · 起
- 角色：少年
- 伏筆：埋[[伏筆:舊玉來歷]]／埋[[伏筆:母親的信]]

## 幕002 · 收一條
- 角色：少年
- 伏筆：收[[伏筆:舊玉來歷]]
"""

ARC02 = "# arc02\n\n## 幕101 · 略\n- 角色：少年\n- 伏筆：—\n"


def _book(tmp_path, objects: dict[str, str] | None = None, settings: dict[str, str] | None = None, all_built=True):
    book = tmp_path / "book"
    beats = book / "story" / "幕綱"
    beats.mkdir(parents=True, exist_ok=True)
    (beats / "_順序.md").write_text(INDEX, encoding="utf-8")
    (beats / "arc01.md").write_text(ARC01, encoding="utf-8")
    if all_built:
        (beats / "arc02.md").write_text(ARC02, encoding="utf-8")
    for name, body in (objects or {}).items():
        d = book / "story" / "物件"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(body, encoding="utf-8")
    for name, body in (settings or {}).items():
        d = book / "story" / "設定" / "角色"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(body, encoding="utf-8")
    return book


def _obj(reveal: str) -> str:
    return f"---\n型別: 伏筆\n揭示層級: {reveal}\n---\n## 為什麼存在\n略。\n"


# ------------------------------------------------------------ 四種結果

def test_reveal_pointing_at_a_paid_beat_resolves(tmp_path):
    rep = build(_book(tmp_path, {"舊玉來歷.md": _obj("水下｜揭示於 收[[伏筆:舊玉來歷]]")}))
    assert rep.ice_scanned == 1
    assert [why for _i, why in rep.ice_resolved] == ["揭示於 幕002（arc01）"]
    assert rep.ice_unparsed == 0


def test_cross_book_resolves(tmp_path):
    rep = build(_book(tmp_path, {"甲.md": _obj("水下｜跨集留白，本書不揭")}))
    assert len(rep.ice_resolved) == 1 and rep.ice_unparsed == 0


def test_planted_but_unpaid_is_pending_not_suspect(tmp_path):
    """揭示點還不存在是合法狀態（共同約定.md 六）。"""
    rep = build(_book(tmp_path, {"母親的信.md": _obj("水下｜揭示於 收[[伏筆:母親的信]]")}))
    assert len(rep.ice_pending) == 1 and rep.ice_unparsed == 0
    assert "該伏筆已埋" in rep.ice_pending[0][1]


def test_unknown_name_with_an_unbuilt_arc_is_pending(tmp_path):
    rep = build(
        _book(tmp_path, {"甲.md": _obj("水下｜揭示於 收[[伏筆:還沒排的線]]")}, all_built=False)
    )
    assert len(rep.ice_pending) == 1 and rep.ice_unparsed == 0
    assert "arc02 尚未拆幕" in rep.ice_pending[0][1]


def test_unknown_name_with_everything_built_is_suspect(tmp_path):
    rep = build(_book(tmp_path, {"甲.md": _obj("水下｜揭示於 收[[伏筆:打錯的名字]]")}))
    assert rep.ice_unparsed == 1
    assert "既無這條伏筆的埋也無收" in rep.ice_suspect[0][1]


def test_public_is_not_a_reveal_mark(tmp_path):
    rep = build(_book(tmp_path, {"甲.md": _obj("公開")}))
    assert rep.ice_scanned == 0


# ------------------------------------------------------------ 單一語法（V1）

@pytest.mark.parametrize(
    "bad",
    [
        "🧊水下: 收[[伏筆:舊玉來歷]]",  # 舊的 front-matter 鍵
        "後段才揭",  # 散文
        "水下",  # 沒二選一
    ],
)
def test_other_syntaxes_are_reported_not_silently_ignored(tmp_path, bad):
    """舊版對不合語法的寫法是**靜默跳過**，於是 91 處隱形。現在它們是可疑點。"""
    rep = build(_book(tmp_path, {"甲.md": _obj(bad)}))
    assert rep.ice_scanned == 1
    assert rep.ice_unparsed == 1


def test_ice_left_in_a_settings_derived_file_is_a_retired_location(tmp_path):
    """設定層 `.ai.md` 的 🧊 ＝不可重生的裁決住在會被重生的檔裡（V2）。"""
    rep = build(
        _book(
            tmp_path,
            settings={"少年.ai.md": "## 需求四象限\n- 期盼：【🧊 水下｜揭示於 收[[伏筆:舊玉來歷]]】略\n"},
        )
    )
    assert rep.ice_scanned == 1 and rep.ice_unparsed == 1
    assert "落點已廢除" in rep.ice_suspect[0][1]


# ------------------------------------------------------------ 誠實的計數（E2）

def test_report_always_prints_how_many_were_scanned(tmp_path):
    """0 處也要印——「掃到 0 處」本身就是訊息（它會暴露落點搬走沒人跟上）。"""
    rep = build(_book(tmp_path))
    out = format_report(rep, rep.threads, "全書伏筆帳")
    assert "揭示層級：掃到 0 處／解析 0 處／待落幕 0 處／**無法解析 0 處**" in out


def test_report_prints_resolved_marks_not_only_suspects(tmp_path):
    """舊版把 ice_resolved 算出來卻不印，於是輸出裡看不出它到底解析了什麼。"""
    rep = build(_book(tmp_path, {"舊玉來歷.md": _obj("水下｜揭示於 收[[伏筆:舊玉來歷]]")}))
    out = format_report(rep, rep.threads, "全書伏筆帳")
    assert "掃到 1 處／解析 1 處" in out
    assert "舊玉來歷.md 第 3 行：揭示於 幕002（arc01）" in out


def test_unparsed_marks_make_the_tool_exit_nonzero(tmp_path):
    from foreshadow_project.cli import main

    book = _book(tmp_path, {"甲.md": _obj("水下｜揭示於 收[[伏筆:打錯的名字]]")})
    assert main(["--book", str(book)]) == 1
