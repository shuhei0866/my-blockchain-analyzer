"""Cached Transaction Analyzer with Multi-RPC support"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from .multi_rpc_client import MultiRPCClient, DEFAULT_PUBLIC_RPCS
from .cache import TransactionCache
from solders.pubkey import Pubkey
from solders.signature import Signature


def _make_json_serializable(obj: Any) -> Any:
    """Recursively convert objects to JSON-serializable types"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Pubkey):
        return str(obj)
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _make_json_serializable(v) for k, v in obj.items()}
    # For any other object, try to convert to string
    return str(obj)


class CachedTransactionAnalyzer:
    """
    Transaction Analyzer with caching and multi-RPC support
    """

    def __init__(
        self,
        rpc_urls: Optional[List[str]] = None,
        cache_db: str = "data/solana_cache.db"
    ):
        """
        Initialize Cached Transaction Analyzer

        Args:
            rpc_urls: List of RPC URLs (uses default public RPCs if None)
            cache_db: Path to SQLite cache database
        """
        self.rpc_urls = rpc_urls or DEFAULT_PUBLIC_RPCS
        self.cache = TransactionCache(cache_db)
        print(f"Cache database: {cache_db}")

    async def fetch_signatures_incremental(
        self,
        address: str,
        limit: int = 1000,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch signatures incrementally (only new ones)

        Args:
            address: Solana address
            limit: Maximum total signatures to have
            force_refresh: Force fetching from RPC even if cached

        Returns:
            List of all signatures (cached + new)
        """
        # Check cache first
        if not force_refresh:
            cached_sigs = self.cache.get_cached_signatures(address)
            print(f"Found {len(cached_sigs)} cached signatures")

            if cached_sigs:
                # Get the most recent cached signature
                most_recent = cached_sigs[0]
                print(f"Most recent cached: {most_recent['signature'][:16]}... "
                      f"(block_time: {most_recent.get('block_time')})")

        # Fetch new signatures from RPC
        async with MultiRPCClient(self.rpc_urls) as client:
            pubkey = Pubkey.from_string(address)
            all_new_signatures = []
            before = None

            print(f"\nFetching new signatures from RPC...")

            while len(all_new_signatures) < limit:
                batch_size = min(1000, limit - len(all_new_signatures))

                response = await client.get_signatures_for_address(
                    pubkey,
                    limit=batch_size,
                    before=before
                )

                if response.value is None or len(response.value) == 0:
                    break

                batch = [
                    {
                        'signature': str(sig.signature),
                        'slot': sig.slot,
                        'block_time': sig.block_time,
                        'err': sig.err,
                        'memo': sig.memo,
                    }
                    for sig in response.value
                ]

                all_new_signatures.extend(batch)
                print(f"  Fetched {len(batch)} signatures (total: {len(all_new_signatures)})")

                if len(response.value) < batch_size:
                    break

                before = response.value[-1].signature

            # Save new signatures to cache
            if all_new_signatures:
                print(f"Saving {len(all_new_signatures)} signatures to cache...")
                self.cache.save_signatures(address, all_new_signatures)

            # Update metadata
            self.cache.update_address_metadata(
                address,
                len(all_new_signatures),
                all_new_signatures[0]['signature'] if all_new_signatures else None
            )

            client.print_stats()

        # Return all signatures from cache
        return self.cache.get_cached_signatures(address, limit=limit)

    async def fetch_transaction_details_cached(
        self,
        address: str,
        signatures: List[Dict[str, Any]],
        batch_size: int = 5,
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Fetch transaction details with caching

        Args:
            address: Solana address
            signatures: List of signature information
            batch_size: Number of transactions to fetch per batch
            max_concurrent: Maximum concurrent RPC requests

        Returns:
            List of transaction details
        """
        all_transactions = []

        # Check which transactions are already cached
        uncached_sigs = []
        for sig_info in signatures:
            cached = self.cache.get_cached_transaction(sig_info['signature'])
            if cached:
                all_transactions.append(cached)
            else:
                uncached_sigs.append(sig_info)

        print(f"\nTransaction cache status:")
        print(f"  Cached: {len(all_transactions)}")
        print(f"  Need to fetch: {len(uncached_sigs)}")

        if not uncached_sigs:
            return all_transactions

        # Fetch uncached transactions
        async with MultiRPCClient(self.rpc_urls) as client:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def fetch_with_semaphore(sig_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                async with semaphore:
                    try:
                        sig = Signature.from_string(sig_info['signature'])
                        response = await client.get_transaction(
                            sig,
                            encoding="jsonParsed",
                            max_supported_transaction_version=0
                        )

                        if response.value is None:
                            return None

                        tx = response.value
                        tx_data = {
                            'signature': sig_info['signature'],
                            'slot': tx.slot,
                            'block_time': tx.block_time,
                            'meta': self._parse_meta(tx.transaction.meta) if tx.transaction.meta else None,
                            'transaction': self._parse_transaction(tx.transaction.transaction),
                        }

                        # Save to cache
                        self.cache.save_transaction(address, sig_info['signature'], tx_data)

                        return tx_data

                    except Exception as e:
                        # Silently fail for individual transactions
                        return None

            # Process in batches
            for i in range(0, len(uncached_sigs), batch_size):
                batch = uncached_sigs[i:i + batch_size]
                print(f"Fetching details {i + 1}-{min(i + batch_size, len(uncached_sigs))} "
                      f"of {len(uncached_sigs)}...")

                tasks = [fetch_with_semaphore(sig) for sig in batch]
                results = await asyncio.gather(*tasks)

                for tx in results:
                    if tx is not None:
                        all_transactions.append(tx)

                # Small delay between batches
                if i + batch_size < len(uncached_sigs):
                    await asyncio.sleep(0.5)

            client.print_stats()

        return all_transactions

    def _parse_meta(self, meta: Any) -> Dict[str, Any]:
        """Parse transaction meta information"""
        # Convert error to string if present (can be complex types like TransactionErrorInstructionError)
        err = None
        if meta.err is not None:
            err = str(meta.err)

        return {
            'err': err,
            'fee': meta.fee,
            'pre_balances': list(meta.pre_balances) if meta.pre_balances else [],
            'post_balances': list(meta.post_balances) if meta.post_balances else [],
            'pre_token_balances': [
                self._parse_token_balance(tb) for tb in (meta.pre_token_balances or [])
            ],
            'post_token_balances': [
                self._parse_token_balance(tb) for tb in (meta.post_token_balances or [])
            ],
            'log_messages': list(meta.log_messages) if meta.log_messages else [],
        }

    def _parse_token_balance(self, token_balance: Any) -> Dict[str, Any]:
        """Parse token balance information"""
        return {
            'account_index': token_balance.account_index,
            'mint': str(token_balance.mint),
            'owner': str(token_balance.owner) if token_balance.owner else None,
            'program_id': str(token_balance.program_id) if token_balance.program_id else None,
            'ui_token_amount': {
                'amount': token_balance.ui_token_amount.amount,
                'decimals': token_balance.ui_token_amount.decimals,
                'ui_amount': token_balance.ui_token_amount.ui_amount,
                'ui_amount_string': token_balance.ui_token_amount.ui_amount_string,
            } if token_balance.ui_token_amount else None,
        }

    def _parse_transaction(self, transaction: Any) -> Dict[str, Any]:
        """Parse transaction information"""
        message = transaction.message

        # Handle ParsedAccountTxStatus objects (have .pubkey) or plain strings
        account_keys = []
        for key in message.account_keys:
            if hasattr(key, 'pubkey'):
                account_keys.append(str(key.pubkey))
            else:
                account_keys.append(str(key))

        return {
            'signatures': [str(sig) for sig in transaction.signatures],
            'message': {
                'account_keys': account_keys,
                'recent_blockhash': str(message.recent_blockhash),
                'instructions': [
                    self._parse_instruction(inst) for inst in message.instructions
                ],
            },
        }

    def _parse_instruction(self, instruction: Any) -> Dict[str, Any]:
        """Parse instruction information"""
        result = {}

        # ParsedInstruction has program_id, not program_id_index
        if hasattr(instruction, 'program_id'):
            result['program_id'] = str(instruction.program_id)
        if hasattr(instruction, 'program_id_index'):
            result['program_id_index'] = instruction.program_id_index

        if hasattr(instruction, 'program'):
            result['program'] = instruction.program

        if hasattr(instruction, 'accounts'):
            # accounts might contain Pubkey objects
            result['accounts'] = _make_json_serializable(instruction.accounts)

        if hasattr(instruction, 'data'):
            result['data'] = instruction.data

        if hasattr(instruction, 'parsed'):
            # parsed can contain nested Pubkey objects
            result['parsed'] = _make_json_serializable(instruction.parsed)

        if hasattr(instruction, 'stack_height'):
            result['stack_height'] = instruction.stack_height

        return result

    async def get_current_balances(self, address: str) -> Dict[str, Any]:
        """Get current token balances"""
        from solana.rpc.types import TokenAccountOpts

        async with MultiRPCClient(self.rpc_urls) as client:
            pubkey = Pubkey.from_string(address)

            opts = TokenAccountOpts(
                program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
            )

            response = await client.get_token_accounts_by_owner_json_parsed(
                pubkey,
                opts
            )

            balances = {}

            if response.value:
                for account in response.value:
                    if account.account.data and hasattr(account.account.data, 'parsed'):
                        parsed = account.account.data.parsed
                        if 'info' in parsed:
                            info = parsed['info']
                            mint = info.get('mint', 'Unknown')
                            token_amount = info.get('tokenAmount', {})

                            balances[mint] = {
                                'amount': token_amount.get('amount', '0'),
                                'decimals': token_amount.get('decimals', 0),
                                'ui_amount': token_amount.get('uiAmount', 0.0),
                                'ui_amount_string': token_amount.get('uiAmountString', '0'),
                            }

            sol_balance_response = await client.get_balance(pubkey)
            balances['SOL'] = {
                'amount': str(sol_balance_response.value),
                'decimals': 9,
                'ui_amount': sol_balance_response.value / 1e9,
                'ui_amount_string': str(sol_balance_response.value / 1e9),
            }

            return balances

    def get_cache_stats(self, address: str) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_cache_stats(address)

    def close(self):
        """Close cache connection"""
        self.cache.close()
