"""Web UI for Multi-chain Blockchain Analyzer"""
import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from blockchain_analyzer.chains.base import Chain
from blockchain_analyzer.analyzer import MultiChainAnalyzer

# Load environment variables
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# Translations
TRANSLATIONS = {
    "ja": {
        "title": "ブロックチェーンアナライザー",
        "subtitle": "マルチチェーン ウォレット分析ツール",
        "wallet_address": "ウォレットアドレス",
        "placeholder": "0x... または Solanaアドレス",
        "select_chain": "チェーンを選択",
        "analyze": "分析する",
        "api_status": "API ステータス",
        "analysis_result": "分析結果",
        "new_analysis": "新規分析",
        "native_balance": "ネイティブ残高",
        "token_holdings": "保有トークン数",
        "total_transfers": "総取引数",
        "token_activity": "トークン取引履歴 (上位20件)",
        "token": "トークン",
        "in": "受取",
        "out": "送金",
        "net": "差引",
        "txns": "取引数",
        "yearly_activity": "年間アクティビティ",
        "year": "年",
        "tokens_in": "トークン受取",
        "tokens_out": "トークン送金",
        "net_flow": "純フロー",
        "unique_tokens": "取引トークン種類",
        "current_balances": "現在のトークン残高",
        "no_transfers": "トークン取引が見つかりません",
        "no_yearly": "年間データがありません",
        "no_balances": "トークン残高がありません",
        "analysis_failed": "分析失敗",
        "try_again": "再試行",
        "address": "アドレス",
        "chain": "チェーン",
        "error": "エラー",
        "language": "言語",
    },
    "en": {
        "title": "Blockchain Analyzer",
        "subtitle": "Multi-chain wallet analysis tool",
        "wallet_address": "Wallet Address",
        "placeholder": "0x... or Solana address",
        "select_chain": "Select Chain",
        "analyze": "Analyze Wallet",
        "api_status": "API Status",
        "analysis_result": "Analysis Result",
        "new_analysis": "New Analysis",
        "native_balance": "Native Balance",
        "token_holdings": "Token Holdings",
        "total_transfers": "Total Transfers",
        "token_activity": "Token Activity (Top 20)",
        "token": "Token",
        "in": "In",
        "out": "Out",
        "net": "Net",
        "txns": "Txns",
        "yearly_activity": "Yearly Activity",
        "year": "Year",
        "tokens_in": "Tokens In",
        "tokens_out": "Tokens Out",
        "net_flow": "Net Flow",
        "unique_tokens": "Unique Tokens",
        "current_balances": "Current Token Balances",
        "no_transfers": "No token transfers found",
        "no_yearly": "No yearly data available",
        "no_balances": "No token balances found",
        "analysis_failed": "Analysis Failed",
        "try_again": "Try Again",
        "address": "Address",
        "chain": "Chain",
        "error": "Error",
        "language": "Language",
    }
}

def get_translations(lang: str = "ja") -> dict:
    """Get translations for the specified language"""
    return TRANSLATIONS.get(lang, TRANSLATIONS["ja"])

app = FastAPI(title="Blockchain Analyzer", description="Multi-chain wallet analysis tool")

# Templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# API keys from environment
HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY")
ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY")

# Chain mapping
CHAIN_MAP = {
    "solana": Chain.SOLANA,
    "ethereum": Chain.ETHEREUM,
    "polygon": Chain.POLYGON,
    "arbitrum": Chain.ARBITRUM,
    "optimism": Chain.OPTIMISM,
    "base": Chain.BASE,
}

CHAIN_NAMES = {
    "solana": "Solana",
    "ethereum": "Ethereum",
    "polygon": "Polygon",
    "arbitrum": "Arbitrum",
    "optimism": "Optimism",
    "base": "Base",
}

NATIVE_SYMBOLS = {
    "solana": "SOL",
    "ethereum": "ETH",
    "polygon": "MATIC",
    "arbitrum": "ETH",
    "optimism": "ETH",
    "base": "ETH",
}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, lang: str = Query("ja")):
    """Home page with analysis form"""
    t = get_translations(lang)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "chains": CHAIN_NAMES,
        "solana_enabled": bool(HELIUS_API_KEY),
        "evm_enabled": bool(ALCHEMY_API_KEY),
        "t": t,
        "lang": lang,
    })


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    address: str = Form(...),
    chain: str = Form(...),
    lang: str = Form("ja")
):
    """Analyze a wallet address"""
    t = get_translations(lang)

    if chain not in CHAIN_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown chain: {chain}")

    chain_enum = CHAIN_MAP[chain]

    # Check API keys
    if chain_enum == Chain.SOLANA and not HELIUS_API_KEY:
        raise HTTPException(status_code=400, detail="Solana API key not configured")
    if chain_enum != Chain.SOLANA and not ALCHEMY_API_KEY:
        raise HTTPException(status_code=400, detail="Alchemy API key not configured")

    try:
        analyzer = MultiChainAnalyzer(
            solana_api_key=HELIUS_API_KEY,
            alchemy_api_key=ALCHEMY_API_KEY
        )

        result = await analyzer.analyze_address(address, chain_enum, limit=100)

        # Process for display
        analysis = result.get("analysis", {})
        by_token = analysis.get("by_token", {})

        # Sort tokens by activity
        sorted_tokens = sorted(
            by_token.items(),
            key=lambda x: x[1]["in"] + x[1]["out"],
            reverse=True
        )[:20]

        # Format token data
        token_data = []
        for symbol, data in sorted_tokens:
            net = data["in"] - data["out"]
            token_data.append({
                "symbol": symbol[:20] if len(symbol) > 20 else symbol,
                "in": data["in"],
                "out": data["out"],
                "net": net,
                "in_count": data.get("in_count", 0),
                "out_count": data.get("out_count", 0),
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

        return templates.TemplateResponse("result.html", {
            "request": request,
            "address": address,
            "chain": chain,
            "chain_name": CHAIN_NAMES.get(chain, chain),
            "native_symbol": NATIVE_SYMBOLS.get(chain, ""),
            "native_balance": result.get("native_balance", 0),
            "token_count": len(result.get("token_balances", [])),
            "transfer_count": analysis.get("total_transfers", 0),
            "tokens": token_data,
            "yearly": yearly_data,
            "balances": result.get("token_balances", [])[:20],
            "t": t,
            "lang": lang,
        })

    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": str(e),
            "address": address,
            "chain": chain,
            "t": t,
            "lang": lang,
        })


@app.get("/api/analyze/{chain}/{address}")
async def api_analyze(chain: str, address: str, limit: int = 100):
    """API endpoint for analysis"""
    if chain not in CHAIN_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown chain: {chain}")

    chain_enum = CHAIN_MAP[chain]

    analyzer = MultiChainAnalyzer(
        solana_api_key=HELIUS_API_KEY,
        alchemy_api_key=ALCHEMY_API_KEY
    )

    result = await analyzer.analyze_address(address, chain_enum, limit=limit)
    return result


@app.get("/history/{chain}/{address}", response_class=HTMLResponse)
async def token_history(
    request: Request,
    chain: str,
    address: str,
    lang: str = Query("ja")
):
    """Token value history page with charts"""
    t = get_translations(lang)

    if chain not in CHAIN_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown chain: {chain}")

    chain_enum = CHAIN_MAP[chain]

    try:
        analyzer = MultiChainAnalyzer(
            solana_api_key=HELIUS_API_KEY,
            alchemy_api_key=ALCHEMY_API_KEY
        )

        result = await analyzer.analyze_address(address, chain_enum, limit=500)

        # Build timeline data from transfers
        analysis = result.get("analysis", {})
        transfers = result.get("transfers", [])

        # Group by date and token
        from collections import defaultdict
        from datetime import datetime

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

        return templates.TemplateResponse("history.html", {
            "request": request,
            "address": address,
            "chain": chain,
            "chain_name": CHAIN_NAMES.get(chain, chain),
            "timeline_data": timeline_data,
            "top_tokens": top_token_symbols,
            "t": t,
            "lang": lang,
        })

    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": str(e),
            "address": address,
            "chain": chain,
            "t": t,
            "lang": lang,
        })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
