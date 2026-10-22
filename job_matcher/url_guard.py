"""防幻覺規則：URL 只能從原文抽取，不能由 AI 生成。

這是你之前遇到 13 筆幻覺資料後定下的規則，現在變成一段可以被測試的程式。
"""
import hashlib
import re
from urllib.parse import urlparse, urlunparse

URL_PATTERN = re.compile(r"https?://[^\s<>\"'）)】]+")


def normalize_url(url: str) -> str:
    """去掉追蹤參數與結尾斜線，讓同一職缺只對應一個 URL。"""
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))


def extract_urls(raw_text: str) -> list:
    return [normalize_url(u) for u in URL_PATTERN.findall(raw_text)]


def url_in_source(url: str, raw_text: str) -> bool:
    """AI 回傳的 URL 必須真的出現在原始信件或剪藏頁面中。"""
    return normalize_url(url) in set(extract_urls(raw_text))


def job_id(url: str) -> str:
    """去重用的文件 ID：同一個職缺網址永遠得到同一個 ID。"""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()[:16]
