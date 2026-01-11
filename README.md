# Solana Analyzer

Solanaアドレスのトークン残高、トランザクション履歴、トークンフローを分析・可視化するツールです。

## 特徴

- ✅ トークン残高の取得と可視化
- ✅ トークンシンボル表示（Jupiter Token Listを使用）
- ✅ トランザクション履歴のキャッシング（SQLite）
- ✅ 複数RPCエンドポイントのサポート（レート制限回避）
- ✅ トークンフロー分析（サンキーダイアグラム、時系列チャート）

## ディレクトリ構成

```
.
├── README.md                    # このファイル
├── requirements.txt             # 依存パッケージ
├── .env.example                 # 環境変数の例
│
├── scripts/                     # メインスクリプト
│   ├── save_balance.py         # 残高データを保存
│   ├── visualize_balance.py    # 残高チャートを生成（シンボル表示）
│   ├── create_sankey.py        # サンキーダイアグラムを生成
│   ├── visualize_flows.py      # トランザクションフローチャートを生成
│   ├── fetch_transactions.py   # トランザクション詳細を取得
│   └── download_token_list.py  # トークンリストをダウンロード
│
├── solana_analyzer/            # バックエンドライブラリ
│   └── backend/
│       ├── token_registry.py          # トークンシンボル管理
│       ├── transaction_parser.py      # トランザクション解析
│       ├── multi_rpc_client.py        # マルチRPCクライアント
│       ├── cache.py                   # SQLiteキャッシュ
│       └── cached_analyzer.py         # キャッシュ付き分析器
│
├── data/                        # データファイル
│   ├── balance.json            # 残高データ
│   ├── token_list.json         # トークンリスト（キャッシュ）
│   └── solana_cache.db         # トランザクションキャッシュ
│
├── output/                      # 出力ファイル
│   ├── charts_v2/              # 残高チャート（シンボル表示）
│   ├── sankey/                 # サンキーダイアグラム
│   └── flows/                  # トランザクションフローチャート
│
├── docs/                        # ドキュメント
│   ├── USAGE_GUIDE.md          # 使い方ガイド
│   ├── IMPROVEMENTS.md         # 改善履歴
│   └── TOKEN_SYMBOLS.md        # トークンシンボル機能の説明
│
└── examples/                    # 旧バージョン・例示スクリプト
    └── ...
```

## セットアップ

### 1. 仮想環境の作成

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows
```

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. トークンリストのダウンロード（オプション）

```bash
python scripts/download_token_list.py
```

## クイックスタート

最も簡単な使い方（トランザクション詳細なし）：

```bash
# 1. 仮想環境を有効化
source venv/bin/activate

# 2. 残高データを保存
python scripts/save_balance.py <YOUR_SOLANA_ADDRESS>

# 3. チャート生成
python scripts/visualize_balance.py

# 4. サンキーダイアグラム生成
python scripts/create_sankey.py
```

生成されたチャート:
- `output/charts_v2/` - 3つの残高チャート（PNG）
- `output/sankey/balance_sankey.html` - サンキーダイアグラム（ブラウザで開く）

## 使い方

### 基本的な使い方

#### 1. 残高データの保存

```bash
python scripts/save_balance.py <YOUR_SOLANA_ADDRESS>
```

出力: `data/balance.json`

#### 2. チャートの生成（シンボル表示）

```bash
python scripts/visualize_balance.py
```

出力: `output/charts_v2/` 以下に3つのチャート

#### 3. サンキーダイアグラムの生成

```bash
python scripts/create_sankey.py
```

出力: `output/sankey/balance_sankey.html`（ブラウザで開く）

#### 4. トランザクション詳細の取得（オプション）

```bash
python scripts/fetch_transactions.py <YOUR_SOLANA_ADDRESS> --limit 100
```

出力: `data/solana_cache.db` にキャッシュ

#### 5. トランザクションフローチャートの生成（トランザクション詳細が必要）

```bash
python scripts/visualize_flows.py data/solana_cache.db <YOUR_SOLANA_ADDRESS>
```

出力: `output/flows/` 以下にサンキーダイアグラムと時系列チャート

### 例

```bash
# アドレスを環境変数に設定（便利）
export SOLANA_ADDRESS="DpkWS7Epdx7EcVJkavFAU9nRRJ3ixuw8z7U7QKA9sNRq"

# 1. 残高を保存
python scripts/save_balance.py $SOLANA_ADDRESS

# 2. 残高チャート生成
python scripts/visualize_balance.py

# 3. サンキーダイアグラム生成
python scripts/create_sankey.py

# 4. トランザクション取得（オプション）
python scripts/fetch_transactions.py $SOLANA_ADDRESS --limit 200

# 5. トランザクションフローチャート生成（トランザクション詳細が必要）
python scripts/visualize_flows.py data/solana_cache.db $SOLANA_ADDRESS
```

## 生成されるチャート

### 残高チャート（`output/charts_v2/`）

1. **`1_top_10_tokens_symbols.png`**
   - トップ10トークンの横棒グラフ
   - シンボル表示（例: SOL、USDC）

2. **`2_token_distribution_symbols.png`**
   - 円グラフによるトークン分布
   - シンボルでラベル表示

3. **`3_token_details_table.png`**
   - 詳細テーブル
   - ランク、シンボル、名前、金額、アドレス

### サンキーダイアグラム（`output/sankey/`）

1. **`balance_sankey.html`**
   - インタラクティブなサンキーダイアグラム
   - トークン保有量の視覚化
   - ブラウザで開いて表示

### トランザクションフローチャート（`output/flows/`）

**⚠️ 注意: トランザクション詳細の取得が必要です**

1. **`sankey_diagram.html`**
   - インタラクティブなサンキーダイアグラム
   - トークンの入出金フローを可視化

2. **`1_token_inflows_timeseries.png`**
   - 時系列のトークン流入量

3. **`2_token_outflows_timeseries.png`**
   - 時系列のトークン流出量

4. **`3_net_flows_timeseries.png`**
   - 純フロー（流入 - 流出）の推移

5. **`4_token_activity_heatmap.png`**
   - トークンアクティビティのヒートマップ

## トラブルシューティング

### RPC接続エラー

公開RPCエンドポイントは不安定な場合があります。複数のエンドポイントを自動的に試行しますが、失敗する場合は時間を置いて再試行してください。

### トークンシンボルが表示されない

Jupiter Token Listをダウンロードしてください：

```bash
python scripts/download_token_list.py
```

### トランザクション詳細が取得できない

RPC制限により、トランザクション詳細の取得が失敗することがあります。`--limit`を減らして再試行するか、時間を置いて実行してください。

## 技術スタック

- **Python 3.13**
- **solana-py** - Solana RPC クライアント
- **matplotlib** - 静的チャート生成
- **plotly** - インタラクティブチャート
- **pandas** - データ処理
- **SQLite** - トランザクションキャッシュ

## ドキュメント

詳細なドキュメントは `docs/` ディレクトリを参照してください：

- [USAGE_GUIDE.md](docs/USAGE_GUIDE.md) - 詳細な使い方ガイド
- [TOKEN_SYMBOLS.md](docs/TOKEN_SYMBOLS.md) - トークンシンボル機能の説明
- [IMPROVEMENTS.md](docs/IMPROVEMENTS.md) - 改善履歴

## ライセンス

MIT License
