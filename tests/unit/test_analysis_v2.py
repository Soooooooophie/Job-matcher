"""單元測試：分析方法第二版（因真實資料而改）。

真實資料揭露的兩件事：
  1. 「已投遞」「面試中」是比手動收藏更強的正向訊號，應該納入
  2. 勾選後 29 筆裡只剩 2 筆是中立 → 「喜歡 vs 其他」不成立，要改成「喜歡 vs 不喜歡」直接對比
"""
from job_matcher.analysis import (Row, ats_separation, data_quality_issues,
                                  generate_insights, row_from_notion, split_groups)


def row(tags=(), ats=88.0, liked=False, disliked=False, title="職缺", **flags):
    return Row(title=title, ats=ats, skills=set(tags), liked=liked, disliked=disliked, **flags)


# ---------- 正向訊號的來源 ----------
def test_applied_counts_as_positive():
    r = row_from_notion({"職位名稱": "x", "來源": "104", "已投遞": "__YES__", "ATS分數": 90})
    assert r.liked and r.applied


def test_interviewing_counts_as_positive():
    r = row_from_notion({"職位名稱": "x", "來源": "104", "面試中": "__YES__", "ATS分數": 89})
    assert r.liked and r.interviewing


def test_tags_come_from_the_single_unified_column():
    """v3：只讀「技能標籤」一欄；v2 的職能標籤、領域標籤已移除，即使殘留也不讀。"""
    r = row_from_notion({"職位名稱": "x", "來源": "104",
                         "技能標籤": '["LLM", "專案管理"]', "領域標籤": '["supply_chain"]'})
    assert r.skills == {"LLM", "專案管理"}


# ---------- 參照組的選擇 ----------
def test_uses_disliked_as_reference_when_neutral_group_is_too_small():
    rows = ([row({"領域:finance"}, liked=True) for _ in range(10)]
            + [row({"領域:esg"}, disliked=True) for _ in range(5)]
            + [row() for _ in range(2)])                        # 中立只有 2 筆
    report = generate_insights(rows, min_group=10)
    assert "對比不喜歡組" in report.message
    pref = next(i for i in report.insights if i.title.endswith("領域:finance"))
    assert "不喜歡組 0/5" in pref.evidence


def test_uses_neutral_as_reference_when_it_is_large_enough():
    rows = ([row({"技術:llm"}, liked=True) for _ in range(10)]
            + [row() for _ in range(10)])
    report = generate_insights(rows, min_group=10)
    assert "對比中立組" in report.message


# ---------- 樣本分級 ----------
def test_group_between_5_and_9_gives_preliminary_observation_not_suggestion():
    rows = ([row({"領域:esg"}, disliked=True) for _ in range(6)]
            + [row({"領域:finance"}, liked=True) for _ in range(12)])
    report = generate_insights(rows, min_group=10, min_preliminary=5)
    esg = next(i for i in report.insights if "領域:esg" in i.title)
    assert esg.title.startswith("【初步觀察】")
    assert "樣本 6 筆" in esg.suggestion


def test_group_below_5_gives_nothing():
    rows = ([row({"領域:esg"}, disliked=True) for _ in range(4)]
            + [row({"領域:finance"}, liked=True) for _ in range(12)])
    report = generate_insights(rows, min_group=10, min_preliminary=5)
    assert not any("領域:esg" in i.title for i in report.insights)


# ---------- ATS 總分是否能區分你的喜好 ----------
def test_ats_separation_reports_mean_difference():
    liked = [row(ats=88, liked=True), row(ats=90, liked=True)]
    disliked = [row(ats=89, disliked=True), row(ats=87, disliked=True)]
    assert ats_separation(liked, disliked) == (89.0, 88.0, 1.0)


def test_insight_when_ats_cannot_separate_liked_from_disliked():
    rows = ([row(ats=88, liked=True) for _ in range(10)]
            + [row(ats=88, disliked=True) for _ in range(6)])
    report = generate_insights(rows, min_group=10, min_preliminary=5)
    assert any(i.kind == "項目差異" and "無法區分" in i.title for i in report.insights)


# ---------- 不一致案例要列出「有區別」的標籤，而不是單純最常見的 ----------
def test_overrated_case_lists_distinctive_tags_not_generic_ones():
    """真實資料揭露：舊版列出的「共同標籤」在喜歡組也一樣常見，會誤導。"""
    liked = [row({"職能:pm", "領域:finance"}, ats=90, liked=True) for _ in range(10)]
    disliked = [row({"職能:pm", "領域:esg"}, ats=90, disliked=True) for _ in range(5)]
    report = generate_insights(liked + disliked, min_group=10, min_preliminary=5)
    over = next(i for i in report.insights if i.kind == "公式高估")
    assert "領域:esg" in over.evidence
    assert "職能:pm" not in over.evidence


def test_overrated_case_says_so_when_no_tag_is_shared():
    liked = [row({"職能:pm"}, ats=90, liked=True) for _ in range(10)]
    disliked = [row({f"領域:d{i}"}, ats=90, disliked=True, title=f"J{i}") for i in range(5)]
    report = generate_insights(liked + disliked, min_group=10, min_preliminary=5)
    over = next(i for i in report.insights if i.kind == "公式高估")
    assert "沒有共同的區別標籤" in over.evidence


# ---------- 資料一致性 ----------
def test_flags_interviewing_without_applied():
    issues = data_quality_issues([row(title="代工K-2", liked=True, interviewing=True, applied=False)])
    assert issues == ["「代工K-2」勾了面試中，但沒有勾已投遞"]


def test_flags_applied_and_disliked_at_the_same_time():
    issues = data_quality_issues([row(title="A", liked=True, applied=True, disliked=True)])
    assert "同時勾了已投遞和不喜歡" in issues[0]
