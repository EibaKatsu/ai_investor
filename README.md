# ai_investor
AIによる投資アドバイス

## Project Docs

- `docs/agent_spec.md`: 投資判断フロー仕様カタログ（複数仕様の入口）
- `docs/agent_specs/`: 各投資判断フロー仕様（例: `tse-prime-laggard-flow-v1.md`）
- `docs/implementation_plan.md`: 実装タスク分解（MVP）
- `docs/data_sources.md`: データソース確定方針（無料優先）
- `config/strategy_v1.yaml`: 初期戦略パラメータ

## Skill Sources

- `skills/`: Codex Skill のソースを格納
- `skills/<skill-name>/SKILL.md`: スキル本体
- `skills/<skill-name>/references/`: 紐づく仕様ドキュメント
- `scripts/sync_codex_skills.sh`: `skills/` から `~/.codex/skills` へ同期

同期コマンド:

```bash
./scripts/sync_codex_skills.sh
```

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
OPENAI_API_KEY=your-openai-api-key
# Optional:
# JQUANTS_MAX_STATEMENT_CODES=300
# JQUANTS_LIQUIDITY_LOOKBACK_DAYS=5
# WEB_NEWS_MAX_ITEMS=20
```

実行時に `src/ai_investor/main.py` が `.env` を自動読込します。

ニュース収集はAPIキー不要のWeb検索方式（Google News RSS）です。
必要に応じて `WEB_NEWS_MAX_ITEMS` で1銘柄あたりの取得上限件数を調整できます。

環境変数で直接設定する場合:

```bash
export JQUANTS_API_KEY="your-api-key"
export OPENAI_API_KEY="your-openai-api-key"
export JQUANTS_MAX_STATEMENT_CODES=300
export JQUANTS_LIQUIDITY_LOOKBACK_DAYS=5
export WEB_NEWS_MAX_ITEMS=20
```

## SBI CSV Mode

SBI銘柄スクリーニングCSVを使う場合:

1. `data/sbi_screening/出遅れ株/` または `data/sbi_screening/成長株/` にCSVを配置
2. `config/strategy_sbi_csv.yaml` で実行

```bash
PYTHONPATH=src python3.11 -m ai_investor.main \
  --config config/strategy_sbi_csv.yaml \
  --as-of 2026-02-16 \
  --output reports
```
