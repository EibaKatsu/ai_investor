from __future__ import annotations

from ai_investor.models import Candidate


def score_candidates(candidates: list[Candidate], metrics: list[dict[str, str]]) -> None:
    """Placeholder scoring: set score to 0 when data is unavailable."""
    _ = metrics
    for candidate in candidates:
        candidate.quantitative_score = 0.0
