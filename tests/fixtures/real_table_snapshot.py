"""真實快照：Notion「Claude職缺配對總表」2026-10-19 15:18 的狀態（Sophie 勾選後，28 筆）。

標籤來自 llm_tags.py 經 validate_tags 驗證後的結果；勾選狀態照抄 Notion。
"""
import json

from job_matcher.tagger import validate_tags
from fixtures.llm_tags import JD_TEXTS, LLM_TAGS

# 名稱: (來源, ATS, 已投遞, 面試中, 不喜歡)
FLAGS = {
    "金控A架構": ("104", 91, 1, 0, 0), "製造B": ("104", 90, 1, 0, 0),
    "電信C": ("104", 92, 0, 0, 0), "租賃D": ("104", 90, 1, 0, 0),
    "外商E": ("104", 89, 1, 0, 0), "科技F": ("104", 89, 1, 0, 0),
    "集團G": ("104", 88, 0, 0, 1), "外商H SA": ("LinkedIn", 87, 1, 0, 0),
    "租賃I": ("104", 89, 1, 0, 0), "租賃J": ("104", 90, 1, 0, 0),
    "代工K-1": ("104", 93, 1, 0, 0), "代工K-2": ("104", 89, 1, 1, 0),   # Sophie 已補勾已投遞
    "電信L": ("104", 91, 0, 0, 1), "電子M": ("104", 88, 0, 0, 0),
    "電子N": ("104", 90, 0, 0, 1), "電子O": ("104", 87, 1, 0, 0),
    "外商P": ("Glassdoor", 88, 1, 0, 0), "外商Q": ("Glassdoor", 81, 0, 0, 1),
    "外商R台中": ("LinkedIn", 86, 1, 0, 0), "電子S": ("104", 88, 1, 0, 0),
    "外商T": ("LinkedIn", 85, 1, 0, 0), "科技U": ("104", 88, 0, 0, 1),
    "科技V": ("Glassdoor", 82, 1, 0, 0), "外商R桃園": ("LinkedIn", 86, 1, 0, 0),
    "製造W": ("104", 86, 0, 0, 1), "外商H DevRel": ("Glassdoor", 80, 1, 0, 0),
    "金控A轉型": ("104", 93, 1, 0, 0), "範例科技": ("手動收藏", None, 0, 0, 0),
}

_YN = {1: "__YES__", 0: "__NO__"}


def _props(name):
    src, ats, applied, interview, dislike = FLAGS[name]
    tags, _ = validate_tags(LLM_TAGS[name], JD_TEXTS[name])
    props = {"職位名稱": name, "來源": src, "ATS分數": ats,
             "已投遞": _YN[applied], "面試中": _YN[interview], "不喜歡": _YN[dislike],
             "配對日期": None if src == "手動收藏" else "2026-10-16",
             "JD連結": "https://www.104.com.tw/job/x",
             "技能標籤": json.dumps(sorted(tags), ensure_ascii=False)}
    return props


SNAPSHOT = [_props(n) for n in FLAGS]
