#!/usr/bin/env python3
"""Create Sankey diagram from balance data"""
import json
from pathlib import Path
import plotly.graph_objects as go
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana_analyzer.backend.token_registry import TokenRegistry


def create_balance_sankey(
    balance_file: str = "data/balance.json",
    output_file: str = "output/sankey/balance_sankey.html",
    top_n: int = 15
):
    """
    Create Sankey diagram showing token holdings

    Args:
        balance_file: Path to balance JSON file
        output_file: Output HTML file path
        top_n: Number of top tokens to show
    """
    print(f"\n{'='*70}")
    print("  Creating Balance Sankey Diagram")
    print(f"{'='*70}\n")

    # Load balance data
    print(f"📂 Loading balance data from {balance_file}...")
    with open(balance_file, 'r') as f:
        data = json.load(f)

    address = data['address']
    balances = data['current_balances']

    print(f"✓ Address: {address}")
    print(f"✓ Total tokens: {len(balances)}\n")

    # Initialize token registry
    registry = TokenRegistry()

    # Filter non-zero balances and sort
    non_zero = [
        (mint, balance)
        for mint, balance in balances.items()
        if float(balance.get('ui_amount', 0) or 0) > 0
    ]

    sorted_balances = sorted(
        non_zero,
        key=lambda x: float(x[1].get('ui_amount', 0)),
        reverse=True
    )[:top_n]

    print(f"📊 Creating Sankey diagram for top {len(sorted_balances)} tokens...\n")

    # Prepare Sankey data
    labels = ["External Sources", "Your Wallet", "Token Holdings"]
    sources = []
    targets = []
    values = []
    colors = []

    # Add token nodes (offset by 3 for the main nodes)
    node_offset = 3
    print("Token symbols:")
    for i, (mint, balance) in enumerate(sorted_balances):
        symbol = registry.get_symbol(mint)
        name = registry.get_name(mint)
        amount = float(balance.get('ui_amount', 0))

        print(f"  {i+1}. {symbol:12s} ({name[:30]:30s}) - {amount:>12,.2f}")

        # Add token label
        if name and name != symbol and len(name) < 25:
            label = f"{symbol}\n({name[:20]})"
        else:
            label = symbol
        labels.append(label)

        token_node = node_offset + i

        # Flow: External Sources -> Token -> Wallet
        sources.append(0)  # External Sources
        targets.append(token_node)  # Token
        values.append(amount)

        sources.append(token_node)  # Token
        targets.append(1)  # Wallet
        values.append(amount)

        # Flow: Wallet -> Token Holdings (for display)
        sources.append(1)  # Wallet
        targets.append(2)  # Token Holdings
        values.append(amount)

    # Define colors
    node_colors = [
        '#14F195',  # External Sources (green)
        '#9945FF',  # Your Wallet (purple)
        '#FF6B6B',  # Token Holdings (red)
    ] + ['#00D4AA'] * len(sorted_balances)  # Tokens (teal)

    link_colors = []
    for i in range(len(sources)):
        if targets[i] == 1:  # Links going to wallet
            link_colors.append('rgba(153, 69, 255, 0.2)')  # Purple
        elif sources[i] == 1:  # Links from wallet
            link_colors.append('rgba(255, 107, 107, 0.2)')  # Red
        else:
            link_colors.append('rgba(20, 241, 149, 0.2)')  # Green

    # Create Sankey diagram
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=20,
            thickness=25,
            line=dict(color="black", width=1),
            label=labels,
            color=node_colors,
            customdata=[f"Node: {label}" for label in labels],
            hovertemplate='%{customdata}<br />Total: %{value}<extra></extra>'
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            hovertemplate='Flow: %{value:.2f}<extra></extra>'
        )
    )])

    # Update layout
    fig.update_layout(
        title={
            'text': f"Token Holdings Flow<br><sub>Address: {address[:20]}...{address[-12:]}</sub>",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20, 'color': '#333'}
        },
        font_size=12,
        height=800,
        width=1400,
        plot_bgcolor='#f8f9fa',
        paper_bgcolor='white'
    )

    # Save
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path))

    print(f"✓ Created: {output_path.name}")
    print(f"✓ Location: {output_path.absolute()}")
    print(f"\n{'='*70}")
    print(f"✅ Sankey diagram saved!")
    print(f"{'='*70}")
    print(f"\n💡 Open in browser: file://{output_path.absolute()}\n")

    # Also save as static image if kaleido is available
    try:
        import kaleido
        png_path = output_path.with_suffix('.png')
        fig.write_image(str(png_path), width=1400, height=800)
        print(f"✓ Also saved as PNG: {png_path.name}\n")
    except ImportError:
        print("💡 Tip: Install kaleido to save as PNG: pip install kaleido\n")


def main():
    """Main function"""
    import sys

    balance_file = sys.argv[1] if len(sys.argv) > 1 else "data/balance.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "output/sankey/balance_sankey.html"
    top_n = int(sys.argv[3]) if len(sys.argv) > 3 else 15

    create_balance_sankey(balance_file, output_file, top_n)


if __name__ == '__main__':
    main()
