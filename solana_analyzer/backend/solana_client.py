"""Solana RPC Client for fetching transaction data"""
import asyncio
from typing import List, Dict, Any, Optional
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from solders.signature import Signature
import base64


class SolanaRPCClient:
    """Client for interacting with Solana blockchain"""

    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        """
        Initialize Solana RPC Client

        Args:
            rpc_url: Solana RPC endpoint URL
        """
        self.rpc_url = rpc_url
        self.client: Optional[AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.client = AsyncClient(self.rpc_url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.close()

    async def get_signatures(
        self,
        address: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get transaction signatures for an address

        Args:
            address: Solana address to query
            limit: Maximum number of signatures to fetch

        Returns:
            List of signature information dictionaries
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        pubkey = Pubkey.from_string(address)
        all_signatures = []
        before = None

        while len(all_signatures) < limit:
            batch_size = min(1000, limit - len(all_signatures))

            response = await self.client.get_signatures_for_address(
                pubkey,
                limit=batch_size,
                before=before,
                commitment=Confirmed
            )

            if response.value is None or len(response.value) == 0:
                break

            signatures = [
                {
                    'signature': str(sig.signature),
                    'slot': sig.slot,
                    'block_time': sig.block_time,
                    'err': sig.err,
                    'memo': sig.memo,
                }
                for sig in response.value
            ]

            all_signatures.extend(signatures)

            if len(response.value) < batch_size:
                break

            before = response.value[-1].signature

        return all_signatures[:limit]

    async def get_transaction_details(
        self,
        signature: str,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed transaction information

        Args:
            signature: Transaction signature
            max_retries: Maximum number of retry attempts

        Returns:
            Transaction details dictionary or None if failed
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        sig = Signature.from_string(signature)

        for attempt in range(max_retries):
            try:
                response = await self.client.get_transaction(
                    sig,
                    encoding="jsonParsed",
                    max_supported_transaction_version=0,
                    commitment=Confirmed
                )

                if response.value is None:
                    return None

                tx = response.value

                return {
                    'signature': signature,
                    'slot': tx.slot,
                    'block_time': tx.block_time,
                    'meta': self._parse_meta(tx.transaction.meta) if tx.transaction.meta else None,
                    'transaction': self._parse_transaction(tx.transaction.transaction),
                }
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"Failed to fetch transaction {signature}: {e}")
                    return None
                await asyncio.sleep(0.5 * (attempt + 1))

        return None

    def _parse_meta(self, meta: Any) -> Dict[str, Any]:
        """Parse transaction meta information"""
        return {
            'err': meta.err,
            'fee': meta.fee,
            'pre_balances': meta.pre_balances,
            'post_balances': meta.post_balances,
            'pre_token_balances': [
                self._parse_token_balance(tb) for tb in (meta.pre_token_balances or [])
            ],
            'post_token_balances': [
                self._parse_token_balance(tb) for tb in (meta.post_token_balances or [])
            ],
            'log_messages': meta.log_messages or [],
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

        return {
            'signatures': [str(sig) for sig in transaction.signatures],
            'message': {
                'account_keys': [str(key) for key in message.account_keys],
                'recent_blockhash': str(message.recent_blockhash),
                'instructions': [
                    self._parse_instruction(inst) for inst in message.instructions
                ],
            },
        }

    def _parse_instruction(self, instruction: Any) -> Dict[str, Any]:
        """Parse instruction information"""
        result = {
            'program_id_index': instruction.program_id_index,
        }

        if hasattr(instruction, 'accounts'):
            result['accounts'] = instruction.accounts

        if hasattr(instruction, 'data'):
            result['data'] = instruction.data

        if hasattr(instruction, 'parsed'):
            result['parsed'] = instruction.parsed

        return result

    async def get_current_token_balance(
        self,
        address: str,
        token_mint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get current token balances for an address

        Args:
            address: Solana address to query
            token_mint: Optional specific token mint address

        Returns:
            Dictionary of token balances
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        pubkey = Pubkey.from_string(address)

        from solana.rpc.types import TokenAccountOpts

        opts = TokenAccountOpts(
            mint=Pubkey.from_string(token_mint) if token_mint else None,
            program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA") if not token_mint else None
        )

        response = await self.client.get_token_accounts_by_owner_json_parsed(
            pubkey,
            opts,
            commitment=Confirmed
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

        sol_balance_response = await self.client.get_balance(pubkey, commitment=Confirmed)
        balances['SOL'] = {
            'amount': str(sol_balance_response.value),
            'decimals': 9,
            'ui_amount': sol_balance_response.value / 1e9,
            'ui_amount_string': str(sol_balance_response.value / 1e9),
        }

        return balances
