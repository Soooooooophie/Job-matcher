"""單元測試：判斷 Notion 頁面是不是 Clipper 剛剪進來的手動收藏，並補上「來源」。

判斷規則（三個條件同時成立）：
  1. 「來源」是空的
  2. 「ATS分數」和「配對日期」也是空的（自動配對的紀錄一定有這兩個）
  3. 「JD連結」是 104 職缺網址
"""
from job_matcher.notion_sync import MANUAL_SOURCE, backfill_source, is_manual_clip
from fixtures.real_advantech import REAL_PAGE

AUTO_MATCHED = {"來源": "104", "ATS分數": 88.0, "配對日期": "2026-10-18",
                "JD連結": "https://www.104.com.tw/job/7aaa1"}


def test_fresh_clipper_page_is_detected():
    assert is_manual_clip(REAL_PAGE["properties"])


def test_auto_matched_row_is_not_touched():
    assert not is_manual_clip(AUTO_MATCHED)
    assert backfill_source(AUTO_MATCHED) is None


def test_already_labeled_manual_is_not_updated_again():
    """冪等性：已經標好的不要每次都重寫一次。"""
    labeled = dict(REAL_PAGE["properties"], 來源=MANUAL_SOURCE)
    assert backfill_source(labeled) is None


def test_row_with_score_but_missing_source_is_not_guessed():
    """有分數卻沒來源，代表是資料異常，不是手動收藏，不能亂貼標籤。"""
    odd = {"來源": "", "ATS分數": 72.0, "JD連結": "https://www.104.com.tw/job/1"}
    assert not is_manual_clip(odd)


def test_non_104_page_is_not_labeled():
    blog = {"來源": "", "JD連結": "https://medium.com/some-article"}
    assert not is_manual_clip(blog)


def test_backfill_returns_only_the_source_field():
    assert backfill_source(REAL_PAGE["properties"]) == {"來源": MANUAL_SOURCE}
