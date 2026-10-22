# 🧪 Sophie AI Learning Lab：職缺配對 Agent

每天打開信箱就有幾十封職缺通知，我要的不只是一張排好序的清單，而是一個**會從我的行為學習偏好、但把決定權留給我**的系統。

這份紀錄整理開發過程中的核心技術與關鍵設計，並附上原始碼片段佐證。

---

## 🛠️ 核心技術

- `Claude Code`（從規格、測試到實作的開發夥伴）
- `Gmail MCP` / `Notion MCP`（讀取配對信、讀寫 Notion 資料庫）
- `Notion Web Clipper`（一鍵把 104 職缺頁存進資料庫，取代複製貼上）
- `ATS 評分公式`（技術 55%、年資 15%、學歷 15%、公司類型 15%，另有關鍵字加分）
- `LLM Tagging + Evidence Validation`（LLM 提出標籤，程式驗證證據確實出現在 JD 原文）
- `Jaccard 相似度` / `Lift`（收藏相似度加分、偏好訊號分析）
- `pytest`（96 個單元測試與整合測試，含真實資料快照與黃金標準）

---

## ✨ 關鍵亮點

### 1. 防幻覺規則：URL 只能從原文抽，不能由 AI 生成

早期一次事故中，AI 編出了 13 筆看起來很合理、實際上不存在的職缺。從此定下整個系統最重要的規則：**AI 回傳的每一個網址，都必須在原始信件裡找得到。**

```python
def url_in_source(url: str, raw_text: str) -> bool:
    """AI 回傳的 URL 必須真的出現在原始信件或剪藏頁面中。"""
    return normalize_url(url) in set(extract_urls(raw_text))
```

在每日流程中，LLM 只負責「抽取候選職缺」，每一筆都要先過這道檢查：

```python
for email in emails:
    for job in extractor(email["raw"], email["source"]):
        if url_in_source(job.url, email["raw"]):
            candidates.append(job)
        else:
            report.rejected_hallucinated.append(job.url)
```

- **LLM 不碰資料庫**：它只提出候選，寫入前一律由程式驗證。
- **被丟棄的不會消失**：記錄在 `rejected_hallucinated`，事後可以追查 AI 什麼時候開始亂編。
- **網址先正規化**：去掉 `?utm_source=` 這類追蹤參數，同一職缺不會因參數不同被當成兩筆。

---

### 2. LLM 提出標籤，程式驗證證據

最早用關鍵字辭典標技能，結果「導入」兩個字讓 28 筆裡有 16 筆都被標成同一個標籤；電信C的「供應鏈流程診斷、AI 系統規格規劃」則完全標不到。

理解一句中文 JD 是語意判斷，適合交給 LLM，但 LLM 會亂標。所以沿用防幻覺原則：**每個標籤都要附上 JD 原文的證據片段。**

LLM 的輸出長這樣：

```json
[
  {"tag": "流程優化", "evidence": "流程診斷"},
  {"tag": "需求分析", "evidence": "系統規格規劃"},
  {"tag": "導入推動", "evidence": "跨部門導入落地"},
  {"tag": "資料・系統整合", "evidence": "SAP 系統整合"}
]
```

程式逐筆驗證，只保留「在詞彙表內、而且證據確實出現在原文」的標籤：

```python
def validate_tags(raw, jd_text: str):
    """回傳 (標籤集合, [被丟棄的標籤與原因])。"""
    text = _norm(jd_text)
    tags, rejected = set(), []
    for item in raw or []:
        tag, evidence = item.get("tag", ""), item.get("evidence", "")
        if tag not in TAGS:
            reason = "不在詞彙表"
        elif not evidence or _norm(evidence) not in text:
            reason = "證據不在原文"
        else:
            tags.add(tag)
            continue
        rejected.append({"tag": tag, "evidence": evidence, "reason": reason})
    return tags, rejected
```

- **第四筆被丟棄**：JD 裡根本沒有「SAP」，LLM 是在猜，所以回報 `證據不在原文`。
- **固定詞彙表**：只接受 14 個標籤，阻止標籤數量再度膨脹。
- **忽略空白與大小寫**：`_norm()` 讓「ai  agent」也能對上原文的「AI Agent」。

---

### 3. 標籤不能太細：資料稀疏會讓權重算不出來

修好「標錯」之後，我一度把標籤拆成技術、職能、領域三個維度，結果 28 筆職缺用了 33 個標籤，**其中 19 個只出現 1～2 次**，統計上沒有樣本，權重根本無從計算。

最後收斂成 14 個求職網站常見的技能詞，並把「可計算性」寫成驗收測試：

```python
def test_tags_are_computable_most_appear_in_at_least_3_jobs():
    """標籤要能拿來算權重：至少 13/14 個標籤出現在 3 筆以上的職缺。"""
    support = Counter(t for tags, _ in _all_tags().values() for t in tags)
    computable = [t for t in TAGS if support[t] >= 3]
    assert len(computable) >= len(TAGS) - 1, dict(support)
```

- **標錯和標太細是兩種病**：證據驗證治標錯，粗粒度詞彙表治標太細，兩者都要保留。
- **測試守住設計原則**：之後有人想新增標籤，只要讓標籤變得太稀疏，測試就會失敗。

---

### 4. 手動收藏當錨點：加分有上限，而且說得出原因

Agent 原本只讀得到 104 的配對信，讀不到我手動收藏的職缺。現在收藏的職缺成為「錨點」，新職缺和錨點越像，就多拿一點分數：

```python
def similarity_bonus(job: Job, anchors: list) -> tuple:
    """和手動收藏（錨點）最相似的那一筆決定加分，最多 10 分。"""
    best_sim, best_title = 0.0, ""
    for anchor in anchors:
        if anchor.url == job.url:      # 不跟自己比
            continue
        sim = jaccard(job.skills, anchor.skills)
        if sim > best_sim:
            best_sim, best_title = sim, f"{anchor.company}｜{anchor.title}"
    bonus = round(min(SIMILARITY_CAP, SIMILARITY_CAP * best_sim), 2)
    return bonus, best_title if bonus > 0 else ""
```

- **原公式不動**：ATS 基本分和個人化加分分開記錄，客觀分數不會被偏好扭曲。
- **上限 10 分**：避免單一方向的職缺壓過所有其他推薦。
- **可解釋**：回傳「與哪一筆收藏相似」，例如藍海數據的 AI 應用專案經理從 82 分加到 88.67 分，因為和範例科技的 AI TPM 相似。

Clipper 剪藏時無法自動填欄位，所以由 Agent 判斷哪些頁面是剛剪進來的收藏：

```python
def is_manual_clip(props: dict) -> bool:
    if props.get("來源") == MANUAL_SOURCE:
        return True
    return (_empty(props.get("來源"))
            and _empty(props.get("ATS分數"))
            and _empty(props.get("配對日期"))
            and bool(JOB_URL.search(props.get("JD連結") or "")))
```

- **三個條件同時成立才算收藏**：自動配對的紀錄一定有分數和日期，不會被誤判。
- **有分數卻沒來源的資料不亂貼標籤**：那是資料異常，不是收藏。

---

### 5. 偏好分析：從行為找訊號，但樣本不夠就不下結論

我勾選了已投遞、面試中、不喜歡，系統比較喜歡組和不喜歡組，找出哪些標籤真正有區別：

```python
def skill_lift(group, reference) -> dict:
    """回傳 {標籤: (組內比例, 參照比例, Lift)}；拉普拉斯平滑避免除以 0。"""
    result = {}
    tags = set().union(*(r.skills for r in group)) if group else set()
    ng, nr = len(group), len(reference)
    for t in tags:
        cg, cr = _count(group, t), _count(reference, t)
        lift = ((cg + 1) / (ng + 2)) / ((cr + 1) / (nr + 2))
        result[t] = (round(cg / ng, 4) if ng else 0.0,
                     round(cr / nr, 4) if nr else 0.0,
                     round(lift, 2))
    return result
```

不喜歡的只有 6 筆，結論不能說得太滿，所以加上樣本分級：

```python
def _tier(n, min_group, min_preliminary):
    if n >= min_group:
        return "建議"
    if n >= min_preliminary:
        return "初步"
    return None
```

- **拉普拉斯平滑**：不喜歡組 0 筆出現某標籤時，不會除以 0 或算出無限大。
- **對照組隨資料調整**：勾選後中立職缺只剩 2 筆，自動改成喜歡 vs 不喜歡直接對比。
- **最重要的發現**：喜歡和不喜歡的 ATS 平均分是 88 vs 87.3，原本的公式分不出我的喜好；AI Agent（Lift 2.55）與數位轉型（Lift 2.18）才是明確的偏好訊號。
- **決定權在我**：每筆洞察寫進 Notion 時預設「待決定」，系統不會自動改權重。

---

### 6. 真實資料會揭露樣本資料永遠不會出現的 bug

用樣本資料寫的 26 個測試全綠，第一筆真實的 Notion 剪藏一進來就報錯。其中一個例子是：`api` 用子字串比對，會命中 rapid、capital。

```python
def _compile(alias: str) -> re.Pattern:
    escaped = re.escape(alias)
    if _ASCII.match(alias):
        return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")
    return re.compile(escaped)
```

- **英文用單字邊界**：前後不能接英數字，`api` 就不會命中 rapid。
- **中文維持子字串比對**：中文沒有空格分詞，用邊界反而會漏抓。
- **先寫失敗的測試再修**：每個真實資料揭露的問題都對應一個測試，修正後舊測試全部重跑，確認沒有弄壞既有功能。

使用者指出的錯誤也直接變成黃金標準測試：

```python
def test_gold_taiwan_mobile_supply_chain_job():
    """實際技能是供應鏈流程診斷、AI 系統規格規劃、跨部門導入落地。"""
    tags, rejected = validate_tags(LLM_TAGS["電信C"], TWM)
    assert rejected == []
    assert {"流程優化", "需求分析", "導入推動"} <= tags
```

---

## 🔧 技術債

- 舊紀錄的 ATS 拆解欄位留空（舊分數由原 Agent 計算，回推會和總分對不上）
- 104 的「擅長工具」「工作技能」欄位 Clipper 抓不到，目前從職稱與內文判斷
- 不喜歡的原因無法從技能標籤看出，考慮新增「不喜歡原因」欄位
- 「不喜歡」目前只用於分析，尚未用於扣分
