#!/usr/bin/env python3
"""Create token flow visualizations (Sankey diagram and time series)"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import plotly.graph_objects as go
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_analyzer.backend.transaction_parser import TransactionParser
from solana_analyzer.backend.token_registry import TokenRegistry


def load_transactions_from_cache(
    cache_db: str = "data/solana_cache.db",
    address: str = None
) -> list:
    """Load transactions from cache database"""
    print(f"\n{'='*70}")
    print("  Loading Transaction Data from Cache")
    print(f"{'='*70}\n")

    conn = sqlite3.connect(cache_db)
    cursor = conn.cursor()

    # Get transactions
    if address:
        cursor.execute("""
            SELECT t.signature, t.transaction_data
            FROM transactions t
            JOIN signatures s ON t.signature = s.signature
            WHERE s.address = ?
            ORDER BY s.block_time DESC
        """, (address,))
    else:
        cursor.execute("""
            SELECT signature, transaction_data
            FROM transactions
            ORDER BY id DESC
        """)

    rows = cursor.fetchall()
    conn.close()

    transactions = []
    for signature, tx_data_str in rows:
        try:
            tx_data = json.loads(tx_data_str)
            transactions.append({
                'signature': signature,
                'data': tx_data
            })
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse transaction {signature}: {e}")

    print(f"✓ Loaded {len(transactions)} transactions from cache\n")
    return transactions


def create_sankey_diagram(
    flows: dict,
    registry: TokenRegistry,
    output_file: str = "output/flows/sankey_diagram.html",
    top_n: int = 15
):
    """Create Sankey diagram for token flows"""
    print(f"📊 Creating Sankey diagram...")

    by_token = flows.get('by_token', {})

    # Get top tokens by total flow
    sorted_tokens = sorted(
        by_token.items(),
        key=lambda x: x[1]['in'] + x[1]['out'],
        reverse=True
    )[:top_n]

    # Prepare data
    labels = []
    sources = []
    targets = []
    values = []
    colors = []

    # Create nodes
    labels.append('Incoming Transfers')  # 0
    labels.append('Your Wallet')  # 1
    labels.append('Outgoing Transfers')  # 2

    node_offset = 3

    # Add token nodes and flows
    for i, (mint, data) in enumerate(sorted_tokens):
        symbol = registry.get_symbol(mint)
        labels.append(symbol)

        token_node = node_offset + i

        # Incoming flow: Incoming -> Token -> Wallet
        if data['in'] > 0:
            sources.append(0)  # Incoming
            targets.append(token_node)  # Token
            values.append(data['in'])

            sources.append(token_node)  # Token
            targets.append(1)  # Wallet
            values.append(data['in'])

        # Outgoing flow: Wallet -> Token -> Outgoing
        if data['out'] > 0:
            sources.append(1)  # Wallet
            targets.append(token_node)  # Token
            values.append(data['out'])

            sources.append(token_node)  # Token
            targets.append(2)  # Outgoing
            values.append(data['out'])

    # Create figure
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels,
            color=['#14F195', '#9945FF', '#FF6B6B'] + ['#00D4AA'] * (len(labels) - 3)
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color='rgba(153, 69, 255, 0.3)'
        )
    )])

    fig.update_layout(
        title_text="Token Flow Diagram",
        font_size=12,
        height=800,
        width=1400
    )

    # Save
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path))

    print(f"✓ Created: {output_path.name}")
    print(f"  Open in browser: {output_path.absolute()}\n")


def create_timeseries_charts(
    flows: dict,
    registry: TokenRegistry,
    output_dir: str = "output/flows",
    top_n: int = 10
):
    """Create time series charts for token flows"""
    print(f"📊 Creating time series charts...")

    by_date = flows.get('by_date', {})
    by_token = flows.get('by_token', {})

    if not by_date:
        print("⚠️  No date-based flow data available")
        return

    # Get top tokens
    sorted_tokens = sorted(
        by_token.items(),
        key=lambda x: x[1]['in'] + x[1]['out'],
        reverse=True
    )[:top_n]

    top_mints = [mint for mint, _ in sorted_tokens]

    # Prepare data
    dates = sorted(by_date.keys())
    date_objects = [datetime.strptime(d, '%Y-%m-%d') for d in dates]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Chart 1: Cumulative inflows by token
    fig, ax = plt.subplots(figsize=(16, 8))

    for mint in top_mints:
        symbol = registry.get_symbol(mint)
        inflows = []

        for date in dates:
            date_data = by_date.get(date, {})
            token_data = date_data.get(mint, {'in': 0, 'out': 0})
            inflows.append(token_data['in'])

        if sum(inflows) > 0:  # Only plot if there's data
            ax.plot(date_objects, inflows, marker='o', label=symbol, linewidth=2, markersize=5)

    ax.set_xlabel('Date', fontsize=14, fontweight='bold')
    ax.set_ylabel('Inflow Amount', fontsize=14, fontweight='bold')
    ax.set_title('Token Inflows Over Time (Top 10)', fontsize=16, fontweight='bold', pad=20)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    filepath = output_path / "1_token_inflows_timeseries.png"
    plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Created: {filepath.name}")
    plt.close()

    # Chart 2: Cumulative outflows by token
    fig, ax = plt.subplots(figsize=(16, 8))

    for mint in top_mints:
        symbol = registry.get_symbol(mint)
        outflows = []

        for date in dates:
            date_data = by_date.get(date, {})
            token_data = date_data.get(mint, {'in': 0, 'out': 0})
            outflows.append(token_data['out'])

        if sum(outflows) > 0:  # Only plot if there's data
            ax.plot(date_objects, outflows, marker='o', label=symbol, linewidth=2, markersize=5)

    ax.set_xlabel('Date', fontsize=14, fontweight='bold')
    ax.set_ylabel('Outflow Amount', fontsize=14, fontweight='bold')
    ax.set_title('Token Outflows Over Time (Top 10)', fontsize=16, fontweight='bold', pad=20)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    filepath = output_path / "2_token_outflows_timeseries.png"
    plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Created: {filepath.name}")
    plt.close()

    # Chart 3: Net flows (stacked area chart)
    fig, ax = plt.subplots(figsize=(16, 8))

    net_flows_by_token = {}
    for mint in top_mints:
        symbol = registry.get_symbol(mint)
        net_flows = []

        for date in dates:
            date_data = by_date.get(date, {})
            token_data = date_data.get(mint, {'in': 0, 'out': 0})
            net_flows.append(token_data['in'] - token_data['out'])

        net_flows_by_token[symbol] = net_flows

    # Prepare DataFrame for stacked area
    df = pd.DataFrame(net_flows_by_token, index=date_objects)

    # Only include tokens with significant flows
    df_filtered = df.loc[:, (df != 0).any(axis=0)]

    if not df_filtered.empty:
        # Use line plot instead of stacked area since net flows can be positive or negative
        df_filtered.plot(ax=ax, alpha=0.7, linewidth=2, marker='o', markersize=4)

        ax.set_xlabel('Date', fontsize=14, fontweight='bold')
        ax.set_ylabel('Net Flow Amount', fontsize=14, fontweight='bold')
        ax.set_title('Net Token Flows Over Time (Inflow - Outflow)', fontsize=16, fontweight='bold', pad=20)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        filepath = output_path / "3_net_flows_timeseries.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Created: {filepath.name}")
        plt.close()

    # Chart 4: Heatmap of daily flows by token
    fig, ax = plt.subplots(figsize=(16, 10))

    # Prepare data for heatmap
    heatmap_data = []
    token_labels = []

    for mint in top_mints:
        symbol = registry.get_symbol(mint)
        token_labels.append(symbol)

        daily_totals = []
        for date in dates:
            date_data = by_date.get(date, {})
            token_data = date_data.get(mint, {'in': 0, 'out': 0})
            total = token_data['in'] + token_data['out']
            daily_totals.append(total)

        heatmap_data.append(daily_totals)

    # Create heatmap
    im = ax.imshow(heatmap_data, aspect='auto', cmap='YlOrRd')

    # Set ticks
    ax.set_xticks(range(len(dates)))
    ax.set_yticks(range(len(token_labels)))
    ax.set_xticklabels([datetime.strptime(d, '%Y-%m-%d').strftime('%m/%d') for d in dates], rotation=45, ha='right')
    ax.set_yticklabels(token_labels)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Total Flow Amount', rotation=270, labelpad=20, fontsize=12, fontweight='bold')

    ax.set_xlabel('Date', fontsize=14, fontweight='bold')
    ax.set_ylabel('Token', fontsize=14, fontweight='bold')
    ax.set_title('Token Activity Heatmap (Inflow + Outflow)', fontsize=16, fontweight='bold', pad=20)

    plt.tight_layout()

    filepath = output_path / "4_token_activity_heatmap.png"
    plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Created: {filepath.name}")
    plt.close()

    print()


def main(
    cache_db: str = "data/solana_cache.db",
    address: str = None,
    output_dir: str = "output/flows"
):
    """Main function"""
    print(f"\n{'='*70}")
    print("  Token Flow Analyzer")
    print(f"{'='*70}\n")

    # Initialize
    parser = TransactionParser()
    registry = TokenRegistry()

    # Load transactions
    transactions = load_transactions_from_cache(cache_db, address)

    if not transactions:
        print("❌ No transactions found in cache")
        print("\nTip: Run analyze.py first to fetch and cache transactions")
        return

    # Parse transactions
    print(f"🔍 Parsing transactions...")
    parsed_txs = []
    for tx in transactions:
        parsed = parser.parse_transaction(tx['data'], address)
        if parsed:
            parsed_txs.append(parsed)

    print(f"✓ Parsed {len(parsed_txs)} transactions with token transfers\n")

    if not parsed_txs:
        print("❌ No token transfers found in transactions")
        return

    # Aggregate flows
    print(f"📊 Aggregating token flows...")
    flows = parser.aggregate_flows(parsed_txs, address)

    print(f"✓ Found flows for {len(flows['by_token'])} different tokens")
    print(f"✓ Spanning {len(flows['by_date'])} different dates\n")

    # Display summary
    print(f"{'='*70}")
    print("Token Flow Summary")
    print(f"{'='*70}")
    print(f"{'Token':<12} {'Inflow':>15} {'Outflow':>15} {'Net':>15} {'Txs':>8}")
    print(f"{'-'*70}")

    sorted_tokens = sorted(
        flows['by_token'].items(),
        key=lambda x: x[1]['in'] + x[1]['out'],
        reverse=True
    )[:20]

    for mint, data in sorted_tokens:
        symbol = registry.get_symbol(mint)
        print(f"{symbol:<12} {data['in']:>15,.2f} {data['out']:>15,.2f} {data['net']:>15,.2f} {data['count']:>8}")

    print(f"\n{'='*70}\n")

    # Create visualizations
    create_sankey_diagram(flows, registry, f"{output_dir}/sankey_diagram.html")
    create_timeseries_charts(flows, registry, output_dir)

    print(f"{'='*70}")
    print(f"✅ All flow visualizations saved to: {Path(output_dir).absolute()}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    import sys

    cache_db = sys.argv[1] if len(sys.argv) > 1 else "data/solana_cache.db"
    address = sys.argv[2] if len(sys.argv) > 2 else None
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "output/flows"

    main(cache_db, address, output_dir)
