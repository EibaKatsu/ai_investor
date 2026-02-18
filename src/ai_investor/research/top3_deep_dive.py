from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import os

import requests

from ai_investor.collectors.news import NewsItem, TdnetPublicCollector, WebSearchNewsCollector
from ai_investor.models import Candidate, Recommendation

AI_DEFAULT_MODEL = "gpt-4o-mini"
AI_TIMEOUT_SECONDS = 30


@dataclass(slots=True)
class _AIEvaluation:
    total_score: float
    decision: str
    reasons: list[str]
    risks: list[str]
    assumptions: list[str]
    industry_trends: list[str]
    peer_strengths: list[str]
    peer_weaknesses: list[str]
    lag_causes: list[str]
    critical_views: list[str]
    break_scenarios: list[str]
    reevaluation_triggers: list[str]


def build_recommendations(
    candidates: list[Candidate],
    top_k: int,
    *,
    web_news: WebSearchNewsCollector | None = None,
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
        news_items = _collect_news(
            candidate,
            web_news=web_news,
            tdnet=tdnet,
            lookback_days=news_lookback_days,
            as_of=as_of,
        )
        evaluation = _evaluate_candidate(candidate, news_items, as_of, peer_candidates=ranked)
        links = _build_source_links(news_items)

        recommendations.append(
            Recommendation(
                ticker=candidate.ticker,
                decision=evaluation.decision,
                reasons=evaluation.reasons,
                risks=evaluation.risks,
                assumptions=evaluation.assumptions,
                industry_trends=evaluation.industry_trends,
                peer_strengths=evaluation.peer_strengths,
                peer_weaknesses=evaluation.peer_weaknesses,
                lag_causes=evaluation.lag_causes,
                critical_views=evaluation.critical_views,
                break_scenarios=evaluation.break_scenarios,
                reevaluation_triggers=evaluation.reevaluation_triggers,
                source_links=links,
            )
        )
    return recommendations


def _collect_news(
    candidate: Candidate,
    *,
    web_news: WebSearchNewsCollector | None,
    tdnet: TdnetPublicCollector | None,
    lookback_days: int,
    as_of: date | None,
) -> list[NewsItem]:
    items: list[NewsItem] = []
    if web_news is not None:
        query = f'"{candidate.company_name}" OR "{candidate.ticker}"'
        items.extend(web_news.fetch_news(query=query, lookback_days=lookback_days, as_of=as_of))
    if tdnet is not None:
        items.extend(tdnet.fetch_news(ticker=candidate.ticker, lookback_days=lookback_days, as_of=as_of))
    return _dedupe_by_url(items)


def _evaluate_candidate(
    candidate: Candidate,
    news_items: list[NewsItem],
    as_of: date | None,
    *,
    peer_candidates: list[Candidate],
) -> _AIEvaluation:
    ai_eval = _evaluate_with_llm(candidate, news_items, as_of, peer_candidates=peer_candidates)
    if ai_eval is not None:
        return ai_eval
    return _fallback_evaluation(candidate, news_items, peer_candidates=peer_candidates)

def _evaluate_with_llm(
    candidate: Candidate,
    news_items: list[NewsItem],
    as_of: date | None,
    *,
    peer_candidates: list[Candidate],
) -> _AIEvaluation | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("OPENAI_MODEL", AI_DEFAULT_MODEL).strip() or AI_DEFAULT_MODEL
    api_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    endpoint = f"{api_base}/chat/completions"

    news_for_prompt = [
        {
            "title": item.title,
            "source": item.source,
            "published_at": item.published_at,
            "url": item.url,
            "summary": item.summary,
        }
        for item in news_items[:10]
    ]
    payload_obj = {
        "as_of": as_of.isoformat() if as_of is not None else None,
        "ticker": candidate.ticker,
        "company_name": candidate.company_name,
        "quantitative_score": round(candidate.quantitative_score, 2),
        "quantitative_score_price_now": round(candidate.quantitative_score_price_now, 2),
        "quantitative_score_fundamentals_base": round(candidate.quantitative_score_fundamentals_base, 2),
        "qualitative_score_total": round(candidate.qualitative_score_total, 2),
        "qualitative_score_max": round(candidate.qualitative_score_max, 2),
        "qualitative_score_100": round(candidate.qualitative_score_normalized, 2),
        "quantitative_metrics": candidate.quantitative_metrics,
        "peer_snapshot": _build_peer_snapshot(candidate, peer_candidates),
        "news": news_for_prompt,
    }

    system_prompt = (
        "あなたは日本株アナリストです。入力データのみを根拠に、"
        "投資判断を0-100点へポイント換算してください。"
        "キーワード機械判定ではなく、文脈・整合性・リスクの強弱で評価します。"
        "さらに、出遅れ原因を具体的に特定し、投資判断に対する批判的意見も提示してください。"
        "あわせて、業種の景気動向・傾向と、同業比較での強み・弱みを明示してください。"
        "以下5軸を0-5で採点し、平均×20をtotal_scoreにしてください。"
        "1) valuation_attractiveness 2) financial_quality 3) catalyst_strength "
        "4) downside_risk_control 5) evidence_quality。"
        "decisionは Recommend/Watch/Skip のいずれか。"
        "出力はJSONのみで返してください。"
    )
    user_prompt = (
        "次のJSONデータを評価してください。\n"
        f"{json.dumps(payload_obj, ensure_ascii=False)}\n"
        "出力JSONスキーマ:\n"
        "{"
        '"axis_scores":{"valuation_attractiveness":0-5,"financial_quality":0-5,"catalyst_strength":0-5,'
        '"downside_risk_control":0-5,"evidence_quality":0-5},'
        '"total_score":0-100,'
        '"decision":"Recommend|Watch|Skip",'
        '"reasons":["...最大3件"],'
        '"risks":["...最大3件"],'
        '"assumptions":["...最大3件"],'
        '"industry_trends":["...業種の景気動向・傾向を最大3件"],'
        '"peer_strengths":["...同業比較での強みを最大3件"],'
        '"peer_weaknesses":["...同業比較での弱みを最大3件"],'
        '"lag_causes":["...具体的な出遅れ原因を最大3件"],'
        '"critical_views":["...投資判断への批判的意見を最大3件"],'
        '"break_scenarios":["...最大3件"],'
        '"reevaluation_triggers":["...最大3件"]'
        "}"
    )

    body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(endpoint, headers=headers, json=body, timeout=AI_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    try:
        content = payload["choices"][0]["message"]["content"]
        model_result = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None

    axis_scores = model_result.get("axis_scores", {})
    score_values = []
    for key in (
        "valuation_attractiveness",
        "financial_quality",
        "catalyst_strength",
        "downside_risk_control",
        "evidence_quality",
    ):
        raw = axis_scores.get(key)
        if isinstance(raw, (int, float)):
            score_values.append(float(raw))

    if len(score_values) < 3:
        return None

    total_score = model_result.get("total_score")
    if not isinstance(total_score, (int, float)):
        total_score = (sum(score_values) / len(score_values)) * 20.0
    total_score = max(0.0, min(100.0, float(total_score)))

    decision = str(model_result.get("decision", "")).strip()
    if decision not in {"Recommend", "Watch", "Skip"}:
        decision = _decision_from_score(total_score)

    reasons = _clip_text_list(model_result.get("reasons"), 3)
    risks = _clip_text_list(model_result.get("risks"), 3)
    assumptions = _clip_text_list(model_result.get("assumptions"), 3)
    industry_trends = _clip_text_list(model_result.get("industry_trends"), 3)
    peer_strengths = _clip_text_list(model_result.get("peer_strengths"), 3)
    peer_weaknesses = _clip_text_list(model_result.get("peer_weaknesses"), 3)
    lag_causes = _clip_text_list(model_result.get("lag_causes"), 3)
    critical_views = _clip_text_list(model_result.get("critical_views"), 3)
    break_scenarios = _clip_text_list(model_result.get("break_scenarios"), 3)
    reevaluation_triggers = _clip_text_list(model_result.get("reevaluation_triggers"), 3)

    score_headline = (
        f"AI総合点 {total_score:.1f}/100 "
        f"(Valuation {axis_scores.get('valuation_attractiveness', 'N/A')}, "
        f"Financial {axis_scores.get('financial_quality', 'N/A')}, "
        f"Catalyst {axis_scores.get('catalyst_strength', 'N/A')}, "
        f"Risk {axis_scores.get('downside_risk_control', 'N/A')}, "
        f"Evidence {axis_scores.get('evidence_quality', 'N/A')})"
    )
    reasons = [score_headline] + reasons

    if not risks:
        risks = ["短期材料の変化により判断が変わる可能性"]
    if not assumptions:
        assumptions = ["次回決算・開示で前提条件を更新すること"]
    if not industry_trends:
        industry_trends = _infer_industry_trends(candidate, news_items)
    if not peer_strengths or not peer_weaknesses:
        fallback_strengths, fallback_weaknesses = _infer_peer_strengths_weaknesses(candidate, peer_candidates)
        if not peer_strengths:
            peer_strengths = fallback_strengths
        if not peer_weaknesses:
            peer_weaknesses = fallback_weaknesses
    if not lag_causes:
        lag_causes = _infer_lag_causes(candidate, news_items)
    if not critical_views:
        critical_views = _infer_critical_views(candidate, news_items, decision)
    if not break_scenarios:
        break_scenarios = ["業績または資本政策が悪化し前提が崩れる場合"]
    if not reevaluation_triggers:
        reevaluation_triggers = ["次回決算発表", "業績予想修正・配当修正の開示"]

    return _AIEvaluation(
        total_score=total_score,
        decision=decision,
        reasons=reasons[:3],
        risks=risks[:3],
        assumptions=assumptions[:3],
        industry_trends=industry_trends[:3],
        peer_strengths=peer_strengths[:3],
        peer_weaknesses=peer_weaknesses[:3],
        lag_causes=lag_causes[:3],
        critical_views=critical_views[:3],
        break_scenarios=break_scenarios[:3],
        reevaluation_triggers=reevaluation_triggers[:3],
    )

def _fallback_evaluation(
    candidate: Candidate,
    news_items: list[NewsItem],
    *,
    peer_candidates: list[Candidate],
) -> _AIEvaluation:
    qual_100 = candidate.qualitative_score_normalized
    total_score = (candidate.quantitative_score * 0.8) + (qual_100 * 0.2)
    decision = _decision_from_score(total_score)
    reasons = [
        f"暫定点 {total_score:.1f}/100（AI評価API未設定または応答不正）",
        f"定量総合点 {candidate.quantitative_score:.1f} / 定性換算 {qual_100:.1f}",
        f"参照ニュース件数 {len(news_items)}件",
    ]
    risks = [
        "AI評価が未適用のため、詳細判断の精度が限定的",
    ]
    assumptions = [
        "AI評価APIを有効化して再採点すること",
    ]
    industry_trends = _infer_industry_trends(candidate, news_items)
    peer_strengths, peer_weaknesses = _infer_peer_strengths_weaknesses(candidate, peer_candidates)
    lag_causes = _infer_lag_causes(candidate, news_items)
    critical_views = _infer_critical_views(candidate, news_items, decision)
    break_scenarios = [
        "決算や開示で前提条件が変化した場合",
    ]
    reevaluation_triggers = [
        "OPENAI_API_KEY設定後の再実行",
        "次回決算発表",
    ]
    return _AIEvaluation(
        total_score=total_score,
        decision=decision,
        reasons=reasons[:3],
        risks=risks[:3],
        assumptions=assumptions[:3],
        industry_trends=industry_trends[:3],
        peer_strengths=peer_strengths[:3],
        peer_weaknesses=peer_weaknesses[:3],
        lag_causes=lag_causes[:3],
        critical_views=critical_views[:3],
        break_scenarios=break_scenarios[:3],
        reevaluation_triggers=reevaluation_triggers[:3],
    )


def _decision_from_score(score: float) -> str:
    if score >= 75.0:
        return "Recommend"
    if score >= 50.0:
        return "Watch"
    return "Skip"


def _clip_text_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _build_source_links(items: list[NewsItem]) -> list[str]:
    links = []
    for item in items[:5]:
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


def _build_peer_snapshot(candidate: Candidate, peer_candidates: list[Candidate]) -> dict[str, object]:
    strengths, weaknesses = _infer_peer_strengths_weaknesses(candidate, peer_candidates)
    metric_snapshot = {}
    for metric_id in (
        "pbr",
        "per",
        "dividend_yield",
        "roe",
        "equity_ratio",
        "net_de_ratio",
        "revenue_cagr_3y",
        "op_income_cagr_3y",
    ):
        rank_info = _metric_peer_rank(candidate, peer_candidates, metric_id, higher_is_better=(metric_id not in {"pbr", "per", "net_de_ratio"}))
        if rank_info is None:
            continue
        rank, n = rank_info
        metric_snapshot[metric_id] = {"rank": rank, "peer_count": n}
    return {
        "sector": candidate.sector,
        "strengths": strengths[:3],
        "weaknesses": weaknesses[:3],
        "metric_ranks": metric_snapshot,
    }


def _infer_industry_trends(candidate: Candidate, news_items: list[NewsItem]) -> list[str]:
    sector_name = candidate.sector or "対象業種"
    if not news_items:
        return [
            f"{sector_name}の景気動向を評価するニュース件数が不足している",
        ]

    positive_kw = ("需要", "回復", "増", "改善", "上方", "拡大", "好調", "追い風")
    negative_kw = ("減速", "悪化", "下方", "停滞", "逆風", "不透明", "事故", "訴訟", "減益")
    positive_count = 0
    negative_count = 0
    for item in news_items:
        title = item.title
        if any(k in title for k in positive_kw):
            positive_count += 1
        if any(k in title for k in negative_kw):
            negative_count += 1

    trends: list[str] = []
    if positive_count > negative_count:
        trends.append(f"{sector_name}は足元で回復・拡大寄りのニュースが優勢（+{positive_count}/-{negative_count}）")
    elif negative_count > positive_count:
        trends.append(f"{sector_name}は足元で減速・逆風寄りのニュースが優勢（+{positive_count}/-{negative_count}）")
    else:
        trends.append(f"{sector_name}は強弱材料が拮抗し、方向感が定まりにくい（+{positive_count}/-{negative_count}）")

    latest = news_items[0].title if news_items else ""
    if latest:
        trends.append(f"直近材料: {latest}")
    if len(news_items) < 3:
        trends.append("記事母数が少ないため、業種トレンド判定の確度は限定的")
    return trends[:3]


def _infer_peer_strengths_weaknesses(candidate: Candidate, peer_candidates: list[Candidate]) -> tuple[list[str], list[str]]:
    metric_defs = [
        ("pbr", "PBR", False),
        ("per", "PER", False),
        ("dividend_yield", "配当利回り", True),
        ("roe", "ROE", True),
        ("equity_ratio", "自己資本比率", True),
        ("net_de_ratio", "ネットD/E", False),
        ("revenue_cagr_3y", "売上高変化率", True),
        ("op_income_cagr_3y", "経常利益変化率", True),
    ]

    strengths: list[str] = []
    weaknesses: list[str] = []
    for metric_id, label, higher_is_better in metric_defs:
        rank_info = _metric_peer_rank(candidate, peer_candidates, metric_id, higher_is_better=higher_is_better)
        if rank_info is None:
            continue
        rank, n = rank_info
        bucket = max(1, (n + 2) // 3)
        if rank <= bucket:
            strengths.append(f"{label}が同業{n}社中で上位（{rank}位）")
        if rank > n - bucket:
            weaknesses.append(f"{label}が同業{n}社中で下位（{rank}位）")

    if not strengths:
        strengths.append("同業比較で突出した優位性は限定的")
    if not weaknesses:
        weaknesses.append("同業比較で顕著な弱点は限定的")
    return strengths[:3], weaknesses[:3]


def _metric_peer_rank(
    candidate: Candidate,
    peer_candidates: list[Candidate],
    metric_id: str,
    *,
    higher_is_better: bool,
) -> tuple[int, int] | None:
    peers = _peer_group(candidate, peer_candidates)
    values: list[tuple[str, float]] = []
    for peer in peers:
        value = _metric(peer.quantitative_metrics, metric_id)
        if value is None:
            continue
        values.append((peer.ticker, value))

    if len(values) < 3:
        return None
    sorted_values = sorted(values, key=lambda x: x[1], reverse=higher_is_better)
    for idx, (ticker, _) in enumerate(sorted_values, start=1):
        if ticker == candidate.ticker:
            return idx, len(sorted_values)
    return None


def _peer_group(candidate: Candidate, peers: list[Candidate]) -> list[Candidate]:
    same_sector = [peer for peer in peers if peer.sector == candidate.sector]
    if len(same_sector) >= 3:
        return same_sector
    return peers


def _infer_lag_causes(candidate: Candidate, news_items: list[NewsItem]) -> list[str]:
    metrics = candidate.quantitative_metrics
    causes: list[str] = []

    per = _metric(metrics, "per")
    pbr = _metric(metrics, "pbr")
    roe = _metric(metrics, "roe")
    revenue = _metric(metrics, "revenue_cagr_3y")
    op_income = _metric(metrics, "op_income_cagr_3y")
    de_ratio = _metric(metrics, "net_de_ratio")

    if per is not None and per < 12.0 and pbr is not None and pbr < 1.2:
        causes.append("低PER・低PBRの割安状態が継続し、評価修正が進んでいない")
    if revenue is not None and revenue < 5.0:
        causes.append("売上成長率が鈍く、成長期待の織り込みが弱い")
    if op_income is not None and op_income < 5.0:
        causes.append("利益成長の弱さが株価評価の重しになっている")
    if roe is not None and roe < 8.0:
        causes.append("ROE水準が相対的に低く、資本効率面で評価が伸びにくい")
    if de_ratio is not None and de_ratio > 80.0:
        causes.append("財務レバレッジへの懸念がバリュエーションを抑制している")

    negative_heads = _extract_negative_headlines(news_items)
    if negative_heads:
        causes.append(f"直近でネガティブ材料（例: {negative_heads[0]}）が意識されている")
    if not causes:
        causes.append("材料不足により評価見直しのトリガーが不明確")
    return causes[:3]


def _infer_critical_views(candidate: Candidate, news_items: list[NewsItem], decision: str) -> list[str]:
    metrics = candidate.quantitative_metrics
    views: list[str] = []

    if decision == "Recommend":
        views.append("割安指標はバリュートラップであり、再評価が起きない可能性がある")

    if _metric(metrics, "op_income_cagr_3y") is not None and _metric(metrics, "op_income_cagr_3y") < 0.0:
        views.append("利益成長がマイナスで、投資判断が早計である可能性がある")
    if _metric(metrics, "revenue_cagr_3y") is not None and _metric(metrics, "revenue_cagr_3y") < 0.0:
        views.append("売上が縮小トレンドで、中長期の成長前提が崩れる可能性がある")
    if _metric(metrics, "net_de_ratio") is not None and _metric(metrics, "net_de_ratio") > 100.0:
        views.append("負債負担が重く、景気後退局面で下振れ余地が大きい")
    if not news_items:
        views.append("ニュース根拠が限定的で、現時点の判断確度は十分ではない")
    elif _extract_negative_headlines(news_items):
        views.append("直近ニュースにネガティブ事象が含まれ、想定以上の下方リスクがある")

    if not views:
        views.append("外部環境悪化時には想定リターンより先にリスクが顕在化し得る")
    return views[:3]


def _extract_negative_headlines(news_items: list[NewsItem]) -> list[str]:
    keywords = ("減益", "下方修正", "事故", "訴訟", "不祥事", "赤字", "業績悪化", "減配")
    found: list[str] = []
    for item in news_items:
        title = item.title
        if any(k in title for k in keywords):
            found.append(title)
        if len(found) >= 3:
            break
    return found


def _metric(metrics: dict[str, float], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None
