#!/usr/bin/env python3
"""
Solana Address Analyzer - Main Entry Point

This script analyzes a Solana address and generates visualizations.
"""
import asyncio
import argparse
from pathlib import Path
from solana_analyzer.backend.analyzer_api import SolanaAnalyzerAPI
from solana_analyzer.visualization.visualizer import SolanaVisualizer


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Analyze a Solana address and visualize transaction history'
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
        '--rpc-url',
        type=str,
        default='https://api.mainnet-beta.solana.com',
        help='Solana RPC endpoint URL'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory for results and visualizations (default: output)'
    )

    parser.add_argument(
        '--no-visualize',
        action='store_true',
        help='Skip visualization generation'
    )

    parser.add_argument(
        '--show-plots',
        action='store_true',
        help='Display plots interactively (default: save only)'
    )

    args = parser.parse_args()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    api = SolanaAnalyzerAPI(rpc_url=args.rpc_url)

    results_file = output_path / f"analysis_{args.address[:8]}.json"

    print("\n" + "="*60)
    print("  Solana Address Analyzer")
    print("="*60)

    results = await api.analyze_address(
        address=args.address,
        limit=args.limit,
        save_to_file=str(results_file)
    )

    if not args.no_visualize:
        print("\n" + "="*60)
        print("  Generating Visualizations")
        print("="*60 + "\n")

        visualizer = SolanaVisualizer()

        visualizer.create_summary_report(
            results,
            output_dir=str(output_path)
        )

        if args.show_plots:
            print("\nDisplaying summary plots...")

            visualizer.plot_token_flows(
                results['summary'].get('token_flows', {}),
                show=True
            )

            visualizer.plot_transaction_timeline(
                results['balance_histories'],
                show=True
            )

    print("\n" + "="*60)
    print("  Summary")
    print("="*60)

    summary = results['summary']
    print(f"\nAddress: {summary['address']}")
    print(f"Total Transactions: {summary['total_transactions']}")
    print(f"Successful: {summary['successful_transactions']}")
    print(f"Failed: {summary['failed_transactions']}")

    if summary.get('first_transaction_time'):
        print(f"First Transaction: {summary['first_transaction_time']}")
    if summary.get('last_transaction_time'):
        print(f"Last Transaction: {summary['last_transaction_time']}")

    print("\nCurrent Balances:")
    for mint, balance in summary.get('current_balances', {}).items():
        token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
        print(f"  {token_name}: {balance.get('ui_amount', 0)}")

    print("\nToken Flows:")
    for mint, flows in summary.get('token_flows', {}).items():
        token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
        print(f"  {token_name}:")
        print(f"    Received: {flows['total_received']:.4f}")
        print(f"    Sent: {flows['total_sent']:.4f}")
        print(f"    Net Change: {flows['net_change']:.4f}")
        print(f"    Transactions: {flows['transaction_count']}")

    print(f"\nResults saved to: {output_path}")
    print("="*60 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
