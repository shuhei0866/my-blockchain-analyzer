"""Configuration and Constants for the Web UI"""
import os
from blockchain_analyzer.chains.base import Chain

# API keys from environment
HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY")
ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY")

# Chain mapping
CHAIN_MAP = {
    "solana": Chain.SOLANA,
    "ethereum": Chain.ETHEREUM,
    "polygon": Chain.POLYGON,
    "arbitrum": Chain.ARBITRUM,
    "optimism": Chain.OPTIMISM,
    "base": Chain.BASE,
}

CHAIN_NAMES = {
    "solana": "Solana",
    "ethereum": "Ethereum",
    "polygon": "Polygon",
    "arbitrum": "Arbitrum",
    "optimism": "Optimism",
    "base": "Base",
}

NATIVE_SYMBOLS = {
    "solana": "SOL",
    "ethereum": "ETH",
    "polygon": "MATIC",
    "arbitrum": "ETH",
    "optimism": "ETH",
    "base": "ETH",
}
