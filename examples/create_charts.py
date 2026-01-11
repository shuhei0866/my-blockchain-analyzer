#!/usr/bin/env python3
"""Create visualizations from saved balance data"""
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from datetime import datetime


def create_visualizations(balance_file: str = "data/balance.json",
                         cache_db: str = "data/solana_cache.db",
                         output_dir: str = "output/charts"):
    """Create visualizations from saved data"""
    print(f"\n{'='*70}")
    print("  Creating Visualizations")
    print(f"{'='*70}\n")

    # Load balance data
    print(f"📂 Loading data from {balance_file}...")
    with open(balance_file, 'r') as f:
        data = json.load(f)

    address = data['address']
    balances = data['current_balances']

    print(f"✓ Address: {address}")
    print(f"✓ Tokens: {len(balances)}\n")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Sort balances
    balances_sorted = sorted(
        balances.items(),
        key=lambda x: float(x[1].get('ui_amount', 0) or 0),
        reverse=True
    )

    # Filter non-zero
    non_zero = [(mint, balance) for mint, balance in balances_sorted
                if float(balance.get('ui_amount', 0) or 0) > 0]

    print(f"📊 Creating {3} visualizations...\n")

    # 1. Top 10 Tokens - Horizontal Bar Chart
    top_10 = non_zero[:10]
    if top_10:
        fig, ax = plt.subplots(figsize=(14, 8))

        tokens = [mint if mint == 'SOL' else f"{mint[:8]}..." for mint, _ in top_10]
        amounts = [float(balance.get('ui_amount', 0) or 0) for _, balance in top_10]

        # Solana brand colors
        colors = ['#14F195' if mint == 'SOL' else '#9945FF' for mint, _ in top_10]

        bars = ax.barh(tokens, amounts, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

        ax.set_xlabel('Amount', fontsize=14, fontweight='bold')
        ax.set_ylabel('Token', fontsize=14, fontweight='bold')
        ax.set_title(f'Top 10 Token Holdings\\n{address[:20]}...{address[-12:]}',
                    fontsize=16, fontweight='bold', pad=20)

        # Add value labels
        for bar, amount in zip(bars, amounts):
            if amount > 0:
                label = f'{amount:,.2f}' if amount < 1000 else f'{amount:,.0f}'
                ax.text(amount, bar.get_y() + bar.get_height()/2,
                       f'  {label}',
                       va='center', fontsize=11, fontweight='bold')

        ax.grid(True, alpha=0.2, axis='x', linestyle='--')
        ax.set_axisbelow(True)
        plt.tight_layout()

        filepath = output_path / "1_top_10_tokens.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Created: {filepath.name}")
        plt.close()

    # 2. Token Distribution - Pie Chart
    if len(non_zero) > 1:
        fig, ax = plt.subplots(figsize=(12, 12))

        # Show top 10 + others
        top_n = 10
        if len(non_zero) > top_n:
            top_tokens = non_zero[:top_n]
            others_sum = sum(float(b.get('ui_amount', 0) or 0) for _, b in non_zero[top_n:])
            labels = [mint if mint == 'SOL' else f"{mint[:6]}..." for mint, _ in top_tokens]
            labels.append(f'Others\\n({len(non_zero) - top_n} tokens)')
            sizes = [float(b.get('ui_amount', 0) or 0) for _, b in top_tokens]
            sizes.append(others_sum)
        else:
            labels = [mint if mint == 'SOL' else f"{mint[:6]}..." for mint, _ in non_zero]
            sizes = [float(b.get('ui_amount', 0) or 0) for _, b in non_zero]

        # Custom colors - Solana theme
        colors = ['#14F195', '#9945FF', '#00D4AA', '#FF6B6B', '#4ECDC4',
                 '#FFD93D', '#6BCF7F', '#C084FC', '#FB923C', '#38BDF8', '#D946EF']

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct=lambda pct: f'{pct:.1f}%' if pct > 2 else '',
            startangle=45,
            colors=colors,
            pctdistance=0.85,
            explode=[0.05] + [0]*(len(sizes)-1),  # Explode first slice
            shadow=True
        )

        for text in texts:
            text.set_fontsize(10)
            text.set_fontweight('bold')

        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(10)

        ax.set_title(f'Token Distribution\\n{address[:20]}...{address[-12:]}\\n'
                    f'Total: {len(balances)} tokens ({len(non_zero)} non-zero)',
                    fontsize=16, fontweight='bold', pad=25)

        plt.tight_layout()

        filepath = output_path / "2_token_distribution.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Created: {filepath.name}")
        plt.close()

    # 3. Token Count Overview
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # Left: Token count by category
    total = len(balances)
    has_balance = len(non_zero)
    zero_balance = total - has_balance

    categories = ['Non-Zero\\nBalance', 'Zero\\nBalance']
    counts = [has_balance, zero_balance]
    colors_cat = ['#14F195', '#9945FF']

    bars = ax1.bar(categories, counts, color=colors_cat, alpha=0.8, edgecolor='black', linewidth=1.5)

    ax1.set_ylabel('Number of Tokens', fontsize=13, fontweight='bold')
    ax1.set_title('Token Portfolio Overview', fontsize=15, fontweight='bold', pad=15)

    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, height,
                f'{count}\\n({count/total*100:.1f}%)',
                ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax1.grid(True, alpha=0.2, axis='y', linestyle='--')
    ax1.set_axisbelow(True)

    # Right: Top 5 tokens value comparison
    top_5 = non_zero[:5]
    if top_5:
        tokens_5 = [mint if mint == 'SOL' else f"{mint[:8]}..." for mint, _ in top_5]
        amounts_5 = [float(balance.get('ui_amount', 0) or 0) for _, balance in top_5]

        bars2 = ax2.bar(range(len(tokens_5)), amounts_5,
                       color=['#14F195', '#9945FF', '#00D4AA', '#FF6B6B', '#4ECDC4'][:len(tokens_5)],
                       alpha=0.8, edgecolor='black', linewidth=1.5)

        ax2.set_ylabel('Amount', fontsize=13, fontweight='bold')
        ax2.set_xlabel('Token', fontsize=13, fontweight='bold')
        ax2.set_title('Top 5 Holdings', fontsize=15, fontweight='bold', pad=15)
        ax2.set_xticks(range(len(tokens_5)))
        ax2.set_xticklabels(tokens_5, rotation=15, ha='right')

        for bar, amount in zip(bars2, amounts_5):
            label = f'{amount:,.0f}' if amount > 100 else f'{amount:,.2f}'
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    label, ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax2.grid(True, alpha=0.2, axis='y', linestyle='--')
        ax2.set_axisbelow(True)

    plt.tight_layout()

    filepath = output_path / "3_portfolio_overview.png"
    plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Created: {filepath.name}")
    plt.close()

    # 4. Transaction activity from cache
    try:
        import sqlite3
        conn = sqlite3.connect(cache_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT block_time FROM signatures
            WHERE address = ?
            ORDER BY block_time
        """, (address,))

        timestamps = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()

        if timestamps:
            import pandas as pd

            dates = [datetime.fromtimestamp(ts).date() for ts in timestamps]
            date_counts = pd.Series(dates).value_counts().sort_index()

            fig, ax = plt.subplots(figsize=(15, 7))

            ax.plot(date_counts.index, date_counts.values, marker='o',
                   linewidth=3, markersize=8, color='#14F195', markeredgecolor='black',
                   markeredgewidth=1.5)
            ax.fill_between(date_counts.index, date_counts.values, alpha=0.3, color='#14F195')

            ax.set_xlabel('Date', fontsize=13, fontweight='bold')
            ax.set_ylabel('Number of Transactions', fontsize=13, fontweight='bold')
            ax.set_title(f'Transaction Activity Timeline\\n{address[:20]}...{address[-12:]}',
                        fontsize=16, fontweight='bold', pad=20)

            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_axisbelow(True)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            filepath = output_path / "4_transaction_timeline.png"
            plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
            print(f"✓ Created: {filepath.name}")
            plt.close()

    except Exception as e:
        print(f"  (Skipped transaction timeline: {e})")

    print(f"\n{'='*70}")
    print(f"✅ All visualizations saved to: {output_path.absolute()}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    import sys

    balance_file = sys.argv[1] if len(sys.argv) > 1 else "data/balance.json"
    cache_db = sys.argv[2] if len(sys.argv) > 2 else "data/solana_cache.db"
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "output/charts"

    create_visualizations(balance_file, cache_db, output_dir)
