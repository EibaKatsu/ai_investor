from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NewsItem:
    source: str
    title: str
    url: str
    published_at: str


class TdnetPublicCollector:
    """Stub collector for TDnet public-view pages."""

    def fetch_news(self, ticker: str, lookback_days: int) -> list[NewsItem]:
        return []


class GNewsCollector:
    """Stub collector for GNews free plan."""

    def fetch_news(self, query: str, lookback_days: int) -> list[NewsItem]:
        return []
