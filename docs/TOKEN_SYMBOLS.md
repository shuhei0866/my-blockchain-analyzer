# トークンシンボル表示機能

## 概要

トークンをコントラクトアドレス（mint address）ではなく、シンボル（例：USDC、SOL、USDT）で表示する機能を追加しました。

## 実装内容

### 1. TokenRegistry クラス

**ファイル**: `solana_analyzer/backend/token_registry.py`

Jupiter Token Listを使用して、約15,000以上のSolanaトークンのシンボル・名前・メタデータを提供します。

#### 主な機能

- **トークンシンボル取得**: `get_symbol(mint_address)`
- **トークン名取得**: `get_name(mint_address)`
- **フォーマット表示**: `format_token_display(mint_address)`
- **トークン検索**: `search_tokens(query)`

#### キャッシング

- 初回実行時にJupiterからトークンリストをダウンロード
- `data/token_list.json` にキャッシュ（約15MB）
- 24時間有効（デフォルト）
- オフラインでも動作（キャッシュがあれば）

### 2. 改良版可視化スクリプト

**ファイル**: `create_charts_v2.py`

トークンシンボルを使った可視化を生成します。

## 使い方

### 基本的な使い方

```bash
# 1. トークンリストをダウンロード（初回のみ推奨）
python download_token_list.py

# 2. 残高データを保存
python save_balance.py <YOUR_ADDRESS>

# 3. シンボル表示のグラフを生成
python create_charts_v2.py
```

### 出力例

```
Token Holdings (with symbols)
======================================================================
Rank  Symbol       Name                                    Amount
----------------------------------------------------------------------
1     4vMsoUT2...  4vMsoUT2...                          18,556.57
2     MikamiBj...  MikamiBj...                           8,633.28
...
13    SOL          Solana                                    3.99
...
20    USDT         USDT                                      0.02
```

### 生成されるグラフ

1. **`1_top_10_tokens_symbols.png`**
   - トップ10トークンの横棒グラフ
   - シンボル表示（例：SOL、USDC）

2. **`2_token_distribution_symbols.png`**
   - 円グラフ
   - シンボルでラベル表示

3. **`3_token_details_table.png`**
   - 詳細テーブル
   - ランク、シンボル、名前、金額、アドレス

## Pythonコードから使用

```python
from solana_analyzer.backend.token_registry import TokenRegistry

# 初期化
registry = TokenRegistry()

# シンボル取得
symbol = registry.get_symbol("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
print(symbol)  # "USDC"

# 名前取得
name = registry.get_name("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
print(name)  # "USD Coin"

# フォーマット表示
display = registry.format_token_display(
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    show_address=True
)
print(display)  # "USDC (EPjFWdd5...)"

# トークン検索
results = registry.search_tokens("usdc", limit=5)
for token in results:
    print(f"{token['symbol']}: {token['name']}")
```

## データソース

### Jupiter Token List

- **URL**: https://tokens.jup.ag/tokens
- **トークン数**: 約15,000+
- **更新頻度**: 定期的（コミュニティ管理）
- **含まれる情報**:
  - symbol（シンボル）
  - name（名前）
  - decimals（小数点桁数）
  - logoURI（ロゴURL）
  - tags（タグ）

### フォールバックリスト

ネットワーク接続できない場合、以下の主要トークンを含むフォールバックリストを使用：

- SOL（Solana）
- USDC（USD Coin）
- USDT（Tether）
- BONK（Bonk）
- mSOL（Marinade staked SOL）
- stSOL（Lido Staked SOL）

## 設定

### キャッシュ設定

```python
# カスタムキャッシュパスとTTL
registry = TokenRegistry(
    cache_file="my_custom_cache.json",
    cache_ttl_hours=48  # 48時間有効
)
```

### 手動でキャッシュを更新

```bash
# キャッシュを削除して再ダウンロード
rm data/token_list.json
python download_token_list.py
```

## トラブルシューティング

### Q: トークンリストがダウンロードできない

**A**: ネットワーク接続を確認してください。オフラインの場合、フォールバックリストが使用されます。

```bash
# 手動でダウンロードを試す
python download_token_list.py
```

### Q: 一部のトークンがシンボル表示されない

**A**: Jupiter Token Listに含まれていない可能性があります。その場合、アドレスの一部が表示されます。

### Q: キャッシュのサイズが大きい

**A**: Jupiter Token Listは約15MBです。必要に応じて削除できます：

```bash
rm data/token_list.json
```

次回実行時に再ダウンロードされます。

## パフォーマンス

- **初回ロード**: 1-3秒（ダウンロード + キャッシュ保存）
- **キャッシュから**: 0.1秒未満
- **シンボル取得**: O(1)（辞書検索）

## 今後の拡張

1. **複数のデータソース統合**
   - Solana Token Registry
   - Metaplex Metadata
   - CoinGecko API

2. **価格情報の追加**
   - USD価格表示
   - ポートフォリオ総額計算

3. **カスタムトークン追加**
   - ユーザー定義のトークンマッピング
   - ローカルオーバーライド

4. **ロゴ表示**
   - トークンロゴのダウンロード
   - グラフへのロゴ埋め込み

## まとめ

✅ **実装完了**
- トークンシンボル表示
- Jupiter Token List統合
- キャッシング機構
- フォールバック対応

🎯 **メリット**
- 読みやすい表示
- オフライン対応
- 高速検索
- 包括的なカバレッジ（15,000+トークン）
