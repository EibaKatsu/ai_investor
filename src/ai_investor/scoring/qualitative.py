from __future__ import annotations

from ai_investor.models import Candidate


def score_candidates(candidates: list[Candidate], axes: list[dict[str, str]]) -> None:
    """Placeholder qualitative scoring with empty evidence."""
    for candidate in candidates:
        candidate.qualitative_scores = {axis["id"]: 0.0 for axis in axes}
        candidate.qualitative_score_total = 0.0
