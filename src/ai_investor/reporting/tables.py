from __future__ import annotations

from ai_investor.models import Candidate


def to_markdown_table(candidates: list[Candidate]) -> str:
    axis_ids = _axis_columns(candidates)
    axis_header = "".join(f"|{_axis_label(axis_id)}" for axis_id in axis_ids)
    header = (
        f"|Ticker|Company|Sector|Quant|Q(Price)|Q(Fund)|Qual|Composite|Excluded|Reasons{axis_header}|\n"
        f"|---|---|---|---:|---:|---:|---:|---:|---|---{''.join('|---:' for _ in axis_ids)}|"
    )
    rows = []
    for candidate in candidates:
        axis_values = "".join(
            f"|{candidate.qualitative_scores.get(axis_id, 0.0):.2f}"
            for axis_id in axis_ids
        )
        rows.append(
            "|{ticker}|{name}|{sector}|{quant:.2f}|{q_price:.2f}|{q_fund:.2f}|{qual:.2f}|{comp:.2f}|{excluded}|{reasons}{axis_values}|".format(
                ticker=candidate.ticker,
                name=candidate.company_name,
                sector=candidate.sector,
                quant=candidate.quantitative_score,
                q_price=candidate.quantitative_score_price_now,
                q_fund=candidate.quantitative_score_fundamentals_base,
                qual=candidate.qualitative_score_total,
                comp=candidate.composite_score,
                excluded="yes" if candidate.excluded else "no",
                reasons=", ".join(candidate.exclusion_reasons),
                axis_values=axis_values,
            )
        )
    return header + ("\n" + "\n".join(rows) if rows else "")


def _axis_columns(candidates: list[Candidate]) -> list[str]:
    preferred_order = [
        "temporary_lag_factor",
        "growth_driver_confidence",
        "management_and_capital_policy",
        "competitive_advantage",
        "risk_resilience",
    ]
    present: set[str] = set()
    for candidate in candidates:
        present.update(candidate.qualitative_scores.keys())
    ordered = [axis_id for axis_id in preferred_order if axis_id in present]
    extras = sorted(axis_id for axis_id in present if axis_id not in preferred_order)
    return ordered + extras


def _axis_label(axis_id: str) -> str:
    labels = {
        "temporary_lag_factor": "Q-Temp",
        "growth_driver_confidence": "Q-Growth",
        "management_and_capital_policy": "Q-Mgmt",
        "competitive_advantage": "Q-Edge",
        "risk_resilience": "Q-Risk",
    }
    return labels.get(axis_id, axis_id)
