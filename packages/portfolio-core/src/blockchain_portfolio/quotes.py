"""Fixed public spot market reads; no wallet identities, keys or fallback."""
from datetime import datetime,timedelta,timezone
import json
import urllib.request
from .model import AnalysisError,number,iso,canonical,digest
from .providers import _NoRedirect
from . import __version__

PRODUCTS={"SOLUSD":"SOLUSD","ETHUSD":"XETHZUSD","USDCUSD":"USDCUSD"}
ROOT="https://api.kraken.com/0/public/Trades"
CONTRACT_PRODUCTS={"STETH":"0xae7ab96520de3a18e5e111b5eaab095312d7fe84",
                   "USDT":"0xdac17f958d2ee523a2206206994597c13d831ec7"}
CONTRACT_ROOT="https://api.coingecko.com/api/v3/simple/token_price/ethereum"

def coingecko_get(product):
    """Read one fixed Ethereum contract reference price; no key discovery or fallback."""
    if product not in CONTRACT_PRODUCTS:raise AnalysisError("unsupported contract product")
    url=CONTRACT_ROOT+"?contract_addresses="+CONTRACT_PRODUCTS[product]+"&vs_currencies=usd&include_last_updated_at=true"
    request=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"blockchain-portfolio-core/"+__version__})
    opener=urllib.request.build_opener(_NoRedirect())
    with opener.open(request,timeout=10) as response:raw=response.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:raise AnalysisError("market response too large")
    return json.loads(raw,parse_float=str)

def coingecko_quote(product,payload,*,at):
    """Validate the exact contract and source timestamp; this is an aggregate reference."""
    try:
        contract=CONTRACT_PRODUCTS[product]
        if not isinstance(payload,dict) or set(payload)!={contract}:raise AnalysisError("contract product mismatch")
        row=payload[contract]
        if not isinstance(row,dict) or set(row)!={"usd","last_updated_at"}:raise AnalysisError("invalid contract quote")
        price=number(row["usd"]);stamp=row["last_updated_at"]
        if price<=0 or type(stamp) is not int or not 0<=stamp<=253402300799:raise AnalysisError("invalid contract quote")
        updated=datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(seconds=stamp)
        return {"product":product,"currency":"USD","unit_price":str(price),"observed_at":iso(at),
                "source_updated_at":iso(updated),"source":"coingecko_contract:"+product,"kind":"reference",
                "response_digest":digest(canonical(payload))}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        raise AnalysisError("invalid contract quote") from None

def kraken_get(product):
    """Read one recent spot trade from a fixed product allowlist."""
    if product not in PRODUCTS:raise AnalysisError("unsupported market product")
    request=urllib.request.Request(ROOT+"?pair="+product+"&count=1",headers={"Accept":"application/json"})
    opener=urllib.request.build_opener(_NoRedirect())
    with opener.open(request,timeout=10) as response:raw=response.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:raise AnalysisError("market response too large")
    # Preserve the JSON decimal lexeme; never round financial input through float.
    return json.loads(raw,parse_float=str)

def kraken_quote(product,payload,*,at):
    """Validate a single product response; caller supplies the receipt clock."""
    try:
        if product not in PRODUCTS or not isinstance(payload,dict) or payload.get("error")!=[]:
            raise AnalysisError("invalid market response")
        result=payload["result"]
        if set(result)!={PRODUCTS[product],"last"}:raise AnalysisError("market product mismatch")
        rows=result[PRODUCTS[product]]
        if not isinstance(rows,list) or len(rows)!=1:raise AnalysisError("invalid recent trade count")
        row=rows[0]
        if not isinstance(row,list) or len(row)<7:raise AnalysisError("invalid recent trade")
        if not isinstance(row[0],str):raise AnalysisError("market price must be a decimal string")
        price=number(row[0]);stamp=number(row[2])
        if price<=0 or stamp<0 or stamp>253402300799:raise AnalysisError("invalid recent trade")
        seconds=int(stamp)
        updated=datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(seconds=seconds,microseconds=int((stamp-seconds)*1000000))
        return {"product":product,"currency":"USD","unit_price":str(price),"observed_at":iso(at),
                "source_updated_at":iso(updated),"source":"kraken_spot_last:"+product,"kind":"last_trade",
                "response_digest":digest(canonical(payload))}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,IndexError):
        raise AnalysisError("invalid market quote") from None
