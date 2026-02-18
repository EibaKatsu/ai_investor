from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_investor.config import DataSource, UniverseConfig
from ai_investor.collectors.market_data import UniverseRow


@dataclass(slots=True)
class _SbiRecord:
    ticker: str
    company_name: str
    market: str
    metrics: dict[str, float]


class SbiCsvMarketDataCollector:
    """Collector that builds universe and metrics from SBI screening CSV."""

    def __init__(self, *, data_source: DataSource, universe_config: UniverseConfig) -> None:
        self.data_source = data_source
        self.universe_config = universe_config
        self._records_cache: list[_SbiRecord] | None = None

    def fetch_universe(self) -> list[UniverseRow]:
        records = self._load_records()
        rows = [
            UniverseRow(ticker=r.ticker, company_name=r.company_name, sector=r.market)
            for r in records
            if self._passes_market(r) and self._passes_liquidity(r)
        ]
        return rows

    def fetch_quant_metrics(self, tickers: list[str]) -> dict[str, dict[str, float]]:
        selected = set(tickers)
        metrics_map: dict[str, dict[str, float]] = {}
        for record in self._load_records():
            if record.ticker in selected:
                metrics_map[record.ticker] = dict(record.metrics)
        return metrics_map

    def _load_records(self) -> list[_SbiRecord]:
        if self._records_cache is not None:
            return self._records_cache

        csv_path = self._resolve_csv_path()
        rows: list[_SbiRecord] = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if not row:
                    continue
                ticker = str(row.get("コード", "")).strip()
                if not ticker:
                    continue

                company_name = str(row.get("銘柄名", "")).strip() or ticker
                market = str(row.get("市場", "")).strip() or "UNKNOWN"

                metrics: dict[str, float] = {}
                self._put_metric(metrics, "latest_close", row.get("現在値"))
                self._put_metric_from_columns(metrics, "per", row, ["PER(株価収益率)(予)(倍)", "PER(株価収益率)(倍)"])
                self._put_metric_from_columns(metrics, "pbr", row, ["PBR(株価純資産倍率)(倍)"])
                self._put_metric_from_columns(metrics, "dividend_yield", row, ["配当利回り(%)"])
                self._put_metric_from_columns(metrics, "roe", row, ["ROE(自己資本利益率)(%)", "ROE(%)"])
                self._put_metric_from_columns(metrics, "equity_ratio", row, ["自己資本比率(%)"])
                self._put_metric_from_columns(metrics, "net_de_ratio", row, ["有利子負債自己資本比率(%)"])
                self._put_metric_from_columns(metrics, "operating_margin", row, ["売上高営業利益率(%)"])
                self._put_metric_from_columns(
                    metrics,
                    "revenue_growth_forecast",
                    row,
                    ["売上高成長率(予)(%)", "売上高変化率(%)"],
                )
                self._put_metric_from_columns(
                    metrics,
                    "op_income_growth_forecast",
                    row,
                    ["経常利益成長率(予)(%)", "経常利益変化率(%)"],
                )
                self._put_metric_from_columns(
                    metrics,
                    "revenue_cagr_3y",
                    row,
                    ["過去3年平均売上高成長率(予)(%)", "売上高変化率(%)"],
                )
                self._put_metric_from_columns(
                    metrics,
                    "op_income_cagr_3y",
                    row,
                    ["過去3年平均経常利益成長率(予)(%)", "経常利益変化率(%)"],
                )

                market_cap_million = _to_float(row.get("時価総額(百万円)"))
                if market_cap_million is not None:
                    metrics["market_cap_jpy"] = market_cap_million * 1_000_000

                avg_turnover_thousand = _to_float(row.get("平均売買代金(千円)"))
                if avg_turnover_thousand is not None:
                    metrics["avg_turnover_20d"] = avg_turnover_thousand * 1_000

                rows.append(_SbiRecord(ticker=ticker, company_name=company_name, market=market, metrics=metrics))

        self._records_cache = rows
        return rows

    def _resolve_csv_path(self) -> Path:
        explicit_path = self.data_source.constraints.get("csv_path")
        if isinstance(explicit_path, str) and explicit_path.strip():
            path = Path(explicit_path)
            if path.exists():
                return path

        csv_dir = self.data_source.constraints.get("csv_dir", "data/raw/sbi_screening")
        pattern = self.data_source.constraints.get("csv_glob", "*.csv")
        path_dir = Path(str(csv_dir))
        files = sorted(path_dir.glob(str(pattern)))
        if not files:
            raise FileNotFoundError(f"No SBI CSV found: {path_dir}/{pattern}")
        return files[-1]

    def _passes_market(self, record: _SbiRecord) -> bool:
        if self.universe_config.market != "TSE_PRIME":
            return True
        return (
            "東証P" in record.market
            or "東P" in record.market
            or "プライム" in record.market
            or "Prime" in record.market
        )

    def _passes_liquidity(self, record: _SbiRecord) -> bool:
        avg_turnover = record.metrics.get("avg_turnover_20d")
        if avg_turnover is None:
            return False
        if avg_turnover < self.universe_config.min_avg_trading_value_20d_jpy:
            return False

        market_cap = record.metrics.get("market_cap_jpy")
        if market_cap is not None and market_cap < self.universe_config.min_market_cap_jpy:
            return False
        return True

    @staticmethod
    def _put_metric(metrics: dict[str, float], key: str, raw_value: Any) -> None:
        value = _to_float(raw_value)
        if value is not None:
            metrics[key] = value

    @classmethod
    def _put_metric_from_columns(
        cls,
        metrics: dict[str, float],
        key: str,
        row: dict[str, Any],
        column_names: list[str],
    ) -> None:
        for column_name in column_names:
            raw_value = row.get(column_name)
            value = _to_float(raw_value)
            if value is None:
                continue
            metrics[key] = value
            return


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "--", "---", "N/A", "n/a"}:
        return None
    text = text.replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None
