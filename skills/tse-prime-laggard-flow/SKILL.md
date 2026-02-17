---
name: tse-prime-laggard-flow
description: 東証プライムの出遅れ株候補を抽出し、定量+定性で評価して上位3件の条件付き投資判断を作るワークフロー。J-Quants V2データを使ったスクリーニング、候補20件テーブル作成、除外ルール判定、ニュースを含む詳細調査を行うときに使う。`docs/agent_specs/tse-prime-laggard-flow-v1.md` 準拠の手順で分析・再実行・レポート更新が必要な場面で呼び出す。
---

# TSE Prime Laggard Flow

## Overview

このスキルは `docs/agent_specs/tse-prime-laggard-flow-v1.md` の v1 仕様を実行用手順に落としたものです。  
東証プライム銘柄から「出遅れ株候補」を評価し、候補20件と上位3件の投資判断（Recommend / Watch / Skip）を出力します。

## Inputs

- 必須入力:
  - `--config` (`config/strategy_v1.yaml` など)
- 推奨入力:
  - `--output reports`
- 主な環境変数:
  - `JQUANTS_API_KEY`
  - `OPENAI_API_KEY`
  - `JQUANTS_LIQUIDITY_LOOKBACK_DAYS`（デフォルト5）
  - `JQUANTS_ENFORCE_MARKET_CAP`（1なら時価総額300億円以上を強制）
  - `JQUANTS_MAX_STATEMENT_CODES`（無料枠の取得量制御）
  - `WEB_NEWS_MAX_ITEMS`

## As-of Rule

- `--as-of` は手動入力せず、`data/` 配下の最新CSVから決定する。
- 日付をファイル名から抽出できるCSV（例: `*_20260216.csv`）がある場合は、その最大日付を `as-of` に使う。
- ファイル名に日付がないCSVのみの場合は、更新時刻が最も新しいCSVの日付を `as-of` に使う。
- 解決スクリプト: `skills/tse-prime-laggard-flow/scripts/latest_csv_asof.py`

## Workflow

1. 実行条件を確認する。
- 取引執行は行わず、推薦のみ出力する。
- 無料優先モードではデータ鮮度制約を明記する。

2. 定量スクリーニングを実行する。
- 定量総合点の上位20件を候補にする。
- v1の主な反映指標は PBR / PER / ROE / 配当利回り / 営業CFマージン / 自己資本比率。
- `price_now` と `fundamentals_base` を平均して定量総合点を作る。

3. 候補20件を定性5軸で採点する。
- 各軸を0-5点で採点する。
- 根拠テキスト、参照URL、取得日付を必ず残す。
- 5軸: 出遅れ要因の一時性 / 成長ドライバー実現確度 / 経営品質・資本政策 / 競争優位性 / リスク耐性。

4. 除外ルールを適用する。
- GC疑義、重大不正、債務超過、長期営業CF悪化、流動性不足、説明不十分な大幅下方修正を除外候補にする。

5. 暫定総合点で上位3件を選定する。
- 暫定総合点 = 定量総合点(0-100) + 定性総合点(100点換算)。
- 除外フラグ付き銘柄を除外する。

6. 上位3件を詳細調査する。
- 直近ニュース（30日以内を優先）を確認する。
- ポジ/ネガ材料、反証（買わない理由）、ベース/強気/弱気シナリオを整理する。
- 業種トレンドと同業比較（強み/弱み）を反映する。

7. 出力を整形する。
- 候補20件テーブルに必須列を含める。
- 上位3件レポートに推薦判断、理由、主要リスク、前提条件、破綻シナリオ、再評価トリガー、根拠リンクを含める。

## Standard Command

```bash
AS_OF="$(python3 skills/tse-prime-laggard-flow/scripts/latest_csv_asof.py --data-dir data)"
PYTHONPATH=src python3.11 -m ai_investor.main \
  --config config/strategy_sbi_csv.yaml \
  --as-of "$AS_OF" \
  --output reports
```

必要に応じて `--top-n` / `--top-k` を指定して母集団や最終件数を調整する。

## Audit Log Rules

- 銘柄ごとに根拠URL・取得日・採点理由を保持する。
- スコア変更履歴を保持する。
- 参照不能リンクを定期検知する。

## Reference

- 詳細仕様: `references/agent_spec_v1.md`
