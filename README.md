# ai_investor
AIによる投資アドバイス

## Project Docs

- `docs/agent_spec.md`: 投資判断エージェント仕様（v1）
- `docs/implementation_plan.md`: 実装タスク分解（MVP）
- `docs/data_sources.md`: データソース確定方針（無料優先）
- `config/strategy_v1.yaml`: 初期戦略パラメータ

## Quick Start

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m ai_investor.main --config config/strategy_v1.yaml --dry-run
```
