"""單元測試：偏好分析模組。

三組資料：
  喜歡   = 來源是「手動收藏」
  不喜歡 = 勾選「不喜歡」
  基準   = 其他自動配對的職缺（比較的參考線）
"""
import pytest

from job_matcher.analysis import (Row, component_deltas, disagreements,
                                  generate_insights, row_from_notion,
                                  skill_lift, split_groups, to_notion_insight)
from job_matcher.models import Job, SOURCE_104_EMAIL
from job_matcher.scoring import ats_breakdown, ats_score
from fixtures.samples import PROFILE


def row(skills=(), ats=80.0, liked=False, disliked=False, comps=None, title="職缺"):
    return Row(title=title, ats=ats, skills=set(skills), liked=liked,
               disliked=disliked, components=comps or {})


# ---------- 分數拆解 ----------
def test_breakdown_parts_add_up_to_ats_score():
    job = Job(url="https://a", title="AI PM", company="", text="", source=SOURCE_104_EMAIL,
              skills={"llm", "rag", "sap"}, years_required=5, company_type="foreign_or_listed")
    parts = ats_breakdown(job, PROFILE)
    assert set(parts) == {"技術分", "年資分", "學歷分", "公司分", "關鍵字加分"}
    assert round(sum(parts.values()), 2) == ats_score(job, PROFILE)


# ---------- 從 Notion 欄位讀資料 ----------
def test_row_from_notion_reads_flags_skills_and_components():
    props = {"職位名稱": "範例科技 AI TPM", "來源": "手動收藏", "不喜歡": "__NO__",
             "技能標籤": '["llm", "rag"]', "ATS分數": 85.8, "技術分": 42.8, "年資分": 15}
    r = row_from_notion(props)
    assert r.liked and not r.disliked
    assert r.skills == {"llm", "rag"}               # v3：單一欄位，不加前綴
    assert r.components == {"技術分": 42.8, "年資分": 15}


def test_disliked_checkbox_is_read():
    r = row_from_notion({"職位名稱": "x", "來源": "104", "不喜歡": "__YES__", "ATS分數": 90})
    assert r.disliked and not r.liked


# ---------- 分群 ----------
def test_split_groups_and_exclude_conflicts():
    """同一筆又收藏又勾不喜歡 → 訊號互相矛盾，兩邊都不算，另外回報。"""
    rows = [row(liked=True), row(disliked=True), row(), row(liked=True, disliked=True)]
    liked, disliked, baseline, conflicts = split_groups(rows)
    assert (len(liked), len(disliked), len(baseline), len(conflicts)) == (1, 1, 1, 1)


# ---------- Lift ----------
def test_lift_above_1_when_skill_is_more_common_in_group():
    group = [row({"ai_governance"}) for _ in range(6)] + [row() for _ in range(4)]
    base = [row({"ai_governance"}) for _ in range(2)] + [row() for _ in range(8)]
    share_g, share_b, lift = skill_lift(group, base)["ai_governance"]
    assert share_g == 0.6 and share_b == 0.2
    assert lift > 2


def test_lift_does_not_explode_when_baseline_never_has_the_skill():
    """平滑處理：基準組 0 次時不能除以 0，也不能算出無限大。"""
    group = [row({"esg"})]
    base = [row() for _ in range(5)]
    _, _, lift = skill_lift(group, base)["esg"]
    assert 1 < lift < 10


# ---------- ATS 各項目平均差異 ----------
def test_component_deltas_compare_group_mean_to_baseline_mean():
    group = [row(comps={"技術分": 30}), row(comps={"技術分": 40})]
    base = [row(comps={"技術分": 50}), row(comps={"技術分": 50})]
    assert component_deltas(group, base) == {"技術分": -15.0}


def test_component_deltas_skip_rows_without_breakdown():
    group = [row(comps={"技術分": 30}), row(comps={})]
    base = [row(comps={"技術分": 40})]
    assert component_deltas(group, base) == {"技術分": -10.0}


# ---------- 公式和你判斷不一致的案例 ----------
def test_disagreements_find_underrated_and_overrated():
    liked = [row(ats=70, liked=True, title="低分但收藏"), row(ats=90, liked=True)]
    disliked = [row(ats=92, disliked=True, title="高分但不喜歡"), row(ats=60, disliked=True)]
    under, over = disagreements(liked, disliked, threshold=85)
    assert [r.title for r in under] == ["低分但收藏"]
    assert [r.title for r in over] == ["高分但不喜歡"]


# ---------- 產生洞察 ----------
def test_no_suggestions_when_sample_is_too_small():
    """樣本不足時寧可不給建議，避免把巧合當成規律。"""
    rows = [row({"esg"}, liked=True) for _ in range(3)] + [row() for _ in range(20)]
    report = generate_insights(rows, min_group=10)
    assert report.status == "樣本不足"
    assert report.insights == []
    assert "3" in report.message          # 告訴你目前累積了幾筆


def test_preference_insight_includes_evidence_numbers():
    rows = ([row({"ai_governance", "llm"}, liked=True) for _ in range(7)]
            + [row({"llm"}, liked=True) for _ in range(3)]
            + [row({"ai_governance"}) for _ in range(2)]
            + [row({"sap"}) for _ in range(18)])
    report = generate_insights(rows, min_group=10)
    gov = next(i for i in report.insights if "ai_governance" in i.title)
    assert gov.kind == "偏好"
    assert gov.sample_size == 10
    assert "7/10" in gov.evidence and "2/20" in gov.evidence


def test_disliked_group_produces_aversion_insight():
    rows = ([row({"sap"}, disliked=True) for _ in range(10)]
            + [row({"llm"}) for _ in range(20)])
    report = generate_insights(rows, min_group=10)
    assert any(i.kind == "排斥" and "sap" in i.title for i in report.insights)


def test_insight_maps_to_notion_properties_with_pending_decision():
    rows = ([row({"esg"}, liked=True) for _ in range(10)] + [row() for _ in range(20)])
    insight = generate_insights(rows, min_group=10).insights[0]
    props = to_notion_insight(insight, "2026-10-19")
    assert props["你的決定"] == "待決定"           # 建議只是建議，由你決定
    assert props["date:分析日期:start"] == "2026-10-19"
    assert props["樣本數"] == 10
