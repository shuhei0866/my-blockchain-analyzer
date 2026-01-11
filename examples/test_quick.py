#!/usr/bin/env python3
"""Quick test to verify the API works"""
import asyncio
from solana_analyzer.backend.analyzer_api import SolanaAnalyzerAPI


async def quick_test():
    """Quick test with minimal transaction fetching"""
    print("\n=== Quick API Test ===\n")

    api = SolanaAnalyzerAPI()

    address = "HiqfiyxQTRSZ4VBs6A1XPz2GKhu3gd1Py7xfWMtcD1P"

    print("Testing quick summary...")
    try:
        summary = await api.get_address_summary(address)

        print(f"\n✓ Test passed!")
        print(f"  Address: {summary['address']}")
        print(f"  Total Transactions: {summary['total_transactions']}")
        print(f"  Current Balances: {len(summary['current_balances'])} tokens")

        print("\n  Token balances:")
        for mint, balance in summary['current_balances'].items():
            token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
            print(f"    {token_name}: {balance['ui_amount']}")

        print("\n=== Test Complete ===\n")
        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(quick_test())
    exit(0 if success else 1)
