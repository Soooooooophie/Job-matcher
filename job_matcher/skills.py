"""技能關鍵字辭典。用固定 key 而不是自由文字（Zona 偏好記憶的做法）。

同一個技能的各種寫法都對應到同一個 key，相似度計算才不會因為寫法不同而失準。

英文別名用「單字邊界」比對：避免 api 命中 rapid、capital 這類誤判
（這是接上真實資料後才發現的 bug）。中文沒有空格分詞，維持子字串比對。
"""
import re

SKILL_ALIASES = {
    "llm": ["llm", "大型語言模型", "生成式ai", "gen ai", "genai", "generative ai"],
    "rag": ["rag", "檢索增強", "retrieval-augmented"],
    "python": ["python"],
    "sql": ["sql"],
    "power_automate": ["power automate"],
    "m365_copilot": ["m365 copilot", "microsoft 365 copilot", "copilot"],
    "power_bi": ["power bi"],
    "sap": ["sap"],
    "project_management": ["專案管理", "project management", "program management", "pmp"],
    "requirements": ["需求訪談", "需求分析", "需求整合", "requirements", "business needs"],
    "ai_governance": ["ai治理", "ai governance", "iso 42001", "iso/iec 42001",
                      "human-in-the-loop", "human oversight", "guardrails"],
    "esg": ["esg", "碳盤查", "iso 14064"],
    "recommender": ["推薦系統", "recommender"],
    "nlp": ["nlp", "自然語言處理"],
    "cloud": ["gcp", "aws", "azure", "雲端", "cloud"],
    "api_integration": ["api", "apis", "json", "system integration", "system integrations"],
    "change_management": ["導入", "變革管理", "change management", "教育訓練",
                          "onboarding", "user adoption", "rollout"],
    "agile": ["agile", "scrum", "jira", "azure devops"],
    # 以下五個是回填既有紀錄時才發現缺的（真實職缺最常見的概念）
    "ai_agent": ["agent", "agents", "agentic", "智能代理", "代理人"],
    "automation": ["自動化", "automation", "rpa"],
    "data_governance": ["資料治理", "語意治理", "數據管理", "主檔", "data governance",
                        "data management"],
    "digital_transformation": ["數位轉型", "數位化", "digital transformation", "transformation"],
    "analytics": ["數據分析", "資料分析", "analytics", "business intelligence", "bi"],
}

_ASCII = re.compile(r"^[\x00-\x7f]+$")


def _compile(alias: str) -> re.Pattern:
    escaped = re.escape(alias)
    if _ASCII.match(alias):
        return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")
    return re.compile(escaped)


_PATTERNS = {key: [_compile(a) for a in aliases] for key, aliases in SKILL_ALIASES.items()}


def extract_skills(text: str) -> set:
    lowered = text.lower()
    return {key for key, patterns in _PATTERNS.items()
            if any(p.search(lowered) for p in patterns)}
