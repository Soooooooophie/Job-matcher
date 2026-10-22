"""整合測試：把解析、防幻覺、去重、評分、儲存串起來跑一次完整流程。

單元測試證明「每個零件是好的」；整合測試證明「零件接起來還是好的」。
這裡唯一被替換掉的是 LLM（換成 fake_extractor），因為：
  1. 真的 LLM 每次回答不一樣，測試結果會飄
  2. 我們要能刻意讓它「說謊」，驗證防幻覺機制
"""
import pytest

from job_matcher.models import Job, SOURCE_104_EMAIL, SOURCE_LINKEDIN_EMAIL
from job_matcher.pipeline import run_daily
from job_matcher.skills import extract_skills
from job_matcher.storage import InMemoryStore
from job_matcher.url_guard import extract_urls
from fixtures.samples import (CLIP_AI_PM, CLIP_BROKEN, EMAIL_104, EMAIL_LINKEDIN,
                              JD_TEXT, PROFILE)

HALLUCINATED_URL = "https://www.104.com.tw/job/7ccc3"


def fake_extractor(raw, source, hallucinate=False):
    """假的 LLM：照信件內容回傳職缺；hallucinate=True 時會多編一筆不存在的職缺。"""
    jobs = []
    for url in extract_urls(raw):
        text = JD_TEXT[url]
        jobs.append(Job(url=url, title=url.rsplit("/", 1)[-1], company="", text=text,
                        source=source, skills=extract_skills(text)))
    if hallucinate and source == SOURCE_104_EMAIL:
        jobs.append(Job(url=HALLUCINATED_URL, title="不存在的職缺", company="",
                        text="", source=source, skills={"llm"}))
    return jobs


EMAILS = [{"source": SOURCE_104_EMAIL, "raw": EMAIL_104},
          {"source": SOURCE_LINKEDIN_EMAIL, "raw": EMAIL_LINKEDIN}]


@pytest.fixture
def store():
    return InMemoryStore()


def test_full_run_stores_all_real_jobs(store):
    report = run_daily(EMAILS, [CLIP_AI_PM], PROFILE, store, fake_extractor)
    assert report.processed == 4                 # 3 筆信件職缺 + 1 筆手動收藏
    assert store.count() == 4


def test_hallucinated_job_never_reaches_the_database(store):
    report = run_daily(EMAILS, [], PROFILE, store,
                       lambda raw, src: fake_extractor(raw, src, hallucinate=True))
    assert report.rejected_hallucinated == [HALLUCINATED_URL]
    assert store.get(HALLUCINATED_URL) is None


def test_running_twice_does_not_create_duplicates(store):
    run_daily(EMAILS, [CLIP_AI_PM], PROFILE, store, fake_extractor)
    run_daily(EMAILS, [CLIP_AI_PM], PROFILE, store, fake_extractor)
    assert store.count() == 4


def test_saved_job_pushes_similar_job_over_threshold(store):
    """這是這次功能的核心驗收：手動收藏真的會改變推薦結果。"""
    target = "https://www.104.com.tw/job/7aaa1"

    run_daily(EMAILS, [], PROFILE, store, fake_extractor)
    without_clip = store.get(target)

    store2 = InMemoryStore()
    run_daily(EMAILS, [CLIP_AI_PM], PROFILE, store2, fake_extractor)
    with_clip = store2.get(target)

    assert without_clip.ats_score == with_clip.ats_score     # 原公式分數不受影響
    assert without_clip.recommended is False                 # 沒收藏時差一點點
    assert with_clip.recommended is True                     # 收藏後被推上門檻
    assert "晨曦智能" in with_clip.similar_to                  # 而且說得出原因


def test_unrelated_job_is_not_boosted(store):
    run_daily(EMAILS, [CLIP_AI_PM], PROFILE, store, fake_extractor)
    sap_job = store.get("https://www.104.com.tw/job/7bbb2")
    assert sap_job.similarity_bonus == 0
    assert sap_job.recommended is False


def test_real_notion_clip_works_end_to_end(store):
    """真實資料驗收：範例科技的剪藏頁面當錨點，相似職缺被推上門檻，不相關的仍不推薦。"""
    from fixtures.real_advantech import REAL_PAGE
    report = run_daily(EMAILS, [REAL_PAGE], PROFILE, store, fake_extractor)

    assert report.clip_errors == []
    assert store.get("https://www.104.com.tw/job/9abcd") is not None   # 收藏本身有存進去
    similar = store.get("https://www.104.com.tw/job/7aaa1")
    assert similar.recommended is True and "範例科技" in similar.similar_to
    assert store.get("https://www.104.com.tw/job/7bbb2").recommended is False


def test_broken_clip_is_reported_but_does_not_stop_the_run(store):
    report = run_daily(EMAILS, [CLIP_BROKEN, CLIP_AI_PM], PROFILE, store, fake_extractor)
    assert len(report.clip_errors) == 1
    assert store.count() == 4
