#!/usr/bin/env python3
"""Fetch and cache transaction details"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_analyzer.backend.cached_analyzer import CachedTransactionAnalyzer


async def main():
    """Main function to fetch transactions"""
    if len(sys.argv) < 2:
        print("Usage: python fetch_transactions.py <ADDRESS> [--limit LIMIT] [--force] [--rpc URL]")
        print("\nExample:")
        print("  python fetch_transactions.py DpkWS7Epdx7EcVJkavFAU9nRRJ3ixuw8z7U7QKA9sNRq --limit 100")
        print("\nWith Helius API:")
        print("  export HELIUS_API_KEY=your_api_key")
        print("  python fetch_transactions.py <ADDRESS> --limit 500")
        print("\nOr specify RPC directly:")
        print("  python fetch_transactions.py <ADDRESS> --rpc https://mainnet.helius-rpc.com/?api-key=YOUR_KEY")
        sys.exit(1)

    address = sys.argv[1]
    limit = 100
    force = False
    rpc_url = None

    # Parse arguments
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--force':
            force = True
            i += 1
        elif sys.argv[i] == '--rpc' and i + 1 < len(sys.argv):
            rpc_url = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    # Check for Helius API key in environment
    helius_api_key = os.environ.get('HELIUS_API_KEY')
    if helius_api_key and not rpc_url:
        rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}"
        print("Using Helius RPC (from HELIUS_API_KEY environment variable)")

    print(f"\n{'='*70}")
    print("  Fetching Transaction Details")
    print(f"{'='*70}\n")
    print(f"Address: {address}")
    print(f"Limit: {limit}")
    print(f"Force refresh: {force}")
    if rpc_url:
        # Hide API key in output
        display_url = rpc_url.split('?')[0] + "?api-key=***" if '?' in rpc_url else rpc_url
        print(f"RPC: {display_url}")
    print()

    # Initialize analyzer with custom RPC if provided
    rpc_urls = [rpc_url] if rpc_url else None
    analyzer = CachedTransactionAnalyzer(rpc_urls=rpc_urls, cache_db="data/solana_cache.db")

    # Step 1: Fetch signatures
    print(f"{'='*70}")
    print("Step 1: Fetching Transaction Signatures")
    print(f"{'='*70}\n")

    signatures = await analyzer.fetch_signatures_incremental(
        address,
        limit=limit,
        force_refresh=force
    )

    print(f"\n✓ Total signatures: {len(signatures)}\n")

    # Step 2: Fetch transaction details
    print(f"{'='*70}")
    print("Step 2: Fetching Transaction Details")
    print(f"{'='*70}\n")

    details = await analyzer.fetch_transaction_details_cached(
        address,
        signatures
    )

    print(f"\n✓ Total transaction details: {len(details)}\n")

    # Show summary
    success_count = sum(1 for d in details if d.get('meta', {}).get('err') is None)
    failed_count = len(details) - success_count

    print(f"{'='*70}")
    print("Summary")
    print(f"{'='*70}")
    print(f"Total transactions: {len(details)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"\n{'='*70}")
    print("✅ Transaction details cached successfully!")
    print(f"{'='*70}\n")

    # Close
    analyzer.close()


if __name__ == '__main__':
    asyncio.run(main())
