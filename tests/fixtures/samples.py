"""測試用樣本資料。內容是虛構的，但格式仿照真實的 104 信件與 Notion 剪藏。"""
from job_matcher.models import Profile

PROFILE = Profile(skills={
    "llm", "rag", "python", "sql", "project_management", "requirements",
    "ai_governance", "power_automate", "m365_copilot", "change_management",
    "esg", "recommender", "nlp", "api_integration",
})

# Notion Web Clipper 剪下來的 104 職缺頁（手動收藏）
CLIP_AI_PM = """AI 導入專案經理
晨曦智能股份有限公司
https://www.104.com.tw/job/8abc1?jobsource=hotjob
工作內容
1. 負責生成式 AI（LLM、RAG）導入專案管理
2. 與各部門進行需求訪談與需求整合
3. 規劃導入後的教育訓練與成效追蹤
條件要求
學歷要求：大學以上
工作經歷：3年以上
福利制度
年終獎金
"""

# Clipper 只抓到殼、沒抓到動態內文的情況
CLIP_BROKEN = """AI 工程師
某某科技
https://www.104.com.tw/job/9zzz9
"""

# 104 每日配對信原文（簡化）
EMAIL_104 = """您好，以下是今日為您配對的職缺：
【AI 應用專案經理】藍海數據有限公司
https://www.104.com.tw/job/7aaa1?utm_source=mail
【SAP 系統工程師】大河製造股份有限公司
https://www.104.com.tw/job/7bbb2
"""

EMAIL_LINKEDIN = """Jobs you may be interested in
AI Governance Specialist - Northwind Taiwan
https://www.linkedin.com/jobs/view/4001
"""

# 「LLM」從信件讀出來的 JD 內容（正式版是 LLM 解析，測試時寫死）
JD_TEXT = {
    "https://www.104.com.tw/job/7aaa1": "負責 LLM 與 RAG 應用的專案管理，需求分析，熟悉 GCP 雲端",
    "https://www.104.com.tw/job/7bbb2": "SAP 系統維運，SQL，雲端主機管理",
    "https://www.linkedin.com/jobs/view/4001": "AI Governance, ISO 42001, LLM risk, project management",
}
