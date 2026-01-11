"""Token symbol registry using Jupiter Token List"""
import requests
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta


class TokenRegistry:
    """
    Token symbol registry
    Uses Jupiter Token List for comprehensive token data
    """

    def __init__(self, cache_file: str = "data/token_list.json", cache_ttl_hours: int = 24):
        """
        Initialize token registry

        Args:
            cache_file: Path to cache file
            cache_ttl_hours: Cache time-to-live in hours
        """
        self.cache_file = Path(cache_file)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.token_map: Dict[str, Dict] = {}
        self._load_tokens()

    def _load_tokens(self):
        """Load tokens from cache or fetch from Jupiter"""
        # Check cache first
        if self.cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(self.cache_file.stat().st_mtime)
            if cache_age < self.cache_ttl:
                print(f"Loading token list from cache ({self.cache_file})...")
                try:
                    with open(self.cache_file, 'r') as f:
                        data = json.load(f)
                        self.token_map = {token['address']: token for token in data}
                        print(f"✓ Loaded {len(self.token_map)} tokens from cache")

                        # Also load custom token list
                        self._load_custom_tokens()
                        return
                except Exception as e:
                    print(f"Warning: Could not load cache: {e}")

        # Fetch from Jupiter
        print("Fetching token list...")
        urls = [
            "https://tokens.jup.ag/tokens?tags=verified",
            "https://token.jup.ag/all",
            "https://raw.githubusercontent.com/solana-labs/token-list/main/src/tokens/solana.tokenlist.json"
        ]
        
        tokens = None
        for url in urls:
            try:
                print(f"Trying {url}...")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, dict) and 'tokens' in data:
                    tokens = data['tokens']
                else:
                    tokens = data
                
                print(f"✓ Successfully fetched from {url}")
                break
            except Exception as e:
                print(f"⚠ Could not fetch from {url}: {e}")
                continue

        if tokens:
            self.token_map = {token['address']: token for token in tokens}

            # Save to cache
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(self.cache_file, 'w') as f:
                    json.dump(tokens, f, indent=2)
                print(f"✓ Loaded {len(self.token_map)} tokens and saved to cache")
            except Exception as e:
                print(f"Warning: Could not save cache: {e}")

            # Load custom tokens
            self._load_custom_tokens()
        else:
            print("Warning: All token list sources failed.")
            # Use fallback list of common tokens
            self._use_fallback_list()
            # Load custom tokens even with fallback
            self._load_custom_tokens()

    def _use_fallback_list(self):
        """Use fallback list of common tokens"""
        print("Using fallback token list...")
        fallback = {
            "So11111111111111111111111111111111111111112": {
                "symbol": "SOL",
                "name": "Solana",
                "decimals": 9,
                "logoURI": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png"
            },
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {
                "symbol": "USDC",
                "name": "USD Coin",
                "decimals": 6,
                "logoURI": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v/logo.png"
            },
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {
                "symbol": "USDT",
                "name": "USDT",
                "decimals": 6,
                "logoURI": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB/logo.png"
            },
            "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": {
                "symbol": "BONK",
                "name": "Bonk",
                "decimals": 5,
            },
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": {
                "symbol": "mSOL",
                "name": "Marinade staked SOL",
                "decimals": 9,
            },
            "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj": {
                "symbol": "stSOL",
                "name": "Lido Staked SOL",
                "decimals": 9,
            },
        }
        self.token_map = fallback

    def _load_custom_tokens(self):
        """Load custom token list (from DexScreener, etc.)"""
        custom_file = Path("data/custom_token_list.json")
        if custom_file.exists():
            try:
                with open(custom_file, 'r') as f:
                    custom_tokens = json.load(f)
                    # Update token_map with custom tokens (overwrites existing)
                    for token in custom_tokens:
                        self.token_map[token['address']] = token
                    print(f"✓ Loaded {len(custom_tokens)} custom tokens")
            except Exception as e:
                print(f"Warning: Could not load custom tokens: {e}")

    def get_token_info(self, mint_address: str) -> Optional[Dict]:
        """
        Get token information by mint address

        Args:
            mint_address: Token mint address

        Returns:
            Token info dict or None
        """
        return self.token_map.get(mint_address)

    def get_symbol(self, mint_address: str, fallback: Optional[str] = None) -> str:
        """
        Get token symbol

        Args:
            mint_address: Token mint address
            fallback: Fallback value if not found

        Returns:
            Token symbol or fallback
        """
        if mint_address == "SOL":
            return "SOL"

        token = self.token_map.get(mint_address)
        if token:
            return token.get('symbol', fallback or f"{mint_address[:8]}...")

        return fallback or f"{mint_address[:8]}..."

    def get_name(self, mint_address: str, fallback: Optional[str] = None) -> str:
        """
        Get token name

        Args:
            mint_address: Token mint address
            fallback: Fallback value if not found

        Returns:
            Token name or fallback
        """
        if mint_address == "SOL":
            return "Solana"

        token = self.token_map.get(mint_address)
        if token:
            return token.get('name', fallback or f"{mint_address[:8]}...")

        return fallback or f"{mint_address[:8]}..."

    def format_token_display(
        self,
        mint_address: str,
        show_address: bool = False,
        max_address_len: int = 8
    ) -> str:
        """
        Format token for display

        Args:
            mint_address: Token mint address
            show_address: Whether to show address
            max_address_len: Maximum length of address to show

        Returns:
            Formatted string (e.g., "USDC" or "USDC (EPjFWdd5...)")
        """
        symbol = self.get_symbol(mint_address)

        if show_address and mint_address != "SOL":
            short_addr = f"{mint_address[:max_address_len]}...{mint_address[-4:]}"
            return f"{symbol} ({short_addr})"

        return symbol

    def search_tokens(self, query: str, limit: int = 10) -> list:
        """
        Search tokens by symbol or name

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching tokens
        """
        query_lower = query.lower()
        results = []

        for token in self.token_map.values():
            symbol = token.get('symbol', '').lower()
            name = token.get('name', '').lower()

            if query_lower in symbol or query_lower in name:
                results.append(token)

            if len(results) >= limit:
                break

        return results

    def get_stats(self) -> Dict:
        """Get registry statistics"""
        return {
            'total_tokens': len(self.token_map),
            'cache_file': str(self.cache_file),
            'cache_exists': self.cache_file.exists(),
        }
