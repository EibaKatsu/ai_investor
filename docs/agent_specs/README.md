# agent_specs

投資判断フロー仕様を複数管理するディレクトリです。

## 命名規則

- 形式: `<flow-name>-v<version>.md`
- 例:
  - `tse-prime-laggard-flow-v1.md`
  - `tse-growth-stock-flow-v1.md`
  - `tse-prime-momentum-flow-v1.md`
  - `tse-prime-defensive-flow-v1.md`

## 運用手順

1. 新しいフロー仕様をこのディレクトリに追加する。
2. `skills/<flow-name>/` に Skill を作成する。
3. `skills/<flow-name>/references/` に対応仕様を配置する。
4. `~/.codex/skills/<flow-name>/` へ登録する。
