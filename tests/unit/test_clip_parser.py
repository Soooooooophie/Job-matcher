"""單元測試：Notion 剪藏解析。"""
import pytest

from job_matcher.clip_parser import ClipParseError, parse_clip
from job_matcher.models import SOURCE_MANUAL_CLIP
from fixtures.samples import CLIP_AI_PM, CLIP_BROKEN


def test_parses_title_company_and_clean_url():
    job = parse_clip(CLIP_AI_PM)
    assert job.title == "AI 導入專案經理"
    assert job.company == "晨曦智能股份有限公司"
    assert job.url == "https://www.104.com.tw/job/8abc1"
    assert job.source == SOURCE_MANUAL_CLIP


def test_extracts_skills_and_years_from_jd():
    job = parse_clip(CLIP_AI_PM)
    assert {"llm", "rag", "requirements", "change_management"} <= job.skills
    assert job.years_required == 3


def test_clip_without_job_content_fails_loudly():
    """Clipper 沒抓到動態內文時，要明確報錯，不能存一筆空殼進資料庫。"""
    with pytest.raises(ClipParseError, match="工作內容"):
        parse_clip(CLIP_BROKEN)


def test_clip_without_104_url_fails():
    with pytest.raises(ClipParseError, match="網址"):
        parse_clip("某個部落格文章\n工作內容\n隨便寫寫")
