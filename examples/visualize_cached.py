#!/usr/bin/env python3
"""Visualize cached transaction data"""
import asyncio
import sys
from pathlib import Path
from solana_analyzer.backend.cached_analyzer import CachedTransactionAnalyzer
from solana_analyzer.backend.transaction_analyzer import TransactionAnalyzer
from solana_analyzer.backend.balance_tracker import BalanceTracker
from solana_analyzer.visualization.visualizer import SolanaVisualizer


async def visualize_from_cache(address: str, output_dir: str = "output/visualizations"):
    """Visualize data from cache"""
    print(f"\n{'='*70}")
    print("  Visualizing Cached Data")
    print(f"{'='*70}\n")

    analyzer = CachedTransactionAnalyzer()

    # Get cache stats
    stats = analyzer.get_cache_stats(address)
    print(f"Cache Status:")
    print(f"  Signatures: {stats['cached_signatures']}")
    print(f"  Transactions: {stats['cached_transactions']}")

    if stats['cached_signatures'] == 0:
        print("\n❌ No cached data found. Please run analyze.py first.")
        return

    # Get cached signatures
    signatures = analyzer.cache.get_cached_signatures(address, limit=100)
    print(f"\n✓ Loaded {len(signatures)} signatures from cache")

    # Get current balances
    print("\n📊 Fetching current balances...")
    try:
        current_balances = await analyzer.get_current_balances(address)
        print(f"✓ Found {len(current_balances)} tokens")
    except Exception as e:
        print(f"⚠ Warning: Could not fetch current balances: {e}")
        current_balances = stats['metadata']['current_balances'] if stats['metadata'] else {}

    # Get cached transactions
    print(f"\n📦 Loading transaction details from cache...")
    transactions = analyzer.cache.get_cached_transactions(address, limit=100)
    print(f"✓ Loaded {len(transactions)} transaction details")

    if len(transactions) < len(signatures) * 0.3:
        print(f"\n⚠ Warning: Only {len(transactions)}/{len(signatures)} transactions have details")
        print("  Run analyze.py to fetch missing transaction details")

    # Analyze
    print(f"\n🔍 Analyzing data...")
    tx_analyzer = TransactionAnalyzer()
    token_flows = tx_analyzer.analyze_token_flows(transactions, address)

    balance_tracker = BalanceTracker()
    balance_histories = balance_tracker.calculate_balance_history(
        transactions,
        address,
        current_balances
    )

    daily_balances = balance_tracker.calculate_daily_balances(balance_histories)

    # Prepare results
    balance_history_data = {mint: df.to_dict('records') for mint, df in balance_histories.items()}
    daily_balance_data = {mint: df.to_dict('records') for mint, df in daily_balances.items()}

    # Count transactions
    successful = sum(1 for tx in transactions if tx.get('meta') and not tx['meta'].get('err'))
    failed = sum(1 for tx in transactions if tx.get('meta') and tx['meta'].get('err'))

    # Time range
    from datetime import datetime
    timestamps = [sig['block_time'] for sig in signatures if sig['block_time']]
    first_tx_time = datetime.fromtimestamp(min(timestamps)).isoformat() if timestamps else None
    last_tx_time = datetime.fromtimestamp(max(timestamps)).isoformat() if timestamps else None

    summary = {
        'address': address,
        'total_transactions': len(signatures),
        'successful_transactions': successful,
        'failed_transactions': failed,
        'first_transaction_time': first_tx_time,
        'last_transaction_time': last_tx_time,
        'token_flows': token_flows,
        'current_balances': current_balances,
    }

    results = {
        'summary': summary,
        'balance_histories': balance_history_data,
        'daily_balances': daily_balance_data,
    }

    # Visualize
    print(f"\n📈 Generating visualizations...")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    visualizer = SolanaVisualizer()
    visualizer.create_summary_report(results, output_dir=str(output_path))

    # Print summary
    print(f"\n{'='*70}")
    print("  Summary")
    print(f"{'='*70}")
    print(f"\nAddress: {address}")
    print(f"Total Transactions: {len(signatures)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if first_tx_time:
        print(f"First Transaction: {first_tx_time}")
    if last_tx_time:
        print(f"Last Transaction: {last_tx_time}")

    print(f"\nCurrent Balances (Top 10):")
    balances_sorted = sorted(
        current_balances.items(),
        key=lambda x: float(x[1].get('ui_amount', 0) or 0),
        reverse=True
    )
    for mint, balance in balances_sorted[:10]:
        token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
        print(f"  {token_name}: {balance.get('ui_amount', 0)}")

    if token_flows:
        print(f"\nToken Activity (Top 5):")
        flows_sorted = sorted(
            token_flows.items(),
            key=lambda x: x[1]['transaction_count'],
            reverse=True
        )
        for mint, flows in flows_sorted[:5]:
            token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
            print(f"  {token_name}: {flows['transaction_count']} transactions")

    print(f"\n✅ Visualizations saved to: {output_path}")
    print(f"{'='*70}\n")

    analyzer.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python visualize_cached.py <SOLANA_ADDRESS> [output_dir]")
        sys.exit(1)

    address = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output/visualizations"

    asyncio.run(visualize_from_cache(address, output_dir))
