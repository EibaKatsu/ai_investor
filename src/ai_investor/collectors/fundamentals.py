from __future__ import annotations

from ai_investor.models import Evidence


class EdinetCollector:
    """Stub collector for EDINET filings and extracted evidence."""

    def fetch_evidence(self, ticker: str) -> list[Evidence]:
        return []
