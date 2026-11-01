# Blockchain Portfolio Core

独立してbuildできる、read-onlyの分析ライブラリ。旧WebUI、pandas/float経路、設定、環境変数、home、DBをimport時に読み込まない。

- `blockchain_portfolio.model`: chain + contract/mint/nativeの資産ID、整数base units + decimalsの保有量、Decimal価格、明示された残存取得原価、取得範囲。
- `providers`: 固定されたEVM/Solanaのread RPC。口座参照・観測時刻・transportを呼出側から渡す。送信/署名/鍵/既定の保存先を持たない。
- `value_holding`: 単一保有の評価額と、渡された原価が一致する場合の含み損益。時刻・price setは呼出側が指定する。原価や価格が不明ならnullを保持する。
- `quotes`: Krakenの固定公開spot APIからSOLUSD/ETHUSD/USDCUSDの直近1約定を読む。通貨・価格種別・約定時刻を保持し、資産との対応付けはconsumerが行う。

EVMはEthereum/ArbitrumのETH・ネイティブUSDCと、Soneium mainnetのETH・USDC.e。Soneiumは[公式network情報](https://docs.soneium.org/docs/builders/sfa)のchain ID 1868とRPCを固定し、同一blockで読む。[公式bridge資料](https://docs.soneium.org/docs/users/bridging)にあるUSDC.eは別contract/coverageとして保持し、ネイティブUSDCや同価格とは扱わない。Solanaはnative SOL、legacy SPL、Token-2022。DeFi/NFT評価、その他token/networkは未対応として明示する。失敗を空残高や0へ変えず、coverageを返す。例外本文・RPC URLを結果へ入れない。

RPCは`blockchain-portfolio-core/<version>`のUser-Agentでアプリを識別する。Python標準の識別名がHTTP 403 / Cloudflare 1010になる場合に対する[公式の設定案内](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/)に沿う。ブラウザの識別名は使わず、固定接続先・TLS検証・redirect拒否・失敗時のcoverageを維持する。

trading-opsはconsumerの一つ。口座一覧・所有区分・取得原価の根拠・内部送金照合・採用する資産表現・実験帰属・保存・UIのpolicyはconsumerが管理する。SDKは所有者を推測せず、異なる口座の合計や期間損益を計算しない。

```sh
PYTHONPATH=packages/portfolio-core/src python3 -m unittest discover -s packages/portfolio-core/tests -v
python3 -m pip wheel --no-deps ./packages/portfolio-core -w /path/to/wheelhouse
```

配布対象はこのsubprojectだけ。root全体、legacy data/output、設定、テストfixtureをwheelへ入れない。consumerはimmutable commitとpackage subdirectoryを指定し、正規化行/評価結果にSDK版とschema版を残す。

価格参照は[Kraken Recent Trades](https://docs.kraken.com/api-reference/market-data/get-recent-trades)。GET先・product・応答keyを固定し、redirect/認証探索/暗黙fallbackを持たない。JSON数値はDecimal文字列で読み、時刻をfloatへ変換しない。`kraken_quote(product, payload, at=...)` はreceipt clockをcallerが指定する。`Price.kind` は任意の価格種別で、valuationにも記録する。直近約定は執行可能価格や全venue共通の公正価値を保証しない。
