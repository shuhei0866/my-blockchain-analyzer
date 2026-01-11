#!/usr/bin/env python3
"""
Example script showing different ways to use the Solana Analyzer
"""
import asyncio
from solana_analyzer.backend.analyzer_api import SolanaAnalyzerAPI
from solana_analyzer.visualization.visualizer import SolanaVisualizer


async def example_full_analysis():
    """Example: Full address analysis with visualization"""
    print("\n=== Example 1: Full Analysis ===\n")

    api = SolanaAnalyzerAPI()
    visualizer = SolanaVisualizer()

    address = "HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P"

    results = await api.analyze_address(
        address=address,
        limit=100,
        save_to_file=f"output/example_analysis.json"
    )

    visualizer.create_summary_report(results, output_dir="output/example")

    print("\nAnalysis complete!")
    print(f"Found {results['summary']['total_transactions']} transactions")
    print(f"Current balances: {len(results['summary']['current_balances'])} tokens")


async def example_quick_summary():
    """Example: Quick address summary without full details"""
    print("\n=== Example 2: Quick Summary ===\n")

    api = SolanaAnalyzerAPI()

    address = "HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P"

    summary = await api.get_address_summary(address)

    print(f"Address: {summary['address']}")
    print(f"Total Transactions: {summary['total_transactions']}")
    print("\nCurrent Balances:")
    for mint, balance in summary['current_balances'].items():
        token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
        print(f"  {token_name}: {balance['ui_amount']}")


async def example_token_flows():
    """Example: Analyze token flows only"""
    print("\n=== Example 3: Token Flow Analysis ===\n")

    api = SolanaAnalyzerAPI()
    visualizer = SolanaVisualizer()

    address = "HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P"

    flow_data = await api.get_token_flow_analysis(address, limit=100)

    print(f"Analyzed {flow_data['total_transactions']} transactions\n")

    for mint, flows in flow_data['token_flows'].items():
        token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
        print(f"{token_name}:")
        print(f"  Received: {flows['total_received']:.4f}")
        print(f"  Sent: {flows['total_sent']:.4f}")
        print(f"  Net: {flows['net_change']:.4f}")
        print()

    visualizer.plot_token_flows(
        flow_data['token_flows'],
        output_path="output/example_token_flows.png",
        show=False
    )


async def example_load_and_visualize():
    """Example: Load previously saved results and create new visualizations"""
    print("\n=== Example 4: Load and Re-visualize ===\n")

    api = SolanaAnalyzerAPI()
    visualizer = SolanaVisualizer()

    try:
        results = api.load_results("output/example_analysis.json")

        print("Loaded previous analysis results")
        print(f"Address: {results['summary']['address']}")
        print(f"Transactions: {results['summary']['total_transactions']}")

        visualizer.plot_token_flows(
            results['summary']['token_flows'],
            output_path="output/reloaded_flows.png",
            show=False
        )

        print("\nNew visualization created from saved data")

    except FileNotFoundError:
        print("No saved results found. Run example_full_analysis() first.")


async def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("  Solana Analyzer - Examples")
    print("="*60)

    # Example 1: Full analysis
    await example_full_analysis()

    # Example 2: Quick summary
    await example_quick_summary()

    # Example 3: Token flows
    await example_token_flows()

    # Example 4: Load and re-visualize
    await example_load_and_visualize()

    print("\n" + "="*60)
    print("  All examples completed!")
    print("  Check the 'output/' directory for results")
    print("="*60 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
