#!/usr/bin/env python3
"""
Demo script to test with a known active Solana address
"""
import asyncio
from solana_analyzer.backend.analyzer_api import SolanaAnalyzerAPI
from solana_analyzer.visualization.visualizer import SolanaVisualizer


async def demo_analysis():
    """Demo analysis with a known active address"""
    print("\n" + "="*60)
    print("  Demo: Analyzing Active Solana Address")
    print("="*60 + "\n")

    # Using a known active address (Raydium program)
    # You can replace this with any active Solana address
    demo_addresses = [
        # Example: Solana Foundation wallet (often has activity)
        "GThUX1Atko4tqhN2NaiTazWSeFWMuiUvfFnyJyUghFMJ",
    ]

    api = SolanaAnalyzerAPI()

    for address in demo_addresses:
        print(f"\n{'='*60}")
        print(f"Analyzing: {address}")
        print(f"{'='*60}\n")

        try:
            # First, check if the address has any transactions
            summary = await api.get_address_summary(address)

            print(f"Total Transactions: {summary['total_transactions']}")
            print(f"Current Balances: {len(summary['current_balances'])} tokens\n")

            if summary['total_transactions'] > 0:
                print("This address has transaction history!")
                print("Running full analysis with visualization...\n")

                # Run full analysis
                results = await api.analyze_address(
                    address=address,
                    limit=50,  # Limiting to 50 for demo
                    save_to_file=f"output/demo_analysis.json"
                )

                # Create visualizations
                visualizer = SolanaVisualizer()
                visualizer.create_summary_report(results, output_dir="output/demo")

                print(f"\n{'='*60}")
                print("Demo Analysis Summary")
                print(f"{'='*60}")
                print(f"Successful Transactions: {results['summary']['successful_transactions']}")
                print(f"Failed Transactions: {results['summary']['failed_transactions']}")

                if results['summary'].get('token_flows'):
                    print("\nToken Activity:")
                    for mint, flows in list(results['summary']['token_flows'].items())[:5]:
                        token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
                        print(f"  {token_name}:")
                        print(f"    Transactions: {flows['transaction_count']}")
                        print(f"    Net Change: {flows['net_change']:.4f}")

                print(f"\nResults saved to: output/demo/")
                print(f"{'='*60}\n")

                return True
            else:
                print("This address has no transaction history.")
                print("Trying next address...\n")

        except Exception as e:
            print(f"Error analyzing {address}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print("\nNote: You can analyze any Solana address by running:")
    print("  python main.py <YOUR_ADDRESS>")

    return False


if __name__ == '__main__':
    asyncio.run(demo_analysis())
