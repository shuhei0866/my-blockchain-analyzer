#!/usr/bin/env python3
"""Quick balance check without fetching transaction details"""
import asyncio
import sys
from solana_analyzer.backend.analyzer_api import SolanaAnalyzerAPI


async def quick_balance_check(address: str):
    """Quick balance and transaction count check"""
    print(f"\n{'='*60}")
    print(f"  Quick Balance Check")
    print(f"{'='*60}\n")
    print(f"Address: {address}\n")

    api = SolanaAnalyzerAPI()

    try:
        summary = await api.get_address_summary(address)

        print(f"✓ Analysis Complete\n")
        print(f"{'='*60}")
        print(f"Transaction Count: {summary['total_transactions']}")
        print(f"Token Count: {len(summary['current_balances'])}")
        print(f"{'='*60}\n")

        print("Current Balances:")
        print(f"{'-'*60}")

        # Sort balances by ui_amount (descending)
        balances = sorted(
            summary['current_balances'].items(),
            key=lambda x: float(x[1].get('ui_amount', 0) or 0),
            reverse=True
        )

        # Show top 20 tokens
        for i, (mint, balance) in enumerate(balances[:20], 1):
            token_name = mint if mint == 'SOL' else f"{mint[:8]}...{mint[-4:]}"
            amount = balance.get('ui_amount', 0)

            if amount and amount > 0:
                print(f"{i:2d}. {token_name:20s}  {amount:>20,.8f}")

        if len(balances) > 20:
            print(f"\n... and {len(balances) - 20} more tokens")

        print(f"\n{'='*60}\n")

        return summary

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python quick_balance.py <SOLANA_ADDRESS>")
        sys.exit(1)

    address = sys.argv[1]
    asyncio.run(quick_balance_check(address))
