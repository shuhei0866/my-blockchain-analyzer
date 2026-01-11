#!/usr/bin/env python3
"""
Improved Solana Address Analyzer with Multi-RPC and Caching

Features:
- Multiple RPC endpoints for rate limit avoidance
- SQLite caching for faster subsequent runs
- Incremental updates (only fetch new transactions)
"""
import asyncio
import argparse
from pathlib import Path
from solana_analyzer.backend.cached_analyzer import CachedTransactionAnalyzer
from solana_analyzer.backend.transaction_analyzer import TransactionAnalyzer
from solana_analyzer.backend.balance_tracker import BalanceTracker
from solana_analyzer.visualization.visualizer import SolanaVisualizer


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Analyze Solana address with caching and multi-RPC support'
    )

    parser.add_argument(
        'address',
        type=str,
        help='Solana address to analyze'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=500,
        help='Maximum number of transactions to fetch (default: 500)'
    )

    parser.add_argument(
        '--cache-db',
        type=str,
        default='data/solana_cache.db',
        help='SQLite cache database path (default: data/solana_cache.db)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory for results (default: output)'
    )

    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force refresh from RPC (ignore cache)'
    )

    parser.add_argument(
        '--no-details',
        action='store_true',
        help='Skip fetching transaction details (faster, signatures only)'
    )

    parser.add_argument(
        '--no-visualize',
        action='store_true',
        help='Skip visualization generation'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Transaction batch size (default: 5)'
    )

    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=3,
        help='Max concurrent requests (default: 3)'
    )

    args = parser.parse_args()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*70)
    print("  Solana Address Analyzer (Multi-RPC + Cache)")
    print("="*70)

    # Initialize analyzer
    analyzer = CachedTransactionAnalyzer(cache_db=args.cache_db)

    # Show cache stats
    cache_stats = analyzer.get_cache_stats(args.address)
    print(f"\n📦 Cache Status:")
    print(f"  Database: {args.cache_db}")
    print(f"  Cached Signatures: {cache_stats['cached_signatures']}")
    print(f"  Cached Transactions: {cache_stats['cached_transactions']}")

    if cache_stats['metadata']:
        print(f"  Last Updated: {cache_stats['metadata']['last_updated']}")

    print(f"\n🔍 Analyzing Address: {args.address}")
    print(f"  Transaction Limit: {args.limit}")
    print(f"  Force Refresh: {args.force_refresh}")
    print(f"  Fetch Details: {not args.no_details}")

    # Fetch signatures (incremental)
    print(f"\n{'='*70}")
    print("Step 1: Fetching Transaction Signatures")
    print(f"{'='*70}")

    signatures = await analyzer.fetch_signatures_incremental(
        args.address,
        limit=args.limit,
        force_refresh=args.force_refresh
    )

    print(f"\n✓ Total signatures available: {len(signatures)}")

    # Get current balances
    print(f"\n{'='*70}")
    print("Step 2: Fetching Current Balances")
    print(f"{'='*70}")

    current_balances = await analyzer.get_current_balances(args.address)
    print(f"✓ Found {len(current_balances)} tokens")

    # Save metadata
    analyzer.cache.update_address_metadata(
        args.address,
        len(signatures),
        signatures[0]['signature'] if signatures else None,
        current_balances
    )

    # Fetch transaction details
    transactions = []
    if not args.no_details and signatures:
        print(f"\n{'='*70}")
        print("Step 3: Fetching Transaction Details")
        print(f"{'='*70}")

        transactions = await analyzer.fetch_transaction_details_cached(
            args.address,
            signatures[:args.limit],
            batch_size=args.batch_size,
            max_concurrent=args.max_concurrent
        )

        print(f"\n✓ Retrieved {len(transactions)} transaction details")

    # Analyze
    print(f"\n{'='*70}")
    print("Step 4: Analyzing Data")
    print(f"{'='*70}")

    # Use existing analyzer for statistics
    tx_analyzer = TransactionAnalyzer()
    token_flows = tx_analyzer.analyze_token_flows(transactions, args.address)

    # Calculate balance history
    balance_tracker = BalanceTracker()
    balance_histories = balance_tracker.calculate_balance_history(
        transactions,
        args.address,
        current_balances
    )

    daily_balances = balance_tracker.calculate_daily_balances(balance_histories)

    # Prepare results
    balance_history_data = {}
    for mint, df in balance_histories.items():
        balance_history_data[mint] = df.to_dict('records')

    daily_balance_data = {}
    for mint, df in daily_balances.items():
        daily_balance_data[mint] = df.to_dict('records')

    # Count transactions by status
    successful = sum(1 for tx in transactions if tx.get('meta') and not tx['meta'].get('err'))
    failed = sum(1 for tx in transactions if tx.get('meta') and tx['meta'].get('err'))

    # Get time range
    timestamps = [sig['block_time'] for sig in signatures if sig['block_time'] is not None]
    from datetime import datetime
    first_tx_time = datetime.fromtimestamp(min(timestamps)).isoformat() if timestamps else None
    last_tx_time = datetime.fromtimestamp(max(timestamps)).isoformat() if timestamps else None

    summary = {
        'address': args.address,
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

    # Save results
    import json
    results_file = output_path / f"analysis_{args.address[:8]}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print(f"✓ Results saved to: {results_file}")

    # Visualize
    if not args.no_visualize and transactions:
        print(f"\n{'='*70}")
        print("Step 5: Generating Visualizations")
        print(f"{'='*70}\n")

        visualizer = SolanaVisualizer()
        visualizer.create_summary_report(results, output_dir=str(output_path))

    # Final summary
    print(f"\n{'='*70}")
    print("  Summary")
    print(f"{'='*70}")
    print(f"\nAddress: {summary['address']}")
    print(f"Total Transactions: {summary['total_transactions']}")
    print(f"Successful: {summary['successful_transactions']}")
    print(f"Failed: {summary['failed_transactions']}")

    if summary.get('first_transaction_time'):
        print(f"First Transaction: {summary['first_transaction_time']}")
    if summary.get('last_transaction_time'):
        print(f"Last Transaction: {summary['last_transaction_time']}")

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
        print(f"\nToken Flows (Top 5):")
        flows_sorted = sorted(
            token_flows.items(),
            key=lambda x: x[1]['transaction_count'],
            reverse=True
        )
        for mint, flows in flows_sorted[:5]:
            token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
            print(f"  {token_name}:")
            print(f"    Transactions: {flows['transaction_count']}")
            print(f"    Net Change: {flows['net_change']:.4f}")

    # Cache stats
    final_cache_stats = analyzer.get_cache_stats(args.address)
    print(f"\n📦 Final Cache Stats:")
    print(f"  Signatures: {final_cache_stats['cached_signatures']}")
    print(f"  Transactions: {final_cache_stats['cached_transactions']}")

    print(f"\nResults saved to: {output_path}")
    print(f"{'='*70}\n")

    analyzer.close()


if __name__ == '__main__':
    asyncio.run(main())
