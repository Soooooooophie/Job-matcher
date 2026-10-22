"""單元測試：用「真實」的 Notion 剪藏頁面（範例科技）驗證解析器。

這些測試是在看到真實資料之後才寫的，每一個都對應一個實際發現的問題。
"""
import pytest

from job_matcher.clip_parser import ClipParseError, parse_notion_clip
from job_matcher.models import SOURCE_MANUAL_CLIP
from job_matcher.skills import extract_skills
from fixtures.real_advantech import REAL_PAGE


# 問題 1：網址在 Notion 欄位「JD連結」，內文裡反而是登入頁、TOEIC 等無關網址
def test_url_comes_from_property_not_page_body():
    job = parse_notion_clip(REAL_PAGE)
    assert job.url == "https://www.104.com.tw/job/9abcd"


# 問題 2：標題被 Clipper 存成「職稱_編號｜公司｜地點－104 人力銀行」，公司名稱欄位是空的
def test_title_and_company_are_split_from_page_title():
    job = parse_notion_clip(REAL_PAGE)
    assert job.title.startswith("AI Technical Project Manager")
    assert "104 人力銀行" not in job.title
    assert job.company == "範例科技"


# 問題 3：「條件要求」區塊是空的（動態載入沒抓到），年資寫在英文內文裡
def test_years_parsed_from_english_range():
    assert parse_notion_clip(REAL_PAGE).years_required == 3


# 問題 4：英文 JD 的技能沒被辨識（requirements、onboarding/adoption/rollout）
def test_english_jd_skills_are_recognized():
    skills = parse_notion_clip(REAL_PAGE).skills
    assert {"requirements", "change_management", "project_management",
            "llm", "rag", "ai_governance"} <= skills


# 問題 5：「api」被當成子字串比對，rapid、capital 都被誤判成 API 技能
def test_short_english_alias_does_not_match_inside_other_words():
    assert "api_integration" not in extract_skills("負責 rapid prototyping 與 capital 規劃")
    assert "api_integration" in extract_skills("熟悉 REST API 串接")


# 問題 6：回填既有 28 筆紀錄時，15 筆抽不到有意義的技能（辭典缺了真實職缺最常見的概念）
@pytest.mark.parametrize("text, skill", [
    ("設計多Agent協作工作流", "ai_agent"),
    ("Agentic AI應用開發", "ai_agent"),
    ("企業內部商用系統AI自動化規劃", "automation"),
    ("AI Automation Engineer", "automation"),
    ("製造主檔語意治理", "data_governance"),
    ("BI報表與數據管理、資料治理", "data_governance"),
    ("主導企業內部數位轉型專案", "digital_transformation"),
    ("推動企業流程數位化", "digital_transformation"),
    ("以HR場景推動數據分析", "analytics"),
    ("Senior Business Intelligence Specialist", "analytics"),
])
def test_common_job_concepts_are_recognized(text, skill):
    assert skill in extract_skills(text)


def test_agent_does_not_match_inside_other_words():
    assert "ai_agent" not in extract_skills("contact our agency for management")


def test_marked_as_manual_clip():
    assert parse_notion_clip(REAL_PAGE).source == SOURCE_MANUAL_CLIP


def test_page_without_job_content_fails_loudly():
    broken = {"properties": REAL_PAGE["properties"], "content": "## 條件要求\n### 工作經歷\n"}
    with pytest.raises(ClipParseError, match="工作內容"):
        parse_notion_clip(broken)
