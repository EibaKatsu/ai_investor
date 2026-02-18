from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class DataSource:
    provider: str
    plan: str
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UniverseConfig:
    market: str
    min_avg_trading_value_20d_jpy: int
    min_market_cap_jpy: int


@dataclass(slots=True)
class QuantitativeConfig:
    normalization: str
    composite_method: str
    top_n_candidates: int
    metrics: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class QualitativeConfig:
    scale_min: int
    scale_max: int
    composite_method: str
    axes: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class DeepDiveConfig:
    top_k: int
    news_lookback_days: int
    require_refutation_check: bool


@dataclass(slots=True)
class RuntimeConfig:
    required_env: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StrategyConfig:
    version: int
    name: str
    mode: str
    data_sources: dict[str, DataSource]
    universe: UniverseConfig
    quantitative: QuantitativeConfig
    qualitative: QualitativeConfig
    exclusion_rules: list[dict[str, Any]]
    deep_dive: DeepDiveConfig
    runtime: RuntimeConfig
    output: dict[str, Any]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)
    if not isinstance(loaded, dict):
        raise ValueError(f"Invalid strategy config: {path}")
    return loaded


def load_strategy(path: str | Path) -> StrategyConfig:
    cfg_path = Path(path)
    loaded = _load_yaml(cfg_path)

    data_sources = {
        key: DataSource(
            provider=value["provider"],
            plan=value["plan"],
            constraints=value.get("constraints", {}),
        )
        for key, value in loaded["data_sources"].items()
    }

    universe = UniverseConfig(**loaded["universe"])
    quantitative = QuantitativeConfig(**loaded["quantitative"])
    qualitative = QualitativeConfig(**loaded["qualitative"])
    deep_dive = DeepDiveConfig(**loaded["deep_dive"])
    runtime = RuntimeConfig(**loaded.get("runtime", {}))

    return StrategyConfig(
        version=loaded["version"],
        name=loaded["name"],
        mode=loaded.get("mode", "free_first"),
        data_sources=data_sources,
        universe=universe,
        quantitative=quantitative,
        qualitative=qualitative,
        exclusion_rules=loaded.get("exclusion_rules", []),
        deep_dive=deep_dive,
        runtime=runtime,
        output=loaded.get("output", {}),
    )
