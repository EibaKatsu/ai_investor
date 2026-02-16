from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import os
import re
from xml.etree import ElementTree

import requests


@dataclass(slots=True)
class NewsItem:
    source: str
    title: str
    url: str
    published_at: str
    summary: str = ""


class TdnetPublicCollector:
    """Stub collector for TDnet public-view pages."""

    def fetch_news(self, ticker: str, lookback_days: int, as_of: date | None = None) -> list[NewsItem]:
        _ = ticker, lookback_days, as_of
        return []


class WebSearchNewsCollector:
    """News collector via public internet search (Google News RSS)."""

    def __init__(self) -> None:
        self.base_url = "https://news.google.com/rss/search"
        self.timeout = 15
        self.max_items = _read_int_env("WEB_NEWS_MAX_ITEMS", default=20, minimum=1, maximum=100)
        self.user_agent = os.getenv(
            "WEB_NEWS_USER_AGENT",
            "ai-investor/0.1 (public-rss-news-collector)",
        ).strip()

    def fetch_news(self, query: str, lookback_days: int, as_of: date | None = None) -> list[NewsItem]:
        end_dt = datetime.now(timezone.utc) if as_of is None else datetime.combine(as_of, time.max, tzinfo=timezone.utc)
        start_dt = end_dt - timedelta(days=max(1, lookback_days))

        params = {
            "q": f"{query} when:{max(1, lookback_days)}d",
            "hl": "ja",
            "gl": "JP",
            "ceid": "JP:ja",
        }
        headers = {"User-Agent": self.user_agent}

        try:
            response = requests.get(self.base_url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
        except (requests.RequestException, ElementTree.ParseError):
            return []

        items: list[NewsItem] = []
        for node in root.findall("./channel/item"):
            title = _clean_text(_xml_text(node, "title"))
            link = _clean_text(_xml_text(node, "link"))
            if not title or not link:
                continue

            description_raw = _xml_text(node, "description")
            description = _clean_text(_strip_html(description_raw))
            source_node = node.find("source")
            source_name = _clean_text(source_node.text if source_node is not None else "") or "Google News"

            # Google News RSS can provide redirect links. Prefer original URL if it can be extracted.
            candidate_url = _extract_first_url(description_raw)
            if candidate_url and "news.google.com" not in candidate_url:
                link = candidate_url

            pub_text = _clean_text(_xml_text(node, "pubDate"))
            published_dt = _parse_rss_datetime(pub_text)
            if published_dt is not None:
                if published_dt > end_dt:
                    continue
                if published_dt < start_dt:
                    continue
                published_at = published_dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            else:
                published_at = pub_text

            items.append(
                NewsItem(
                    source=source_name,
                    title=title,
                    url=link,
                    published_at=published_at,
                    summary=description,
                )
            )

            if len(items) >= self.max_items:
                break

        return _dedupe_by_url(items)


def _xml_text(node: ElementTree.Element, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text


def _parse_rss_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", text)
    return unescape(no_tags)


def _extract_first_url(text: str) -> str:
    if not text:
        return ""
    match = re.search(r'https?://[^\s"<>]+', text)
    if not match:
        return ""
    return unescape(match.group(0))


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _dedupe_by_url(items: list[NewsItem]) -> list[NewsItem]:
    deduped: list[NewsItem] = []
    seen_urls: set[str] = set()
    for item in items:
        if not item.url or item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        deduped.append(item)
    return deduped


def _read_int_env(name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


# Backward compatibility alias.
GNewsCollector = WebSearchNewsCollector
