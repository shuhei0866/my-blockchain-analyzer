"""Multi-chain wallet analyzer"""
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

from .chains.base import Chain, ChainClient, Transaction, TokenTransfer, TokenBalance
from .chains.evm import EVMClient
from .chains.solana import SolanaClient
from .price_service import PriceService


class MultiChainAnalyzer:
    """Analyze wallets across multiple blockchains"""

    def __init__(
        self,
        solana_api_key: str = None,
        alchemy_api_key: str = None
    ):
        """
        Initialize multi-chain analyzer

        Args:
            solana_api_key: Helius API key for Solana
            alchemy_api_key: Alchemy API key for EVM chains
        """
        self.solana_api_key = solana_api_key
        self.alchemy_api_key = alchemy_api_key
        self.clients: Dict[Chain, ChainClient] = {}

    def get_client(self, chain: Chain) -> ChainClient:
        """Get or create client for a chain"""
        if chain in self.clients:
            return self.clients[chain]

        if chain == Chain.SOLANA:
            if not self.solana_api_key:
                raise ValueError("Solana API key required")
            client = SolanaClient(api_key=self.solana_api_key)
        else:
            if not self.alchemy_api_key:
                raise ValueError("Alchemy API key required for EVM chains")
            client = EVMClient(chain=chain, api_key=self.alchemy_api_key)

        self.clients[chain] = client
        return client

    async def analyze_address(
        self,
        address: str,
        chain: Chain,
        limit: int = 100,
        include_prices: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze a single address on a chain

        Returns:
            Dict with transactions, transfers, balances, summary
        """
        client = self.get_client(chain)

        async with client:
            # Get data
            transfers = await client.get_token_transfers(address, limit)
            transactions = await client.get_transactions(address, limit)
            balances = await client.get_token_balances(address)
            native_balance = await client.get_native_balance(address)

        # Analyze flows
        analysis = self._analyze_flows(transfers, address)

        # Convert balances to dicts
        balance_dicts = [b.__dict__ for b in balances]

        # Get price data
        price_data = None
        if include_prices and chain != Chain.SOLANA:  # Skip Solana for now
            try:
                async with PriceService() as price_service:
                    price_data = await price_service.get_prices_with_balances(
                        chain, balance_dicts, native_balance
                    )

                    # Add USD values to balances
                    for b in balance_dicts:
                        addr = b.get("token_address", "").lower()
                        token_info = price_data.get("token_usd", {}).get(addr, {})
                        b["usd_price"] = token_info.get("price", 0)
                        b["usd_value"] = token_info.get("usd_value", 0)
            except Exception as e:
                print(f"Error fetching prices: {e}")

        return {
            'chain': chain.value,
            'address': address,
            'native_balance': native_balance,
            'native_usd': price_data.get("native_usd", 0) if price_data else 0,
            'native_price': price_data.get("native_price", 0) if price_data else 0,
            'total_usd': price_data.get("total_usd", 0) if price_data else 0,
            'token_balances': balance_dicts,
            'transactions': [t.to_dict() for t in transactions],
            'transfers': [t.to_dict() for t in transfers],
            'analysis': analysis
        }

    def _analyze_flows(self, transfers: List[TokenTransfer], address: str) -> Dict:
        """Analyze token flows"""
        by_token = defaultdict(lambda: {'in': 0, 'out': 0, 'in_count': 0, 'out_count': 0})
        by_year = defaultdict(lambda: defaultdict(lambda: {'in': 0, 'out': 0}))

        for t in transfers:
            token_key = t.token_symbol or t.token_address[:12]
            year = datetime.fromtimestamp(t.timestamp).year

            if t.direction == 'in':
                by_token[token_key]['in'] += t.amount
                by_token[token_key]['in_count'] += 1
                by_year[year][token_key]['in'] += t.amount
            else:
                by_token[token_key]['out'] += t.amount
                by_token[token_key]['out_count'] += 1
                by_year[year][token_key]['out'] += t.amount

        return {
            'by_token': dict(by_token),
            'by_year': {y: dict(tokens) for y, tokens in by_year.items()},
            'total_transfers': len(transfers)
        }

    async def analyze_multi_chain(
        self,
        addresses: Dict[Chain, str],
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Analyze addresses across multiple chains

        Args:
            addresses: Dict mapping Chain -> address
            limit: Max transfers per chain
        """
        results = {}

        for chain, address in addresses.items():
            try:
                print(f"\nAnalyzing {chain.value}: {address[:8]}...{address[-4:]}")
                result = await self.analyze_address(address, chain, limit)
                results[chain.value] = result
                print(f"  Found {len(result['transfers'])} transfers")
            except Exception as e:
                print(f"  Error: {e}")
                results[chain.value] = {'error': str(e)}

        return results


async def main():
    """Example usage"""
    import os
    import sys

    # Get API keys from environment
    solana_key = os.environ.get('HELIUS_API_KEY')
    alchemy_key = os.environ.get('ALCHEMY_API_KEY')

    if len(sys.argv) < 3:
        print("Usage: python -m blockchain_analyzer.analyzer <chain> <address>")
        print("\nChains: solana, ethereum, polygon, arbitrum, optimism, base")
        print("\nExample:")
        print("  python -m blockchain_analyzer.analyzer solana DpkWS7Epdx7EcVJkavFAU9nRRJ3ixuw8z7U7QKA9sNRq")
        print("  python -m blockchain_analyzer.analyzer ethereum 0x...")
        print("\nEnvironment variables:")
        print("  HELIUS_API_KEY - for Solana")
        print("  ALCHEMY_API_KEY - for EVM chains")
        sys.exit(1)

    chain_name = sys.argv[1].lower()
    address = sys.argv[2]

    # Map chain name to enum
    chain_map = {
        'solana': Chain.SOLANA,
        'ethereum': Chain.ETHEREUM,
        'eth': Chain.ETHEREUM,
        'polygon': Chain.POLYGON,
        'matic': Chain.POLYGON,
        'arbitrum': Chain.ARBITRUM,
        'arb': Chain.ARBITRUM,
        'optimism': Chain.OPTIMISM,
        'op': Chain.OPTIMISM,
        'base': Chain.BASE,
    }

    if chain_name not in chain_map:
        print(f"Unknown chain: {chain_name}")
        sys.exit(1)

    chain = chain_map[chain_name]

    # Check API keys
    if chain == Chain.SOLANA and not solana_key:
        print("Error: HELIUS_API_KEY environment variable required")
        sys.exit(1)
    if chain != Chain.SOLANA and not alchemy_key:
        print("Error: ALCHEMY_API_KEY environment variable required")
        sys.exit(1)

    # Run analysis
    analyzer = MultiChainAnalyzer(
        solana_api_key=solana_key,
        alchemy_api_key=alchemy_key
    )

    result = await analyzer.analyze_address(address, chain, limit=100)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  {chain.value.upper()} WALLET ANALYSIS")
    print(f"{'='*60}")
    print(f"\nAddress: {address}")
    print(f"Native Balance: {result['native_balance']:.4f}")
    print(f"Token Balances: {len(result['token_balances'])}")
    print(f"Total Transfers: {result['analysis']['total_transfers']}")

    # Top tokens
    print(f"\nTop Tokens by Activity:")
    by_token = result['analysis']['by_token']
    sorted_tokens = sorted(
        by_token.items(),
        key=lambda x: x[1]['in'] + x[1]['out'],
        reverse=True
    )[:10]

    print(f"{'Token':<15} {'In':>15} {'Out':>15} {'Net':>15}")
    print("-" * 60)
    for token, data in sorted_tokens:
        net = data['in'] - data['out']
        print(f"{token:<15} {data['in']:>15,.2f} {data['out']:>15,.2f} {net:>15,.2f}")


if __name__ == '__main__':
    asyncio.run(main())
