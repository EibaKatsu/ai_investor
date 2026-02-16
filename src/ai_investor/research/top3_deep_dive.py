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
        evaluation = _evaluate_candidate(candidate, news_items, as_of)
        links = _build_source_links(news_items)

        recommendations.append(
            Recommendation(
                ticker=candidate.ticker,
                decision=evaluation.decision,
                reasons=evaluation.reasons,
                risks=evaluation.risks,
                assumptions=evaluation.assumptions,
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


def _evaluate_candidate(candidate: Candidate, news_items: list[NewsItem], as_of: date | None) -> _AIEvaluation:
    ai_eval = _evaluate_with_llm(candidate, news_items, as_of)
    if ai_eval is not None:
        return ai_eval
    return _fallback_evaluation(candidate, news_items)


def _evaluate_with_llm(candidate: Candidate, news_items: list[NewsItem], as_of: date | None) -> _AIEvaluation | None:
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
        "quantitative_metrics": candidate.quantitative_metrics,
        "news": news_for_prompt,
    }

    system_prompt = (
        "あなたは日本株アナリストです。入力データのみを根拠に、"
        "投資判断を0-100点へポイント換算してください。"
        "キーワード機械判定ではなく、文脈・整合性・リスクの強弱で評価します。"
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
        break_scenarios=break_scenarios[:3],
        reevaluation_triggers=reevaluation_triggers[:3],
    )


def _fallback_evaluation(candidate: Candidate, news_items: list[NewsItem]) -> _AIEvaluation:
    qual_100 = (candidate.qualitative_score_total / 25.0) * 100.0
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
