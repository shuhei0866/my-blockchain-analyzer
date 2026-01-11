#!/usr/bin/env python3
"""Create visualizations with token symbols"""
import json
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_analyzer.backend.token_registry import TokenRegistry


def create_visualizations_v2(balance_file: str = "data/balance.json",
                             cache_db: str = "data/solana_cache.db",
                             output_dir: str = "output/charts_v2"):
    """Create visualizations with token symbols"""
    print(f"\n{'='*70}")
    print("  Creating Visualizations (With Token Symbols)")
    print(f"{'='*70}\n")

    # Initialize token registry
    registry = TokenRegistry()
    stats = registry.get_stats()
    print(f"Token Registry: {stats['total_tokens']} tokens loaded\n")

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

    print(f"📊 Creating visualizations with token symbols...\n")

    # 1. Top 10 Tokens - Horizontal Bar Chart with Symbols
    top_10 = non_zero[:10]
    if top_10:
        fig, ax = plt.subplots(figsize=(14, 8))

        # Get symbols
        token_labels = []
        for mint, _ in top_10:
            symbol = registry.get_symbol(mint)
            name = registry.get_name(mint)
            # Format: "SYMBOL (Name)" or just "SYMBOL" if name is same
            if name and name != symbol and len(name) < 20:
                label = f"{symbol} ({name})"
            else:
                label = symbol
            token_labels.append(label)

        amounts = [float(balance.get('ui_amount', 0) or 0) for _, balance in top_10]

        # Colors
        colors = ['#14F195' if mint == 'SOL' else '#9945FF' for mint, _ in top_10]

        bars = ax.barh(token_labels, amounts, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

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

        filepath = output_path / "1_top_10_tokens_symbols.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Created: {filepath.name}")
        plt.close()

    # 2. Token Distribution - Pie Chart with Symbols
    if len(non_zero) > 1:
        fig, ax = plt.subplots(figsize=(12, 12))

        top_n = 10
        if len(non_zero) > top_n:
            top_tokens = non_zero[:top_n]
            others_sum = sum(float(b.get('ui_amount', 0) or 0) for _, b in non_zero[top_n:])
            labels = [registry.get_symbol(mint) for mint, _ in top_tokens]
            labels.append(f'Others\\n({len(non_zero) - top_n})')
            sizes = [float(b.get('ui_amount', 0) or 0) for _, b in top_tokens]
            sizes.append(others_sum)
        else:
            labels = [registry.get_symbol(mint) for mint, _ in non_zero]
            sizes = [float(b.get('ui_amount', 0) or 0) for _, b in non_zero]

        colors = ['#14F195', '#9945FF', '#00D4AA', '#FF6B6B', '#4ECDC4',
                 '#FFD93D', '#6BCF7F', '#C084FC', '#FB923C', '#38BDF8', '#D946EF']

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct=lambda pct: f'{pct:.1f}%' if pct > 2 else '',
            startangle=45,
            colors=colors,
            pctdistance=0.85,
            explode=[0.05] + [0]*(len(sizes)-1),
            shadow=True
        )

        for text in texts:
            text.set_fontsize(11)
            text.set_fontweight('bold')

        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(10)

        ax.set_title(f'Token Distribution\\n{address[:20]}...{address[-12:]}\\n'
                    f'Total: {len(balances)} tokens ({len(non_zero)} non-zero)',
                    fontsize=16, fontweight='bold', pad=25)

        plt.tight_layout()

        filepath = output_path / "2_token_distribution_symbols.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Created: {filepath.name}")
        plt.close()

    # 3. Detailed Token List with Symbols
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.axis('off')

    # Create table data
    table_data = []
    table_data.append(['Rank', 'Symbol', 'Name', 'Amount', 'Mint Address'])

    for i, (mint, balance) in enumerate(non_zero[:20], 1):
        symbol = registry.get_symbol(mint)
        name = registry.get_name(mint)
        amount = float(balance.get('ui_amount', 0) or 0)
        mint_short = mint if mint == 'SOL' else f"{mint[:8]}...{mint[-4:]}"

        amount_str = f'{amount:,.2f}' if amount < 1000 else f'{amount:,.0f}'

        table_data.append([
            str(i),
            symbol,
            name[:20] if len(name) > 20 else name,
            amount_str,
            mint_short
        ])

    table = ax.table(
        cellText=table_data,
        cellLoc='left',
        loc='center',
        colWidths=[0.08, 0.15, 0.35, 0.20, 0.22]
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)

    # Style header
    for i in range(5):
        cell = table[(0, i)]
        cell.set_facecolor('#9945FF')
        cell.set_text_props(weight='bold', color='white', fontsize=10)

    # Alternate row colors
    for i in range(1, len(table_data)):
        for j in range(5):
            cell = table[(i, j)]
            if i % 2 == 0:
                cell.set_facecolor('#F0F0F0')
            else:
                cell.set_facecolor('white')

    ax.set_title(f'Top 20 Token Holdings (Detailed)\\n{address}',
                fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()

    filepath = output_path / "3_token_details_table.png"
    plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Created: {filepath.name}")
    plt.close()

    # 4. Print formatted list
    print(f"\n{'='*70}")
    print("Token Holdings (with symbols)")
    print(f"{'='*70}")
    print(f"{'Rank':<5} {'Symbol':<12} {'Name':<25} {'Amount':>20}")
    print(f"{'-'*70}")

    for i, (mint, balance) in enumerate(non_zero[:20], 1):
        symbol = registry.get_symbol(mint)
        name = registry.get_name(mint)
        amount = float(balance.get('ui_amount', 0) or 0)

        name_display = name[:22] + "..." if len(name) > 25 else name

        print(f"{i:<5} {symbol:<12} {name_display:<25} {amount:>20,.2f}")

    print(f"\n{'='*70}")
    print(f"✅ All visualizations saved to: {output_path.absolute()}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    import sys

    balance_file = sys.argv[1] if len(sys.argv) > 1 else "data/balance.json"
    cache_db = sys.argv[2] if len(sys.argv) > 2 else "data/solana_cache.db"
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "output/charts_v2"

    create_visualizations_v2(balance_file, cache_db, output_dir)
