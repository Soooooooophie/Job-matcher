"""單元測試：評分公式。每個測試只驗證一條規則，失敗時一眼就知道是哪條規則壞了。"""
import pytest

from job_matcher.models import (Job, SOURCE_104_EMAIL, SOURCE_LINKEDIN_EMAIL,
                                SOURCE_MANUAL_CLIP)
from job_matcher.scoring import (SIMILARITY_CAP, ats_score, passes_threshold,
                                 similarity_bonus, technical_points)
from fixtures.samples import PROFILE


def make_job(url="https://www.104.com.tw/job/1", skills=None, **kw):
    return Job(url=url, title=kw.get("title", "職缺"), company=kw.get("company", "公司"),
               text=kw.get("text", ""), source=kw.get("source", SOURCE_104_EMAIL),
               skills=skills or set(), **{k: v for k, v in kw.items()
                                          if k in ("company_type", "years_required", "degree_required")})


# ---------- 門檻邊界：最容易寫錯成 > 而不是 >= ----------
@pytest.mark.parametrize("score, expected", [(84.99, False), (85.0, True), (92.0, True)])
def test_104_threshold_boundary(score, expected):
    assert passes_threshold(SOURCE_104_EMAIL, score) is expected


@pytest.mark.parametrize("score, expected", [(79.99, False), (80.0, True)])
def test_linkedin_threshold_boundary(score, expected):
    assert passes_threshold(SOURCE_LINKEDIN_EMAIL, score) is expected


def test_manual_clip_always_passes_because_you_already_chose_it():
    assert passes_threshold(SOURCE_MANUAL_CLIP, 10.0)


# ---------- ATS 基本分 ----------
def test_technical_points_is_55_times_coverage():
    job = make_job(skills={"llm", "rag", "sap", "cloud"})      # 你會 2/4
    assert technical_points(job, PROFILE) == 27.5


def test_ats_score_never_exceeds_100():
    job = make_job(skills={"llm"}, title="AI PM", company_type="foreign_or_listed")
    assert ats_score(job, PROFILE) <= 100


# ---------- 個人化加分 ----------
def test_similarity_bonus_is_capped_at_10():
    job = make_job(url="https://a", skills={"llm", "rag"})
    twin = make_job(url="https://b", skills={"llm", "rag"})     # 完全相同 → 相似度 1.0
    bonus, _ = similarity_bonus(job, [twin])
    assert bonus == SIMILARITY_CAP


def test_no_bonus_when_nothing_in_common():
    job = make_job(url="https://a", skills={"sap", "sql"})
    anchor = make_job(url="https://b", skills={"llm", "rag"})
    assert similarity_bonus(job, [anchor]) == (0.0, "")


def test_a_saved_job_does_not_get_bonus_from_itself():
    job = make_job(url="https://a", skills={"llm"})
    assert similarity_bonus(job, [job]) == (0.0, "")


def test_bonus_explains_which_saved_job_it_came_from():
    job = make_job(url="https://a", skills={"llm", "rag"})
    anchor = make_job(url="https://b", skills={"llm", "rag", "nlp"},
                      title="AI PM", company="晨曦")
    _, similar_to = similarity_bonus(job, [anchor])
    assert similar_to == "晨曦｜AI PM"
