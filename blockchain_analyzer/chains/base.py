"""Base chain interface for multi-chain support"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


class Chain(Enum):
    """Supported blockchain networks"""
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    BSC = "bsc"


@dataclass
class TokenTransfer:
    """Normalized token transfer across chains"""
    chain: Chain
    timestamp: int
    block_number: int
    tx_hash: str
    from_address: str
    to_address: str
    token_address: str  # Contract address (or mint for Solana)
    token_symbol: Optional[str]
    token_name: Optional[str]
    token_decimals: int
    amount_raw: str  # Raw amount as string to preserve precision
    amount: float  # Human-readable amount
    direction: str  # 'in' or 'out' relative to the analyzed address
    usd_value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'chain': self.chain.value,
            'timestamp': self.timestamp,
            'block_number': self.block_number,
            'tx_hash': self.tx_hash,
            'from_address': self.from_address,
            'to_address': self.to_address,
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'token_name': self.token_name,
            'token_decimals': self.token_decimals,
            'amount_raw': self.amount_raw,
            'amount': self.amount,
            'direction': self.direction,
            'usd_value': self.usd_value,
        }


@dataclass
class Transaction:
    """Normalized transaction across chains"""
    chain: Chain
    timestamp: int
    block_number: int
    tx_hash: str
    from_address: str
    to_address: Optional[str]
    value: float  # Native token value (ETH, SOL, MATIC)
    fee: float
    status: str  # 'success' or 'failed'
    transfers: List[TokenTransfer] = field(default_factory=list)
    tx_type: str = 'unknown'  # 'transfer', 'swap', 'airdrop', etc.
    raw_data: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'chain': self.chain.value,
            'timestamp': self.timestamp,
            'block_number': self.block_number,
            'tx_hash': self.tx_hash,
            'from_address': self.from_address,
            'to_address': self.to_address,
            'value': self.value,
            'fee': self.fee,
            'status': self.status,
            'transfers': [t.to_dict() for t in self.transfers],
            'tx_type': self.tx_type,
        }


@dataclass
class TokenBalance:
    """Token balance information"""
    chain: Chain
    token_address: str
    token_symbol: Optional[str]
    token_name: Optional[str]
    token_decimals: int
    balance_raw: str
    balance: float
    usd_value: Optional[float] = None


class ChainClient(ABC):
    """Abstract base class for blockchain clients"""

    chain: Chain

    @abstractmethod
    async def get_transactions(
        self,
        address: str,
        limit: int = 100,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[Transaction]:
        """Get transaction history for an address"""
        pass

    @abstractmethod
    async def get_token_transfers(
        self,
        address: str,
        limit: int = 100,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[TokenTransfer]:
        """Get token transfer history for an address"""
        pass

    @abstractmethod
    async def get_token_balances(
        self,
        address: str
    ) -> List[TokenBalance]:
        """Get current token balances for an address"""
        pass

    @abstractmethod
    async def get_native_balance(
        self,
        address: str
    ) -> float:
        """Get native token balance (ETH, SOL, MATIC, etc.)"""
        pass

    @abstractmethod
    def get_explorer_url(self, tx_hash: str) -> str:
        """Get block explorer URL for a transaction"""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
