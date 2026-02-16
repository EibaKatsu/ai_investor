from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class UniverseRow:
    ticker: str
    company_name: str
    sector: str


class JQuantsMarketDataCollector:
    """Stub collector for J-Quants data."""

    def fetch_universe(self) -> list[UniverseRow]:
        return []

    def fetch_quant_metrics(self, tickers: list[str]) -> dict[str, dict[str, float]]:
        return {ticker: {} for ticker in tickers}
