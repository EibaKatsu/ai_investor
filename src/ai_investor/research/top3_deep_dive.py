from __future__ import annotations

from ai_investor.models import Candidate, Recommendation


def build_recommendations(candidates: list[Candidate], top_k: int) -> list[Recommendation]:
    ranked = sorted(
        [c for c in candidates if not c.excluded],
        key=lambda c: c.composite_score,
        reverse=True,
    )
    selected = ranked[:top_k]
    recommendations: list[Recommendation] = []
    for candidate in selected:
        recommendations.append(
            Recommendation(
                ticker=candidate.ticker,
                decision="Watch",
                reasons=["Scaffold mode: deep-dive logic not implemented yet."],
                risks=["Data collector integration pending."],
                assumptions=["Switch decision after real news and filing evidence."],
            )
        )
    return recommendations
