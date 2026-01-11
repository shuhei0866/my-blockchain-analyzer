"""Solana Chain Client - Wrapper for existing solana_analyzer code"""
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from .base import (
    ChainClient, Chain, Transaction, TokenTransfer, TokenBalance
)


class SolanaClient(ChainClient):
    """Solana Chain Client using Helius API"""

    chain = Chain.SOLANA

    def __init__(self, api_key: str = None, rpc_url: str = None):
        """
        Initialize Solana client

        Args:
            api_key: Helius API key (optional if rpc_url provided)
            rpc_url: Full RPC URL (optional if api_key provided)
        """
        if rpc_url:
            self.rpc_url = rpc_url
        elif api_key:
            self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"
        else:
            raise ValueError("Either api_key or rpc_url must be provided")

        self.api_key = api_key
        self._analyzer = None

    async def __aenter__(self):
        from solana_analyzer.backend.cached_analyzer import CachedTransactionAnalyzer
        self._analyzer = CachedTransactionAnalyzer(
            rpc_urls=[self.rpc_url],
            cache_db="data/solana_cache.db"
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._analyzer:
            self._analyzer.close()

    async def get_token_transfers(
        self,
        address: str,
        limit: int = 100,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[TokenTransfer]:
        """Get token transfer history"""
        from solana_analyzer.backend.token_registry import TokenRegistry
        registry = TokenRegistry()

        # Fetch signatures and transactions
        signatures = await self._analyzer.fetch_signatures_incremental(address, limit=limit)
        transactions = await self._analyzer.fetch_transaction_details_cached(address, signatures)

        transfers = []

        for tx in transactions:
            block_time = tx.get('block_time', 0)
            signature = tx.get('signature', '')
            meta = tx.get('meta', {})

            if meta.get('err'):
                continue

            pre_balances = meta.get('pre_token_balances', [])
            post_balances = meta.get('post_token_balances', [])

            # Build balance change map
            changes = {}

            for pre in pre_balances:
                owner = pre.get('owner')
                if owner == address:
                    mint = pre.get('mint')
                    ui_amount = pre.get('ui_token_amount', {})
                    if mint not in changes:
                        changes[mint] = {'pre': 0, 'post': 0, 'decimals': ui_amount.get('decimals', 9)}
                    changes[mint]['pre'] = float(ui_amount.get('ui_amount') or 0)

            for post in post_balances:
                owner = post.get('owner')
                if owner == address:
                    mint = post.get('mint')
                    ui_amount = post.get('ui_token_amount', {})
                    if mint not in changes:
                        changes[mint] = {'pre': 0, 'post': 0, 'decimals': ui_amount.get('decimals', 9)}
                    changes[mint]['post'] = float(ui_amount.get('ui_amount') or 0)
                    changes[mint]['decimals'] = ui_amount.get('decimals', 9)

            # Create transfers for changes
            for mint, data in changes.items():
                change = data['post'] - data['pre']
                if abs(change) > 0.0000001:
                    symbol = registry.get_symbol(mint)
                    decimals = data.get('decimals', 9)
                    raw_amount = str(int(abs(change) * (10 ** decimals)))

                    transfers.append(TokenTransfer(
                        chain=Chain.SOLANA,
                        timestamp=block_time,
                        block_number=tx.get('slot', 0),
                        tx_hash=signature,
                        from_address=address if change < 0 else "",
                        to_address=address if change > 0 else "",
                        token_address=mint,
                        token_symbol=symbol,
                        token_name=None,
                        token_decimals=decimals,
                        amount_raw=raw_amount,
                        amount=abs(change),
                        direction='in' if change > 0 else 'out',
                        usd_value=None
                    ))

        # Sort by timestamp descending
        transfers.sort(key=lambda x: x.timestamp, reverse=True)

        return transfers

    async def get_transactions(
        self,
        address: str,
        limit: int = 100,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[Transaction]:
        """Get transaction history"""
        transfers = await self.get_token_transfers(address, limit)

        # Group transfers by tx_hash
        tx_map: Dict[str, List[TokenTransfer]] = {}
        for transfer in transfers:
            if transfer.tx_hash not in tx_map:
                tx_map[transfer.tx_hash] = []
            tx_map[transfer.tx_hash].append(transfer)

        transactions = []
        for tx_hash, tx_transfers in tx_map.items():
            first = tx_transfers[0]

            has_in = any(t.direction == "in" for t in tx_transfers)
            has_out = any(t.direction == "out" for t in tx_transfers)

            if has_in and has_out:
                tx_type = "swap"
            elif has_in:
                tx_type = "receive"
            else:
                tx_type = "send"

            transactions.append(Transaction(
                chain=Chain.SOLANA,
                timestamp=first.timestamp,
                block_number=first.block_number,
                tx_hash=tx_hash,
                from_address=first.from_address,
                to_address=first.to_address,
                value=0,
                fee=0,
                status="success",
                transfers=tx_transfers,
                tx_type=tx_type
            ))

        transactions.sort(key=lambda x: x.timestamp, reverse=True)
        return transactions

    async def get_token_balances(self, address: str) -> List[TokenBalance]:
        """Get current token balances"""
        from solana_analyzer.backend.token_registry import TokenRegistry
        registry = TokenRegistry()

        balances_data = await self._analyzer.get_current_balances(address)
        balances = []

        for mint, data in balances_data.items():
            if mint == 'SOL':
                continue  # Handle separately

            symbol = registry.get_symbol(mint)
            decimals = data.get('decimals', 9)
            balance = data.get('ui_amount', 0)

            if balance > 0:
                balances.append(TokenBalance(
                    chain=Chain.SOLANA,
                    token_address=mint,
                    token_symbol=symbol,
                    token_name=None,
                    token_decimals=decimals,
                    balance_raw=data.get('amount', '0'),
                    balance=balance,
                    usd_value=None
                ))

        return balances

    async def get_native_balance(self, address: str) -> float:
        """Get SOL balance"""
        balances = await self._analyzer.get_current_balances(address)
        sol_data = balances.get('SOL', {})
        return sol_data.get('ui_amount', 0)

    def get_explorer_url(self, tx_hash: str) -> str:
        """Get Solscan URL"""
        return f"https://solscan.io/tx/{tx_hash}"
