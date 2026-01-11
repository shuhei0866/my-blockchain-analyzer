#!/usr/bin/env python3
"""Analyze token flows in USD terms with profit/loss calculation"""
import asyncio
import sqlite3
import json
import aiohttp
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_analyzer.backend.token_registry import TokenRegistry


class USDFlowAnalyzer:
    """Analyze token flows in USD terms"""

    def __init__(self, cache_db: str = "data/solana_cache.db"):
        self.cache_db = cache_db
        self.registry = TokenRegistry()
        self.prices = {}  # mint -> price in USD

        # Known stablecoins (1:1 USD)
        self.stablecoins = {
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 1.0,  # USDC
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 1.0,  # USDT
        }

        # SOL mint address
        self.sol_mint = 'So11111111111111111111111111111111111111112'

    async def fetch_prices(self, mints: list) -> dict:
        """Fetch current prices from multiple sources"""
        print("Fetching current token prices...")

        prices = {}

        # Add stablecoins
        for mint, price in self.stablecoins.items():
            prices[mint] = price

        # Filter out stablecoins from API request
        mints_to_fetch = [m for m in mints if m not in self.stablecoins]

        if not mints_to_fetch:
            return prices

        async with aiohttp.ClientSession() as session:
            # 1. Try Jupiter Price API v2
            print("  Trying Jupiter Price API...")
            base_url = "https://api.jup.ag/price/v2"

            batch_size = 100
            for i in range(0, len(mints_to_fetch), batch_size):
                batch = mints_to_fetch[i:i + batch_size]
                ids = ",".join(batch)

                try:
                    async with session.get(f"{base_url}?ids={ids}", timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for mint, info in data.get('data', {}).items():
                                if info and 'price' in info and info['price']:
                                    prices[mint] = float(info['price'])
                except Exception as e:
                    print(f"    Warning: Jupiter error: {e}")

            print(f"    Jupiter: {len([m for m in mints_to_fetch if m in prices])} prices")

            # 2. Try DexScreener for remaining tokens
            remaining = [m for m in mints_to_fetch if m not in prices]
            if remaining:
                print("  Trying DexScreener API for remaining tokens...")
                dex_url = "https://api.dexscreener.com/latest/dex/tokens"

                for mint in remaining:
                    try:
                        async with session.get(f"{dex_url}/{mint}", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                pairs = data.get('pairs', [])
                                if pairs:
                                    # Get price from first pair (usually most liquid)
                                    price_usd = pairs[0].get('priceUsd')
                                    if price_usd:
                                        prices[mint] = float(price_usd)
                        await asyncio.sleep(0.2)  # Rate limit
                    except Exception as e:
                        pass  # Silently skip failures

                print(f"    DexScreener: {len([m for m in remaining if m in prices])} additional prices")

        print(f"  Total: {len(prices)} tokens with prices")
        return prices

    def load_transactions(self, address: str) -> list:
        """Load transactions from cache"""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT transaction_data FROM transactions
            WHERE address = ?
        """, (address,))

        rows = cursor.fetchall()
        conn.close()

        transactions = []
        for row in rows:
            try:
                tx = json.loads(row[0])
                transactions.append(tx)
            except:
                pass

        return transactions

    def parse_flows(self, transactions: list, address: str) -> list:
        """Parse token flows from transactions"""
        flows = []

        for tx in transactions:
            block_time = tx.get('block_time')
            if not block_time:
                continue

            meta = tx.get('meta', {})
            if meta.get('err'):
                continue  # Skip failed transactions

            pre_balances = meta.get('pre_token_balances', [])
            post_balances = meta.get('post_token_balances', [])

            # Build balance change map
            balance_changes = {}

            for pre in pre_balances:
                idx = pre.get('account_index')
                owner = pre.get('owner')
                if owner == address and idx is not None:
                    ui_amount = pre.get('ui_token_amount', {})
                    balance_changes[idx] = {
                        'mint': pre.get('mint'),
                        'pre': float(ui_amount.get('ui_amount') or 0),
                        'post': 0
                    }

            for post in post_balances:
                idx = post.get('account_index')
                owner = post.get('owner')
                if owner == address and idx is not None:
                    ui_amount = post.get('ui_token_amount', {})
                    if idx not in balance_changes:
                        balance_changes[idx] = {
                            'mint': post.get('mint'),
                            'pre': 0,
                            'post': 0
                        }
                    balance_changes[idx]['post'] = float(ui_amount.get('ui_amount') or 0)
                    balance_changes[idx]['mint'] = post.get('mint')

            # Calculate changes
            for idx, data in balance_changes.items():
                change = data['post'] - data['pre']
                if abs(change) > 0.0000001:
                    flows.append({
                        'timestamp': block_time,
                        'date': datetime.fromtimestamp(block_time),
                        'mint': data['mint'],
                        'amount': change,
                        'direction': 'in' if change > 0 else 'out'
                    })

        return flows

    def analyze_by_period(self, flows: list, prices: dict) -> dict:
        """Analyze flows by year and month"""

        # Organize by year-month
        by_year = defaultdict(lambda: {
            'inflow_usd': 0,
            'outflow_usd': 0,
            'by_month': defaultdict(lambda: {'inflow_usd': 0, 'outflow_usd': 0, 'tokens': defaultdict(lambda: {'in': 0, 'out': 0, 'in_usd': 0, 'out_usd': 0})}),
            'tokens': defaultdict(lambda: {'in': 0, 'out': 0, 'in_usd': 0, 'out_usd': 0})
        })

        unknown_tokens = set()

        for flow in flows:
            year = flow['date'].year
            month = flow['date'].strftime('%Y-%m')
            mint = flow['mint']
            amount = abs(flow['amount'])
            direction = flow['direction']

            # Get USD price
            price = prices.get(mint, 0)
            if price == 0:
                unknown_tokens.add(mint)

            usd_value = amount * price

            # Aggregate
            if direction == 'in':
                by_year[year]['inflow_usd'] += usd_value
                by_year[year]['by_month'][month]['inflow_usd'] += usd_value
                by_year[year]['by_month'][month]['tokens'][mint]['in'] += amount
                by_year[year]['by_month'][month]['tokens'][mint]['in_usd'] += usd_value
                by_year[year]['tokens'][mint]['in'] += amount
                by_year[year]['tokens'][mint]['in_usd'] += usd_value
            else:
                by_year[year]['outflow_usd'] += usd_value
                by_year[year]['by_month'][month]['outflow_usd'] += usd_value
                by_year[year]['by_month'][month]['tokens'][mint]['out'] += amount
                by_year[year]['by_month'][month]['tokens'][mint]['out_usd'] += usd_value
                by_year[year]['tokens'][mint]['out'] += amount
                by_year[year]['tokens'][mint]['out_usd'] += usd_value

        return {
            'by_year': dict(by_year),
            'unknown_tokens': unknown_tokens
        }

    def print_report(self, analysis: dict, prices: dict):
        """Print formatted report"""
        by_year = analysis['by_year']
        unknown_tokens = analysis['unknown_tokens']

        print(f"\n{'='*80}")
        print("  USD-BASED TOKEN FLOW ANALYSIS")
        print(f"{'='*80}\n")

        if unknown_tokens:
            print(f"Note: {len(unknown_tokens)} tokens without price data (showing as $0)")
            print()

        total_inflow = 0
        total_outflow = 0

        for year in sorted(by_year.keys()):
            data = by_year[year]
            net = data['inflow_usd'] - data['outflow_usd']
            total_inflow += data['inflow_usd']
            total_outflow += data['outflow_usd']

            print(f"{'='*80}")
            print(f"  {year} ANNUAL SUMMARY")
            print(f"{'='*80}")
            print(f"  Total Inflow:  ${data['inflow_usd']:>15,.2f}")
            print(f"  Total Outflow: ${data['outflow_usd']:>15,.2f}")
            print(f"  Net Flow:      ${net:>15,.2f} {'(PROFIT)' if net > 0 else '(LOSS)' if net < 0 else ''}")
            print()

            # Monthly breakdown
            print(f"  {'Month':<10} {'Inflow':>15} {'Outflow':>15} {'Net':>15}")
            print(f"  {'-'*55}")

            for month in sorted(data['by_month'].keys()):
                m_data = data['by_month'][month]
                m_net = m_data['inflow_usd'] - m_data['outflow_usd']
                print(f"  {month:<10} ${m_data['inflow_usd']:>13,.2f} ${m_data['outflow_usd']:>13,.2f} ${m_net:>13,.2f}")

            print()

            # Top tokens for the year
            print(f"  Top Tokens by USD Volume:")
            print(f"  {'Token':<15} {'In (USD)':>15} {'Out (USD)':>15} {'Net (USD)':>15}")
            print(f"  {'-'*60}")

            sorted_tokens = sorted(
                data['tokens'].items(),
                key=lambda x: x[1]['in_usd'] + x[1]['out_usd'],
                reverse=True
            )[:10]

            for mint, t_data in sorted_tokens:
                symbol = self.registry.get_symbol(mint)
                t_net = t_data['in_usd'] - t_data['out_usd']
                print(f"  {symbol:<15} ${t_data['in_usd']:>13,.2f} ${t_data['out_usd']:>13,.2f} ${t_net:>13,.2f}")

            print()

        # Grand total
        print(f"{'='*80}")
        print(f"  GRAND TOTAL (ALL YEARS)")
        print(f"{'='*80}")
        print(f"  Total Inflow:  ${total_inflow:>15,.2f}")
        print(f"  Total Outflow: ${total_outflow:>15,.2f}")
        net_total = total_inflow - total_outflow
        print(f"  Net Flow:      ${net_total:>15,.2f} {'(PROFIT)' if net_total > 0 else '(LOSS)' if net_total < 0 else ''}")
        print(f"{'='*80}\n")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_usd_flows.py <ADDRESS>")
        print("\nExample:")
        print("  python analyze_usd_flows.py DpkWS7Epdx7EcVJkavFAU9nRRJ3ixuw8z7U7QKA9sNRq")
        sys.exit(1)

    address = sys.argv[1]

    analyzer = USDFlowAnalyzer()

    # Load transactions
    print(f"\nLoading transactions for {address[:8]}...{address[-4:]}...")
    transactions = analyzer.load_transactions(address)
    print(f"  Loaded {len(transactions)} transactions")

    # Parse flows
    print("\nParsing token flows...")
    flows = analyzer.parse_flows(transactions, address)
    print(f"  Found {len(flows)} token transfers")

    # Get unique mints
    mints = list(set(f['mint'] for f in flows))
    print(f"  Involving {len(mints)} unique tokens")

    # Fetch prices
    prices = await analyzer.fetch_prices(mints)
    analyzer.prices = prices

    # Analyze
    print("\nAnalyzing flows...")
    analysis = analyzer.analyze_by_period(flows, prices)

    # Print report
    analyzer.print_report(analysis, prices)


if __name__ == '__main__':
    asyncio.run(main())
