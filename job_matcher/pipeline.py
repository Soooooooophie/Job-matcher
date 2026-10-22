"""每日流程：每日配對信 + 手動剪藏 → 驗證 → 去重 → 評分 → 儲存。

LLM 的角色只有一個：從信件文字抽出候選職缺（extractor）。
它回傳的每一筆都要通過 url_in_source 檢查，不通過就丟棄並記錄。
"""
from dataclasses import dataclass, field

from .clip_parser import ClipParseError, parse_clip, parse_notion_clip
from .scoring import score_job
from .url_guard import job_id, url_in_source


@dataclass
class RunReport:
    processed: int = 0
    stored: int = 0
    recommended: int = 0
    rejected_hallucinated: list = field(default_factory=list)
    clip_errors: list = field(default_factory=list)


def run_daily(emails, clips, profile, store, extractor) -> RunReport:
    """
    emails:    [{"source": "104_email", "raw": "<信件原文>"}, ...]
    clips:     [<Notion 剪藏頁面文字>, ...]
    extractor: callable(raw_text, source) -> [Job, ...]（正式版是 LLM，測試時換成假的）
    """
    report = RunReport()

    # 1. 手動收藏 → 錨點
    anchors = []
    for clip in clips:
        try:
            # dict = 真實 Notion 頁面；str = 早期的純文字樣本
            anchors.append(parse_notion_clip(clip) if isinstance(clip, dict) else parse_clip(clip))
        except ClipParseError as e:
            report.clip_errors.append(str(e))

    # 2. 每日配對信 → 候選職缺（LLM 抽取 + 防幻覺檢查）
    candidates = []
    for email in emails:
        for job in extractor(email["raw"], email["source"]):
            if url_in_source(job.url, email["raw"]):
                candidates.append(job)
            else:
                report.rejected_hallucinated.append(job.url)

    # 3. 去重（信件之間、信件與收藏之間）後評分
    seen = set()
    for job in anchors + candidates:
        key = job_id(job.url)
        if key in seen:
            continue
        seen.add(key)
        result = score_job(job, profile, anchors)
        store.upsert(result)
        report.processed += 1
        report.recommended += int(result.recommended)

    report.stored = store.count()
    return report
