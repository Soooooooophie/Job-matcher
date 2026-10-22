"""資料結構。所有元件之間只傳這幾種物件，不傳自由文字。"""
from dataclasses import dataclass, field


# 職缺來源：每日配對信（104 / LinkedIn）或手動剪藏（Notion Web Clipper）
SOURCE_104_EMAIL = "104_email"
SOURCE_LINKEDIN_EMAIL = "linkedin_email"
SOURCE_MANUAL_CLIP = "manual_clip"


@dataclass
class Job:
    url: str
    title: str
    company: str
    text: str                      # JD 原文（工作內容 + 條件要求）
    source: str
    company_type: str = "unlisted_local"
    years_required: int = 0
    degree_required: str = "bachelor"   # bachelor / master / phd
    skills: set = field(default_factory=set)


@dataclass
class Profile:
    """你的履歷基準。之後可以改成每位試用者一份。"""
    skills: set
    years_experience: int = 3
    degree: str = "phd_candidate"
    bonus_keywords: tuple = ("AI治理", "AI Governance", "ESG", "AI PM", "AI 專案經理")


@dataclass
class ScoreResult:
    url: str
    title: str
    company: str
    source: str
    ats_score: float               # 原公式分數，不受偏好影響
    similarity_bonus: float        # 手動收藏帶來的個人化加分
    similar_to: str                # 和哪一筆收藏最像（可解釋性）
    final_score: float
    recommended: bool
