"""單元測試：防幻覺規則。只測一個函式，不碰任何外部服務。"""
from job_matcher.url_guard import job_id, normalize_url, url_in_source


def test_normalize_removes_tracking_params_and_trailing_slash():
    assert normalize_url("https://www.104.com.tw/job/7aaa1/?utm_source=mail") \
        == "https://www.104.com.tw/job/7aaa1"


def test_url_that_appears_in_email_is_accepted():
    email = "今日職缺 https://www.104.com.tw/job/7aaa1?utm_source=mail"
    assert url_in_source("https://www.104.com.tw/job/7aaa1", email)


def test_url_invented_by_ai_is_rejected():
    """這就是 13 筆幻覺資料事件：AI 編出一個看起來很合理、但信裡沒有的網址。"""
    email = "今日職缺 https://www.104.com.tw/job/7aaa1"
    assert not url_in_source("https://www.104.com.tw/job/7aaa2", email)


def test_same_job_with_different_tracking_gets_same_id():
    a = job_id("https://www.104.com.tw/job/7aaa1?utm_source=mail")
    b = job_id("https://www.104.com.tw/job/7aaa1?jobsource=hotjob")
    assert a == b
