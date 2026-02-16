from __future__ import annotations

from ai_investor.models import Candidate


PRICE_NOW_METRICS = {
    "pbr",
    "per",
    "dividend_yield",
}


def score_candidates(candidates: list[Candidate], metrics: list[dict[str, str]]) -> None:
    """Split quantitative scoring into price_now and fundamentals_base tracks."""
    if not candidates or not metrics:
        return

    price_metric_defs = [m for m in metrics if m.get("id") in PRICE_NOW_METRICS]
    fundamentals_metric_defs = [m for m in metrics if m.get("id") not in PRICE_NOW_METRICS]

    price_scores_by_metric = _score_by_metrics(candidates, price_metric_defs)
    fundamentals_scores_by_metric = _score_by_metrics(candidates, fundamentals_metric_defs)

    for candidate in candidates:
        price_values = [score_map[candidate.ticker] for score_map in price_scores_by_metric if candidate.ticker in score_map]
        fundamentals_values = [
            score_map[candidate.ticker] for score_map in fundamentals_scores_by_metric if candidate.ticker in score_map
        ]

        candidate.quantitative_score_price_now = _avg(price_values)
        candidate.quantitative_score_fundamentals_base = _avg(fundamentals_values)

        track_scores = [s for s in [candidate.quantitative_score_price_now, candidate.quantitative_score_fundamentals_base] if s > 0]
        candidate.quantitative_score = _avg(track_scores)


def _score_by_metrics(candidates: list[Candidate], metric_defs: list[dict[str, str]]) -> list[dict[str, float]]:
    scored_metrics: list[dict[str, float]] = []
    for metric_def in metric_defs:
        metric_id = metric_def.get("id")
        if not metric_id:
            continue
        better = metric_def.get("better", "higher")
        metric_values = []
        for candidate in candidates:
            value = candidate.quantitative_metrics.get(metric_id)
            if isinstance(value, (int, float)):
                metric_values.append((candidate.ticker, float(value)))
        if not metric_values:
            continue
        scored_metrics.append(_rank_score(metric_values, higher_is_better=(better == "higher")))
    return scored_metrics


def _rank_score(metric_values: list[tuple[str, float]], higher_is_better: bool) -> dict[str, float]:
    sorted_values = sorted(metric_values, key=lambda item: item[1], reverse=higher_is_better)
    n = len(sorted_values)
    if n == 1:
        return {sorted_values[0][0]: 100.0}

    scores: dict[str, float] = {}
    for idx, (ticker, _) in enumerate(sorted_values):
        percentile = 1.0 - (idx / (n - 1))
        scores[ticker] = percentile * 100.0
    return scores


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
