# 実装計画（MVP）

## 1. スコープ

- 目的: `docs/agent_spec.md` に基づく v1 エージェントを実装する
- 成果物: CLI実行で候補20件の表と上位3件レポートを出力
- 非スコープ: 自動売買、ポートフォリオ最適化、本番監視

## 2. 推奨ディレクトリ構成

```text
src/ai_investor/
  main.py
  config.py
  pipeline.py
  models.py
  collectors/
    market_data.py
    fundamentals.py
    news.py
  scoring/
    quantitative.py
    qualitative.py
    exclusion.py
  research/
    top3_deep_dive.py
  reporting/
    tables.py
    markdown_report.py
data/
  raw/
  processed/
reports/
config/
  strategy_v1.yaml
```

## 3. フェーズ分解

### Phase 1: 基盤

1. Pythonプロジェクト初期化（依存管理、実行入口）
2. `config/strategy_v1.yaml` の読込実装
3. データモデル定義（銘柄、スコア、根拠、除外理由）

完了条件:

- `python -m ai_investor.main --config config/strategy_v1.yaml --dry-run` が実行できる

### Phase 2: 定量スクリーニング

1. ユニバース取得（東証プライム）
2. 流動性・時価総額フィルタ
3. 10指標計算と正規化
4. 定量総合点算出、上位20件抽出

完了条件:

- 候補20件をCSV/Markdownで出力できる

### Phase 3: 定性評価

1. 定性5軸の採点テンプレートを実装
2. 根拠URL・日付・要約テキスト保存
3. 定性総合点算出

完了条件:

- 20件すべてで5軸スコアと根拠が埋まる

### Phase 4: 除外判定と上位3件深掘り

1. 除外ルール判定モジュール実装
2. 暫定総合点で並べ替え
3. 上位3件のニュース深掘りと反証チェック

完了条件:

- 上位3件に対する条件付き推薦が生成される

### Phase 5: レポーティングと監査

1. 候補20件テーブルを整形
2. 上位3件レポートをMarkdownで出力
3. 監査ログ（根拠リンク、取得日、採点理由）保存

完了条件:

- `reports/YYYYMMDD_report.md` が生成される

## 4. データソース設計指針

1. 株価・基礎財務はJ-Quantsを利用する
2. 開示一次情報はEDINET APIを利用する
3. 適時開示はTDnet公開閲覧を利用し、APIは将来拡張とする
4. 一般ニュース補完はWeb検索（Google News RSS）を利用する
5. 取得失敗時は再試行し、失敗理由をログ化する
6. ソースごとに最終更新日時を保持する
7. 無料優先モードでは鮮度制約を評価に反映する

## 5. 品質ゲート

1. 欠損率チェック（10指標の欠損率）
2. リンク生存チェック
3. 最新性チェック（ニュースは30日以内を優先）
4. 除外判定ロジックの単体テスト

## 6. CLI仕様（MVP）

```bash
python -m ai_investor.main \
  --config config/strategy_v1.yaml \
  --as-of YYYY-MM-DD \
  --output reports/
```

主要オプション:

- `--dry-run`: データ取得なしで設定検証のみ
- `--top-n`: 候補件数（デフォルト20）
- `--top-k`: 深掘り件数（デフォルト3）

## 7. 次の意思決定ポイント

1. データソースの確定（財務・株価・ニュース）
2. 定性採点の自動化レベル（完全自動/人手レビュー併用）
3. v2での重み最適化方針（バックテスト期間・評価指標）
