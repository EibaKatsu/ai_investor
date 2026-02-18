from __future__ import annotations

from datetime import date

from ai_investor.collectors.fundamentals import EdinetCollector
from ai_investor.collectors.market_data import JQuantsMarketDataCollector
from ai_investor.collectors.news import TdnetPublicCollector, WebSearchNewsCollector
from ai_investor.collectors.sbi_csv import SbiCsvMarketDataCollector
from ai_investor.config import StrategyConfig
from ai_investor.models import Candidate, PipelineResult
from ai_investor.research.top3_deep_dive import build_recommendations
from ai_investor.scoring import exclusion, qualitative, quantitative


class InvestorPipeline:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        prices_source = config.data_sources["prices_and_fundamentals"]
        if prices_source.provider == "sbi_csv":
            self.market_data = SbiCsvMarketDataCollector(
                data_source=prices_source,
                universe_config=config.universe,
            )
        else:
            self.market_data = JQuantsMarketDataCollector(
                data_source=prices_source,
                universe_config=config.universe,
            )
        self.edinet = EdinetCollector()
        self.tdnet = TdnetPublicCollector()
        self.web_news = WebSearchNewsCollector()

    def run(
        self,
        dry_run: bool,
        top_n: int | None = None,
        top_k: int | None = None,
        as_of: date | None = None,
    ) -> PipelineResult:
        if as_of is not None and hasattr(self.market_data, "as_of"):
            self.market_data.as_of = as_of

        if dry_run:
            return PipelineResult()

        universe_rows = self.market_data.fetch_universe()
        candidates = [
            Candidate(ticker=row.ticker, company_name=row.company_name, sector=row.sector)
            for row in universe_rows
        ]

        quant_metrics = self.market_data.fetch_quant_metrics([c.ticker for c in candidates])
        for candidate in candidates:
            candidate.quantitative_metrics = quant_metrics.get(candidate.ticker, {})

        quantitative.score_candidates(candidates, self.config.quantitative.metrics)
        qualitative.score_candidates(
            candidates,
            self.config.qualitative.axes,
            scale_max=self.config.qualitative.scale_max,
        )
        exclusion.apply_exclusion_rules(candidates, self.config.exclusion_rules)

        for candidate in candidates:
            candidate.composite_score = candidate.quantitative_score + candidate.qualitative_score_normalized

        ranked = sorted(candidates, key=lambda c: c.composite_score, reverse=True)
        selected_top_n = top_n or self.config.quantitative.top_n_candidates
        shortlisted = ranked[:selected_top_n]
        selected_top_k = top_k or self.config.deep_dive.top_k
        recommendations = build_recommendations(
            shortlisted,
            selected_top_k,
            web_news=self.web_news,
            tdnet=self.tdnet,
            news_lookback_days=self.config.deep_dive.news_lookback_days,
            as_of=as_of,
        )

        return PipelineResult(candidates=shortlisted, top_recommendations=recommendations)
