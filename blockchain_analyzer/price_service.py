"""Token Price Service using CoinGecko API"""
import aiohttp
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass

from .chains.base import Chain


# CoinGecko platform IDs for each chain
COINGECKO_PLATFORMS = {
    Chain.ETHEREUM: "ethereum",
    Chain.POLYGON: "polygon-pos",
    Chain.ARBITRUM: "arbitrum-one",
    Chain.OPTIMISM: "optimistic-ethereum",
    Chain.BASE: "base",
    Chain.SOLANA: "solana",
}

# Native token CoinGecko IDs
NATIVE_TOKEN_IDS = {
    Chain.ETHEREUM: "ethereum",
    Chain.POLYGON: "matic-network",
    Chain.ARBITRUM: "ethereum",
    Chain.OPTIMISM: "ethereum",
    Chain.BASE: "ethereum",
    Chain.SOLANA: "solana",
}


@dataclass
class TokenPrice:
    """Token price data"""
    address: str
    symbol: Optional[str]
    usd_price: float
    usd_24h_change: Optional[float] = None


class PriceService:
    """Fetch token prices from CoinGecko"""

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, TokenPrice] = {}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_native_price(self, chain: Chain) -> float:
        """Get native token price (ETH, MATIC, SOL)"""
        token_id = NATIVE_TOKEN_IDS.get(chain)
        if not token_id:
            return 0

        try:
            url = f"{self.BASE_URL}/simple/price"
            params = {
                "ids": token_id,
                "vs_currencies": "usd"
            }

            async with self.session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get(token_id, {}).get("usd", 0)
        except Exception as e:
            print(f"Error fetching native price: {e}")

        return 0

    async def get_token_prices(
        self,
        chain: Chain,
        token_addresses: List[str]
    ) -> Dict[str, float]:
        """Get prices for multiple tokens by contract address"""
        platform = COINGECKO_PLATFORMS.get(chain)
        if not platform or not token_addresses:
            return {}

        prices = {}

        # CoinGecko limits to ~100 addresses per request
        batch_size = 50
        for i in range(0, len(token_addresses), batch_size):
            batch = token_addresses[i:i + batch_size]
            batch_prices = await self._fetch_batch_prices(platform, batch)
            prices.update(batch_prices)

            # Rate limit: CoinGecko free tier is 10-30 calls/min
            if i + batch_size < len(token_addresses):
                await asyncio.sleep(1)

        return prices

    async def _fetch_batch_prices(
        self,
        platform: str,
        addresses: List[str]
    ) -> Dict[str, float]:
        """Fetch prices for a batch of addresses"""
        try:
            url = f"{self.BASE_URL}/simple/token_price/{platform}"
            params = {
                "contract_addresses": ",".join(addresses),
                "vs_currencies": "usd"
            }

            async with self.session.get(url, params=params, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Normalize addresses to lowercase for matching
                    return {
                        addr.lower(): info.get("usd", 0)
                        for addr, info in data.items()
                    }
                elif resp.status == 429:
                    print("CoinGecko rate limit hit, waiting...")
                    await asyncio.sleep(60)
                    return {}
        except Exception as e:
            print(f"Error fetching token prices: {e}")

        return {}

    async def get_prices_with_balances(
        self,
        chain: Chain,
        balances: List[Dict],
        native_balance: float
    ) -> Dict[str, any]:
        """
        Get USD values for all balances

        Returns dict with:
        - native_usd: USD value of native balance
        - token_usd: Dict of token address -> USD value
        - total_usd: Total portfolio value
        """
        # Get native price
        native_price = await self.get_native_price(chain)
        native_usd = native_balance * native_price

        # Get token addresses
        token_addresses = [
            b.get("token_address", "").lower()
            for b in balances
            if b.get("token_address")
        ]

        # Get token prices
        token_prices = await self.get_token_prices(chain, token_addresses)

        # Calculate USD values
        token_usd = {}
        total_token_usd = 0

        for balance in balances:
            addr = balance.get("token_address", "").lower()
            amount = balance.get("balance", 0)
            price = token_prices.get(addr, 0)
            usd_value = amount * price

            token_usd[addr] = {
                "price": price,
                "usd_value": usd_value,
                "symbol": balance.get("token_symbol")
            }
            total_token_usd += usd_value

        return {
            "native_price": native_price,
            "native_usd": native_usd,
            "token_prices": token_prices,
            "token_usd": token_usd,
            "total_usd": native_usd + total_token_usd
        }
