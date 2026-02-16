from __future__ import annotations

from ai_investor.models import Candidate


def apply_exclusion_rules(candidates: list[Candidate], rules: list[dict]) -> None:
    """Placeholder exclusion gate. Replace with real checks."""
    _ = rules
    for candidate in candidates:
        candidate.excluded = False
        candidate.exclusion_reasons = []
