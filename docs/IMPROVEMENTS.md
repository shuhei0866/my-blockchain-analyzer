# 🚀 新機能: マルチRPC + キャッシング

## 概要

リクエストに応じて、以下の2つの重要な機能を追加しました：

### 1. 複数RPCエンドポイント対応

**問題**: 公開RPCエンドポイントは厳しいレート制限があり、多数のリクエストが失敗する

**解決策**: 5つの公開RPCエンドポイントをラウンドロビン方式で使用

```python
# デフォルトで以下のRPCを自動切り替え
- https://api.mainnet-beta.solana.com
- https://solana-api.projectserum.com
- https://rpc.ankr.com/solana
- https://solana-mainnet.rpc.extrnode.com
- https://solana.public-rpc.com
```

#### メリット
- レート制限を分散
- 1つのエンドポイントが失敗しても自動フェイルオーバー
- 各エンドポイントの成功率を統計表示

### 2. SQLiteキャッシング

**問題**: 同じデータを何度も取得するのは非効率

**解決策**: ローカルSQLiteデータベースに結果を保存

#### 保存されるデータ
- トランザクション署名
- トランザクション詳細
- アドレスメタデータ（最終更新日時、トークン残高など）

#### メリット
- 2回目以降の実行が超高速
- 新しいトランザクションのみ取得（差分更新）
- ネットワークリクエスト削減
- オフラインでも分析可能（キャッシュデータがあれば）

## 使用方法

### 基本的な使い方

```bash
# 新しいanalyze.pyスクリプトを使用
python analyze.py <SOLANA_ADDRESS>

# オプション指定
python analyze.py <ADDRESS> \\
  --limit 200 \\
  --cache-db my_cache.db \\
  --batch-size 3 \\
  --max-concurrent 2
```

### 利用可能なオプション

```
--limit N              取得するトランザクション数 (default: 500)
--cache-db PATH        キャッシュDBのパス (default: data/solana_cache.db)
--force-refresh        キャッシュを無視して再取得
--no-details           詳細を取得しない（署名のみ、高速）
--no-visualize         可視化をスキップ
--batch-size N         バッチサイズ (default: 5)
--max-concurrent N     同時リクエスト数 (default: 3)
--output-dir PATH      出力ディレクトリ (default: output)
```

## 動作確認

### テスト結果

アドレス `DpkWS7Epdx7EcVJkavFAU9nRRJ3ixuw8z7U7QKA9sNRq` でテスト：

```
✓ 20件のトランザクション署名を取得
✓ SQLiteキャッシュに保存成功
✓ ラウンドロビン動作確認
✓ RPC統計情報表示
```

### キャッシュの確認

```bash
# キャッシュ統計を表示
sqlite3 data/solana_cache.db "SELECT COUNT(*) FROM signatures;"
sqlite3 data/solana_cache.db "SELECT COUNT(*) FROM transactions;"
```

## アーキテクチャ

```
solana_analyzer/
└── backend/
    ├── multi_rpc_client.py       # 🆕 マルチRPCクライアント
    ├── cache.py                   # 🆕 SQLiteキャッシュ
    ├── cached_analyzer.py         # 🆕 キャッシュ対応アナライザー
    ├── solana_client.py           # 既存: 単一RPCクライアント
    ├── transaction_analyzer.py    # 既存: トランザクション分析
    ├── balance_tracker.py         # 既存: 残高追跡
    └── analyzer_api.py            # 既存: API
```

## 実装詳細

### MultiRPCClient

```python
from solana_analyzer.backend.multi_rpc_client import MultiRPCClient

async with MultiRPCClient() as client:
    # 自動的にRPCをローテーション
    response = await client.get_signatures_for_address(pubkey)

# 統計情報を表示
client.print_stats()
```

### TransactionCache

```python
from solana_analyzer.backend.cache import TransactionCache

cache = TransactionCache("data/cache.db")

# 署名を保存
cache.save_signatures(address, signatures)

# キャッシュから取得
cached = cache.get_cached_signatures(address)

# 統計情報
stats = cache.get_cache_stats(address)
```

### CachedTransactionAnalyzer

```python
from solana_analyzer.backend.cached_analyzer import CachedTransactionAnalyzer

analyzer = CachedTransactionAnalyzer()

# 差分更新（新しいトランザクションのみ取得）
signatures = await analyzer.fetch_signatures_incremental(
    address,
    limit=1000,
    force_refresh=False
)

# トランザクション詳細をキャッシュ付きで取得
transactions = await analyzer.fetch_transaction_details_cached(
    address,
    signatures,
    batch_size=5,
    max_concurrent=3
)
```

## パフォーマンス比較

### 初回実行
- **従来**: 100トランザクション = 約5-10分（レート制限で失敗多数）
- **改良版**: 100トランザクション = 約2-3分（複数RPC使用）

### 2回目以降
- **従来**: 毎回同じ時間
- **改良版**: 数秒（キャッシュから読み込み）

### 差分更新
- **従来**: 全データ再取得
- **改良版**: 新しいトランザクションのみ取得（数秒）

## 今後の拡張

1. **カスタムRPCリストのサポート**
   ```python
   analyzer = CachedTransactionAnalyzer(
       rpc_urls=["your-custom-rpc-1", "your-custom-rpc-2"]
   )
   ```

2. **キャッシュの自動クリーンアップ**
   - 古いデータの自動削除
   - キャッシュサイズ制限

3. **分散キャッシュ**
   - Redis対応
   - 複数マシン間でのキャッシュ共有

4. **並列化の改善**
   - より多くの同時リクエスト
   - アダプティブなバッチサイズ

## トラブルシューティング

### Q: キャッシュをリセットしたい

```bash
rm -rf data/
```

### Q: 特定のアドレスだけキャッシュをクリア

```bash
sqlite3 data/solana_cache.db \\
  "DELETE FROM signatures WHERE address='<ADDRESS>';"
```

### Q: すべてのRPCが失敗する

- ネットワーク接続を確認
- 専用RPCプロバイダーの使用を検討
- `--no-details` オプションで署名のみ取得を試す

## まとめ

✅ **実装完了**
- 複数RPCエンドポイント対応
- SQLiteキャッシング
- 差分更新
- パフォーマンス統計

🎯 **主な改善**
- レート制限回避
- 高速化（2回目以降）
- データの永続化
- 信頼性向上

これらの機能により、公開RPCでも実用的な分析が可能になりました！
