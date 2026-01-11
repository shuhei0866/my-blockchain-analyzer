#!/usr/bin/env python3
"""Fetch token information from DexScreener API"""
import json
import requests
import time
from pathlib import Path


def fetch_token_info_from_dex(mint_address: str) -> dict:
    """
    Fetch token info from DexScreener

    Args:
        mint_address: Token mint address

    Returns:
        Dict with symbol, name, etc.
    """
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        if not data or 'pairs' not in data or len(data['pairs']) == 0:
            return None

        # Get base token from first pair
        pair = data['pairs'][0]
        base_token = pair.get('baseToken', {})

        return {
            'address': mint_address,
            'symbol': base_token.get('symbol', f"{mint_address[:8]}..."),
            'name': base_token.get('name', 'Unknown'),
            'source': 'dexscreener'
        }

    except Exception as e:
        print(f"  ✗ Error fetching {mint_address[:16]}...: {e}")
        return None


def fetch_all_tokens(balance_file: str = "data/balance.json",
                    output_file: str = "data/custom_token_list.json"):
    """Fetch token info for all tokens in balance file"""
    print(f"\n{'='*70}")
    print("  Fetching Token Info from DexScreener")
    print(f"{'='*70}\n")

    # Load balance data
    with open(balance_file, 'r') as f:
        data = json.load(f)

    balances = data['current_balances']

    # Get non-zero tokens
    mints = [mint for mint, balance in balances.items()
             if float(balance.get('ui_amount', 0) or 0) > 0 and mint != 'SOL']

    print(f"Fetching info for {len(mints)} tokens...\n")

    token_list = []
    success_count = 0
    fail_count = 0

    for i, mint in enumerate(mints, 1):
        print(f"[{i}/{len(mints)}] {mint[:16]}...", end=" ")

        info = fetch_token_info_from_dex(mint)

        if info:
            token_list.append(info)
            print(f"✓ {info['symbol']} - {info['name']}")
            success_count += 1
        else:
            # Add placeholder
            token_list.append({
                'address': mint,
                'symbol': f"{mint[:8]}...",
                'name': mint,
                'source': 'fallback'
            })
            print(f"✗ Not found")
            fail_count += 1

        # Rate limiting
        time.sleep(0.5)

    # Add SOL manually
    token_list.append({
        'address': 'So11111111111111111111111111111111111111112',
        'symbol': 'SOL',
        'name': 'Solana',
        'source': 'manual'
    })

    # Save to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(token_list, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Summary:")
    print(f"  ✓ Successfully fetched: {success_count}")
    print(f"  ✗ Not found: {fail_count}")
    print(f"  💾 Saved to: {output_file}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    import sys

    balance_file = sys.argv[1] if len(sys.argv) > 1 else "data/balance.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "data/custom_token_list.json"

    fetch_all_tokens(balance_file, output_file)
