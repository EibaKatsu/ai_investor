from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging
import os
import time
from typing import Any

import requests

from ai_investor.config import DataSource, UniverseConfig

LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://api.jquants.com/v2"


@dataclass(slots=True)
class UniverseRow:
    ticker: str
    company_name: str
    sector: str


@dataclass(slots=True)
class _PriceSnapshot:
    close: float | None
    avg_turnover_20d: float | None


class JQuantsApiError(RuntimeError):
    """Raised when J-Quants API returns a non-success response."""


class JQuantsApiClient:
    """Thin J-Quants V2 API client with API-key auth."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: int = 30,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self._api_key = api_key or os.getenv("JQUANTS_API_KEY")
        self.max_retries = int(os.getenv("JQUANTS_MAX_RETRIES", "3"))

    def get_listed_info(self, target_date: date | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if target_date:
            params["date"] = target_date.isoformat()
        return self._get_paginated(path="/equities/master", params=params)

    def get_daily_quotes(
        self,
        *,
        target_date: date | None = None,
        code: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if target_date:
            params["date"] = target_date.isoformat()
        if code:
            params["code"] = code
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        return self._get_paginated(path="/equities/bars/daily", params=params)

    def get_financial_summaries(self, code: str) -> list[dict[str, Any]]:
        params = {"code": code}
        return self._get_paginated(path="/fins/summary", params=params)

    def _get_paginated(
        self,
        *,
        path: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        cursor: str | None = None
        base_params = dict(params or {})

        for _ in range(500):
            call_params = dict(base_params)
            if cursor:
                call_params["pagination_key"] = cursor
            payload = self._request("GET", path, params=call_params, authorized=True)
            items = payload.get("data", [])
            if isinstance(items, list):
                merged.extend(items)
            cursor = payload.get("pagination_key")
            if not cursor:
                break

        return merged

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        authorized: bool,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if authorized:
            headers["x-api-key"] = self._ensure_api_key()

        url = f"{self.base_url}{path}"
        response: requests.Response | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                raise JQuantsApiError(f"{method} {path} failed: {exc}") from exc

            if response.status_code != 429:
                break
            if attempt >= self.max_retries:
                break
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait_s = int(retry_after)
            else:
                wait_s = min(2 ** attempt, 10)
            LOGGER.warning("Rate limit hit on %s %s. Retrying in %ss.", method, path, wait_s)
            time.sleep(wait_s)

        if response is None:
            raise JQuantsApiError(f"{method} {path} failed: no response")

        payload: dict[str, Any]
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if not response.ok:
            message = payload.get("message") if isinstance(payload, dict) else response.text
            raise JQuantsApiError(f"{method} {path} failed ({response.status_code}): {message}")

        return payload

    def _ensure_api_key(self) -> str:
        if not self._api_key:
            raise JQuantsApiError("J-Quants API key is missing. Set JQUANTS_API_KEY.")
        return self._api_key


class JQuantsMarketDataCollector:
    """Market/fundamental collector backed by J-Quants API."""

    def __init__(
        self,
        *,
        data_source: DataSource,
        universe_config: UniverseConfig,
        as_of: date | None = None,
        client: JQuantsApiClient | None = None,
    ) -> None:
        self.data_source = data_source
        self.universe_config = universe_config
        self.as_of = as_of or date.today()
        self.client = client or JQuantsApiClient()
        self._price_snapshot_cache: dict[str, _PriceSnapshot] = {}
        self._price_snapshot_cache_as_of: date | None = None

    def fetch_universe(self) -> list[UniverseRow]:
        listed_rows = self.client.get_listed_info(target_date=self.as_of)
        prime_rows: list[UniverseRow] = []
        for row in listed_rows:
            if not self._is_target_market(row):
                continue
            code = str(row.get("Code", "")).strip()
            if not code:
                continue
            company_name = str(row.get("CoName", "")).strip() or str(row.get("CompanyName", "")).strip() or code
            sector = (
                str(row.get("S33Nm", "")).strip()
                or str(row.get("Sector33CodeName", "")).strip()
                or str(row.get("S33", "UNKNOWN")).strip()
                or str(row.get("Sector33Code", "UNKNOWN")).strip()
            )
            prime_rows.append(UniverseRow(ticker=code, company_name=company_name, sector=sector))

        filtered = self._apply_liquidity_filter(prime_rows)
        LOGGER.info("J-Quants universe: listed=%d, filtered=%d", len(prime_rows), len(filtered))
        return filtered

    def fetch_quant_metrics(self, tickers: list[str]) -> dict[str, dict[str, float]]:
        if not tickers:
            return {}

        snapshot = self._build_price_snapshot(set(tickers))
        statement_map = self._fetch_latest_statements(tickers)
        metrics_map: dict[str, dict[str, float]] = {}

        for ticker in tickers:
            metrics: dict[str, float] = {}
            price_row = snapshot.get(ticker, _PriceSnapshot(close=None, avg_turnover_20d=None))

            if price_row.close is not None:
                metrics["latest_close"] = price_row.close
            if price_row.avg_turnover_20d is not None:
                metrics["avg_turnover_20d"] = price_row.avg_turnover_20d

            statement = statement_map.get(ticker)
            if statement:
                self._merge_statement_metrics(metrics, statement, price_row.close)
            metrics_map[ticker] = metrics

        return metrics_map

    def _apply_liquidity_filter(self, rows: list[UniverseRow]) -> list[UniverseRow]:
        if not rows:
            return []
        min_turnover = self.universe_config.min_avg_trading_value_20d_jpy
        snapshots = self._build_price_snapshot({row.ticker for row in rows})
        liquidity_filtered: list[UniverseRow] = []
        for row in rows:
            avg_turnover = snapshots.get(row.ticker, _PriceSnapshot(None, None)).avg_turnover_20d
            if avg_turnover is None:
                continue
            if avg_turnover < min_turnover:
                continue
            liquidity_filtered.append(row)

        enforce_market_cap = os.getenv("JQUANTS_ENFORCE_MARKET_CAP", "0") == "1"
        min_market_cap = self.universe_config.min_market_cap_jpy
        if min_market_cap <= 0 or not enforce_market_cap:
            return liquidity_filtered

        statements = self._fetch_latest_statements([row.ticker for row in liquidity_filtered])
        with_market_cap: list[UniverseRow] = []
        unresolved = 0
        for row in liquidity_filtered:
            statement = statements.get(row.ticker)
            close = snapshots.get(row.ticker, _PriceSnapshot(None, None)).close
            if not statement or close is None:
                unresolved += 1
                with_market_cap.append(row)
                continue
            shares = _first_float(
                statement,
                [
                    "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock",
                    "NumberOfIssuedAndOutstandingSharesAtTheEndOfQuarterIncludingTreasuryStock",
                    "IssuedShares",
                ],
            )
            if shares is None:
                unresolved += 1
                with_market_cap.append(row)
                continue
            market_cap = close * shares
            if market_cap >= min_market_cap:
                with_market_cap.append(row)

        if unresolved:
            LOGGER.warning(
                "Could not resolve market cap for %d tickers. They are kept in the universe by default.",
                unresolved,
            )
        return with_market_cap

    def _build_price_snapshot(self, target_codes: set[str]) -> dict[str, _PriceSnapshot]:
        if not target_codes:
            return {}

        if (
            self._price_snapshot_cache_as_of == self.as_of
            and all(code in self._price_snapshot_cache for code in target_codes)
        ):
            return {code: self._price_snapshot_cache[code] for code in target_codes}

        turnover_sum = {code: 0.0 for code in target_codes}
        trading_days_count = {code: 0 for code in target_codes}
        latest_close: dict[str, float] = {}
        target_trading_days = int(os.getenv("JQUANTS_LIQUIDITY_LOOKBACK_DAYS", "5"))
        target_trading_days = max(1, target_trading_days)
        max_calendar_days = max(15, target_trading_days * 4)

        for offset in range(0, max_calendar_days):
            day = self.as_of - timedelta(days=offset)
            daily_quotes = self.client.get_daily_quotes(target_date=day)
            if not daily_quotes:
                continue
            for quote in daily_quotes:
                code = str(quote.get("Code", "")).strip()
                if code not in target_codes:
                    continue

                turnover = _first_float(quote, ["Va", "TurnoverValue", "turnover_value"])
                if turnover is not None and trading_days_count[code] < target_trading_days:
                    turnover_sum[code] += turnover
                    trading_days_count[code] += 1

                if code not in latest_close:
                    close = _first_float(quote, ["AdjC", "C", "AdjustmentClose", "Close", "adjustment_close", "close"])
                    if close is not None:
                        latest_close[code] = close

            if all(trading_days_count[code] >= target_trading_days for code in target_codes):
                break

        snapshot: dict[str, _PriceSnapshot] = {}
        for code in target_codes:
            count = trading_days_count[code]
            avg_turnover = (turnover_sum[code] / count) if count > 0 else None
            snapshot[code] = _PriceSnapshot(close=latest_close.get(code), avg_turnover_20d=avg_turnover)

        self._price_snapshot_cache_as_of = self.as_of
        self._price_snapshot_cache.update(snapshot)
        return snapshot

    def _fetch_latest_statements(self, tickers: list[str]) -> dict[str, dict[str, Any]]:
        max_codes = int(os.getenv("JQUANTS_MAX_STATEMENT_CODES", "300"))
        selected = tickers[:max_codes]
        if len(tickers) > max_codes:
            LOGGER.warning(
                "Skipping statement fetch for %d tickers due to JQUANTS_MAX_STATEMENT_CODES=%d",
                len(tickers) - max_codes,
                max_codes,
            )

        statement_map: dict[str, dict[str, Any]] = {}
        for ticker in selected:
            summaries = self.client.get_financial_summaries(code=ticker)
            if not summaries:
                continue
            statement_map[ticker] = max(
                summaries,
                key=lambda row: (
                    str(row.get("Date", "")),
                    str(row.get("DiscDate", "")),
                    str(row.get("DiscTime", "")),
                    str(row.get("DiscNo", "")),
                    str(row.get("DisclosedDate", "")),
                    str(row.get("DisclosedTime", "")),
                    str(row.get("DisclosureNumber", "")),
                ),
            )
        return statement_map

    def _merge_statement_metrics(
        self,
        metrics: dict[str, float],
        statement: dict[str, Any],
        close_price: float | None,
    ) -> None:
        book_value_per_share = _first_float(statement, ["BPS", "BookValuePerShare", "book_value_per_share"])
        eps = _first_float(statement, ["EPS", "EarningsPerShare", "eps"])
        equity_ratio = _first_float(statement, ["EqAR", "EquityToAssetRatio", "equity_ratio"])
        cash_flow_from_ops = _first_float(
            statement,
            ["CFO", "CashFlowsFromOperatingActivities", "cash_flows_from_operating_activities"],
        )
        net_sales = _first_float(statement, ["Sales", "NetSales", "Revenue", "net_sales", "revenue"])
        operating_profit = _first_float(
            statement,
            ["OP", "OperatingProfit", "OperatingIncome", "operating_profit", "operating_income"],
        )
        profit = _first_float(statement, ["NP", "Profit", "NetIncome", "profit", "net_income"])
        equity = _first_float(statement, ["Eq", "Equity", "equity"])
        shares_outstanding = _first_float(
            statement,
            [
                "ShOutFY",
                "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock",
                "NumberOfIssuedAndOutstandingSharesAtTheEndOfQuarterIncludingTreasuryStock",
                "IssuedShares",
            ],
        )
        dividend_annual = _first_float(
            statement,
            [
                "ForecastDividendPerShareAnnual",
                "ResultDividendPerShareAnnual",
                "FDivAnn",
                "DivAnn",
                "forecast_dividend_per_share_annual",
                "result_dividend_per_share_annual",
            ],
        )

        if equity_ratio is not None:
            metrics["equity_ratio"] = equity_ratio
        if net_sales is not None:
            metrics["net_sales"] = net_sales
        if operating_profit is not None:
            metrics["operating_profit"] = operating_profit
        if cash_flow_from_ops is not None:
            metrics["operating_cash_flow"] = cash_flow_from_ops
        if profit is not None:
            metrics["profit"] = profit
        if equity is not None:
            metrics["equity"] = equity

        if close_price is not None and close_price > 0 and shares_outstanding is not None and shares_outstanding > 0:
            metrics["market_cap_jpy"] = close_price * shares_outstanding
        if close_price is not None and close_price > 0 and book_value_per_share is not None and book_value_per_share > 0:
            metrics["pbr"] = close_price / book_value_per_share
        if close_price is not None and close_price > 0 and eps is not None and eps > 0:
            metrics["per"] = close_price / eps
        if close_price is not None and close_price > 0 and dividend_annual is not None and dividend_annual >= 0:
            metrics["dividend_yield"] = dividend_annual / close_price
        if profit is not None and equity is not None and equity > 0:
            metrics["roe"] = profit / equity
        if cash_flow_from_ops is not None and net_sales is not None and net_sales != 0:
            metrics["operating_cf_margin"] = cash_flow_from_ops / net_sales

    def _is_target_market(self, row: dict[str, Any]) -> bool:
        if self.universe_config.market != "TSE_PRIME":
            return True

        market_code = str(row.get("Mkt", "")).strip() or str(row.get("MarketCode", "")).strip()
        market_name = str(row.get("MktNm", "")).strip().lower() or str(row.get("MarketCodeName", "")).strip().lower()
        market_segment = str(row.get("MarketSegment", "")).strip().lower()

        if market_code == "0111":
            return True
        if "prime" in market_name or "プライム" in market_name:
            return True
        if "prime" in market_segment or "プライム" in market_segment:
            return True
        return False


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_float(row: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return None
