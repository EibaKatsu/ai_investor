from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Evidence:
    source: str
    url: str
    fetched_at: str
    note: str


@dataclass(slots=True)
class Candidate:
    ticker: str
    company_name: str
    sector: str = "UNKNOWN"
    quantitative_metrics: dict[str, float] = field(default_factory=dict)
    quantitative_score: float = 0.0
    quantitative_score_price_now: float = 0.0
    quantitative_score_fundamentals_base: float = 0.0
    qualitative_scores: dict[str, float] = field(default_factory=dict)
    qualitative_score_total: float = 0.0
    qualitative_score_max: float = 25.0
    qualitative_score_normalized: float = 0.0
    composite_score: float = 0.0
    excluded: bool = False
    exclusion_reasons: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(slots=True)
class Recommendation:
    ticker: str
    decision: str
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    industry_trends: list[str] = field(default_factory=list)
    peer_strengths: list[str] = field(default_factory=list)
    peer_weaknesses: list[str] = field(default_factory=list)
    lag_causes: list[str] = field(default_factory=list)
    critical_views: list[str] = field(default_factory=list)
    break_scenarios: list[str] = field(default_factory=list)
    reevaluation_triggers: list[str] = field(default_factory=list)
    source_links: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PipelineResult:
    candidates: list[Candidate] = field(default_factory=list)
    top_recommendations: list[Recommendation] = field(default_factory=list)
