"""Transaction Analyzer for Solana blockchain data"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import asyncio
from .solana_client import SolanaRPCClient


class TransactionAnalyzer:
    """Analyze Solana transactions for an address"""

    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        """
        Initialize Transaction Analyzer

        Args:
            rpc_url: Solana RPC endpoint URL
        """
        self.rpc_url = rpc_url

    async def fetch_and_analyze_transactions(
        self,
        address: str,
        limit: int = 1000,
        fetch_details: bool = True,
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """
        Fetch and analyze transactions for an address

        Args:
            address: Solana address to analyze
            limit: Maximum number of transactions to fetch
            fetch_details: Whether to fetch full transaction details
            batch_size: Number of transactions to fetch in parallel

        Returns:
            Dictionary containing analyzed transaction data
        """
        async with SolanaRPCClient(self.rpc_url) as client:
            signatures = await client.get_signatures(address, limit=limit)

            print(f"Found {len(signatures)} transactions for address {address}")

            transactions = []

            if fetch_details:
                for i in range(0, len(signatures), batch_size):
                    batch = signatures[i:i + batch_size]
                    print(f"Fetching transaction details {i + 1}-{min(i + batch_size, len(signatures))} of {len(signatures)}")

                    tasks = [
                        client.get_transaction_details(sig['signature'])
                        for sig in batch
                    ]

                    batch_results = await asyncio.gather(*tasks)

                    for tx in batch_results:
                        if tx is not None:
                            transactions.append(tx)

            current_balances = await client.get_current_token_balance(address)

            return {
                'address': address,
                'total_transactions': len(signatures),
                'signatures': signatures,
                'transactions': transactions,
                'current_balances': current_balances,
                'analyzed_at': datetime.now().isoformat(),
            }

    def analyze_token_flows(
        self,
        transactions: List[Dict[str, Any]],
        target_address: str
    ) -> Dict[str, Any]:
        """
        Analyze token flows (incoming/outgoing) from transactions

        Args:
            transactions: List of transaction details
            target_address: Address to analyze flows for

        Returns:
            Dictionary containing token flow analysis
        """
        token_flows = defaultdict(lambda: {
            'total_received': 0,
            'total_sent': 0,
            'net_change': 0,
            'transaction_count': 0,
            'decimals': 9,
        })

        for tx in transactions:
            if not tx.get('meta') or tx['meta'].get('err'):
                continue

            meta = tx['meta']
            pre_token_balances = {
                tb['account_index']: tb for tb in meta.get('pre_token_balances', [])
            }
            post_token_balances = {
                tb['account_index']: tb for tb in meta.get('post_token_balances', [])
            }

            account_keys = tx.get('transaction', {}).get('message', {}).get('account_keys', [])

            try:
                target_indices = [
                    i for i, key in enumerate(account_keys)
                    if key.lower() == target_address.lower()
                ]
            except:
                target_indices = []

            for idx in target_indices:
                if idx in pre_token_balances and idx in post_token_balances:
                    pre = pre_token_balances[idx]
                    post = post_token_balances[idx]

                    if pre['mint'] == post['mint']:
                        mint = pre['mint']

                        pre_amount = float(pre['ui_token_amount']['ui_amount'] or 0)
                        post_amount = float(post['ui_token_amount']['ui_amount'] or 0)
                        change = post_amount - pre_amount

                        token_flows[mint]['decimals'] = pre['ui_token_amount']['decimals']
                        token_flows[mint]['transaction_count'] += 1

                        if change > 0:
                            token_flows[mint]['total_received'] += change
                        elif change < 0:
                            token_flows[mint]['total_sent'] += abs(change)

                        token_flows[mint]['net_change'] += change

                elif idx not in pre_token_balances and idx in post_token_balances:
                    post = post_token_balances[idx]
                    mint = post['mint']
                    amount = float(post['ui_token_amount']['ui_amount'] or 0)

                    token_flows[mint]['decimals'] = post['ui_token_amount']['decimals']
                    token_flows[mint]['total_received'] += amount
                    token_flows[mint]['net_change'] += amount
                    token_flows[mint]['transaction_count'] += 1

                elif idx in pre_token_balances and idx not in post_token_balances:
                    pre = pre_token_balances[idx]
                    mint = pre['mint']
                    amount = float(pre['ui_token_amount']['ui_amount'] or 0)

                    token_flows[mint]['decimals'] = pre['ui_token_amount']['decimals']
                    token_flows[mint]['total_sent'] += amount
                    token_flows[mint]['net_change'] -= amount
                    token_flows[mint]['transaction_count'] += 1

            if target_indices:
                pre_balances = meta.get('pre_balances', [])
                post_balances = meta.get('post_balances', [])

                for idx in target_indices:
                    if idx < len(pre_balances) and idx < len(post_balances):
                        pre_sol = pre_balances[idx] / 1e9
                        post_sol = post_balances[idx] / 1e9
                        change = post_sol - pre_sol

                        if 'SOL' not in token_flows:
                            token_flows['SOL'] = {
                                'total_received': 0,
                                'total_sent': 0,
                                'net_change': 0,
                                'transaction_count': 0,
                                'decimals': 9,
                            }

                        token_flows['SOL']['transaction_count'] += 1

                        if change > 0:
                            token_flows['SOL']['total_received'] += change
                        elif change < 0:
                            token_flows['SOL']['total_sent'] += abs(change)

                        token_flows['SOL']['net_change'] += change

        return dict(token_flows)

    def generate_transaction_summary(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate summary statistics from transaction data

        Args:
            data: Analyzed transaction data

        Returns:
            Summary statistics dictionary
        """
        transactions = data.get('transactions', [])
        signatures = data.get('signatures', [])

        successful_txs = [
            tx for tx in transactions
            if tx.get('meta') and not tx['meta'].get('err')
        ]
        failed_txs = [
            tx for tx in transactions
            if tx.get('meta') and tx['meta'].get('err')
        ]

        timestamps = [
            sig['block_time'] for sig in signatures
            if sig['block_time'] is not None
        ]

        first_tx_time = min(timestamps) if timestamps else None
        last_tx_time = max(timestamps) if timestamps else None

        token_flows = self.analyze_token_flows(
            transactions,
            data['address']
        )

        return {
            'address': data['address'],
            'total_transactions': data['total_transactions'],
            'successful_transactions': len(successful_txs),
            'failed_transactions': len(failed_txs),
            'first_transaction_time': datetime.fromtimestamp(first_tx_time).isoformat() if first_tx_time else None,
            'last_transaction_time': datetime.fromtimestamp(last_tx_time).isoformat() if last_tx_time else None,
            'token_flows': token_flows,
            'current_balances': data.get('current_balances', {}),
        }
