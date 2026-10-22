"""Notion「Claude職缺配對總表」的歸類規則。

Notion Web Clipper 剪藏時無法自動填欄位，所以由 Agent 在每次執行時補上：
把剛剪進來、還沒有來源的 104 頁面標成「手動收藏」，之後就當作配對的錨點。
"""
import re

MANUAL_SOURCE = "手動收藏"
JOB_URL = re.compile(r"104\.com\.tw/job/")


def _empty(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def is_manual_clip(props: dict) -> bool:
    if props.get("來源") == MANUAL_SOURCE:
        return True
    return (_empty(props.get("來源"))
            and _empty(props.get("ATS分數"))
            and _empty(props.get("配對日期"))
            and bool(JOB_URL.search(props.get("JD連結") or "")))


def backfill_source(props: dict):
    """需要更新時回傳要寫回 Notion 的欄位；不需要時回傳 None。"""
    if props.get("來源") == MANUAL_SOURCE or not is_manual_clip(props):
        return None
    return {"來源": MANUAL_SOURCE}


def select_anchors(pages: list) -> list:
    """從整張總表挑出手動收藏的頁面，作為相似度加分的錨點。"""
    return [p for p in pages if is_manual_clip(p.get("properties", {}))]
