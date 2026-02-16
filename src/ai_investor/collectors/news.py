from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import os

import requests


@dataclass(slots=True)
class NewsItem:
    source: str
    title: str
    url: str
    published_at: str


class TdnetPublicCollector:
    """Stub collector for TDnet public-view pages."""

    def fetch_news(self, ticker: str, lookback_days: int, as_of: date | None = None) -> list[NewsItem]:
        _ = ticker, lookback_days, as_of
        return []


class GNewsCollector:
    """Collector for GNews free plan."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GNEWS_API_KEY", "").strip()
        self.base_url = "https://gnews.io/api/v4/search"
        self.timeout = 15
        self.max_items = 10

    def fetch_news(self, query: str, lookback_days: int, as_of: date | None = None) -> list[NewsItem]:
        if not self.api_key:
            return []

        end_dt = datetime.now(timezone.utc) if as_of is None else datetime.combine(as_of, time.max, tzinfo=timezone.utc)
        start_dt = end_dt - timedelta(days=max(1, lookback_days))
        params = {
            "q": query,
            "apikey": self.api_key,
            "lang": "ja",
            "max": self.max_items,
            "from": start_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "to": end_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "sortby": "publishedAt",
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            return []
        except ValueError:
            return []

        rows = payload.get("articles", [])
        if not isinstance(rows, list):
            return []

        items: list[NewsItem] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title", "")).strip()
            url = str(row.get("url", "")).strip()
            if not title or not url:
                continue
            source_name = "GNews"
            source = row.get("source")
            if isinstance(source, dict):
                source_name = str(source.get("name", "")).strip() or source_name
            published_at = str(row.get("publishedAt", "")).strip()
            items.append(
                NewsItem(
                    source=source_name,
                    title=title,
                    url=url,
                    published_at=published_at,
                )
            )
        return items
