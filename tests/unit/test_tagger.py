"""單元測試：統一標籤（v3）+ 證據驗證。

v2 用三個維度、33 個標籤 → 28 筆職缺裡 19 個標籤只出現 1～2 次，算不出權重（資料稀疏）。
v3 依 Sophie 的建議：一個欄位、約 14 個求職網站常見的技能詞，每個標籤要出現夠多次才有統計意義。
證據驗證保留：它解決的是「標錯」，和「標太細」是兩回事。
"""
from collections import Counter

from job_matcher.skills import extract_skills
from job_matcher.tagger import TAGS, build_prompt, validate_tags
from fixtures.llm_tags import JD_TEXTS, LLM_TAGS

TWM = "AI 供應鏈系統規劃與導入專員 供應鏈流程診斷、AI系統規格規劃與跨部門導入落地"
FET = "C7416 AI智能客服副理 建構企業級AI客服服務與知識供給體系"


# ---------- 詞彙表本身 ----------
def test_vocabulary_is_small_enough_to_compute_weights():
    assert len(TAGS) <= 15


def test_prompt_lists_every_tag_and_demands_evidence():
    prompt = build_prompt("任意 JD")
    assert all(tag in prompt for tag in TAGS)
    assert "evidence" in prompt and "原文" in prompt


# ---------- 驗證規則 ----------
def test_tag_with_evidence_in_text_is_kept():
    tags, rejected = validate_tags([{"tag": "流程優化", "evidence": "流程診斷"}], TWM)
    assert tags == {"流程優化"} and rejected == []


def test_tag_whose_evidence_is_not_in_jd_is_rejected():
    tags, rejected = validate_tags([{"tag": "資料・系統整合", "evidence": "SAP 系統整合"}], TWM)
    assert tags == set()
    assert rejected[0]["reason"] == "證據不在原文"


def test_tag_outside_vocabulary_is_rejected():
    """v2 的細標籤（例如 supply_chain）不再接受，避免標籤數量又膨脹回去。"""
    tags, rejected = validate_tags([{"tag": "supply_chain", "evidence": "供應鏈"}], TWM)
    assert tags == set()
    assert rejected[0]["reason"] == "不在詞彙表"


def test_evidence_match_ignores_case_and_spaces():
    tags, _ = validate_tags([{"tag": "AI Agent", "evidence": "ai  agent"}], "負責 AI Agent 建置")
    assert tags == {"AI Agent"}


# ---------- 黃金標準：Sophie 指出的錯誤（v3 用統一標籤表達） ----------
def test_gold_taiwan_mobile_supply_chain_job():
    """Sophie：實際技能是供應鏈流程診斷、AI 系統規格規劃、跨部門導入落地。"""
    tags, rejected = validate_tags(LLM_TAGS["電信C"], TWM)
    assert rejected == []
    assert {"流程優化", "需求分析", "導入推動"} <= tags


def test_gold_far_eastone_customer_service_job():
    """Sophie：舊版完全沒有標籤。"""
    tags, rejected = validate_tags(LLM_TAGS["電信L"], FET)
    assert rejected == []
    assert {"RAG", "AI應用開發"} <= tags


def test_old_keyword_tagger_fails_the_gold_cases():
    assert extract_skills(TWM) == {"change_management"}
    assert extract_skills(FET) == set()


# ---------- 全部 28 筆 ----------
def _all_tags():
    return {n: validate_tags(LLM_TAGS[n], JD_TEXTS[n]) for n in LLM_TAGS}


def test_every_llm_tag_for_real_rows_passes_validation():
    for name, (_, rejected) in _all_tags().items():
        assert rejected == [], f"{name}: {rejected}"


def test_every_job_gets_at_least_one_tag():
    for name, (tags, _) in _all_tags().items():
        assert tags, f"{name} 沒有任何標籤"


def test_tags_are_computable_most_appear_in_at_least_3_jobs():
    """Sophie 的驗收條件：標籤要能拿來算權重。至少 13/14 個標籤出現在 3 筆以上的職缺。"""
    support = Counter(t for tags, _ in _all_tags().values() for t in tags)
    computable = [t for t in TAGS if support[t] >= 3]
    assert len(computable) >= len(TAGS) - 1, dict(support)


def test_rollout_tag_no_longer_dominates():
    """舊版 16/28 筆都有 change_management；v3「導入推動」只標在明確負責導入落地的職缺。"""
    assert sum("導入推動" in tags for tags, _ in _all_tags().values()) < 16
