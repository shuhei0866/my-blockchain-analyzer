"""EVM Chain Client using Alchemy API"""
import aiohttp
import asyncio
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import (
    ChainClient, Chain, Transaction, TokenTransfer, TokenBalance
)


def is_valid_evm_address(address: str) -> bool:
    """Check if address is a valid EVM address (0x + 40 hex chars)"""
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))


# Alchemy RPC endpoints by chain
ALCHEMY_ENDPOINTS = {
    Chain.ETHEREUM: "https://eth-mainnet.g.alchemy.com/v2",
    Chain.POLYGON: "https://polygon-mainnet.g.alchemy.com/v2",
    Chain.ARBITRUM: "https://arb-mainnet.g.alchemy.com/v2",
    Chain.OPTIMISM: "https://opt-mainnet.g.alchemy.com/v2",
    Chain.BASE: "https://base-mainnet.g.alchemy.com/v2",
}

# Block explorers
EXPLORERS = {
    Chain.ETHEREUM: "https://etherscan.io/tx",
    Chain.POLYGON: "https://polygonscan.com/tx",
    Chain.ARBITRUM: "https://arbiscan.io/tx",
    Chain.OPTIMISM: "https://optimistic.etherscan.io/tx",
    Chain.BASE: "https://basescan.org/tx",
}

# Native token symbols
NATIVE_TOKENS = {
    Chain.ETHEREUM: "ETH",
    Chain.POLYGON: "MATIC",
    Chain.ARBITRUM: "ETH",
    Chain.OPTIMISM: "ETH",
    Chain.BASE: "ETH",
}


class EVMClient(ChainClient):
    """EVM Chain Client using Alchemy API"""

    def __init__(self, chain: Chain, api_key: str):
        """
        Initialize EVM client

        Args:
            chain: Target EVM chain
            api_key: Alchemy API key
        """
        if chain not in ALCHEMY_ENDPOINTS:
            raise ValueError(f"Unsupported chain: {chain}")

        self.chain = chain
        self.api_key = api_key
        self.base_url = f"{ALCHEMY_ENDPOINTS[chain]}/{api_key}"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _rpc_call(self, method: str, params: List[Any]) -> Any:
        """Make JSON-RPC call to Alchemy"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }

        try:
            async with self.session.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    raise Exception(f"RPC Error ({method}): {data['error']}")
                return data.get("result")
        except asyncio.TimeoutError:
            raise Exception(f"Timeout calling {method}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error calling {method}: {e}")

    async def get_token_transfers(
        self,
        address: str,
        limit: int = 100,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[TokenTransfer]:
        """
        Get token transfer history using Alchemy's alchemy_getAssetTransfers

        Args:
            address: Wallet address
            limit: Maximum transfers to return
            from_block: Start block (optional)
            to_block: End block (optional)
        """
        transfers = []

        # Get incoming transfers
        incoming = await self._get_asset_transfers(
            address=address,
            direction="to",
            from_block=from_block,
            to_block=to_block,
            max_count=limit
        )

        for tx in incoming:
            transfer = self._parse_transfer(tx, address, "in")
            if transfer:
                transfers.append(transfer)

        # Get outgoing transfers
        outgoing = await self._get_asset_transfers(
            address=address,
            direction="from",
            from_block=from_block,
            to_block=to_block,
            max_count=limit
        )

        for tx in outgoing:
            transfer = self._parse_transfer(tx, address, "out")
            if transfer:
                transfers.append(transfer)

        # Sort by timestamp descending
        transfers.sort(key=lambda x: x.timestamp, reverse=True)

        return transfers[:limit]

    async def _get_asset_transfers(
        self,
        address: str,
        direction: str,  # "to" or "from"
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        max_count: int = 100
    ) -> List[Dict]:
        """Call alchemy_getAssetTransfers"""
        # Polygon doesn't support "external" category
        if self.chain == Chain.POLYGON:
            categories = ["erc20", "erc721", "erc1155"]
        else:
            categories = ["erc20", "erc721", "erc1155", "external"]

        params = {
            "category": categories,
            "withMetadata": True,
            "maxCount": hex(max_count),
        }

        if direction == "to":
            params["toAddress"] = address
        else:
            params["fromAddress"] = address

        if from_block:
            params["fromBlock"] = hex(from_block)
        else:
            params["fromBlock"] = "0x0"

        if to_block:
            params["toBlock"] = hex(to_block)
        else:
            params["toBlock"] = "latest"

        result = await self._rpc_call("alchemy_getAssetTransfers", [params])
        return result.get("transfers", [])

    def _parse_transfer(
        self,
        tx: Dict,
        address: str,
        direction: str
    ) -> Optional[TokenTransfer]:
        """Parse Alchemy transfer to normalized TokenTransfer"""
        try:
            # Get metadata
            metadata = tx.get("metadata", {})
            block_timestamp = metadata.get("blockTimestamp", "")

            # Parse timestamp
            if block_timestamp:
                dt = datetime.fromisoformat(block_timestamp.replace("Z", "+00:00"))
                timestamp = int(dt.timestamp())
            else:
                timestamp = 0

            # Get token info
            raw_contract = tx.get("rawContract", {})
            token_address = raw_contract.get("address") or tx.get("asset", "")
            decimals = raw_contract.get("decimals")

            if decimals:
                decimals = int(decimals, 16) if isinstance(decimals, str) else decimals
            else:
                decimals = 18  # Default for ERC20

            # Parse amount
            value = tx.get("value")
            if value is None:
                value = 0

            # Raw amount from hex if available
            raw_value = raw_contract.get("value", "0")
            if raw_value and raw_value.startswith("0x"):
                raw_amount = str(int(raw_value, 16))
            else:
                raw_amount = str(int(value * (10 ** decimals))) if value else "0"

            return TokenTransfer(
                chain=self.chain,
                timestamp=timestamp,
                block_number=int(tx.get("blockNum", "0x0"), 16),
                tx_hash=tx.get("hash", ""),
                from_address=tx.get("from", ""),
                to_address=tx.get("to", ""),
                token_address=token_address,
                token_symbol=tx.get("asset"),
                token_name=None,
                token_decimals=decimals,
                amount_raw=raw_amount,
                amount=float(value) if value else 0,
                direction=direction,
                usd_value=None
            )
        except Exception as e:
            print(f"Warning: Failed to parse transfer: {e}")
            return None

    async def get_transactions(
        self,
        address: str,
        limit: int = 100,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[Transaction]:
        """Get transaction history"""
        # For now, use token transfers to build transactions
        transfers = await self.get_token_transfers(
            address, limit, from_block, to_block
        )

        # Group transfers by tx_hash
        tx_map: Dict[str, List[TokenTransfer]] = {}
        for transfer in transfers:
            if transfer.tx_hash not in tx_map:
                tx_map[transfer.tx_hash] = []
            tx_map[transfer.tx_hash].append(transfer)

        # Build transactions
        transactions = []
        for tx_hash, tx_transfers in tx_map.items():
            first = tx_transfers[0]

            # Determine transaction type
            has_in = any(t.direction == "in" for t in tx_transfers)
            has_out = any(t.direction == "out" for t in tx_transfers)

            if has_in and has_out:
                tx_type = "swap"
            elif has_in:
                tx_type = "receive"
            else:
                tx_type = "send"

            transactions.append(Transaction(
                chain=self.chain,
                timestamp=first.timestamp,
                block_number=first.block_number,
                tx_hash=tx_hash,
                from_address=first.from_address,
                to_address=first.to_address,
                value=0,  # Would need separate RPC call for native value
                fee=0,  # Would need receipt for gas
                status="success",
                transfers=tx_transfers,
                tx_type=tx_type
            ))

        # Sort by timestamp descending
        transactions.sort(key=lambda x: x.timestamp, reverse=True)

        return transactions

    async def get_token_balances(
        self,
        address: str
    ) -> List[TokenBalance]:
        """Get current token balances using alchemy_getTokenBalances"""
        if not is_valid_evm_address(address):
            raise ValueError(f"Invalid EVM address format: {address}")

        result = await self._rpc_call(
            "alchemy_getTokenBalances",
            [address, "erc20"]
        )

        balances = []
        token_balances = result.get("tokenBalances", [])

        for tb in token_balances:
            token_address = tb.get("contractAddress", "")
            balance_hex = tb.get("tokenBalance", "0x0")

            if balance_hex == "0x0" or balance_hex == "0x":
                continue

            # Get token metadata
            metadata = await self._get_token_metadata(token_address)

            balance_raw = str(int(balance_hex, 16))
            decimals = metadata.get("decimals") or 18
            balance = int(balance_raw) / (10 ** decimals)

            if balance > 0:
                balances.append(TokenBalance(
                    chain=self.chain,
                    token_address=token_address,
                    token_symbol=metadata.get("symbol"),
                    token_name=metadata.get("name"),
                    token_decimals=decimals,
                    balance_raw=balance_raw,
                    balance=balance,
                    usd_value=None
                ))

        return balances

    async def _get_token_metadata(self, token_address: str) -> Dict:
        """Get token metadata"""
        try:
            result = await self._rpc_call(
                "alchemy_getTokenMetadata",
                [token_address]
            )
            return result or {}
        except:
            return {}

    async def get_native_balance(self, address: str) -> float:
        """Get native token balance (ETH, MATIC, etc.)"""
        result = await self._rpc_call("eth_getBalance", [address, "latest"])
        balance_wei = int(result, 16)
        return balance_wei / 1e18

    def get_explorer_url(self, tx_hash: str) -> str:
        """Get block explorer URL"""
        base = EXPLORERS.get(self.chain, "https://etherscan.io/tx")
        return f"{base}/{tx_hash}"
