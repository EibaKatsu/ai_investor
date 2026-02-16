from __future__ import annotations

from datetime import date

from ai_investor.collectors.news import GNewsCollector, NewsItem, TdnetPublicCollector
from ai_investor.models import Candidate, Recommendation

POSITIVE_KEYWORDS = (
    "上方修正",
    "増配",
    "自社株買い",
    "過去最高",
    "黒字転換",
    "受注",
    "提携",
    "成長",
    "新製品",
)

NEGATIVE_KEYWORDS = (
    "下方修正",
    "減配",
    "赤字",
    "不祥事",
    "訴訟",
    "リコール",
    "減益",
    "行政処分",
    "業績悪化",
)


def build_recommendations(
    candidates: list[Candidate],
    top_k: int,
    *,
    gnews: GNewsCollector | None = None,
    tdnet: TdnetPublicCollector | None = None,
    news_lookback_days: int = 30,
    as_of: date | None = None,
) -> list[Recommendation]:
    ranked = sorted(
        [c for c in candidates if not c.excluded],
        key=lambda c: c.composite_score,
        reverse=True,
    )
    selected = ranked[:top_k]
    recommendations: list[Recommendation] = []
    for candidate in selected:
        news_items = _collect_news(candidate, gnews=gnews, tdnet=tdnet, lookback_days=news_lookback_days, as_of=as_of)
        positive_items, negative_items, neutral_items = _classify_news(news_items)
        decision = _decide(
            candidate,
            positive_count=len(positive_items),
            negative_count=len(negative_items),
            total_news=len(news_items),
        )

        reasons = _build_reasons(candidate, positive_items, negative_items, len(news_items))
        risks = _build_risks(negative_items, len(news_items))
        assumptions = _build_assumptions(decision)
        break_scenarios = _build_break_scenarios(negative_items)
        reevaluation_triggers = _build_reevaluation_triggers(decision)
        links = _build_source_links(positive_items, negative_items, neutral_items)

        recommendations.append(
            Recommendation(
                ticker=candidate.ticker,
                decision=decision,
                reasons=reasons,
                risks=risks,
                assumptions=assumptions,
                break_scenarios=break_scenarios,
                reevaluation_triggers=reevaluation_triggers,
                source_links=links,
            )
        )
    return recommendations


def _collect_news(
    candidate: Candidate,
    *,
    gnews: GNewsCollector | None,
    tdnet: TdnetPublicCollector | None,
    lookback_days: int,
    as_of: date | None,
) -> list[NewsItem]:
    items: list[NewsItem] = []
    if gnews is not None:
        query = f"\"{candidate.company_name}\" OR \"{candidate.ticker}\""
        items.extend(gnews.fetch_news(query=query, lookback_days=lookback_days, as_of=as_of))
    if tdnet is not None:
        items.extend(tdnet.fetch_news(ticker=candidate.ticker, lookback_days=lookback_days, as_of=as_of))
    return _dedupe_by_url(items)


def _classify_news(news_items: list[NewsItem]) -> tuple[list[NewsItem], list[NewsItem], list[NewsItem]]:
    positive: list[NewsItem] = []
    negative: list[NewsItem] = []
    neutral: list[NewsItem] = []
    for item in news_items:
        title = item.title
        if any(keyword in title for keyword in NEGATIVE_KEYWORDS):
            negative.append(item)
        elif any(keyword in title for keyword in POSITIVE_KEYWORDS):
            positive.append(item)
        else:
            neutral.append(item)
    return positive, negative, neutral


def _decide(candidate: Candidate, *, positive_count: int, negative_count: int, total_news: int) -> str:
    if negative_count >= 2 and negative_count > positive_count:
        return "Skip"
    if candidate.quantitative_score >= 70.0 and positive_count >= 1 and negative_count == 0:
        return "Recommend"
    if total_news == 0:
        return "Watch"
    return "Watch"


def _build_reasons(
    candidate: Candidate,
    positive_items: list[NewsItem],
    negative_items: list[NewsItem],
    total_news: int,
) -> list[str]:
    reasons = [f"定量総合点 {candidate.quantitative_score:.1f}（Q(Price) {candidate.quantitative_score_price_now:.1f} / Q(Fund) {candidate.quantitative_score_fundamentals_base:.1f}）"]
    if total_news == 0:
        reasons.append("直近ニュースの自動取得件数が0件のため、追加確認が必要")
        return reasons[:3]

    reasons.append(f"直近ニュース {total_news}件（ポジティブ {len(positive_items)} / ネガティブ {len(negative_items)}）")
    if positive_items:
        reasons.append(f"ポジティブ見出し例: {positive_items[0].title}")
    elif negative_items:
        reasons.append(f"ネガティブ見出し例: {negative_items[0].title}")
    return reasons[:3]


def _build_risks(negative_items: list[NewsItem], total_news: int) -> list[str]:
    risks: list[str] = []
    for item in negative_items[:2]:
        risks.append(f"ネガティブ材料: {item.title}")
    if total_news == 0:
        risks.append("ニュース根拠が不足（APIキー未設定または該当記事なし）")
    if not risks:
        risks.append("短期的な材料変化で判断が反転する可能性")
    return risks[:3]


def _build_assumptions(decision: str) -> list[str]:
    if decision == "Recommend":
        return [
            "次回決算でガイダンス維持または改善が確認されること",
            "直近1か月で重大なネガティブ開示がないこと",
        ]
    if decision == "Skip":
        return [
            "ネガティブ材料が継続する前提で保守的に評価",
        ]
    return [
        "追加の決算・開示確認後に再判定すること",
    ]


def _build_break_scenarios(negative_items: list[NewsItem]) -> list[str]:
    if negative_items:
        return [
            "ネガティブ材料が継続し、利益見通しが下方修正される場合",
        ]
    return [
        "資本政策または業績トレンドが反転してバリュエーション優位が失われる場合",
    ]


def _build_reevaluation_triggers(decision: str) -> list[str]:
    base = [
        "次回決算発表",
        "業績予想修正・配当修正の開示",
    ]
    if decision != "Recommend":
        base.append("ポジティブ材料を伴う新規ニュースの増加")
    return base[:3]


def _build_source_links(positive_items: list[NewsItem], negative_items: list[NewsItem], neutral_items: list[NewsItem]) -> list[str]:
    ordered = positive_items + negative_items + neutral_items
    links = []
    for item in ordered[:5]:
        links.append(f"{item.title} | {item.source} | {item.published_at} | {item.url}")
    return links


def _dedupe_by_url(items: list[NewsItem]) -> list[NewsItem]:
    deduped: list[NewsItem] = []
    seen_urls: set[str] = set()
    for item in items:
        if not item.url or item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        deduped.append(item)
    return deduped
