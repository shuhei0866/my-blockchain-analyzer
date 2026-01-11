# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Solana Analyzer is a Python tool for analyzing and visualizing Solana blockchain addresses - tracking token balances, transaction history, and token flows.

## Common Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Download token list (for symbol display)
python scripts/download_token_list.py

# Core workflow - balance analysis
python scripts/save_balance.py <SOLANA_ADDRESS>       # Save balance data to data/balance.json
python scripts/visualize_balance.py                    # Generate charts in output/charts_v2/
python scripts/create_sankey.py                        # Create sankey diagram in output/sankey/

# Transaction analysis (requires RPC calls)
python scripts/fetch_transactions.py <ADDRESS> --limit 100
python scripts/visualize_flows.py data/solana_cache.db <ADDRESS>

# Alternative: Full analysis via examples/main.py
python examples/main.py <ADDRESS> --limit 500 --output-dir output
```

## Architecture

### Two Analysis Paths

1. **Scripts workflow** (`scripts/`): Individual scripts for step-by-step analysis
   - Uses `multi_rpc_client.py` for RPC failover across multiple endpoints
   - Caches transactions in SQLite (`data/solana_cache.db`)
   - Uses Jupiter Token List for token symbol resolution

2. **Library workflow** (`solana_analyzer/`): Programmatic API for integration
   - Entry point: `SolanaAnalyzerAPI` in `backend/analyzer_api.py`
   - Visualization: `SolanaVisualizer` in `visualization/visualizer.py`

### Backend Components (`solana_analyzer/backend/`)

- `analyzer_api.py` - Main API class orchestrating analysis
- `transaction_analyzer.py` - Fetches and analyzes transactions, calculates token flows
- `balance_tracker.py` - Calculates token balance history over time using pandas DataFrames
- `solana_client.py` - Low-level Solana RPC client (async, uses solana-py)
- `multi_rpc_client.py` - Round-robin load balancer across multiple public RPC endpoints
- `cache.py` - SQLite cache for signatures and transaction details
- `token_registry.py` - Token symbol lookup from Jupiter Token List

### Data Flow

```
RPC Endpoints → SolanaRPCClient/MultiRPCClient → TransactionAnalyzer
    → BalanceTracker → SolanaVisualizer (matplotlib/plotly)
    → Cache (SQLite)
```

### Output Structure

- `data/` - Balance JSON, token list cache, SQLite transaction cache
- `output/charts_v2/` - Balance charts (PNG)
- `output/sankey/` - Interactive Sankey diagrams (HTML, open in browser)
- `output/flows/` - Transaction flow charts

## Key Patterns

- All RPC operations are async (`asyncio`)
- Clients use async context managers (`async with SolanaRPCClient() as client:`)
- Balance histories are pandas DataFrames with timestamp, balance, change columns
- Token amounts use `ui_amount` (human-readable with decimals applied)
- SOL balance is tracked separately from SPL tokens (9 decimals, special handling)

## Tech Stack

- Python 3.13, solana-py, solders
- pandas for data processing
- matplotlib (static charts), plotly (interactive Sankey)
- SQLite for caching
- aiohttp for async HTTP
- FastAPI + Jinja2 for WebUI

## Multi-chain Support

The `blockchain_analyzer/` package extends analysis to EVM chains:
- `chains/base.py` - Abstract interfaces (Chain, TokenTransfer, TokenBalance)
- `chains/solana.py` - Solana via Helius API
- `chains/evm.py` - EVM chains via Alchemy API (Ethereum, Polygon, Arbitrum, etc.)
- `analyzer.py` - MultiChainAnalyzer coordinator

WebUI available at `web/app.py` - run with `uvicorn web.app:app --reload`

---

## Design System

This project follows the design principles from `vendor/claude-design-skill`. See `vendor/claude-design-skill/skill/skill.md` for the complete reference.

### Design Direction: Data & Analysis + Sophistication

As a blockchain/financial analysis tool, we blend:
- **Data & Analysis** — Chart-optimized, technical but accessible, numbers as first-class citizens
- **Sophistication & Trust** — Cool tones, layered depth, financial gravitas

### Color Foundation

- **Cool foundation**: Slate/blue-gray for professionalism and trust
- **Dark mode default**: Technical, focused, premium feel
- **Accent color**: Cyan (`#00d4ff`) for primary actions, data highlights

### Design Tokens (CSS Variables)

```css
/* Backgrounds */
--bg-base: #1a1a2e;
--bg-surface: rgba(255, 255, 255, 0.05);
--bg-elevated: rgba(255, 255, 255, 0.08);

/* Borders */
--border-subtle: rgba(255, 255, 255, 0.1);
--border-default: rgba(255, 255, 255, 0.2);

/* Text Hierarchy */
--text-primary: #e4e4e4;
--text-secondary: #ccc;
--text-muted: #888;
--text-faint: #666;

/* Semantic Colors */
--color-positive: #22c55e;
--color-negative: #ef4444;
--color-accent: #00d4ff;
--color-accent-muted: rgba(0, 212, 255, 0.2);

/* Spacing (4px grid) */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;

/* Border Radius (sharp system for technical feel) */
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-xl: 16px;

/* Typography */
--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: ui-monospace, 'SF Mono', Monaco, 'Cascadia Code', monospace;
```

### Core Craft Rules

1. **4px Grid**: All spacing uses 4px multiples (4, 8, 12, 16, 24, 32)
2. **Symmetrical Padding**: TLBR must match unless horizontal needs more room
3. **Monospace for Data**: Numbers, addresses, hashes use `font-family: monospace`
4. **Color for Meaning**: Gray builds structure, color only for status/action
5. **Consistent Depth**: Use borders-only approach for dark mode (no heavy shadows)
6. **Typography Hierarchy**:
   - Headlines: 600 weight, -0.02em letter-spacing
   - Body: 400-500 weight
   - Labels: 500 weight, uppercase with slight positive tracking

### Anti-Patterns (Never Do)

- Dramatic drop shadows on dark backgrounds
- Large border radius (16px+) on small elements
- Asymmetric padding without reason
- Multiple accent colors in one interface
- Spring/bouncy animations
- Decorative gradients (only functional ones allowed)

### Internationalization

- Support Japanese (`ja`) and English (`en`) locales
- Use `lang` attribute on HTML elements
- Store translations in separate JSON/dict structures
- Default to Japanese for this project
