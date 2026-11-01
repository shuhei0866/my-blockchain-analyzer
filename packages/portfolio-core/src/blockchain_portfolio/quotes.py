"""Fixed public spot market reads; no wallet identities, keys or fallback."""
from datetime import datetime,timedelta,timezone
import json
import urllib.request
from .model import AnalysisError,number,iso,canonical,digest
from .providers import _NoRedirect

PRODUCTS={"SOLUSD":"SOLUSD","ETHUSD":"XETHZUSD","USDCUSD":"USDCUSD"}
ROOT="https://api.kraken.com/0/public/Trades"

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
