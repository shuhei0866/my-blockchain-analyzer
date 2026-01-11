"""Multi-RPC Client with load balancing and failover"""
import asyncio
from typing import List, Dict, Any, Optional
from itertools import cycle
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from solders.signature import Signature


# 公開RPCエンドポイントのリスト
DEFAULT_PUBLIC_RPCS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-api.projectserum.com",
    "https://rpc.ankr.com/solana",
    "https://solana-mainnet.rpc.extrnode.com",
    "https://solana.public-rpc.com",
]


class MultiRPCClient:
    """
    Multiple RPC endpoints client with load balancing
    Uses round-robin to distribute requests across endpoints
    """

    def __init__(self, rpc_urls: Optional[List[str]] = None):
        """
        Initialize Multi-RPC Client

        Args:
            rpc_urls: List of RPC endpoint URLs. If None, uses default public RPCs
        """
        self.rpc_urls = rpc_urls or DEFAULT_PUBLIC_RPCS.copy()
        self.url_cycle = cycle(self.rpc_urls)
        self.clients: Dict[str, AsyncClient] = {}
        self.stats = {url: {"requests": 0, "failures": 0} for url in self.rpc_urls}
        print(f"Initialized Multi-RPC client with {len(self.rpc_urls)} endpoints")

    async def __aenter__(self):
        """Async context manager entry"""
        for url in self.rpc_urls:
            self.clients[url] = AsyncClient(url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        for client in self.clients.values():
            await client.close()

    def get_next_client(self) -> tuple[str, AsyncClient]:
        """Get next RPC client in round-robin fashion"""
        url = next(self.url_cycle)
        return url, self.clients[url]

    async def _call_with_retry(
        self,
        operation: str,
        *args,
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """
        Call RPC method with automatic failover to next endpoint

        Args:
            operation: Method name to call
            max_retries: Maximum retry attempts across all endpoints
            *args, **kwargs: Arguments to pass to the method

        Returns:
            Result from the RPC call
        """
        attempts = 0
        last_error = None

        while attempts < max_retries:
            url, client = self.get_next_client()
            self.stats[url]["requests"] += 1

            try:
                method = getattr(client, operation)
                result = await method(*args, **kwargs)
                return result
            except Exception as e:
                self.stats[url]["failures"] += 1
                last_error = e
                attempts += 1

                if attempts < max_retries:
                    await asyncio.sleep(0.3 * attempts)  # Exponential backoff
                    continue

        raise Exception(f"All RPC endpoints failed after {max_retries} attempts: {last_error}")

    async def get_signatures_for_address(
        self,
        address: Pubkey,
        limit: int = 1000,
        before: Optional[Signature] = None,
        commitment=Confirmed
    ):
        """Get transaction signatures for an address"""
        return await self._call_with_retry(
            "get_signatures_for_address",
            address,
            limit=limit,
            before=before,
            commitment=commitment
        )

    async def get_transaction(
        self,
        signature: Signature,
        encoding: str = "jsonParsed",
        max_supported_transaction_version: int = 0,
        commitment=Confirmed
    ):
        """Get transaction details"""
        return await self._call_with_retry(
            "get_transaction",
            signature,
            encoding=encoding,
            max_supported_transaction_version=max_supported_transaction_version,
            commitment=commitment
        )

    async def get_token_accounts_by_owner_json_parsed(
        self,
        owner: Pubkey,
        opts,
        commitment=Confirmed
    ):
        """Get token accounts by owner"""
        return await self._call_with_retry(
            "get_token_accounts_by_owner_json_parsed",
            owner,
            opts,
            commitment=commitment
        )

    async def get_balance(
        self,
        pubkey: Pubkey,
        commitment=Confirmed
    ):
        """Get SOL balance - direct implementation"""
        attempts = 0
        last_error = None
        max_retries = 3

        while attempts < max_retries:
            url, client = self.get_next_client()
            self.stats[url]["requests"] += 1

            try:
                result = await client.get_balance(pubkey, commitment)
                return result
            except Exception as e:
                self.stats[url]["failures"] += 1
                last_error = e
                attempts += 1

                if attempts < max_retries:
                    await asyncio.sleep(0.3 * attempts)
                    continue

        raise Exception(f"All RPC endpoints failed: {last_error}")

    def print_stats(self):
        """Print statistics for each RPC endpoint"""
        print("\n=== RPC Endpoint Statistics ===")
        for url, stats in self.stats.items():
            total = stats["requests"]
            failures = stats["failures"]
            success_rate = ((total - failures) / total * 100) if total > 0 else 0
            print(f"{url}")
            print(f"  Requests: {total}, Failures: {failures}, Success Rate: {success_rate:.1f}%")
