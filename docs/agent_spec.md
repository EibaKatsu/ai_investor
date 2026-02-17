# 投資判断フロー仕様カタログ

このファイルは複数の投資判断フロー仕様への入口です。  
個別仕様は `docs/agent_specs/` 配下に追加します。

## 現在の仕様

- `docs/agent_specs/tse-prime-laggard-flow-v1.md`: 東証プライム出遅れ株フロー（v1）

## 追加ルール

- 1フロー1ファイルで管理する。
- 命名は `<flow-name>-v<version>.md` にする。
- 対応する Codex Skill は `skills/<flow-name>/` に配置する。
- Skill の `references/` には、対応する仕様ファイルをコピーして保持する。
