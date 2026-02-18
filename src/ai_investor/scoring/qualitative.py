from __future__ import annotations

from typing import Any

from ai_investor.models import Candidate


def score_candidates(
    candidates: list[Candidate],
    axes: list[dict[str, Any]],
    *,
    scale_max: int = 5,
) -> None:
    """Rule-based qualitative scoring from available quantitative proxies."""
    axis_defs = _normalize_axes(axes)
    total_weight = sum(weight for _, weight in axis_defs) or 1.0
    max_score = total_weight * float(scale_max)

    for candidate in candidates:
        axis_scores: dict[str, float] = {}
        weighted_total = 0.0
        for axis_id, weight in axis_defs:
            axis_score = _score_axis(candidate, axis_id)
            axis_scores[axis_id] = axis_score
            weighted_total += axis_score * weight

        candidate.qualitative_scores = axis_scores
        candidate.qualitative_score_total = round(weighted_total, 2)
        candidate.qualitative_score_max = round(max_score, 2)
        candidate.qualitative_score_normalized = _to_100(weighted_total, max_score)


def _normalize_axes(axes: list[dict[str, Any]]) -> list[tuple[str, float]]:
    if not axes:
        return []
    normalized: list[tuple[str, float]] = []
    for axis in axes:
        axis_id = str(axis.get("id", "")).strip()
        if not axis_id:
            continue
        raw_weight = axis.get("weight", 1.0)
        weight = float(raw_weight) if isinstance(raw_weight, (int, float)) else 1.0
        if weight <= 0:
            continue
        normalized.append((axis_id, weight))
    return normalized


def _score_axis(candidate: Candidate, axis_id: str) -> float:
    metrics = candidate.quantitative_metrics

    if axis_id == "temporary_lag_factor":
        return _avg(
            [
                _lower_better_score(metrics.get("pbr"), [0.8, 1.0, 1.3, 1.8]),
                _lower_better_score(metrics.get("per"), [8.0, 12.0, 16.0, 22.0]),
                _higher_better_score(metrics.get("roe"), [5.0, 8.0, 12.0, 16.0]),
            ]
        )

    if axis_id == "growth_driver_confidence":
        return _avg(
            [
                _higher_better_score(metrics.get("revenue_cagr_3y"), [0.0, 3.0, 7.0, 12.0]),
                _higher_better_score(metrics.get("op_income_cagr_3y"), [0.0, 5.0, 10.0, 15.0]),
                _higher_better_score(metrics.get("roe"), [5.0, 8.0, 12.0, 16.0]),
            ]
        )

    if axis_id == "management_and_capital_policy":
        return _avg(
            [
                _higher_better_score(metrics.get("dividend_yield"), [1.0, 2.0, 3.0, 4.0]),
                _higher_better_score(metrics.get("equity_ratio"), [25.0, 35.0, 45.0, 60.0]),
                _lower_better_score(metrics.get("net_de_ratio"), [30.0, 60.0, 100.0, 150.0]),
            ]
        )

    if axis_id == "competitive_advantage":
        return _avg(
            [
                _higher_better_score(metrics.get("roe"), [5.0, 8.0, 12.0, 16.0]),
                _higher_better_score(metrics.get("op_income_cagr_3y"), [0.0, 5.0, 10.0, 15.0]),
            ]
        )

    if axis_id == "risk_resilience":
        return _avg(
            [
                _higher_better_score(metrics.get("equity_ratio"), [25.0, 35.0, 45.0, 60.0]),
                _lower_better_score(metrics.get("net_de_ratio"), [30.0, 60.0, 100.0, 150.0]),
            ]
        )

    if axis_id == "revenue_growth_strength":
        growth_now = _metric(metrics, "revenue_growth_forecast")
        growth_3y = _metric(metrics, "revenue_cagr_3y")
        profit_growth = _metric(metrics, "op_income_growth_forecast")
        return _avg(
            [
                _higher_better_score(growth_now, [5.0, 10.0, 15.0, 25.0]),
                _higher_better_score(growth_3y, [5.0, 10.0, 15.0, 20.0]),
                _higher_better_score(profit_growth, [5.0, 10.0, 20.0, 30.0]),
            ]
        )

    if axis_id == "tam_expansion_potential":
        growth_now = _metric(metrics, "revenue_growth_forecast")
        growth_3y = _metric(metrics, "revenue_cagr_3y")
        market_cap = _metric(metrics, "market_cap_jpy")
        return _avg(
            [
                _higher_better_score(growth_now, [10.0, 15.0, 20.0, 30.0]),
                _higher_better_score(growth_3y, [8.0, 12.0, 16.0, 22.0]),
                _tam_runway_score(market_cap),
            ]
        )

    if axis_id == "profit_structure_improvement":
        op_margin = _metric(metrics, "operating_margin")
        profit_growth = _metric(metrics, "op_income_growth_forecast")
        return _avg(
            [
                _higher_better_score(op_margin, [8.0, 12.0, 18.0, 25.0]),
                _higher_better_score(profit_growth, [0.0, 10.0, 20.0, 35.0]),
            ]
        )

    if axis_id == "moat_strength":
        op_margin = _metric(metrics, "operating_margin")
        roe = _metric(metrics, "roe")
        return _avg(
            [
                _higher_better_score(op_margin, [10.0, 15.0, 20.0, 30.0]),
                _higher_better_score(roe, [8.0, 12.0, 16.0, 20.0]),
            ]
        )

    if axis_id == "management_quality":
        equity_ratio = _metric(metrics, "equity_ratio")
        de_ratio = _metric(metrics, "net_de_ratio")
        return _avg(
            [
                _higher_better_score(equity_ratio, [30.0, 40.0, 50.0, 65.0]),
                _lower_better_score(de_ratio, [20.0, 40.0, 70.0, 100.0]),
            ]
        )

    if axis_id == "financial_durability":
        equity_ratio = _metric(metrics, "equity_ratio")
        de_ratio = _metric(metrics, "net_de_ratio")
        op_margin = _metric(metrics, "operating_margin")
        return _avg(
            [
                _higher_better_score(equity_ratio, [30.0, 40.0, 50.0, 70.0]),
                _lower_better_score(de_ratio, [20.0, 40.0, 70.0, 100.0]),
                _higher_better_score(op_margin, [5.0, 10.0, 15.0, 20.0]),
            ]
        )

    if axis_id == "valuation_reasonableness":
        per = _metric(metrics, "per")
        growth_now = _metric(metrics, "revenue_growth_forecast")
        peg_like = _peg_like(per, growth_now)
        return _avg(
            [
                _lower_better_score(peg_like, [0.8, 1.2, 1.8, 2.5]),
                _lower_better_score(per, [15.0, 25.0, 35.0, 50.0]),
            ]
        )

    return 2.5


def _higher_better_score(value: float | None, thresholds: list[float]) -> float:
    if not isinstance(value, (int, float)):
        return 2.5
    points = 1.0
    for threshold in thresholds:
        if float(value) >= threshold:
            points += 1.0
    return min(points, 5.0)


def _lower_better_score(value: float | None, thresholds: list[float]) -> float:
    if not isinstance(value, (int, float)):
        return 2.5
    numeric = float(value)
    if numeric <= thresholds[0]:
        return 5.0
    if numeric <= thresholds[1]:
        return 4.0
    if numeric <= thresholds[2]:
        return 3.0
    if numeric <= thresholds[3]:
        return 2.0
    return 1.0


def _avg(values: list[float]) -> float:
    if not values:
        return 2.5
    return round(sum(values) / len(values), 2)


def _metric(metrics: dict[str, float], key: str) -> float | None:
    value = metrics.get(key)
    if not isinstance(value, (int, float)):
        return None
    return float(value)


def _to_100(total: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (total / maximum) * 100.0)), 2)


def _tam_runway_score(market_cap_jpy: float | None) -> float:
    if market_cap_jpy is None:
        return 2.5
    if market_cap_jpy <= 30_000_000_000:
        return 5.0
    if market_cap_jpy <= 100_000_000_000:
        return 4.0
    if market_cap_jpy <= 500_000_000_000:
        return 3.0
    if market_cap_jpy <= 2_000_000_000_000:
        return 2.0
    return 1.0


def _peg_like(per: float | None, growth_pct: float | None) -> float | None:
    if per is None or growth_pct is None:
        return None
    if growth_pct <= 0:
        return None
    return per / growth_pct
