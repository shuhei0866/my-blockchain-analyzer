#!/usr/bin/env python3
"""Visualize current token balances"""
import asyncio
import sys
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from solana_analyzer.backend.cached_analyzer import CachedTransactionAnalyzer


async def visualize_balances(address: str, output_dir: str = "output/balance_viz"):
    """Visualize current token balances"""
    print(f"\n{'='*70}")
    print("  Token Balance Visualization")
    print(f"{'='*70}\n")

    analyzer = CachedTransactionAnalyzer()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get current balances
    print("📊 Fetching current balances...")
    try:
        balances = await analyzer.get_current_balances(address)
        print(f"✓ Found {len(balances)} tokens\n")
    except Exception as e:
        print(f"❌ Error fetching balances: {e}")
        # Try from cache
        stats = analyzer.get_cache_stats(address)
        if stats['metadata'] and stats['metadata']['current_balances']:
            balances = stats['metadata']['current_balances']
            print(f"✓ Using cached balances: {len(balances)} tokens\n")
        else:
            analyzer.close()
            return

    # Sort by value
    balances_sorted = sorted(
        balances.items(),
        key=lambda x: float(x[1].get('ui_amount', 0) or 0),
        reverse=True
    )

    # Print top tokens
    print("Top 20 Token Holdings:")
    print(f"{'-'*70}")
    for i, (mint, balance) in enumerate(balances_sorted[:20], 1):
        token_name = mint if mint == 'SOL' else f"{mint[:8]}...{mint[-4:]}"
        amount = balance.get('ui_amount', 0)
        if amount and amount > 0:
            print(f"{i:2d}. {token_name:25s} {amount:>20,.8f}")

    # Create visualizations
    print(f"\n📈 Creating visualizations...\n")

    # 1. Top 10 Tokens - Bar Chart
    top_10 = balances_sorted[:10]
    if top_10:
        fig, ax = plt.subplots(figsize=(12, 8))

        tokens = [mint if mint == 'SOL' else f"{mint[:8]}..." for mint, _ in top_10]
        amounts = [float(balance.get('ui_amount', 0) or 0) for _, balance in top_10]

        colors = ['#14F195' if mint == 'SOL' else '#9945FF' for mint, _ in top_10]

        bars = ax.barh(tokens, amounts, color=colors, alpha=0.7)

        ax.set_xlabel('Amount', fontsize=12, fontweight='bold')
        ax.set_ylabel('Token', fontsize=12, fontweight='bold')
        ax.set_title(f'Top 10 Token Holdings\n{address[:16]}...{address[-8:]}',
                    fontsize=14, fontweight='bold', pad=20)

        # Add value labels
        for i, (bar, amount) in enumerate(zip(bars, amounts)):
            if amount > 0:
                ax.text(amount, bar.get_y() + bar.get_height()/2,
                       f' {amount:,.2f}',
                       va='center', fontsize=9)

        ax.grid(True, alpha=0.3, axis='x')
        plt.tight_layout()

        filepath = output_path / "top_10_tokens.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {filepath}")
        plt.close()

    # 2. Token Distribution - Pie Chart (non-zero balances)
    non_zero = [(mint, balance) for mint, balance in balances_sorted
                if float(balance.get('ui_amount', 0) or 0) > 0]

    if len(non_zero) > 1:
        fig, ax = plt.subplots(figsize=(10, 10))

        # Show top 8 + others
        top_n = 8
        if len(non_zero) > top_n:
            top_tokens = non_zero[:top_n]
            others_sum = sum(float(b.get('ui_amount', 0) or 0) for _, b in non_zero[top_n:])
            labels = [mint if mint == 'SOL' else f"{mint[:8]}..." for mint, _ in top_tokens]
            labels.append(f'Others ({len(non_zero) - top_n} tokens)')
            sizes = [float(b.get('ui_amount', 0) or 0) for _, b in top_tokens]
            sizes.append(others_sum)
        else:
            labels = [mint if mint == 'SOL' else f"{mint[:8]}..." for mint, _ in non_zero]
            sizes = [float(b.get('ui_amount', 0) or 0) for _, b in non_zero]

        # Normalize to percentages
        total = sum(sizes)
        percentages = [(s/total)*100 for s in sizes]

        colors = plt.cm.Set3(range(len(labels)))

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct=lambda pct: f'{pct:.1f}%' if pct > 3 else '',
            startangle=90,
            colors=colors,
            pctdistance=0.85
        )

        for text in texts:
            text.set_fontsize(9)
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(8)

        ax.set_title(f'Token Distribution\n{address[:16]}...{address[-8:]}\n'
                    f'Total: {len(balances)} tokens',
                    fontsize=14, fontweight='bold', pad=20)

        plt.tight_layout()

        filepath = output_path / "token_distribution.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {filepath}")
        plt.close()

    # 3. Transaction count from cache
    stats = analyzer.get_cache_stats(address)
    if stats['cached_signatures'] > 0:
        signatures = analyzer.cache.get_cached_signatures(address, limit=1000)

        # Group by date
        from datetime import datetime
        import pandas as pd

        dates = []
        for sig in signatures:
            if sig['block_time']:
                dates.append(datetime.fromtimestamp(sig['block_time']).date())

        if dates:
            date_counts = pd.Series(dates).value_counts().sort_index()

            fig, ax = plt.subplots(figsize=(14, 6))

            ax.plot(date_counts.index, date_counts.values, marker='o',
                   linewidth=2, markersize=6, color='#14F195')
            ax.fill_between(date_counts.index, date_counts.values, alpha=0.3, color='#14F195')

            ax.set_xlabel('Date', fontsize=12, fontweight='bold')
            ax.set_ylabel('Number of Transactions', fontsize=12, fontweight='bold')
            ax.set_title(f'Transaction Activity Over Time\n{address[:16]}...{address[-8:]}',
                        fontsize=14, fontweight='bold', pad=20)

            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            filepath = output_path / "transaction_timeline.png"
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            print(f"✓ Saved: {filepath}")
            plt.close()

    print(f"\n{'='*70}")
    print(f"✅ All visualizations saved to: {output_path}")
    print(f"{'='*70}\n")

    analyzer.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python visualize_balance.py <SOLANA_ADDRESS> [output_dir]")
        sys.exit(1)

    address = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output/balance_viz"

    asyncio.run(visualize_balances(address, output_dir))
