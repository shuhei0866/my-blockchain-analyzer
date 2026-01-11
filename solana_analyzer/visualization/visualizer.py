"""Visualization module for Solana transaction analysis"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime


class SolanaVisualizer:
    """Visualize Solana transaction and balance data"""

    def __init__(self, style: str = 'seaborn-v0_8-darkgrid'):
        """
        Initialize visualizer

        Args:
            style: Matplotlib style to use
        """
        try:
            plt.style.use(style)
        except:
            plt.style.use('default')

    def plot_balance_history(
        self,
        balance_histories: Dict[str, List[Dict[str, Any]]],
        output_dir: Optional[str] = None,
        show: bool = True
    ):
        """
        Plot token balance histories

        Args:
            balance_histories: Dictionary of balance histories by token
            output_dir: Optional directory to save plots
            show: Whether to display plots
        """
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

        for mint, history in balance_histories.items():
            if not history:
                continue

            df = pd.DataFrame(history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            fig, ax = plt.subplots(figsize=(12, 6))

            ax.plot(df['timestamp'], df['balance'], linewidth=2, marker='o', markersize=3)

            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Balance', fontsize=12)

            token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
            ax.set_title(f'Token Balance History - {token_name}', fontsize=14, fontweight='bold')

            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45, ha='right')

            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            if output_dir:
                safe_name = mint.replace('/', '_')[:50]
                filepath = output_path / f"balance_history_{safe_name}.png"
                plt.savefig(filepath, dpi=300, bbox_inches='tight')
                print(f"Saved plot: {filepath}")

            if show:
                plt.show()
            else:
                plt.close()

    def plot_daily_balances(
        self,
        daily_balances: Dict[str, List[Dict[str, Any]]],
        output_dir: Optional[str] = None,
        show: bool = True
    ):
        """
        Plot daily balance snapshots

        Args:
            daily_balances: Dictionary of daily balances by token
            output_dir: Optional directory to save plots
            show: Whether to display plots
        """
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

        for mint, daily in daily_balances.items():
            if not daily:
                continue

            df = pd.DataFrame(daily)
            df['date'] = pd.to_datetime(df['date'])

            fig, ax = plt.subplots(figsize=(12, 6))

            ax.plot(df['date'], df['balance'], linewidth=2, marker='o', markersize=4)
            ax.fill_between(df['date'], df['balance'], alpha=0.3)

            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Balance', fontsize=12)

            token_name = mint if mint == 'SOL' else f"{mint[:8]}..."
            ax.set_title(f'Daily Balance Snapshot - {token_name}', fontsize=14, fontweight='bold')

            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45, ha='right')

            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            if output_dir:
                safe_name = mint.replace('/', '_')[:50]
                filepath = output_path / f"daily_balance_{safe_name}.png"
                plt.savefig(filepath, dpi=300, bbox_inches='tight')
                print(f"Saved plot: {filepath}")

            if show:
                plt.show()
            else:
                plt.close()

    def plot_token_flows(
        self,
        token_flows: Dict[str, Dict[str, float]],
        output_path: Optional[str] = None,
        show: bool = True,
        top_n: int = 10
    ):
        """
        Plot token flow analysis (incoming vs outgoing)

        Args:
            token_flows: Dictionary of token flow data
            output_path: Optional filepath to save plot
            show: Whether to display plot
            top_n: Show only top N tokens by total volume
        """
        if not token_flows:
            print("No token flows to visualize")
            return

        flow_data = []
        for mint, flows in token_flows.items():
            total_volume = flows['total_received'] + flows['total_sent']
            flow_data.append({
                'mint': mint,
                'received': flows['total_received'],
                'sent': flows['total_sent'],
                'net_change': flows['net_change'],
                'total_volume': total_volume,
            })

        df = pd.DataFrame(flow_data)
        df = df.sort_values('total_volume', ascending=False).head(top_n)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        x = range(len(df))
        width = 0.35

        token_labels = [
            mint if mint == 'SOL' else f"{mint[:8]}..."
            for mint in df['mint']
        ]

        ax1.bar([i - width/2 for i in x], df['received'], width, label='Received', color='green', alpha=0.7)
        ax1.bar([i + width/2 for i in x], df['sent'], width, label='Sent', color='red', alpha=0.7)

        ax1.set_xlabel('Token', fontsize=12)
        ax1.set_ylabel('Amount', fontsize=12)
        ax1.set_title('Token Flows - Received vs Sent', fontsize=14, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(token_labels, rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3, axis='y')

        colors = ['green' if val >= 0 else 'red' for val in df['net_change']]
        ax2.barh(token_labels, df['net_change'], color=colors, alpha=0.7)

        ax2.set_xlabel('Net Change', fontsize=12)
        ax2.set_ylabel('Token', fontsize=12)
        ax2.set_title('Token Net Change', fontsize=14, fontweight='bold')
        ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
        ax2.grid(True, alpha=0.3, axis='x')

        plt.tight_layout()

        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"Saved plot: {output_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def plot_transaction_timeline(
        self,
        balance_histories: Dict[str, List[Dict[str, Any]]],
        output_path: Optional[str] = None,
        show: bool = True
    ):
        """
        Plot transaction timeline showing all token changes

        Args:
            balance_histories: Dictionary of balance histories by token
            output_path: Optional filepath to save plot
            show: Whether to display plot
        """
        all_transactions = []

        for mint, history in balance_histories.items():
            for record in history:
                all_transactions.append({
                    'timestamp': pd.to_datetime(record['timestamp']),
                    'mint': mint,
                    'change': record['change'],
                })

        if not all_transactions:
            print("No transactions to visualize")
            return

        df = pd.DataFrame(all_transactions)
        df = df.sort_values('timestamp')

        fig, ax = plt.subplots(figsize=(14, 8))

        for mint in df['mint'].unique():
            mint_df = df[df['mint'] == mint]
            colors = ['green' if c > 0 else 'red' for c in mint_df['change']]

            token_label = mint if mint == 'SOL' else f"{mint[:8]}..."

            ax.scatter(
                mint_df['timestamp'],
                mint_df['change'],
                c=colors,
                label=token_label,
                alpha=0.6,
                s=100
            )

        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Change Amount', fontsize=12)
        ax.set_title('Transaction Timeline - Token Changes', fontsize=14, fontweight='bold')

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45, ha='right')

        ax.grid(True, alpha=0.3)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

        plt.tight_layout()

        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"Saved plot: {output_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def create_summary_report(
        self,
        analysis_results: Dict[str, Any],
        output_dir: str = "output"
    ):
        """
        Create a complete visual report of the analysis

        Args:
            analysis_results: Analysis results from the backend API
            output_dir: Directory to save all plots
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("\n=== Creating Visual Report ===\n")

        balance_histories = analysis_results.get('balance_histories', {})
        daily_balances = analysis_results.get('daily_balances', {})
        summary = analysis_results.get('summary', {})

        print("Plotting balance histories...")
        self.plot_balance_history(
            balance_histories,
            output_dir=str(output_path / "balance_histories"),
            show=False
        )

        print("\nPlotting daily balances...")
        self.plot_daily_balances(
            daily_balances,
            output_dir=str(output_path / "daily_balances"),
            show=False
        )

        print("\nPlotting token flows...")
        if 'token_flows' in summary:
            self.plot_token_flows(
                summary['token_flows'],
                output_path=str(output_path / "token_flows.png"),
                show=False
            )

        print("\nPlotting transaction timeline...")
        self.plot_transaction_timeline(
            balance_histories,
            output_path=str(output_path / "transaction_timeline.png"),
            show=False
        )

        print(f"\n=== Report Complete ===")
        print(f"All visualizations saved to: {output_path}\n")
