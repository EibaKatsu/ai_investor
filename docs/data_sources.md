# データソース方針（2026-02-16時点）

## 1. 採用方針

採用スタックは以下で固定する。

1. 株価・基礎財務: J-Quants
2. 開示一次情報: EDINET API
3. 適時開示: TDnet（公開閲覧を基本、APIは将来拡張）
4. 一般ニュース補完: Web検索（Google News RSS）

J-QuantsはV2 API（APIキー認証）を使用する。

## 2. 無料優先モード（MVP）

無料優先モードでは次の構成で運用する。

1. J-Quants Free
2. EDINET API
3. TDnet適時開示情報閲覧サービス（公開ページ取得）
4. Web検索（Google News RSS）

## 3. 制約（無料優先モード）

1. J-Quants Freeはデータに12週間遅延がある
2. J-Quants Freeは直近2年分の提供制限がある
3. TDnet APIは有料契約が前提のためMVPでは未使用
4. TDnet公開閲覧の掲載期間は31日間
5. Web検索結果は媒体ごとに更新タイミング・掲載範囲が異なる

## 4. 実装上の扱い

1. `quant_pipeline` はJ-Quants Free前提で動作させる
2. `filing_parser` はEDINETを一次ソースとして採点根拠を生成する
3. `timely_disclosure` はTDnet公開閲覧のURLを根拠リンクとして保持する
4. `news_enrichment` はWeb検索（Google News RSS）で補完し、更新時刻を必ず記録する
5. 直近性不足の判定が出た銘柄は最終出力で `Watch` に寄せる

## 5. 有料移行トリガー

以下のいずれかに該当したら有料移行を検討する。

1. 12週間遅延によりスクリーニング結果が運用に使いにくい
2. TDnetの31日制約で根拠保持が不足する
3. ニュース取得の再現性・網羅性を高める必要がある

## 6. 推奨移行順

1. J-Quants Lite以上へ移行（遅延制約を解消）
2. TDnet API契約（開示取得をAPI化）
3. ニュースAPIを商用プランへ移行
