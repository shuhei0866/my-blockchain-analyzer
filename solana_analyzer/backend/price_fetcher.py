"""Price fetcher using CoinGecko API for USD conversion"""
import requests
from typing import Dict, Optional
from datetime import datetime
import time


# Solana token mint address to CoinGecko ID mapping
MINT_TO_COINGECKO = {
    # Native SOL
    'SOL': 'solana',
    # Stablecoins
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 'usd-coin',  # USDC
    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 'tether',  # USDT
    # Popular tokens
    'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263': 'bonk',  # BONK
    'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN': 'jupiter-exchange-solana',  # JUP
    '7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs': 'ethereum-wormhole',  # ETH (Wormhole)
    'So11111111111111111111111111111111111111112': 'wrapped-solana',  # wSOL
    'mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So': 'msol',  # mSOL
    'HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3': 'pyth-network',  # PYTH
    'hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux': 'helium',  # HNT
    'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL': 'jito-governance-token',  # JTO
    'WENWENvqqNya429ubCdR81ZmD69brwQaaBYY6p3LCpk': 'wen-4',  # WEN
    'rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof': 'render-token',  # RENDER
}


class PriceFetcher:
    """Fetch token prices from CoinGecko API"""

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self):
        self.price_cache: Dict[str, float] = {}
        self.last_fetch_time: Optional[float] = None
        self.cache_duration = 300  # 5 minutes

    def get_current_prices(self, force_refresh: bool = False) -> Dict[str, float]:
        """
        Get current USD prices for all mapped tokens

        Args:
            force_refresh: Force refresh even if cache is valid

        Returns:
            Dictionary mapping token mint/symbol to USD price
        """
        now = time.time()

        # Return cached prices if still valid
        if (not force_refresh and
            self.last_fetch_time and
            now - self.last_fetch_time < self.cache_duration and
            self.price_cache):
            return self.price_cache

        coingecko_ids = list(set(MINT_TO_COINGECKO.values()))
        ids_param = ','.join(coingecko_ids)

        try:
            response = requests.get(
                f"{self.BASE_URL}/simple/price",
                params={
                    'ids': ids_param,
                    'vs_currencies': 'usd'
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            # Build price cache with both mint addresses and symbols
            self.price_cache = {}
            for mint, coingecko_id in MINT_TO_COINGECKO.items():
                if coingecko_id in data and 'usd' in data[coingecko_id]:
                    self.price_cache[mint] = data[coingecko_id]['usd']

            self.last_fetch_time = now
            print(f"Fetched prices for {len(self.price_cache)} tokens")

        except Exception as e:
            print(f"Error fetching prices: {e}")
            # Return existing cache if available
            if not self.price_cache:
                # Set stablecoin defaults
                self.price_cache = {
                    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 1.0,  # USDC
                    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 1.0,  # USDT
                }

        return self.price_cache

    def get_price(self, mint_or_symbol: str) -> Optional[float]:
        """
        Get USD price for a specific token

        Args:
            mint_or_symbol: Token mint address or symbol (e.g., 'SOL')

        Returns:
            USD price or None if not available
        """
        prices = self.get_current_prices()
        return prices.get(mint_or_symbol)

    def convert_to_usd(self, amount: float, mint_or_symbol: str) -> Optional[float]:
        """
        Convert token amount to USD

        Args:
            amount: Token amount
            mint_or_symbol: Token mint address or symbol

        Returns:
            USD value or None if price not available
        """
        price = self.get_price(mint_or_symbol)
        if price is not None:
            return amount * price
        return None

    def get_historical_price(
        self,
        coingecko_id: str,
        date: datetime
    ) -> Optional[float]:
        """
        Get historical price for a token on a specific date

        Note: CoinGecko free API has limited historical data access

        Args:
            coingecko_id: CoinGecko token ID
            date: Target date

        Returns:
            USD price on that date or None
        """
        date_str = date.strftime('%d-%m-%Y')

        try:
            response = requests.get(
                f"{self.BASE_URL}/coins/{coingecko_id}/history",
                params={'date': date_str},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if 'market_data' in data and 'current_price' in data['market_data']:
                return data['market_data']['current_price'].get('usd')

        except Exception as e:
            print(f"Error fetching historical price for {coingecko_id} on {date_str}: {e}")

        return None


def get_token_symbol(mint: str, token_registry: dict = None) -> str:
    """
    Get token symbol from mint address

    Args:
        mint: Token mint address
        token_registry: Optional token registry dict

    Returns:
        Token symbol or shortened mint address
    """
    if mint == 'SOL':
        return 'SOL'

    # Check token registry if provided
    if token_registry and mint in token_registry:
        return token_registry[mint].get('symbol', mint[:8])

    # Return shortened address
    return f"{mint[:4]}...{mint[-4:]}"
