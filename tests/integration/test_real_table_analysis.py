"""整合測試：用 Notion 總表的真實快照（Sophie 勾選後），跑「讀取 → 分群 → 產生洞察」完整流程。"""
from job_matcher.analysis import generate_insights, row_from_notion, split_groups
from fixtures.real_table_snapshot import SNAPSHOT


def _report():
    return generate_insights([row_from_notion(p) for p in SNAPSHOT], min_group=10, min_preliminary=5)


def test_real_table_groups_after_sophie_ticked_boxes():
    """18 筆已投遞 + 1 筆面試中 + 1 筆手動收藏 = 20 筆正向；6 筆不喜歡；只剩 2 筆中立。"""
    liked, disliked, neutral, conflicts = split_groups([row_from_notion(p) for p in SNAPSHOT])
    assert (len(liked), len(disliked), len(neutral), len(conflicts)) == (20, 6, 2, 0)


def test_neutral_group_too_small_so_liked_is_compared_with_disliked():
    assert "改為對比不喜歡組" in _report().message


def test_data_quality_is_clean_after_sophie_fixed_j2617():
    """上一輪抓到「代工K-2 面試中但沒勾已投遞」，Sophie 已補勾，現在應該沒有不一致。"""
    assert _report().quality == []


def test_ats_total_cannot_separate_liked_from_disliked():
    """真實資料最重要的發現：喜歡和不喜歡的 ATS 平均分幾乎一樣。"""
    assert any("ATS 總分無法區分" in i.title for i in _report().insights)


def test_formula_overrates_most_disliked_jobs():
    over = [i for i in _report().insights if i.kind == "公式高估"]
    assert over and "5/6" in over[0].title


def test_disliked_insights_are_marked_preliminary():
    """不喜歡只有 6 筆（未滿 10），相關洞察只能是初步觀察。"""
    for i in _report().insights:
        if i.kind in ("排斥", "公式高估"):
            assert i.title.startswith("【初步觀察】")
