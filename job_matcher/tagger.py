"""統一標籤（v3）：LLM 理解、程式驗證。

演進：
  v1 關鍵字辭典 → 標錯（「導入」讓 16/28 筆都是 change_management；供應鏈、客服無處可標）
  v2 三維度 33 個標籤 → 標太細（19 個標籤只出現 1～2 次，算不出權重）
  v3 一個欄位、14 個求職網站常見技能詞 → 每個標籤都有足夠樣本可以統計

證據驗證沿用 v2：LLM 每個標籤都要附 JD 原文片段，證據不在原文就丟棄。
"""
import json
import re

TAGS = {
    "LLM": "大型語言模型、生成式 AI",
    "RAG": "檢索增強生成、知識庫、知識管理",
    "AI Agent": "AI Agent、Agentic AI、多代理協作",
    "自動化": "流程自動化、RPA",
    "數據分析": "數據分析、BI 報表、資料科學",
    "資料・系統整合": "資料治理、ETL、ERP/SAP、API 串接、雲端平台",
    "系統架構": "系統或解決方案架構設計",
    "AI應用開發": "AI 應用開發、建置、PoC、模型部署、應用研究",
    "專案管理": "專案或產品規劃、排程、追蹤；Agile/Scrum",
    "需求分析": "需求訪談、需求澄清、系統規格規劃",
    "流程優化": "流程診斷、流程優化、流程數位化、營運改善",
    "導入推動": "明確負責讓部門或使用者採用（導入落地、推動採用、教育訓練）；不是單純出現「導入」二字",
    "數位轉型": "數位轉型",
    "AI治理": "AI 治理、human-in-the-loop、guardrails",
}


def build_prompt(jd_text: str) -> str:
    vocab = "\n".join(f"  - {tag}：{desc}" for tag, desc in TAGS.items())
    return (
        "請從下列固定標籤中，為這筆職缺挑選所有適用的標籤。\n"
        "規則：只能使用清單裡的標籤名稱；每個標籤都要附上 evidence，"
        "evidence 必須是 JD 原文中逐字出現的片段；沒有原文依據就不要標。\n\n"
        f"{vocab}\n\n"
        '輸出 JSON 陣列：[{"tag": "...", "evidence": "..."}]\n\n'
        f"JD 原文：\n{jd_text}"
    )


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def validate_tags(raw, jd_text: str):
    """回傳 (標籤集合, [被丟棄的標籤與原因])。"""
    if isinstance(raw, str):
        raw = json.loads(raw)
    text = _norm(jd_text)
    tags, rejected = set(), []
    for item in raw or []:
        tag, evidence = item.get("tag", ""), item.get("evidence", "")
        if tag not in TAGS:
            reason = "不在詞彙表"
        elif not evidence or _norm(evidence) not in text:
            reason = "證據不在原文"
        else:
            tags.add(tag)
            continue
        rejected.append({"tag": tag, "evidence": evidence, "reason": reason})
    return tags, rejected
