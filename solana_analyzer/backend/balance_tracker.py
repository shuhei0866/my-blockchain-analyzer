"""Balance Tracker for calculating token balance over time"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import pandas as pd


class BalanceTracker:
    """Track and calculate token balances over time"""

    def __init__(self):
        """Initialize Balance Tracker"""
        pass

    def calculate_balance_history(
        self,
        transactions: List[Dict[str, Any]],
        target_address: str,
        current_balances: Optional[Dict[str, Any]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Calculate token balance history from transactions

        Args:
            transactions: List of transaction details
            target_address: Address to calculate balances for
            current_balances: Current token balances (optional)

        Returns:
            Dictionary mapping token mint to DataFrame with balance history
        """
        sorted_txs = sorted(
            [tx for tx in transactions if tx.get('block_time')],
            key=lambda x: x['block_time']
        )

        token_histories = defaultdict(list)
        token_balances = defaultdict(float)

        if current_balances:
            for mint, balance_info in current_balances.items():
                token_balances[mint] = float(balance_info.get('ui_amount', 0))

        for tx in reversed(sorted_txs):
            if not tx.get('meta') or tx['meta'].get('err'):
                continue

            meta = tx['meta']
            block_time = tx['block_time']
            timestamp = datetime.fromtimestamp(block_time)

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

            processed_tokens = set()

            for idx in target_indices:
                if idx in post_token_balances:
                    post = post_token_balances[idx]
                    mint = post['mint']

                    if mint not in processed_tokens:
                        post_amount = float(post['ui_token_amount']['ui_amount'] or 0)

                        if current_balances and mint in current_balances:
                            token_balances[mint] = post_amount
                        else:
                            if idx in pre_token_balances:
                                pre = pre_token_balances[idx]
                                pre_amount = float(pre['ui_token_amount']['ui_amount'] or 0)
                                change = post_amount - pre_amount
                                token_balances[mint] -= change
                            else:
                                token_balances[mint] -= post_amount

                        processed_tokens.add(mint)

                elif idx in pre_token_balances:
                    pre = pre_token_balances[idx]
                    mint = pre['mint']

                    if mint not in processed_tokens:
                        pre_amount = float(pre['ui_token_amount']['ui_amount'] or 0)
                        token_balances[mint] += pre_amount
                        processed_tokens.add(mint)

                if idx < len(meta.get('post_balances', [])):
                    post_sol = meta['post_balances'][idx] / 1e9

                    if 'SOL' not in processed_tokens:
                        if current_balances and 'SOL' in current_balances:
                            token_balances['SOL'] = post_sol
                        else:
                            if idx < len(meta.get('pre_balances', [])):
                                pre_sol = meta['pre_balances'][idx] / 1e9
                                change = post_sol - pre_sol
                                token_balances['SOL'] -= change
                            else:
                                token_balances['SOL'] -= post_sol

                        processed_tokens.add('SOL')

        for tx in sorted_txs:
            if not tx.get('meta') or tx['meta'].get('err'):
                continue

            meta = tx['meta']
            block_time = tx['block_time']
            timestamp = datetime.fromtimestamp(block_time)

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

            recorded_changes = {}

            for idx in target_indices:
                if idx in pre_token_balances and idx in post_token_balances:
                    pre = pre_token_balances[idx]
                    post = post_token_balances[idx]

                    if pre['mint'] == post['mint']:
                        mint = pre['mint']
                        pre_amount = float(pre['ui_token_amount']['ui_amount'] or 0)
                        post_amount = float(post['ui_token_amount']['ui_amount'] or 0)
                        change = post_amount - pre_amount

                        if mint not in recorded_changes:
                            token_balances[mint] += change
                            recorded_changes[mint] = True

                            token_histories[mint].append({
                                'timestamp': timestamp,
                                'balance': token_balances[mint],
                                'change': change,
                                'signature': tx['signature'],
                            })

                elif idx not in pre_token_balances and idx in post_token_balances:
                    post = post_token_balances[idx]
                    mint = post['mint']
                    amount = float(post['ui_token_amount']['ui_amount'] or 0)

                    if mint not in recorded_changes:
                        token_balances[mint] += amount
                        recorded_changes[mint] = True

                        token_histories[mint].append({
                            'timestamp': timestamp,
                            'balance': token_balances[mint],
                            'change': amount,
                            'signature': tx['signature'],
                        })

                elif idx in pre_token_balances and idx not in post_token_balances:
                    pre = pre_token_balances[idx]
                    mint = pre['mint']
                    amount = float(pre['ui_token_amount']['ui_amount'] or 0)

                    if mint not in recorded_changes:
                        token_balances[mint] -= amount
                        recorded_changes[mint] = True

                        token_histories[mint].append({
                            'timestamp': timestamp,
                            'balance': token_balances[mint],
                            'change': -amount,
                            'signature': tx['signature'],
                        })

                if idx < len(meta.get('pre_balances', [])) and idx < len(meta.get('post_balances', [])):
                    pre_sol = meta['pre_balances'][idx] / 1e9
                    post_sol = meta['post_balances'][idx] / 1e9
                    change = post_sol - pre_sol

                    if 'SOL' not in recorded_changes and change != 0:
                        token_balances['SOL'] += change
                        recorded_changes['SOL'] = True

                        token_histories['SOL'].append({
                            'timestamp': timestamp,
                            'balance': token_balances['SOL'],
                            'change': change,
                            'signature': tx['signature'],
                        })

        result = {}
        for mint, history in token_histories.items():
            if history:
                df = pd.DataFrame(history)
                df = df.sort_values('timestamp')
                result[mint] = df

        return result

    def get_balance_at_time(
        self,
        balance_history: pd.DataFrame,
        target_time: datetime
    ) -> float:
        """
        Get balance at a specific point in time

        Args:
            balance_history: DataFrame with balance history
            target_time: Target datetime

        Returns:
            Balance at the specified time
        """
        if balance_history.empty:
            return 0.0

        mask = balance_history['timestamp'] <= target_time
        if not mask.any():
            return 0.0

        return balance_history[mask].iloc[-1]['balance']

    def calculate_daily_balances(
        self,
        balance_histories: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """
        Calculate daily balance snapshots

        Args:
            balance_histories: Dictionary of balance histories by token

        Returns:
            Dictionary of daily balance DataFrames by token
        """
        daily_balances = {}

        for mint, history in balance_histories.items():
            if history.empty:
                continue

            start_date = history['timestamp'].min().date()
            end_date = history['timestamp'].max().date()

            date_range = pd.date_range(start=start_date, end=end_date, freq='D')

            daily_data = []
            for date in date_range:
                balance = self.get_balance_at_time(
                    history,
                    datetime.combine(date, datetime.max.time())
                )

                daily_data.append({
                    'date': date,
                    'balance': balance,
                })

            if daily_data:
                daily_balances[mint] = pd.DataFrame(daily_data)

        return daily_balances
