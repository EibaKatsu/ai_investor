from __future__ import annotations

from ai_investor.models import Candidate


def score_candidates(candidates: list[Candidate], axes: list[dict[str, str]]) -> None:
    """Rule-based qualitative scoring from available quantitative proxies."""
    for candidate in candidates:
        axis_scores: dict[str, float] = {}
        for axis in axes:
            axis_id = axis.get("id", "")
            axis_scores[axis_id] = _score_axis(candidate, axis_id)

        candidate.qualitative_scores = axis_scores
        candidate.qualitative_score_total = sum(axis_scores.values())


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
