"""Main Analyzer API - Backend interface for Solana address analysis"""
import asyncio
import json
from typing import Dict, Any, Optional
from pathlib import Path
from .transaction_analyzer import TransactionAnalyzer
from .balance_tracker import BalanceTracker


class SolanaAnalyzerAPI:
    """
    Main API for analyzing Solana addresses
    This serves as the backend interface that can be used by web applications
    """

    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        """
        Initialize the Analyzer API

        Args:
            rpc_url: Solana RPC endpoint URL
        """
        self.rpc_url = rpc_url
        self.transaction_analyzer = TransactionAnalyzer(rpc_url)
        self.balance_tracker = BalanceTracker()

    async def analyze_address(
        self,
        address: str,
        limit: int = 1000,
        fetch_details: bool = True,
        save_to_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a Solana address

        Args:
            address: Solana address to analyze
            limit: Maximum number of transactions to fetch
            fetch_details: Whether to fetch full transaction details
            save_to_file: Optional filepath to save results

        Returns:
            Dictionary containing analysis results
        """
        print(f"\n=== Analyzing Solana Address ===")
        print(f"Address: {address}")
        print(f"Transaction limit: {limit}")
        print(f"Fetching details: {fetch_details}\n")

        raw_data = await self.transaction_analyzer.fetch_and_analyze_transactions(
            address=address,
            limit=limit,
            fetch_details=fetch_details
        )

        print("\nGenerating transaction summary...")
        summary = self.transaction_analyzer.generate_transaction_summary(raw_data)

        print("Calculating balance history...")
        balance_histories = self.balance_tracker.calculate_balance_history(
            raw_data['transactions'],
            address,
            raw_data.get('current_balances')
        )

        print("Calculating daily balances...")
        daily_balances = self.balance_tracker.calculate_daily_balances(balance_histories)

        balance_history_data = {}
        for mint, df in balance_histories.items():
            balance_history_data[mint] = df.to_dict('records')

        daily_balance_data = {}
        for mint, df in daily_balances.items():
            daily_balance_data[mint] = df.to_dict('records')

        result = {
            'summary': summary,
            'balance_histories': balance_history_data,
            'daily_balances': daily_balance_data,
            'raw_data': {
                'address': raw_data['address'],
                'total_transactions': raw_data['total_transactions'],
                'analyzed_at': raw_data['analyzed_at'],
            }
        }

        if save_to_file:
            self._save_results(result, save_to_file)
            print(f"\nResults saved to: {save_to_file}")

        print("\n=== Analysis Complete ===\n")

        return result

    def _save_results(self, results: Dict[str, Any], filepath: str):
        """
        Save analysis results to a JSON file

        Args:
            results: Analysis results dictionary
            filepath: Path to save the file
        """
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        save_data = {
            'summary': results['summary'],
            'balance_histories': results['balance_histories'],
            'daily_balances': results['daily_balances'],
            'raw_data': results['raw_data'],
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)

    def load_results(self, filepath: str) -> Dict[str, Any]:
        """
        Load previously saved analysis results

        Args:
            filepath: Path to the saved results file

        Returns:
            Analysis results dictionary
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def get_address_summary(self, address: str) -> Dict[str, Any]:
        """
        Get a quick summary of an address without full transaction details

        Args:
            address: Solana address to summarize

        Returns:
            Summary dictionary
        """
        raw_data = await self.transaction_analyzer.fetch_and_analyze_transactions(
            address=address,
            limit=100,
            fetch_details=False
        )

        return {
            'address': address,
            'total_transactions': raw_data['total_transactions'],
            'current_balances': raw_data.get('current_balances', {}),
        }

    async def get_token_flow_analysis(
        self,
        address: str,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Get token flow analysis for an address

        Args:
            address: Solana address to analyze
            limit: Maximum number of transactions to fetch

        Returns:
            Token flow analysis dictionary
        """
        raw_data = await self.transaction_analyzer.fetch_and_analyze_transactions(
            address=address,
            limit=limit,
            fetch_details=True
        )

        token_flows = self.transaction_analyzer.analyze_token_flows(
            raw_data['transactions'],
            address
        )

        return {
            'address': address,
            'token_flows': token_flows,
            'total_transactions': raw_data['total_transactions'],
        }


def analyze_address_sync(
    address: str,
    limit: int = 1000,
    rpc_url: str = "https://api.mainnet-beta.solana.com",
    save_to_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for address analysis

    Args:
        address: Solana address to analyze
        limit: Maximum number of transactions to fetch
        rpc_url: Solana RPC endpoint URL
        save_to_file: Optional filepath to save results

    Returns:
        Analysis results dictionary
    """
    api = SolanaAnalyzerAPI(rpc_url)
    return asyncio.run(api.analyze_address(
        address=address,
        limit=limit,
        save_to_file=save_to_file
    ))
