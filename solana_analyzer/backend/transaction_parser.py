"""Transaction parser for extracting token transfers and flows"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json


class TransactionParser:
    """
    Parse Solana transactions to extract token transfer information
    """

    def __init__(self):
        """Initialize transaction parser"""
        self.spl_token_program = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

    def parse_transaction(self, tx_detail: Dict, target_address: str) -> Optional[Dict]:
        """
        Parse a transaction to extract transfer information

        Args:
            tx_detail: Transaction detail from RPC (supports both 'result' wrapper and direct format)
            target_address: The address we're analyzing

        Returns:
            Dict with transfer info or None
        """
        if not tx_detail:
            return None

        # Handle both formats: wrapped in 'result' or direct
        if 'result' in tx_detail:
            result = tx_detail['result']
            if not result:
                return None
        else:
            # Direct format (from cached_analyzer)
            result = tx_detail

        if 'meta' not in result or 'transaction' not in result:
            return None

        meta = result['meta']
        transaction = result['transaction']

        if not meta or not transaction:
            return None

        # Get block time (handle both 'blockTime' and 'block_time' keys)
        block_time = result.get('blockTime') or result.get('block_time')
        slot = result.get('slot')

        # Parse token transfers
        transfers = self._extract_token_transfers(transaction, meta, target_address)

        if not transfers:
            return None

        return {
            'block_time': block_time,
            'slot': slot,
            'transfers': transfers,
            'fee': meta.get('fee', 0),
            'success': meta.get('err') is None
        }

    def _extract_token_transfers(
        self,
        transaction: Dict,
        meta: Dict,
        target_address: str
    ) -> List[Dict]:
        """Extract token transfers from transaction"""
        transfers = []

        # Method 1: Parse from preTokenBalances and postTokenBalances
        # Handle both camelCase (RPC) and snake_case (cached) keys
        pre_balances = meta.get('preTokenBalances') or meta.get('pre_token_balances', [])
        post_balances = meta.get('postTokenBalances') or meta.get('post_token_balances', [])

        # Create a mapping of account index to balance changes
        balance_changes = {}

        for pre in pre_balances:
            # Handle both camelCase and snake_case keys
            account_index = pre.get('accountIndex') or pre.get('account_index')
            if account_index is not None:
                balance_changes[account_index] = {
                    'pre': pre,
                    'mint': pre.get('mint'),
                    'owner': pre.get('owner')
                }

        for post in post_balances:
            account_index = post.get('accountIndex') or post.get('account_index')
            if account_index is not None:
                if account_index not in balance_changes:
                    balance_changes[account_index] = {'pre': None}
                balance_changes[account_index]['post'] = post
                balance_changes[account_index]['mint'] = post.get('mint')
                balance_changes[account_index]['owner'] = post.get('owner')

        # Calculate balance changes
        for account_index, data in balance_changes.items():
            pre = data.get('pre', {})
            post = data.get('post', {})

            pre_amount = 0
            post_amount = 0

            if pre:
                # Handle both camelCase and snake_case keys
                pre_ui_amount = pre.get('uiTokenAmount') or pre.get('ui_token_amount', {})
                pre_amount = float(pre_ui_amount.get('uiAmount') or pre_ui_amount.get('ui_amount') or 0)

            if post:
                post_ui_amount = post.get('uiTokenAmount') or post.get('ui_token_amount', {})
                post_amount = float(post_ui_amount.get('uiAmount') or post_ui_amount.get('ui_amount') or 0)

            change = post_amount - pre_amount

            if abs(change) > 0.0000001:  # Ignore very small changes
                mint = data.get('mint')
                owner = data.get('owner')

                # Determine direction relative to target address
                if owner == target_address:
                    direction = 'in' if change > 0 else 'out'
                    transfers.append({
                        'mint': mint,
                        'amount': abs(change),
                        'direction': direction,
                        'owner': owner,
                        'account_index': account_index
                    })

        # Method 2: Parse instructions (for more detailed info)
        message = transaction.get('message', {})
        instructions = message.get('instructions', [])
        account_keys = message.get('accountKeys', [])

        for instruction in instructions:
            program_id_index = instruction.get('programIdIndex')
            if program_id_index is not None and program_id_index < len(account_keys):
                program_id = account_keys[program_id_index]

                # Check if this is a token program instruction
                if program_id == self.spl_token_program:
                    # Could parse instruction data here for more details
                    # For now, we rely on balance changes
                    pass

        return transfers

    def aggregate_flows(
        self,
        transactions: List[Dict],
        target_address: str
    ) -> Dict:
        """
        Aggregate token flows from multiple transactions

        Args:
            transactions: List of parsed transactions
            target_address: The address we're analyzing

        Returns:
            Dict with aggregated flow information
        """
        flows = {
            'by_token': {},  # mint -> {in, out, net}
            'by_date': {},   # date -> {mint -> {in, out}}
            'counterparties': {},  # address -> {mint -> {in, out}}
            'total_transactions': len(transactions)
        }

        for tx in transactions:
            if not tx or not tx.get('success'):
                continue

            block_time = tx.get('block_time')
            if block_time:
                date = datetime.fromtimestamp(block_time).strftime('%Y-%m-%d')
            else:
                date = 'unknown'

            for transfer in tx.get('transfers', []):
                mint = transfer.get('mint', 'SOL')
                amount = transfer.get('amount', 0)
                direction = transfer.get('direction', 'unknown')

                # By token aggregation
                if mint not in flows['by_token']:
                    flows['by_token'][mint] = {'in': 0, 'out': 0, 'net': 0, 'count': 0}

                if direction == 'in':
                    flows['by_token'][mint]['in'] += amount
                    flows['by_token'][mint]['net'] += amount
                elif direction == 'out':
                    flows['by_token'][mint]['out'] += amount
                    flows['by_token'][mint]['net'] -= amount

                flows['by_token'][mint]['count'] += 1

                # By date aggregation
                if date not in flows['by_date']:
                    flows['by_date'][date] = {}

                if mint not in flows['by_date'][date]:
                    flows['by_date'][date][mint] = {'in': 0, 'out': 0}

                if direction == 'in':
                    flows['by_date'][date][mint]['in'] += amount
                elif direction == 'out':
                    flows['by_date'][date][mint]['out'] += amount

        return flows

    def prepare_sankey_data(self, flows: Dict, top_n: int = 10) -> Dict:
        """
        Prepare data for Sankey diagram

        Args:
            flows: Aggregated flow data
            top_n: Number of top tokens to include

        Returns:
            Dict with source, target, value for Sankey
        """
        # Get top tokens by total flow
        by_token = flows.get('by_token', {})
        sorted_tokens = sorted(
            by_token.items(),
            key=lambda x: x[1]['in'] + x[1]['out'],
            reverse=True
        )[:top_n]

        sources = []
        targets = []
        values = []
        labels = set()

        # Create flows
        for mint, data in sorted_tokens:
            if data['in'] > 0:
                sources.append('Incoming')
                targets.append(mint[:8] + '...')
                values.append(data['in'])
                labels.add('Incoming')
                labels.add(mint[:8] + '...')

            if data['out'] > 0:
                sources.append(mint[:8] + '...')
                targets.append('Outgoing')
                values.append(data['out'])
                labels.add(mint[:8] + '...')
                labels.add('Outgoing')

        # Create label index mapping
        label_list = list(labels)
        label_to_index = {label: i for i, label in enumerate(label_list)}

        source_indices = [label_to_index[s] for s in sources]
        target_indices = [label_to_index[t] for t in targets]

        return {
            'labels': label_list,
            'sources': source_indices,
            'targets': target_indices,
            'values': values
        }

    def prepare_timeseries_data(self, flows: Dict) -> Dict:
        """
        Prepare data for time series visualization

        Args:
            flows: Aggregated flow data

        Returns:
            Dict with dates and token flows
        """
        by_date = flows.get('by_date', {})

        # Get all unique tokens
        all_tokens = set()
        for date_data in by_date.values():
            all_tokens.update(date_data.keys())

        # Sort dates
        sorted_dates = sorted(by_date.keys())

        # Prepare series for each token
        series = {}
        for token in all_tokens:
            series[token] = {
                'dates': [],
                'in': [],
                'out': [],
                'net': []
            }

        for date in sorted_dates:
            date_data = by_date[date]
            for token in all_tokens:
                token_data = date_data.get(token, {'in': 0, 'out': 0})
                series[token]['dates'].append(date)
                series[token]['in'].append(token_data['in'])
                series[token]['out'].append(token_data['out'])
                series[token]['net'].append(token_data['in'] - token_data['out'])

        return {
            'dates': sorted_dates,
            'series': series,
            'all_tokens': list(all_tokens)
        }
