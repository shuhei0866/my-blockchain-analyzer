#!/usr/bin/env python3
"""Save balance data to JSON"""
import asyncio
import sys
import json
from pathlib import Path
from solana_analyzer.backend.analyzer_api import SolanaAnalyzerAPI


async def save_balance(address: str, output_file: str = "data/balance.json"):
    """Save current balance to JSON"""
    print(f"\n{'='*60}")
    print(f"  Saving Balance Data")
    print(f"{'='*60}\n")
    print(f"Address: {address}\n")

    api = SolanaAnalyzerAPI()

    try:
        summary = await api.get_address_summary(address)

        print(f"✓ Transaction Count: {summary['total_transactions']}")
        print(f"✓ Token Count: {len(summary['current_balances'])}\n")

        # Save to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"✓ Saved to: {output_path}\n")

        # Print top balances
        balances_sorted = sorted(
            summary['current_balances'].items(),
            key=lambda x: float(x[1].get('ui_amount', 0) or 0),
            reverse=True
        )

        print("Top 15 Token Holdings:")
        print(f"{'-'*60}")
        for i, (mint, balance) in enumerate(balances_sorted[:15], 1):
            token_name = mint if mint == 'SOL' else f"{mint[:8]}...{mint[-4:]}"
            amount = balance.get('ui_amount', 0)
            if amount and amount > 0:
                print(f"{i:2d}. {token_name:20s} {amount:>20,.8f}")

        return summary

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python save_balance.py <SOLANA_ADDRESS> [output_file]")
        sys.exit(1)

    address = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "data/balance.json"

    asyncio.run(save_balance(address, output_file))
