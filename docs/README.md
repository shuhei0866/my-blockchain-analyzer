# Solana Address Analyzer

Solanaアドレスのトークン残高推移やトランザクションログを可視化・分析するPythonツール。

## 特徴

- トランザクション履歴の取得と分析
- トークン残高の時系列推移計算
- トークンフロー分析（受信/送信）
- Matplotlibによる可視化
- バックエンドと可視化の分離設計（将来のWebアプリ化に対応）

## インストール

```bash
# 依存関係のインストール
pip install -r requirements.txt
```

## 使い方

### コマンドライン

```bash
# 基本的な使い方
python main.py HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P

# トランザクション数を指定
python main.py HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P --limit 1000

# 出力ディレクトリを指定
python main.py HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P --output-dir my_analysis

# プロットを表示
python main.py HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P --show-plots

# カスタムRPCエンドポイント
python main.py HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P --rpc-url https://your-rpc-endpoint.com
```

### Pythonコードから使用

```python
import asyncio
from solana_analyzer.backend.analyzer_api import SolanaAnalyzerAPI
from solana_analyzer.visualization.visualizer import SolanaVisualizer

async def analyze():
    # バックエンドAPIの初期化
    api = SolanaAnalyzerAPI()

    # アドレスの分析
    results = await api.analyze_address(
        address='HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P',
        limit=500,
        save_to_file='analysis_results.json'
    )

    # 可視化
    visualizer = SolanaVisualizer()
    visualizer.create_summary_report(results, output_dir='output')

    return results

# 実行
results = asyncio.run(analyze())
```

## プロジェクト構造

```
.
├── main.py                          # メインエントリーポイント
├── requirements.txt                 # Python依存関係
├── solana_analyzer/
│   ├── backend/                     # バックエンド（分析ロジック）
│   │   ├── __init__.py
│   │   ├── solana_client.py        # Solana RPC クライアント
│   │   ├── transaction_analyzer.py # トランザクション分析
│   │   ├── balance_tracker.py      # 残高推移計算
│   │   └── analyzer_api.py         # バックエンドAPI
│   └── visualization/               # 可視化
│       ├── __init__.py
│       └── visualizer.py           # Matplotlib可視化
└── output/                          # 出力結果（自動生成）
```

## 出力

分析結果は以下の形式で出力されます：

### ファイル

- `analysis_{address}.json` - 分析結果のJSONデータ
- `balance_histories/` - 各トークンの残高推移グラフ
- `daily_balances/` - 日次残高スナップショット
- `token_flows.png` - トークンフロー分析グラフ
- `transaction_timeline.png` - トランザクションタイムライン

### データ構造

```json
{
  "summary": {
    "address": "...",
    "total_transactions": 100,
    "successful_transactions": 98,
    "failed_transactions": 2,
    "token_flows": {
      "SOL": {
        "total_received": 10.5,
        "total_sent": 8.2,
        "net_change": 2.3,
        "transaction_count": 50
      }
    },
    "current_balances": { ... }
  },
  "balance_histories": { ... },
  "daily_balances": { ... }
}
```

## バックエンドAPIの使用（Webアプリ化）

バックエンドは分析ロジックと可視化が分離されているため、Webアプリケーションとして簡単に統合できます：

```python
from solana_analyzer.backend.analyzer_api import SolanaAnalyzerAPI

# FastAPIやFlaskなどで使用可能
api = SolanaAnalyzerAPI()

# アドレスサマリー取得（軽量）
summary = await api.get_address_summary(address)

# 詳細分析
analysis = await api.analyze_address(address, limit=1000)

# トークンフロー分析のみ
flows = await api.get_token_flow_analysis(address)
```

## 注意事項

- Solana RPCエンドポイントのレート制限に注意してください
- 大量のトランザクション取得には時間がかかる場合があります
- デフォルトでは公開RPCエンドポイントを使用します（本番環境では専用エンドポイントの使用を推奨）

## ライセンス

MIT License
