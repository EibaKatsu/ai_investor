# ai_investor
AIによる投資アドバイス

## Project Docs

- `docs/agent_spec.md`: 投資判断エージェント仕様（v1）
- `docs/implementation_plan.md`: 実装タスク分解（MVP）
- `docs/data_sources.md`: データソース確定方針（無料優先）
- `config/strategy_v1.yaml`: 初期戦略パラメータ

## Quick Start

```bash
python3.11 -m pip install -e .
PYTHONPATH=src python3.11 -m ai_investor.main --config config/strategy_v1.yaml --dry-run
```

## J-Quants API Key

`.env` で設定する（推奨）:

```bash
cp .env.example .env
```

`.env` の中身:

```bash
JQUANTS_API_KEY=your-api-key
# Optional:
# JQUANTS_MAX_STATEMENT_CODES=300
# JQUANTS_LIQUIDITY_LOOKBACK_DAYS=5
```

実行時に `src/ai_investor/main.py` が `.env` を自動読込します。

環境変数で直接設定する場合:

```bash
export JQUANTS_API_KEY="your-api-key"
export JQUANTS_MAX_STATEMENT_CODES=300
export JQUANTS_LIQUIDITY_LOOKBACK_DAYS=5
```

## SBI CSV Mode

SBI銘柄スクリーニングCSVを使う場合:

1. `data/raw/sbi_screening/` にCSVを配置
2. `config/strategy_sbi_csv.yaml` で実行

```bash
PYTHONPATH=src python3.11 -m ai_investor.main \
  --config config/strategy_sbi_csv.yaml \
  --as-of 2026-02-16 \
  --output reports
```
