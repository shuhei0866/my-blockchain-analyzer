"""Processing Logic and Services for the Web UI"""
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any
from web.config import NATIVE_SYMBOLS

def process_analysis_result(result: Dict[str, Any], chain: str) -> Dict[str, Any]:
    """Process raw analysis results for display in the UI"""
    analysis = result.get("analysis", {})
    by_token = analysis.get("by_token", {})

    # Build symbol to price mapping from balances
    symbol_prices = {}
    for b in result.get("token_balances", []):
        symbol = b.get("token_symbol")
        price = b.get("usd_price", 0)
        if symbol and price > 0:
            symbol_prices[symbol] = price

    # Add native token price
    native_price = result.get("native_price", 0)
    if native_price > 0:
        symbol_prices[NATIVE_SYMBOLS.get(chain, "")] = native_price

    # Sort tokens by activity
    sorted_tokens = sorted(
        by_token.items(),
        key=lambda x: x[1].get("in", 0) + x[1].get("out", 0),
        reverse=True
    )[:20]

    # Format token data with USD values
    token_data = []
    for symbol, data in sorted_tokens:
        in_amount = data.get("in", 0)
        out_amount = data.get("out", 0)
        net = in_amount - out_amount
        price = symbol_prices.get(symbol, 0)
        in_usd = in_amount * price if price else 0
        out_usd = out_amount * price if price else 0
        net_usd = net * price if price else 0

        token_data.append({
            "symbol": symbol[:20] if len(symbol) > 20 else symbol,
            "in": in_amount,
            "out": out_amount,
            "net": net,
            "in_count": data.get("in_count", 0),
            "out_count": data.get("out_count", 0),
            "price": price,
            "in_usd": in_usd,
            "out_usd": out_usd,
            "net_usd": net_usd,
        })

    # Yearly breakdown
    by_year = analysis.get("by_year", {})
    yearly_data = []
    for year in sorted(by_year.keys(), reverse=True):
        year_tokens = by_year[year]
        total_in = sum(t.get("in", 0) for t in year_tokens.values())
        total_out = sum(t.get("out", 0) for t in year_tokens.values())
        yearly_data.append({
            "year": year,
            "in": total_in,
            "out": total_out,
            "net": total_in - total_out,
            "tokens": len(year_tokens),
        })

    # Sort balances by USD value
    balances_sorted = sorted(
        result.get("token_balances", []),
        key=lambda x: x.get("usd_value", 0),
        reverse=True
    )[:20]

    return {
        "token_data": token_data,
        "yearly_data": yearly_data,
        "balances_sorted": balances_sorted
    }

def build_timeline_data(transfers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build timeline data for charts from transfers"""
    daily_flows = defaultdict(lambda: defaultdict(lambda: {"in": 0, "out": 0}))

    for transfer in transfers:
        ts = transfer.get("timestamp", 0)
        if ts > 0:
            date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            symbol = transfer.get("token_symbol") or "Unknown"
            amount = transfer.get("amount", 0)
            direction = transfer.get("direction", "in")

            daily_flows[date_str][symbol][direction] += amount

    # Convert to chart data format
    dates = sorted(daily_flows.keys())
    token_totals = defaultdict(float)

    timeline_data = []
    cumulative = defaultdict(float)

    for date in dates:
        day_data = {"date": date, "tokens": {}}
        for symbol, flows in daily_flows[date].items():
            net = flows["in"] - flows["out"]
            cumulative[symbol] += net
            day_data["tokens"][symbol] = {
                "in": flows["in"],
                "out": flows["out"],
                "net": net,
                "cumulative": cumulative[symbol]
            }
            token_totals[symbol] += abs(flows["in"]) + abs(flows["out"])
        timeline_data.append(day_data)

    # Top tokens by activity
    top_tokens = sorted(token_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    top_token_symbols = [t[0] for t in top_tokens]

    return {
        "timeline_data": timeline_data,
        "top_tokens": top_token_symbols
    }
