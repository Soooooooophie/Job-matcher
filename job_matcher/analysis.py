"""偏好分析：從你的行為（收藏、投遞、面試、不喜歡）找出偏好，以及公式和你判斷的落差。

第二版（因真實資料而改）：
  - 正向訊號 = 手動收藏 或 已投遞 或 面試中；負向訊號 = 不喜歡
  - 參照組：中立組夠大就和中立組比；不夠大（勾選後只剩 2 筆）就改成正負兩組直接對比
  - 樣本分級：≥ min_group 給建議；min_preliminary ~ min_group-1 只給「初步觀察」；更少不輸出
  - 標籤分三個維度（技術／職能／領域），加上維度前綴避免同名混淆

四種比較：
  1. 標籤 Lift      ：某標籤在該組出現比例 ÷ 在參照組出現比例
  2. ATS 各項目差異 ：兩組在技術分、年資分…的平均差
  3. ATS 區分力     ：喜歡和不喜歡的 ATS 平均分是否真的不同
  4. 不一致案例     ：ATS 低卻喜歡（公式低估）、ATS 高卻不喜歡（公式高估）
"""
import json
from dataclasses import dataclass, field
from statistics import mean

from .notion_sync import is_manual_clip

COMPONENTS = ("技術分", "年資分", "學歷分", "公司分", "關鍵字加分")
TAG_COLUMN = "技能標籤"     # v3：單一統一標籤欄位


@dataclass
class Row:
    title: str
    ats: float = None
    skills: set = field(default_factory=set)       # 帶維度前綴的標籤，例如「領域:esg」
    liked: bool = False
    disliked: bool = False
    components: dict = field(default_factory=dict)
    applied: bool = False
    interviewing: bool = False


@dataclass
class Insight:
    title: str
    kind: str              # 偏好 / 排斥 / 項目差異 / 公式低估 / 公式高估
    evidence: str
    suggestion: str
    sample_size: int
    lift: float = None


@dataclass
class Report:
    status: str            # 樣本不足 / 完成
    message: str
    insights: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    quality: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# 讀取
# ---------------------------------------------------------------------------
def _parse_list(value) -> list:
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [v.strip() for v in value.split(",")]
    return [v for v in value if v]


def _yes(value) -> bool:
    return value in ("__YES__", True)


def row_from_notion(props: dict) -> Row:
    tags = set(_parse_list(props.get(TAG_COLUMN)))
    applied, interviewing = _yes(props.get("已投遞")), _yes(props.get("面試中"))
    return Row(
        title=props.get("職位名稱", ""),
        ats=props.get("ATS分數"),
        skills=tags,
        liked=is_manual_clip(props) or applied or interviewing,
        disliked=_yes(props.get("不喜歡")),
        components={k: props[k] for k in COMPONENTS if props.get(k) is not None},
        applied=applied,
        interviewing=interviewing,
    )


# ---------------------------------------------------------------------------
# 計算
# ---------------------------------------------------------------------------
def split_groups(rows):
    liked, disliked, neutral, conflicts = [], [], [], []
    for r in rows:
        if r.liked and r.disliked:
            conflicts.append(r)
        elif r.liked:
            liked.append(r)
        elif r.disliked:
            disliked.append(r)
        else:
            neutral.append(r)
    return liked, disliked, neutral, conflicts


def _count(rows, tag):
    return sum(1 for r in rows if tag in r.skills)


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


def component_deltas(group, reference) -> dict:
    deltas = {}
    for comp in COMPONENTS:
        g = [r.components[comp] for r in group if comp in r.components]
        b = [r.components[comp] for r in reference if comp in r.components]
        if g and b:
            deltas[comp] = round(mean(g) - mean(b), 2)
    return deltas


def ats_separation(liked, disliked):
    """(喜歡組 ATS 平均, 不喜歡組 ATS 平均, 差距)。"""
    a = [r.ats for r in liked if r.ats is not None]
    b = [r.ats for r in disliked if r.ats is not None]
    if not a or not b:
        return None
    ma, mb = round(mean(a), 1), round(mean(b), 1)
    return ma, mb, round(ma - mb, 1)


def disagreements(liked, disliked, threshold=85.0):
    under = [r for r in liked if r.ats is not None and r.ats < threshold]
    over = [r for r in disliked if r.ats is not None and r.ats >= threshold]
    return under, over


def data_quality_issues(rows) -> list:
    issues = []
    for r in rows:
        if r.interviewing and not r.applied:
            issues.append(f"「{r.title}」勾了面試中，但沒有勾已投遞")
        if r.applied and r.disliked:
            issues.append(f"「{r.title}」同時勾了已投遞和不喜歡，訊號互相矛盾")
    return issues


# ---------------------------------------------------------------------------
# 產生洞察
# ---------------------------------------------------------------------------
def _tier(n, min_group, min_preliminary):
    if n >= min_group:
        return "建議"
    if n >= min_preliminary:
        return "初步"
    return None


def _mark(insight: Insight, tier: str) -> Insight:
    if tier == "初步":
        insight.title = "【初步觀察】" + insight.title
        insight.suggestion += f"（樣本 {insight.sample_size} 筆，先觀察，暫不建議據此調整權重）"
    return insight


def _tag_insights(group, reference, kind, label, ref_label, lift_threshold, min_count):
    out = []
    for tag, (sg, sr, lift) in skill_lift(group, reference).items():
        cg = _count(group, tag)
        if lift < lift_threshold or cg < min_count:
            continue
        cr = _count(reference, tag)
        evidence = (f"{label} {cg}/{len(group)} 筆有 {tag}（{sg:.0%}），"
                    f"{ref_label} {cr}/{len(reference)} 筆（{sr:.0%}），Lift {lift}")
        suggestion = (f"考慮提高「{tag}」的權重，或加入關鍵字加分清單" if kind == "偏好"
                      else f"考慮對「{tag}」降低權重，或列為排除條件")
        out.append(Insight(f"{kind}：{tag}", kind, evidence, suggestion, len(group), lift))
    return sorted(out, key=lambda i: -i.lift)


def _component_insights(group, reference, label, ref_label, min_gap=3.0):
    out = []
    for comp, delta in component_deltas(group, reference).items():
        if abs(delta) < min_gap:
            continue
        direction = "高" if delta > 0 else "低"
        out.append(Insight(f"項目差異：{label}的{comp}偏{direction}", "項目差異",
                           f"{label}{comp}平均比{ref_label}{direction} {abs(delta)} 分",
                           f"檢查「{comp}」的權重是否反映你的真實偏好", len(group)))
    return out


def _distinctive_tags(rows, other, top=3, min_lift=1.5, min_count=2):
    """這幾筆案例共有、而且在另一組明顯比較少見的標籤（不是單純最常見的）。"""
    scored = [(t, lift) for t, (_, _, lift) in skill_lift(rows, other).items()
              if lift >= min_lift and _count(rows, t) >= min_count]
    return [t for t, _ in sorted(scored, key=lambda x: (-x[1], x[0]))[:top]]


def _describe_tags(rows, other):
    tags = _distinctive_tags(rows, other)
    if tags:
        return f"區別標籤：{'、'.join(tags)}"
    return "沒有共同的區別標籤（各筆的特徵分散，原因可能不在技能面）"


def generate_insights(rows, min_group=10, min_preliminary=5, lift_threshold=2.0,
                      min_count=3, threshold=85.0) -> Report:
    liked, disliked, neutral, conflicts = split_groups(rows)
    quality = data_quality_issues(rows)
    tier_l = _tier(len(liked), min_group, min_preliminary)
    tier_d = _tier(len(disliked), min_group, min_preliminary)

    if not tier_l and not tier_d:
        return Report("樣本不足",
                      f"目前正向（收藏／投遞／面試）{len(liked)} 筆、不喜歡 {len(disliked)} 筆；"
                      f"任一組累積到 {min_preliminary} 筆後開始初步觀察，{min_group} 筆後產生建議",
                      [], conflicts, quality)

    use_neutral = len(neutral) >= min_group
    insights = []

    if tier_l:
        ref, ref_label = (neutral, "中立組") if use_neutral else (disliked, "不喜歡組")
        if ref:
            batch = (_tag_insights(liked, ref, "偏好", "喜歡組", ref_label, lift_threshold, min_count)
                     + _component_insights(liked, ref, "喜歡組", ref_label))
            insights += [_mark(i, tier_l) for i in batch]

    if tier_d:
        ref, ref_label = (neutral, "中立組") if use_neutral else (liked, "喜歡組")
        if ref:
            batch = (_tag_insights(disliked, ref, "排斥", "不喜歡組", ref_label, lift_threshold, min_count)
                     + _component_insights(disliked, ref, "不喜歡組", ref_label))
            insights += [_mark(i, tier_d) for i in batch]

    # ATS 區分力：兩組都至少達到初步門檻才比
    if tier_l and tier_d:
        sep = ats_separation(liked, disliked)
        both_tier = "建議" if tier_l == tier_d == "建議" else "初步"
        if sep and abs(sep[2]) < 2.0:
            insights.append(_mark(Insight(
                "ATS 總分無法區分喜歡與不喜歡", "項目差異",
                f"喜歡組 ATS 平均 {sep[0]}，不喜歡組 {sep[1]}，差距只有 {sep[2]} 分",
                "目前公式衡量的面向，和你實際喜好的面向不同；可優先參考標籤層面的差異",
                min(len(liked), len(disliked))), both_tier))

    under, over = disagreements(liked, disliked, threshold)
    if tier_l and len(under) >= min_count:
        insights.append(_mark(Insight(
            f"公式低估：{len(under)} 筆喜歡的職缺未達門檻", "公式低估",
            f"例如：{'、'.join(r.title for r in under[:5])}；{_describe_tags(under, disliked or neutral)}",
            "若有區別標籤，可能被公式低估，考慮提高權重", len(under)), tier_l))
    if tier_d and len(over) >= min_count:
        insights.append(_mark(Insight(
            f"公式高估：{len(over)}/{len(disliked)} 筆不喜歡的職缺超過門檻", "公式高估",
            f"例如：{'、'.join(r.title for r in over[:5])}；{_describe_tags(over, liked or neutral)}",
            "若有區別標籤，可能被公式高估，考慮降低權重；若沒有，請補充不喜歡的原因", len(over)), tier_d))

    ref_desc = "對比中立組" if use_neutral else "中立組太少，改為對比不喜歡組"
    return Report("完成",
                  f"正向 {len(liked)} 筆、不喜歡 {len(disliked)} 筆、中立 {len(neutral)} 筆；{ref_desc}",
                  insights, conflicts, quality)


def to_notion_insight(insight: Insight, date: str) -> dict:
    """轉成「偏好洞察」資料庫的欄位；決定欄預設「待決定」。"""
    props = {
        "洞察": insight.title,
        "類型": insight.kind,
        "證據": insight.evidence,
        "建議調整": insight.suggestion,
        "樣本數": insight.sample_size,
        "你的決定": "待決定",
        "date:分析日期:start": date,
        "date:分析日期:is_datetime": 0,
    }
    if insight.lift is not None:
        props["Lift"] = insight.lift
    return props
