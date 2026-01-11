#!/usr/bin/env python3
"""
Analyze profit/loss with historical prices
Uses Birdeye API for historical price data
"""
import asyncio
import sqlite3
import json
import aiohttp
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_analyzer.backend.token_registry import TokenRegistry


class HistoricalPnLAnalyzer:
    """Analyze P&L with historical prices"""

    def __init__(self, cache_db: str = "data/solana_cache.db", birdeye_api_key: str = None):
        self.cache_db = cache_db
        self.registry = TokenRegistry()
        self.birdeye_api_key = birdeye_api_key
        self.price_cache = {}  # (mint, date) -> price

        # Known stablecoins
        self.stablecoins = {
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 'USDC',
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 'USDT',
        }

        # SOL mint
        self.sol_mint = 'So11111111111111111111111111111111111111112'

    async def get_historical_price(self, session: aiohttp.ClientSession, mint: str, timestamp: int) -> float:
        """Get historical price for a token at a specific timestamp"""

        # Stablecoins are always $1
        if mint in self.stablecoins:
            return 1.0

        # Check cache
        date_key = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
        cache_key = (mint, date_key)
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        price = 0.0

        # Try Birdeye if we have API key
        if self.birdeye_api_key:
            try:
                headers = {'X-API-KEY': self.birdeye_api_key}
                # Birdeye historical price endpoint
                url = f"https://public-api.birdeye.so/defi/history_price"
                params = {
                    'address': mint,
                    'address_type': 'token',
                    'type': '1D',
                    'time_from': timestamp - 86400,  # 1 day before
                    'time_to': timestamp + 86400     # 1 day after
                }

                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get('data', {}).get('items', [])
                        if items:
                            # Find closest price to our timestamp
                            closest = min(items, key=lambda x: abs(x['unixTime'] - timestamp))
                            price = float(closest.get('value', 0))
            except Exception as e:
                pass

        # Fallback to DexScreener current price if no historical
        if price == 0:
            try:
                url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get('pairs', [])
                        if pairs:
                            price = float(pairs[0].get('priceUsd', 0) or 0)
            except:
                pass

        self.price_cache[cache_key] = price
        return price

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

    def parse_all_flows(self, transactions: list, address: str) -> list:
        """Parse all token flows with full details"""
        flows = []

        for tx in transactions:
            block_time = tx.get('block_time')
            signature = tx.get('signature', '')
            if not block_time:
                continue

            meta = tx.get('meta', {})
            if meta.get('err'):
                continue

            pre_balances = meta.get('pre_token_balances', [])
            post_balances = meta.get('post_token_balances', [])

            # Build balance change map for target address
            changes = {}

            for pre in pre_balances:
                owner = pre.get('owner')
                if owner == address:
                    mint = pre.get('mint')
                    ui_amount = pre.get('ui_token_amount', {})
                    amount = float(ui_amount.get('ui_amount') or 0)
                    if mint not in changes:
                        changes[mint] = {'pre': 0, 'post': 0}
                    changes[mint]['pre'] = amount

            for post in post_balances:
                owner = post.get('owner')
                if owner == address:
                    mint = post.get('mint')
                    ui_amount = post.get('ui_token_amount', {})
                    amount = float(ui_amount.get('ui_amount') or 0)
                    if mint not in changes:
                        changes[mint] = {'pre': 0, 'post': 0}
                    changes[mint]['post'] = amount

            # Calculate changes and categorize
            tx_inflows = []
            tx_outflows = []

            for mint, data in changes.items():
                change = data['post'] - data['pre']
                if abs(change) > 0.0000001:
                    flow_data = {
                        'mint': mint,
                        'amount': abs(change),
                        'direction': 'in' if change > 0 else 'out'
                    }
                    if change > 0:
                        tx_inflows.append(flow_data)
                    else:
                        tx_outflows.append(flow_data)

            # Categorize transaction type
            tx_type = 'unknown'
            if tx_inflows and not tx_outflows:
                tx_type = 'airdrop_or_receive'
            elif tx_outflows and not tx_inflows:
                tx_type = 'send'
            elif tx_inflows and tx_outflows:
                tx_type = 'swap'

            if tx_inflows or tx_outflows:
                flows.append({
                    'timestamp': block_time,
                    'date': datetime.fromtimestamp(block_time),
                    'signature': signature,
                    'type': tx_type,
                    'inflows': tx_inflows,
                    'outflows': tx_outflows
                })

        return flows

    async def analyze_with_prices(self, flows: list) -> dict:
        """Analyze flows with historical prices"""
        print("\nFetching historical prices...")

        results = {
            'by_year': defaultdict(lambda: {
                'inflow_usd': 0,
                'outflow_usd': 0,
                'realized_pnl': 0,
                'airdrops_usd': 0,
                'transactions': []
            }),
            'airdrops': [],
            'swaps': [],
            'total_realized_pnl': 0
        }

        async with aiohttp.ClientSession() as session:
            for i, flow in enumerate(flows):
                if i % 20 == 0:
                    print(f"  Processing {i+1}/{len(flows)} transactions...")

                year = flow['date'].year
                timestamp = flow['timestamp']

                # Get prices for all tokens in this transaction
                tx_inflow_usd = 0
                tx_outflow_usd = 0

                for inflow in flow['inflows']:
                    price = await self.get_historical_price(session, inflow['mint'], timestamp)
                    usd_value = inflow['amount'] * price
                    inflow['price'] = price
                    inflow['usd_value'] = usd_value
                    tx_inflow_usd += usd_value

                for outflow in flow['outflows']:
                    price = await self.get_historical_price(session, outflow['mint'], timestamp)
                    usd_value = outflow['amount'] * price
                    outflow['price'] = price
                    outflow['usd_value'] = usd_value
                    tx_outflow_usd += usd_value

                # Record
                results['by_year'][year]['inflow_usd'] += tx_inflow_usd
                results['by_year'][year]['outflow_usd'] += tx_outflow_usd

                # Track airdrops
                if flow['type'] == 'airdrop_or_receive':
                    results['airdrops'].append({
                        'date': flow['date'],
                        'tokens': flow['inflows'],
                        'total_usd': tx_inflow_usd
                    })
                    results['by_year'][year]['airdrops_usd'] += tx_inflow_usd

                # Track swaps for P&L
                if flow['type'] == 'swap':
                    # Simple P&L: inflow value - outflow value
                    # (This is simplified - proper P&L would track cost basis)
                    swap_pnl = tx_inflow_usd - tx_outflow_usd
                    results['swaps'].append({
                        'date': flow['date'],
                        'inflows': flow['inflows'],
                        'outflows': flow['outflows'],
                        'inflow_usd': tx_inflow_usd,
                        'outflow_usd': tx_outflow_usd,
                        'pnl': swap_pnl
                    })
                    results['by_year'][year]['realized_pnl'] += swap_pnl

        # Calculate totals
        for year_data in results['by_year'].values():
            results['total_realized_pnl'] += year_data['realized_pnl']

        return results

    def print_report(self, results: dict):
        """Print comprehensive P&L report"""
        print("\n" + "=" * 90)
        print("  PROFIT & LOSS REPORT (HISTORICAL PRICES)")
        print("=" * 90)

        # Airdrops summary
        print("\n" + "-" * 90)
        print("  AIRDROPS RECEIVED")
        print("-" * 90)

        total_airdrop_value = 0
        for ad in sorted(results['airdrops'], key=lambda x: x['date']):
            if ad['total_usd'] > 0.01:  # Only show significant airdrops
                print(f"\n  {ad['date'].strftime('%Y-%m-%d')}:")
                for token in ad['tokens']:
                    symbol = self.registry.get_symbol(token['mint'])
                    print(f"    + {token['amount']:>15,.2f} {symbol:<15} @ ${token['price']:.6f} = ${token['usd_value']:>10,.2f}")
                total_airdrop_value += ad['total_usd']

        print(f"\n  Total Airdrop Value: ${total_airdrop_value:,.2f}")

        # Yearly summary
        print("\n" + "-" * 90)
        print("  YEARLY SUMMARY")
        print("-" * 90)

        for year in sorted(results['by_year'].keys()):
            data = results['by_year'][year]
            net = data['inflow_usd'] - data['outflow_usd']

            print(f"\n  {year}:")
            print(f"    Inflows:      ${data['inflow_usd']:>15,.2f}")
            print(f"    Outflows:     ${data['outflow_usd']:>15,.2f}")
            print(f"    Net Flow:     ${net:>15,.2f}")
            print(f"    Airdrops:     ${data['airdrops_usd']:>15,.2f}")
            print(f"    Realized P&L: ${data['realized_pnl']:>15,.2f}")

        # Grand total
        print("\n" + "=" * 90)
        print("  GRAND TOTAL")
        print("=" * 90)

        total_inflow = sum(d['inflow_usd'] for d in results['by_year'].values())
        total_outflow = sum(d['outflow_usd'] for d in results['by_year'].values())
        total_airdrops = sum(d['airdrops_usd'] for d in results['by_year'].values())

        print(f"\n  Total Inflows:       ${total_inflow:>15,.2f}")
        print(f"  Total Outflows:      ${total_outflow:>15,.2f}")
        print(f"  Net Flow:            ${total_inflow - total_outflow:>15,.2f}")
        print(f"  Total Airdrops:      ${total_airdrops:>15,.2f}")
        print(f"  Total Realized P&L:  ${results['total_realized_pnl']:>15,.2f}")
        print("=" * 90 + "\n")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_pnl_historical.py <ADDRESS> [BIRDEYE_API_KEY]")
        print("\nExample:")
        print("  python analyze_pnl_historical.py DpkWS7Epdx7EcVJkavFAU9nRRJ3ixuw8z7U7QKA9sNRq")
        print("\nWith Birdeye API key for historical prices:")
        print("  python analyze_pnl_historical.py <ADDRESS> YOUR_BIRDEYE_API_KEY")
        sys.exit(1)

    address = sys.argv[1]
    birdeye_key = sys.argv[2] if len(sys.argv) > 2 else None

    if birdeye_key:
        print("Using Birdeye API for historical prices")
    else:
        print("No Birdeye API key - using current prices as approximation")

    analyzer = HistoricalPnLAnalyzer(birdeye_api_key=birdeye_key)

    # Load transactions
    print(f"\nLoading transactions for {address[:8]}...{address[-4:]}...")
    transactions = analyzer.load_transactions(address)
    print(f"  Loaded {len(transactions)} transactions")

    # Parse flows
    print("\nParsing token flows...")
    flows = analyzer.parse_all_flows(transactions, address)
    print(f"  Found {len(flows)} transactions with token movements")

    # Analyze with prices
    results = await analyzer.analyze_with_prices(flows)

    # Print report
    analyzer.print_report(results)


if __name__ == '__main__':
    asyncio.run(main())
