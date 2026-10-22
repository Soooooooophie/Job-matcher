"""評分核心。

最終分數 = ATS 基本分（原公式，不受偏好影響） + 相似度加分（上限 10 分）

ATS 權重：技術 55%、年資 15%、學歷 15%、公司類型 15%，另有關鍵字加分。
門檻：104 ≥ 85、LinkedIn ≥ 80；手動收藏的職缺不需過門檻（你已經親自挑過）。
"""
from .models import (Job, Profile, ScoreResult,
                     SOURCE_104_EMAIL, SOURCE_LINKEDIN_EMAIL, SOURCE_MANUAL_CLIP)

COMPANY_TYPE_POINTS = {
    "foreign_or_listed": 15,
    "national_university": 15,
    "private_university": 12,
    "gov_foundation_academic": 10,
    "unlisted_local": 8,
}

THRESHOLDS = {SOURCE_104_EMAIL: 85.0, SOURCE_LINKEDIN_EMAIL: 80.0}

KEYWORD_BONUS = 5.0
SIMILARITY_CAP = 10.0
DEGREE_RANK = {"bachelor": 1, "master": 2, "phd_candidate": 2, "phd": 3}


def technical_points(job: Job, profile: Profile) -> float:
    if not job.skills:
        return 0.0
    covered = len(job.skills & profile.skills) / len(job.skills)
    return round(55 * covered, 2)


def seniority_points(job: Job, profile: Profile) -> float:
    gap = job.years_required - profile.years_experience
    if gap <= 0:
        return 15.0
    if gap <= 2:
        return 8.0
    return 0.0


def education_points(job: Job, profile: Profile) -> float:
    ok = DEGREE_RANK.get(profile.degree, 1) >= DEGREE_RANK.get(job.degree_required, 1)
    return 15.0 if ok else 5.0


def keyword_bonus(job: Job, profile: Profile) -> float:
    text = f"{job.title} {job.text}".lower()
    return KEYWORD_BONUS if any(k.lower() in text for k in profile.bonus_keywords) else 0.0


def ats_breakdown(job: Job, profile: Profile) -> dict:
    """ATS 拆成五個項目，欄位名稱和 Notion 總表一致，分析時才知道是哪一項造成差異。"""
    return {
        "技術分": technical_points(job, profile),
        "年資分": seniority_points(job, profile),
        "學歷分": education_points(job, profile),
        "公司分": float(COMPANY_TYPE_POINTS.get(job.company_type, 8)),
        "關鍵字加分": keyword_bonus(job, profile),
    }


def ats_score(job: Job, profile: Profile) -> float:
    return min(round(sum(ats_breakdown(job, profile).values()), 2), 100.0)


def passes_threshold(source: str, score: float) -> bool:
    if source == SOURCE_MANUAL_CLIP:
        return True
    return score >= THRESHOLDS[source]


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity_bonus(job: Job, anchors: list) -> tuple:
    """和手動收藏（錨點）最相似的那一筆決定加分，最多 10 分。

    回傳 (加分, 最相似的收藏標題)，讓你看得懂分數為什麼變高。
    """
    best_sim, best_title = 0.0, ""
    for anchor in anchors:
        if anchor.url == job.url:      # 不跟自己比
            continue
        sim = jaccard(job.skills, anchor.skills)
        if sim > best_sim:
            best_sim, best_title = sim, f"{anchor.company}｜{anchor.title}"
    bonus = round(min(SIMILARITY_CAP, SIMILARITY_CAP * best_sim), 2)
    return bonus, best_title if bonus > 0 else ""


def score_job(job: Job, profile: Profile, anchors: list) -> ScoreResult:
    base = ats_score(job, profile)
    bonus, similar_to = similarity_bonus(job, anchors)
    final = min(round(base + bonus, 2), 100.0)
    # 門檻判斷用「最終分數」：收藏帶來的加分，就是要讓接近門檻的相似職缺被推上來
    return ScoreResult(job.url, job.title, job.company, job.source,
                       base, bonus, similar_to, final,
                       passes_threshold(job.source, final))
