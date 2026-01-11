"""Web UI for Multi-chain Blockchain Analyzer"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from blockchain_analyzer.analyzer import MultiChainAnalyzer
from blockchain_analyzer.chains.base import Chain

# Load environment variables
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# Import refactored modules
from web.translations import get_translations
from web.config import (
    HELIUS_API_KEY, ALCHEMY_API_KEY, 
    CHAIN_MAP, CHAIN_NAMES, NATIVE_SYMBOLS
)
from web.services import process_analysis_result, build_timeline_data

app = FastAPI(title="Blockchain Analyzer", description="Multi-chain wallet analysis tool")

# Templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

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
        
        # Process for display using service layer
        processed = process_analysis_result(result, chain)
        
        return templates.TemplateResponse("result.html", {
            "request": request,
            "address": address,
            "chain": chain,
            "chain_name": CHAIN_NAMES.get(chain, chain),
            "native_symbol": NATIVE_SYMBOLS.get(chain, ""),
            "native_balance": result.get("native_balance", 0),
            "native_usd": result.get("native_usd", 0),
            "native_price": result.get("native_price", 0),
            "total_usd": result.get("total_usd", 0),
            "token_count": len(result.get("token_balances", [])),
            "transfer_count": result.get("analysis", {}).get("total_transfers", 0),
            "tokens": processed["token_data"],
            "yearly": processed["yearly_data"],
            "balances": processed["balances_sorted"],
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
        
        # Build timeline data using service layer
        timeline_info = build_timeline_data(result.get("transfers", []))

        return templates.TemplateResponse("history.html", {
            "request": request,
            "address": address,
            "chain": chain,
            "chain_name": CHAIN_NAMES.get(chain, chain),
            "timeline_data": timeline_info["timeline_data"],
            "top_tokens": timeline_info["top_tokens"],
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
