# 再利用する分析モジュール

`packages/portfolio-core` は既存の分析スクリプト/WebUIから独立したPython subproject。公開import名は `blockchain_portfolio`、配布名は `blockchain-portfolio-core`。依存は標準ライブラリだけ。

## 責任の境界

| このpackage | consumer application |
|---|---|
| read RPC、整数数量、資産識別、取得範囲 | 口座登録、所有区分、保存先、アクセス制御 |
| 明示された価格・原価による単一保有の算術 | 価格の選択、原価の根拠、所有口座間の移動照合 |
| failed / unsupportedを含むprovider観測 | 採用する資産表現、口座集計、期間成績、UI |

依存はconsumer→packageの一方向。旧 `blockchain_analyzer` / `solana_analyzer` / `web` はimportしない。floatベースの旧DTOと新契約を暗黙に混ぜない。

`Asset` はnetwork+reference。native・contract・mintは別ID。EVM contractは一箇所で小文字へ正規化し、Solana mintのcaseは維持。異なるnetworkやwrapperを価格記号だけで同一視しない。
`Holding` は整数unitsとdecimals。貸付・借入のうち借入はside=liabilityで表す。デリバティブnotionalを保有資産にしない。
`Price` は通貨、単価、確認時刻、source ID、任意のsource更新時刻とproxyを持つ。API URLや認証値をsource IDへ入れない。`CostBasis` はconsumerが根拠を確認した残存数量・取得原価・通貨・時刻で、初回観測の時価を自動採用しない。

`value_holding(..., at=..., max_price_age=...)` はclockも鮮度policyも呼出側が指定する。価格が古い/未来/欠測なら評価額null。原価がない/数量や通貨が一致しないなら含み損益null。単一保有を超えた集計・送金・時系列損益・税務計算を実装しない。

## 初期providerの範囲

- Ethereum/Arbitrum: native ETHとnative USDC、同じblockで読取。その他token/network/DeFiは未対応。
- Solana: finalized native SOL、legacy SPL、Token-2022のraw base units。Token-2022固有拡張の経済価値、DeFi/NFT評価、名前・価格推定は未対応。
- 取得は逐次であり全networkで原子的なsnapshotではない。観測時刻はcallerが与え、読めたblock/slotとcoverageを保持する。
- 失敗はcoverageへ残す。private URL/例外本文/認証値は結果に出さない。全取得失敗も空資産が確認できたこととは違う。

## 配布と変更

consumerは `git+https` のfull commitと `#subdirectory=packages/portfolio-core` をpinする。ローカルでpaired開発する場合もwheelをbuildしてinstallし、隣接repoのPYTHONPATHやsys.pathへ依存しない。正規化行と評価結果にはpackage版/schema版を記録する。

wheelは4つのpackage `.py` とdist-infoだけをallowlist検査する。rootのdata/output、旧WebUI、設定、テストをwheelに同梱しない。未知schemaはconsumerで拒否し、更新は明示した依存変更として試験する。
