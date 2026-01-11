#!/usr/bin/env python3
"""
2025年トランザクション分析・可視化スクリプト

4つの可視化を生成:
1. 取引相手別サンキーダイアグラム
2. 累積フローチャート
3. カレンダーヒートマップ
4. 月別サマリー
"""
import sqlite3
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import calendar
import sys
import os

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_analyzer.backend.token_registry import TokenRegistry
from solana_analyzer.backend.price_fetcher import PriceFetcher, get_token_symbol

# 2025年の期間定義
YEAR_START = datetime(2025, 1, 1)
YEAR_END = datetime(2025, 12, 31, 23, 59, 59)


def load_transactions_2025(cache_db: str, address: str) -> list:
    """2025年のトランザクションをキャッシュから読み込む"""
    print(f"\n{'='*70}")
    print("  Loading 2025 Transactions from Cache")
    print(f"{'='*70}\n")

    conn = sqlite3.connect(cache_db)
    cursor = conn.cursor()

    # 2025年のUNIXタイムスタンプ範囲
    start_ts = int(YEAR_START.timestamp())
    end_ts = int(YEAR_END.timestamp())

    cursor.execute("""
        SELECT t.signature, t.transaction_data, t.block_time
        FROM transactions t
        WHERE t.address = ?
          AND t.block_time >= ?
          AND t.block_time <= ?
        ORDER BY t.block_time ASC
    """, (address, start_ts, end_ts))

    rows = cursor.fetchall()
    conn.close()

    transactions = []
    for signature, tx_data_str, block_time in rows:
        try:
            tx_data = json.loads(tx_data_str)
            transactions.append({
                'signature': signature,
                'data': tx_data,
                'block_time': block_time,
                'datetime': datetime.fromtimestamp(block_time)
            })
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse transaction {signature}: {e}")

    print(f"Found {len(transactions)} transactions in 2025")
    if transactions:
        print(f"  First: {transactions[0]['datetime'].strftime('%Y-%m-%d')}")
        print(f"  Last:  {transactions[-1]['datetime'].strftime('%Y-%m-%d')}")
    print()

    return transactions


def extract_counterparty_flows(transactions: list, target_address: str) -> dict:
    """
    トランザクションからカウンターパーティフローを抽出

    Returns:
        {
            'counterparties': {address: {'in': float, 'out': float, 'tokens': set}},
            'by_date': {date_str: {'in': float, 'out': float, 'tx_count': int}},
            'by_month': {month_str: {'in': float, 'out': float, 'tx_count': int}},
            'daily_volume': {date_str: float},
            'by_token': {mint: {'in': float, 'out': float}}
        }
    """
    result = {
        'counterparties': defaultdict(lambda: {'in': 0.0, 'out': 0.0, 'tokens': set()}),
        'by_date': defaultdict(lambda: {'in': 0.0, 'out': 0.0, 'tx_count': 0}),
        'by_month': defaultdict(lambda: {'in': 0.0, 'out': 0.0, 'tx_count': 0}),
        'daily_volume': defaultdict(float),
        'by_token': defaultdict(lambda: {'in': 0.0, 'out': 0.0}),
    }

    for tx in transactions:
        data = tx['data']
        dt = tx['datetime']
        date_str = dt.strftime('%Y-%m-%d')
        month_str = dt.strftime('%Y-%m')

        meta = data.get('meta', {})
        if meta.get('err'):
            continue  # Skip failed transactions

        pre_balances = {tb['account_index']: tb for tb in meta.get('pre_token_balances', [])}
        post_balances = {tb['account_index']: tb for tb in meta.get('post_token_balances', [])}

        # Track all balance changes
        all_indices = set(pre_balances.keys()) | set(post_balances.keys())

        for idx in all_indices:
            pre = pre_balances.get(idx, {})
            post = post_balances.get(idx, {})

            pre_amount = float((pre.get('ui_token_amount') or {}).get('ui_amount') or 0)
            post_amount = float((post.get('ui_token_amount') or {}).get('ui_amount') or 0)
            change = post_amount - pre_amount

            if abs(change) < 0.0000001:
                continue

            mint = post.get('mint') or pre.get('mint')
            owner = post.get('owner') or pre.get('owner')

            if not owner or not mint:
                continue

            if owner.lower() == target_address.lower():
                # This is our wallet
                if change > 0:
                    result['by_date'][date_str]['in'] += change
                    result['by_month'][month_str]['in'] += change
                    result['by_token'][mint]['in'] += change
                else:
                    result['by_date'][date_str]['out'] += abs(change)
                    result['by_month'][month_str]['out'] += abs(change)
                    result['by_token'][mint]['out'] += abs(change)
                result['daily_volume'][date_str] += abs(change)
            else:
                # This is a counterparty
                # If they lost tokens and we gained, they sent to us
                if change < 0:
                    result['counterparties'][owner]['out'] += abs(change)
                    result['counterparties'][owner]['tokens'].add(mint)
                elif change > 0:
                    result['counterparties'][owner]['in'] += change
                    result['counterparties'][owner]['tokens'].add(mint)

        # SOL balance changes
        pre_sol_balances = meta.get('pre_balances', [])
        post_sol_balances = meta.get('post_balances', [])
        account_keys = data.get('transaction', {}).get('message', {}).get('account_keys', [])

        for i, key in enumerate(account_keys):
            if i >= len(pre_sol_balances) or i >= len(post_sol_balances):
                continue

            pre_sol = pre_sol_balances[i] / 1e9
            post_sol = post_sol_balances[i] / 1e9
            change = post_sol - pre_sol

            if abs(change) < 0.0000001:
                continue

            if key.lower() == target_address.lower():
                if change > 0:
                    result['by_date'][date_str]['in'] += change
                    result['by_month'][month_str]['in'] += change
                    result['by_token']['SOL']['in'] += change
                else:
                    result['by_date'][date_str]['out'] += abs(change)
                    result['by_month'][month_str]['out'] += abs(change)
                    result['by_token']['SOL']['out'] += abs(change)
                result['daily_volume'][date_str] += abs(change)

        result['by_date'][date_str]['tx_count'] += 1
        result['by_month'][month_str]['tx_count'] += 1

    # Convert defaultdicts to regular dicts
    result['counterparties'] = {k: {'in': v['in'], 'out': v['out'], 'tokens': list(v['tokens'])}
                                for k, v in result['counterparties'].items()}
    result['by_date'] = dict(result['by_date'])
    result['by_month'] = dict(result['by_month'])
    result['daily_volume'] = dict(result['daily_volume'])
    result['by_token'] = dict(result['by_token'])

    return result


def create_counterparty_sankey(
    flows: dict,
    registry: TokenRegistry,
    output_file: str,
    top_n: int = 15,
    use_usd: bool = False,
    price_fetcher: PriceFetcher = None
):
    """取引相手別サンキーダイアグラムを作成"""
    print("Creating counterparty Sankey diagram...")

    counterparties = flows['counterparties']

    # Sort by total volume
    sorted_cp = sorted(
        counterparties.items(),
        key=lambda x: x[1]['in'] + x[1]['out'],
        reverse=True
    )[:top_n]

    if not sorted_cp:
        print("  No counterparty data found")
        return

    # Prepare nodes and links
    labels = []
    sources = []
    targets = []
    values = []
    customdata = []

    # Node indices:
    # 0: "From Others" (inflows)
    # 1: "Your Wallet"
    # 2: "To Others" (outflows)
    # 3+: Individual counterparties

    labels.append("Inflows from Others")
    labels.append("Your Wallet")
    labels.append("Outflows to Others")

    node_offset = 3

    for i, (addr, data) in enumerate(sorted_cp):
        short_addr = f"{addr[:6]}...{addr[-4:]}"
        labels.append(short_addr)

        cp_node = node_offset + i

        # Inflow: Counterparty -> Wallet (they sent tokens that left their account)
        if data['out'] > 0:
            sources.append(cp_node)
            targets.append(1)  # Your Wallet
            values.append(data['out'])
            customdata.append(f"{short_addr} sent")

        # Outflow: Wallet -> Counterparty (they received tokens)
        if data['in'] > 0:
            sources.append(1)  # Your Wallet
            targets.append(cp_node)
            values.append(data['in'])
            customdata.append(f"Sent to {short_addr}")

    # Add summary flows
    total_in = sum(d['out'] for _, d in sorted_cp)
    total_out = sum(d['in'] for _, d in sorted_cp)

    if total_in > 0:
        sources.append(0)  # Inflows
        targets.append(1)  # Wallet
        values.append(total_in)
        customdata.append("Total Inflows")

    if total_out > 0:
        sources.append(1)  # Wallet
        targets.append(2)  # Outflows
        values.append(total_out)
        customdata.append("Total Outflows")

    # Colors
    node_colors = [
        '#14F195',  # Inflows (green)
        '#9945FF',  # Your Wallet (purple)
        '#FF6B6B',  # Outflows (red)
    ] + ['#00D4AA'] * len(sorted_cp)  # Counterparties (teal)

    link_colors = []
    for s, t in zip(sources, targets):
        if t == 1:  # Inflows to wallet
            link_colors.append('rgba(20, 241, 149, 0.3)')
        else:  # Outflows from wallet
            link_colors.append('rgba(255, 107, 107, 0.3)')

    # Create figure
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=20,
            thickness=25,
            line=dict(color="black", width=1),
            label=labels,
            color=node_colors,
            hovertemplate='%{label}<br>Total: %{value:,.2f}<extra></extra>'
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            customdata=customdata,
            hovertemplate='%{customdata}<br>Amount: %{value:,.2f}<extra></extra>'
        )
    )])

    unit_label = "USD" if use_usd else "Token Units"
    fig.update_layout(
        title={
            'text': f"Counterparty Flow Analysis (2025)<br><sub>Top {len(sorted_cp)} counterparties by volume ({unit_label})</sub>",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20}
        },
        font_size=12,
        height=900,
        width=1500,
        plot_bgcolor='#f8f9fa',
        paper_bgcolor='white'
    )

    # Save
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path))

    print(f"  Created: {output_path}")


def create_cumulative_flow_chart(
    flows: dict,
    output_file: str,
    use_usd: bool = False
):
    """累積フローチャートを作成"""
    print("Creating cumulative flow chart...")

    by_date = flows['by_date']
    if not by_date:
        print("  No date data found")
        return

    # Sort dates and calculate cumulative values
    sorted_dates = sorted(by_date.keys())
    dates = [datetime.strptime(d, '%Y-%m-%d') for d in sorted_dates]

    cumulative_in = []
    cumulative_out = []
    cumulative_net = []
    running_in = 0
    running_out = 0

    for date_str in sorted_dates:
        data = by_date[date_str]
        running_in += data['in']
        running_out += data['out']
        cumulative_in.append(running_in)
        cumulative_out.append(running_out)
        cumulative_net.append(running_in - running_out)

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 8))

    ax.plot(dates, cumulative_in, color='#14F195', linewidth=2.5, label='Cumulative Inflows', marker='o', markersize=3)
    ax.plot(dates, cumulative_out, color='#FF6B6B', linewidth=2.5, label='Cumulative Outflows', marker='o', markersize=3)
    ax.plot(dates, cumulative_net, color='#9945FF', linewidth=2.5, label='Cumulative Net', marker='o', markersize=3)

    ax.fill_between(dates, cumulative_in, alpha=0.2, color='#14F195')
    ax.fill_between(dates, cumulative_out, alpha=0.2, color='#FF6B6B')

    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    ax.set_xlabel('Date', fontsize=14, fontweight='bold')
    unit_label = "USD" if use_usd else "Token Units"
    ax.set_ylabel(f'Cumulative Amount ({unit_label})', fontsize=14, fontweight='bold')
    ax.set_title('Cumulative Token Flows (2025)', fontsize=18, fontweight='bold', pad=20)

    ax.legend(loc='upper left', fontsize=12)
    ax.grid(True, alpha=0.3, linestyle='--')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.xticks(rotation=45, ha='right')

    plt.tight_layout()

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"  Created: {output_path}")


def create_calendar_heatmap(
    flows: dict,
    output_file: str
):
    """カレンダーヒートマップを作成"""
    print("Creating calendar heatmap...")

    daily_volume = flows['daily_volume']
    if not daily_volume:
        print("  No daily volume data found")
        return

    # Create figure with 12 subplots (one per month)
    fig, axes = plt.subplots(3, 4, figsize=(20, 15))
    axes = axes.flatten()

    # Get max value for consistent color scale
    max_volume = max(daily_volume.values()) if daily_volume else 1

    # Color map
    cmap = plt.cm.YlOrRd

    for month_idx in range(12):
        ax = axes[month_idx]
        month = month_idx + 1
        year = 2025

        # Get calendar for this month
        cal = calendar.Calendar(firstweekday=6)  # Sunday first
        month_days = cal.monthdayscalendar(year, month)

        # Create grid
        grid = np.zeros((len(month_days), 7))
        grid[:] = np.nan  # Use NaN for empty cells

        for week_idx, week in enumerate(month_days):
            for day_idx, day in enumerate(week):
                if day != 0:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    volume = daily_volume.get(date_str, 0)
                    grid[week_idx, day_idx] = volume

        # Plot
        masked_grid = np.ma.masked_invalid(grid)
        im = ax.imshow(masked_grid, cmap=cmap, vmin=0, vmax=max_volume, aspect='auto')

        # Add day numbers
        for week_idx, week in enumerate(month_days):
            for day_idx, day in enumerate(week):
                if day != 0:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    volume = daily_volume.get(date_str, 0)

                    # Text color based on background
                    text_color = 'white' if volume > max_volume * 0.5 else 'black'
                    ax.text(day_idx, week_idx, str(day),
                           ha='center', va='center', fontsize=8,
                           color=text_color, fontweight='bold')

        # Set title and labels
        ax.set_title(calendar.month_name[month], fontsize=12, fontweight='bold')
        ax.set_xticks(range(7))
        ax.set_xticklabels(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], fontsize=8)
        ax.set_yticks([])

        # Add border
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color('gray')

    # Add colorbar
    fig.subplots_adjust(right=0.9)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label('Daily Transaction Volume', fontsize=12, fontweight='bold')

    fig.suptitle('Transaction Activity Calendar Heatmap (2025)', fontsize=18, fontweight='bold', y=0.98)

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"  Created: {output_path}")


def create_monthly_summary(
    flows: dict,
    output_file: str,
    use_usd: bool = False
):
    """月別サマリーチャートを作成"""
    print("Creating monthly summary chart...")

    by_month = flows['by_month']
    if not by_month:
        print("  No monthly data found")
        return

    # Ensure all months are present
    months = []
    inflows = []
    outflows = []
    net_flows = []
    tx_counts = []

    for month in range(1, 13):
        month_str = f"2025-{month:02d}"
        months.append(calendar.month_abbr[month])
        data = by_month.get(month_str, {'in': 0, 'out': 0, 'tx_count': 0})
        inflows.append(data['in'])
        outflows.append(data['out'])
        net_flows.append(data['in'] - data['out'])
        tx_counts.append(data['tx_count'])

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), gridspec_kw={'height_ratios': [2, 1]})

    # Chart 1: Grouped bar chart for inflows/outflows
    x = np.arange(len(months))
    width = 0.35

    bars1 = ax1.bar(x - width/2, inflows, width, label='Inflows', color='#14F195', alpha=0.8)
    bars2 = ax1.bar(x + width/2, outflows, width, label='Outflows', color='#FF6B6B', alpha=0.8)

    # Add net flow line
    ax1_twin = ax1.twinx()
    ax1_twin.plot(x, net_flows, color='#9945FF', linewidth=3, marker='o', markersize=8, label='Net Flow')
    ax1_twin.axhline(y=0, color='black', linestyle='--', linewidth=1)

    ax1.set_xlabel('Month', fontsize=14, fontweight='bold')
    unit_label = "USD" if use_usd else "Token Units"
    ax1.set_ylabel(f'Amount ({unit_label})', fontsize=14, fontweight='bold')
    ax1_twin.set_ylabel(f'Net Flow ({unit_label})', fontsize=14, fontweight='bold', color='#9945FF')

    ax1.set_title('Monthly Token Flows (2025)', fontsize=18, fontweight='bold', pad=20)
    ax1.set_xticks(x)
    ax1.set_xticklabels(months, fontsize=12)
    ax1.legend(loc='upper left', fontsize=12)
    ax1_twin.legend(loc='upper right', fontsize=12)
    ax1.grid(True, alpha=0.3, axis='y', linestyle='--')

    # Add value labels on bars
    for bar, val in zip(bars1, inflows):
        if val > 0:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{val:,.0f}', ha='center', va='bottom', fontsize=8, rotation=45)

    for bar, val in zip(bars2, outflows):
        if val > 0:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f'{val:,.0f}', ha='center', va='bottom', fontsize=8, rotation=45)

    # Chart 2: Transaction count
    colors = ['#00D4AA' if c > 0 else '#cccccc' for c in tx_counts]
    ax2.bar(x, tx_counts, color=colors, alpha=0.8)
    ax2.set_xlabel('Month', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Transaction Count', fontsize=14, fontweight='bold')
    ax2.set_title('Monthly Transaction Count', fontsize=14, fontweight='bold', pad=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels(months, fontsize=12)
    ax2.grid(True, alpha=0.3, axis='y', linestyle='--')

    # Add count labels
    for i, count in enumerate(tx_counts):
        if count > 0:
            ax2.text(i, count, str(count), ha='center', va='bottom', fontsize=10, fontweight='bold')

    plt.tight_layout()

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"  Created: {output_path}")


def print_summary(flows: dict, registry: TokenRegistry):
    """分析サマリーを表示"""
    print(f"\n{'='*70}")
    print("  2025 Analysis Summary")
    print(f"{'='*70}\n")

    # By token summary
    by_token = flows['by_token']
    if by_token:
        print("Top Tokens by Volume:")
        print(f"{'Token':<15} {'Inflow':>15} {'Outflow':>15} {'Net':>15}")
        print("-" * 60)

        sorted_tokens = sorted(
            by_token.items(),
            key=lambda x: x[1]['in'] + x[1]['out'],
            reverse=True
        )[:15]

        for mint, data in sorted_tokens:
            symbol = registry.get_symbol(mint)
            net = data['in'] - data['out']
            print(f"{symbol:<15} {data['in']:>15,.2f} {data['out']:>15,.2f} {net:>15,.2f}")

    # Monthly summary
    by_month = flows['by_month']
    if by_month:
        print(f"\n{'='*70}")
        print("Monthly Summary:")
        print(f"{'Month':<10} {'Inflow':>15} {'Outflow':>15} {'Net':>15} {'Txs':>8}")
        print("-" * 60)

        for month in range(1, 13):
            month_str = f"2025-{month:02d}"
            data = by_month.get(month_str, {'in': 0, 'out': 0, 'tx_count': 0})
            net = data['in'] - data['out']
            print(f"{calendar.month_abbr[month]:<10} {data['in']:>15,.2f} {data['out']:>15,.2f} {net:>15,.2f} {data['tx_count']:>8}")

    # Counterparty summary
    counterparties = flows['counterparties']
    if counterparties:
        print(f"\n{'='*70}")
        print(f"Top Counterparties: {len(counterparties)} unique addresses")

        sorted_cp = sorted(
            counterparties.items(),
            key=lambda x: x[1]['in'] + x[1]['out'],
            reverse=True
        )[:10]

        print(f"{'Address':<20} {'Received':>12} {'Sent':>12} {'Tokens':>20}")
        print("-" * 70)
        for addr, data in sorted_cp:
            short_addr = f"{addr[:8]}...{addr[-4:]}"
            tokens = ', '.join(data['tokens'][:3])
            if len(data['tokens']) > 3:
                tokens += '...'
            print(f"{short_addr:<20} {data['in']:>12,.2f} {data['out']:>12,.2f} {tokens:>20}")


def main():
    parser = argparse.ArgumentParser(description='Analyze 2025 transactions')
    parser.add_argument('cache_db', help='Path to SQLite cache database')
    parser.add_argument('address', help='Solana address to analyze')
    parser.add_argument('--usd', action='store_true', help='Convert amounts to USD')
    parser.add_argument('--output-dir', default='output/2025', help='Output directory')

    args = parser.parse_args()

    print(f"\n{'='*70}")
    print("  2025 Transaction Analyzer")
    print(f"{'='*70}")
    print(f"Address: {args.address}")
    print(f"Database: {args.cache_db}")
    print(f"USD mode: {args.usd}")
    print(f"Output: {args.output_dir}")

    # Initialize
    registry = TokenRegistry()
    price_fetcher = PriceFetcher() if args.usd else None

    # Load transactions
    transactions = load_transactions_2025(args.cache_db, args.address)

    if not transactions:
        print("\nNo transactions found for 2025.")
        print("Make sure to fetch transactions first:")
        print(f"  python scripts/fetch_transactions.py {args.address} --limit 5000")
        return

    # Extract flows
    print("Extracting flows from transactions...")
    flows = extract_counterparty_flows(transactions, args.address)

    # Print summary
    print_summary(flows, registry)

    # Create visualizations
    print(f"\n{'='*70}")
    print("  Creating Visualizations")
    print(f"{'='*70}\n")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    create_counterparty_sankey(
        flows, registry,
        str(output_dir / "counterparty_sankey.html"),
        use_usd=args.usd,
        price_fetcher=price_fetcher
    )

    create_cumulative_flow_chart(
        flows,
        str(output_dir / "cumulative_flows.png"),
        use_usd=args.usd
    )

    create_calendar_heatmap(
        flows,
        str(output_dir / "calendar_heatmap.png")
    )

    create_monthly_summary(
        flows,
        str(output_dir / "monthly_summary.png"),
        use_usd=args.usd
    )

    print(f"\n{'='*70}")
    print(f"  All visualizations saved to: {output_dir.absolute()}")
    print(f"{'='*70}")
    print(f"\nFiles created:")
    print(f"  - counterparty_sankey.html (open in browser)")
    print(f"  - cumulative_flows.png")
    print(f"  - calendar_heatmap.png")
    print(f"  - monthly_summary.png")
    print()


if __name__ == '__main__':
    main()
