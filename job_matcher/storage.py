"""儲存層。

正式版會是 Firestore 或 Notion；這裡先用記憶體版本，介面一樣（upsert / get / all）。
重點是「用職缺網址雜湊當 ID」，所以同一筆寫幾次都只有一筆。
"""
from .url_guard import job_id


class InMemoryStore:
    def __init__(self):
        self._rows = {}

    def upsert(self, result):
        self._rows[job_id(result.url)] = result

    def get(self, url):
        return self._rows.get(job_id(url))

    def all(self):
        return list(self._rows.values())

    def count(self):
        return len(self._rows)
