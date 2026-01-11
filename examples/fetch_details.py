#!/usr/bin/env python3
"""Fetch transaction details for cached signatures"""
import asyncio
import sys
from solana_analyzer.backend.cached_analyzer import CachedTransactionAnalyzer


async def fetch_transaction_details(address: str, limit: int = 50):
    """Fetch and cache transaction details"""
    print(f"\n{'='*70}")
    print("  Fetching Transaction Details")
    print(f"{'='*70}\n")

    analyzer = CachedTransactionAnalyzer()

    # Get cache stats
    stats = analyzer.get_cache_stats(address)
    print(f"Current Cache:")
    print(f"  Signatures: {stats['cached_signatures']}")
    print(f"  Transactions: {stats['cached_transactions']}")

    if stats['cached_signatures'] == 0:
        print("\n❌ No signatures in cache. Run analyze.py first.")
        return

    # Get cached signatures
    signatures = analyzer.cache.get_cached_signatures(address, limit=limit)
    print(f"\n📝 Found {len(signatures)} signatures")

    # Check which need details
    need_details = []
    for sig in signatures:
        if not analyzer.cache.get_cached_transaction(sig['signature']):
            need_details.append(sig)

    print(f"📦 Already have details: {len(signatures) - len(need_details)}")
    print(f"🔄 Need to fetch: {len(need_details)}")

    if not need_details:
        print("\n✅ All transaction details already cached!")
        analyzer.close()
        return

    # Fetch missing details
    print(f"\n🌐 Fetching {len(need_details)} transaction details...")
    print("  (This may take a while with public RPCs)\n")

    transactions = await analyzer.fetch_transaction_details_cached(
        address,
        need_details,
        batch_size=2,  # Slow to avoid rate limits
        max_concurrent=1  # Sequential to avoid rate limits
    )

    # Final stats
    final_stats = analyzer.get_cache_stats(address)
    print(f"\n✅ Complete!")
    print(f"Final Cache:")
    print(f"  Signatures: {final_stats['cached_signatures']}")
    print(f"  Transactions: {final_stats['cached_transactions']}")
    print(f"  Coverage: {final_stats['cached_transactions']}/{final_stats['cached_signatures']} "
          f"({100*final_stats['cached_transactions']/final_stats['cached_signatures']:.1f}%)")

    analyzer.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python fetch_details.py <SOLANA_ADDRESS> [limit]")
        sys.exit(1)

    address = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    asyncio.run(fetch_transaction_details(address, limit))
