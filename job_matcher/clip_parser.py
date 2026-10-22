"""把 Notion Web Clipper 剪藏下來的 104 頁面文字，轉成 Job。

剪藏內容是確定性的原文，所以這裡用規則解析，不需要 LLM。
解析不到關鍵欄位時直接報錯，不默默產生殘缺資料。
"""
import re

from .models import Job, SOURCE_MANUAL_CLIP
from .skills import extract_skills
from .url_guard import extract_urls, normalize_url

JOB_URL_PATTERN = re.compile(r"104\.com\.tw/job/")


class ClipParseError(ValueError):
    pass


def _section(text: str, heading: str, next_headings: list) -> str:
    stop = "|".join(map(re.escape, next_headings)) or r"\Z"
    match = re.search(rf"{re.escape(heading)}\s*\n(.*?)(?=\n(?:{stop})|\Z)", text, re.S)
    return match.group(1).strip() if match else ""


def parse_clip(clip_text: str) -> Job:
    urls = [u for u in extract_urls(clip_text) if JOB_URL_PATTERN.search(u)]
    if not urls:
        raise ClipParseError("剪藏內容裡找不到 104 職缺網址")

    lines = [ln.strip() for ln in clip_text.splitlines() if ln.strip()]
    title = lines[0] if lines else ""
    company = lines[1] if len(lines) > 1 else ""

    duties = _section(clip_text, "工作內容", ["條件要求", "福利制度", "聯絡方式"])
    requirements = _section(clip_text, "條件要求", ["福利制度", "聯絡方式"])
    if not duties:
        raise ClipParseError("剪藏內容缺少「工作內容」，可能是 Clipper 沒抓到動態載入的內文")

    years = re.search(r"(\d+)\s*年以上", requirements)
    degree = "master" if "碩士" in requirements else "bachelor"
    body = f"{duties}\n{requirements}"
    return Job(url=urls[0], title=title, company=company, text=body,
               source=SOURCE_MANUAL_CLIP,
               years_required=int(years.group(1)) if years else 0,
               degree_required=degree,
               skills=extract_skills(body))


# ---------------------------------------------------------------------------
# 真實版：Notion Web Clipper 存進「Claude職缺配對總表」的頁面
# ---------------------------------------------------------------------------
# 104 頁面標題格式：「職稱_編號｜公司｜地點－104 人力銀行」
TITLE_PATTERN = re.compile(r"^(?P<title>.+?)(?:_[A-Z]{2}\d+)?｜(?P<company>[^｜]+)｜.*104 人力銀行\s*$")
YEARS_PATTERNS = [
    re.compile(r"(\d+)\s*年以上"),
    re.compile(r"(\d+)\s*(?:[–\-~]\s*\d+\s*)?\+?\s*years?", re.I),
]


def _markdown_section(content: str, heading: str) -> str:
    """取出「## 標題」到下一個「## 」之間的文字，並把 <br> 換成換行。"""
    match = re.search(rf"^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", content, re.S | re.M)
    if not match:
        return ""
    text = match.group(1).replace("<br>", "\n")
    # 只剩下「### 小標題」的空殼區塊視為沒有內容
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("###")]
    return "\n".join(lines).strip()


def _parse_years(text: str) -> int:
    for pattern in YEARS_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return 0


def parse_notion_clip(page: dict) -> Job:
    """page = {"properties": {...Notion 欄位...}, "content": "<頁面 Markdown>"}"""
    props = page.get("properties", {})
    content = page.get("content", "")

    url = props.get("JD連結", "").strip()
    if not JOB_URL_PATTERN.search(url):
        raise ClipParseError("Notion 欄位「JD連結」不是 104 職缺網址")

    raw_title = props.get("職位名稱", "").strip()
    match = TITLE_PATTERN.match(raw_title)
    title = match.group("title").strip() if match else raw_title
    company = props.get("公司名稱") or (match.group("company").strip() if match else "")

    duties = _markdown_section(content, "工作內容")
    requirements = _markdown_section(content, "條件要求")
    if not duties:
        raise ClipParseError("剪藏內容缺少「工作內容」，可能是 Clipper 沒抓到動態載入的內文")

    # 條件要求常是空的，所以年資、學歷要從整段 JD 裡找
    body = f"{duties}\n{requirements}"
    degree = "master" if re.search(r"碩士|master'?s degree", body, re.I) else "bachelor"
    return Job(url=normalize_url(url), title=title, company=company, text=body,
               source=SOURCE_MANUAL_CLIP,
               years_required=_parse_years(body),
               degree_required=degree,
               skills=extract_skills(body))
