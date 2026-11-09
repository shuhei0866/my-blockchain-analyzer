"""Fixed public spot market reads; no wallet identities, keys or fallback."""
from datetime import datetime,timedelta,timezone
import json
import re
from itertools import islice
from time import monotonic
import urllib.request
import urllib.parse
from .model import AnalysisError,number,iso,canonical,digest,solana_key
from .providers import _NoRedirect
from . import __version__

PRODUCTS={"SOLUSD":"SOLUSD","ETHUSD":"XETHZUSD","USDCUSD":"USDCUSD"}
ROOT="https://api.kraken.com/0/public/Trades"
CONTRACT_PRODUCTS={"STETH":"0xae7ab96520de3a18e5e111b5eaab095312d7fe84",
                   "USDT":"0xdac17f958d2ee523a2206206994597c13d831ec7"}
CONTRACT_ROOT="https://api.coingecko.com/api/v3/simple/token_price/ethereum"

def _coingecko_public_get(path,limit):
    request=urllib.request.Request("https://api.coingecko.com/api/v3/"+path,
        headers={"Accept":"application/json","User-Agent":"blockchain-portfolio-core/"+__version__})
    deadline=monotonic()+20
    chunks=[];size=0
    with urllib.request.build_opener(_NoRedirect()).open(request,timeout=20) as response:
        while True:
            if monotonic()>=deadline:raise AnalysisError("market response read deadline exceeded")
            chunk=response.read1(min(65536,limit+1-size))
            if monotonic()>=deadline:raise AnalysisError("market response read deadline exceeded")
            if not chunk:break
            chunks.append(chunk);size+=len(chunk)
            if size>limit:raise AnalysisError("market response too large")
    raw=b"".join(chunks)
    if len(raw)>limit:raise AnalysisError("market response too large")
    return json.loads(raw,parse_float=str)

def coingecko_coin_list_get():
    """Read the public mint-to-coin-ID catalog once, without wallet information."""
    return _coingecko_public_get("coins/list?include_platform=true",32*1024*1024)

def _coin_id(value):
    if not isinstance(value,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}",value):
        raise AnalysisError("invalid market coin ID")
    return value

def coingecko_solana_matches(mints,payload):
    """Match exact, case-sensitive Solana mints; no symbol/name inference."""
    mints=list(islice(mints,65))
    if len(mints)>64 or len(mints)!=len(set(mints)):raise AnalysisError("invalid mint scope")
    for mint in mints:solana_key(mint)
    if not isinstance(payload,list) or len(payload)>100000:raise AnalysisError("invalid coin catalog")
    found={mint:[] for mint in mints}
    for row in payload:
        if not isinstance(row,dict):raise AnalysisError("invalid coin catalog")
        platforms=row.get("platforms")
        mint=platforms.get("solana") if isinstance(platforms,dict) else None
        if not isinstance(mint,str) or mint not in found:continue
        coin_id=_coin_id(row.get("id"))
        for key,limit in (("symbol",40),("name",120)):
            value=row.get(key)
            if not isinstance(value,str) or not 0<len(value)<=limit or not value.isprintable():
                raise AnalysisError("invalid coin label")
        found[mint].append({"coin_id":coin_id,"symbol":row["symbol"],"name":row["name"]})
    return [{"reference":mint,"state":"matched" if len(rows)==1 else "unlisted" if not rows else "ambiguous",
             **(rows[0] if len(rows)==1 else {})} for mint,rows in sorted(found.items())]

def coingecko_coin_prices_get(coin_ids):
    """One bounded ID batch; no retry, key discovery or alternative provider."""
    ids=list(islice(coin_ids,65))
    if not 1<=len(ids)<=64 or len(ids)!=len(set(ids)):raise AnalysisError("invalid market coin scope")
    for coin_id in ids:_coin_id(coin_id)
    query=urllib.parse.urlencode({"ids":",".join(sorted(ids)),"vs_currencies":"usd","include_last_updated_at":"true"})
    return _coingecko_public_get("simple/price?"+query,2*1024*1024)

def coingecko_coin_quote(coin_id,payload,*,at):
    """Parse one requested ID from a batch, retaining the source price clock."""
    try:
        _coin_id(coin_id)
        if not isinstance(payload,dict):raise AnalysisError("invalid coin quote")
        row=payload[coin_id]
        if not isinstance(row,dict) or set(row)!={"usd","last_updated_at"}:raise AnalysisError("invalid coin quote")
        price=number(row["usd"]);stamp=row["last_updated_at"]
        if price<=0 or type(stamp) is not int or not 0<=stamp<=253402300799:raise AnalysisError("invalid coin quote")
        updated=datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(seconds=stamp)
        source="coingecko_coin:"+coin_id if len(coin_id)<=81 else "coingecko_coin_sha256:"+digest(coin_id)
        return {"product":coin_id,"currency":"USD","unit_price":str(price),"observed_at":iso(at),
                "source_updated_at":iso(updated),"source":source,"kind":"reference",
                "response_digest":digest(canonical(payload))}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        raise AnalysisError("invalid coin quote") from None

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

# GMO spot identity is explicit. No symbol guessing, holdings or authentication.
GMO_PRODUCTS={"NACJPY":"NAC"}
GMO_TICKER_ROOT="https://api.coin.z.com/public/v1/ticker"
GMO_LIMIT=256*1024

def gmo_ticker_get(product):
    """Return exact bounded public ticker bytes for immutable caller storage."""
    if product not in GMO_PRODUCTS:raise AnalysisError("unsupported GMO product")
    request=urllib.request.Request(GMO_TICKER_ROOT+"?symbol="+GMO_PRODUCTS[product],
        method="GET",headers={"Accept":"application/json","User-Agent":"blockchain-portfolio-core/"+__version__})
    deadline=monotonic()+15
    chunks=[];size=0
    try:
        # No environment proxy, credential lookup, retry or redirect.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect())
        with opener.open(request,timeout=15) as response:
            if response.status!=200:raise AnalysisError("GMO unavailable")
            while True:
                if monotonic()>=deadline:raise AnalysisError("GMO read deadline exceeded")
                chunk=response.read1(min(65536,GMO_LIMIT+1-size))
                if monotonic()>=deadline:raise AnalysisError("GMO read deadline exceeded")
                if not chunk:break
                chunks.append(chunk);size+=len(chunk)
                if size>GMO_LIMIT:raise AnalysisError("GMO response too large")
        return b"".join(chunks)
    except Exception:
        raise AnalysisError("GMO ticker unavailable") from None

def gmo_ticker_quote(product,raw,*,at):
    """NAC/JPY last trade reference; timestamp is the provider's ticker clock."""
    from .model import utc
    import hashlib
    try:
        if product not in GMO_PRODUCTS or not isinstance(raw,bytes) or len(raw)>GMO_LIMIT:
            raise AnalysisError("invalid GMO response")
        def pairs(items):
            d={}
            for key,value in items:
                if key in d:raise AnalysisError("duplicate GMO field")
                d[key]=value
            return d
        payload=json.loads(raw,object_pairs_hook=pairs)
        if not isinstance(payload,dict) or type(payload.get("status")) is not int or payload["status"]!=0:
            raise AnalysisError("invalid GMO status")
        rows=payload["data"]
        if not isinstance(rows,list) or len(rows)!=1:raise AnalysisError("ambiguous GMO product")
        row=rows[0]
        if not isinstance(row,dict) or row.get("symbol")!=GMO_PRODUCTS[product]:raise AnalysisError("GMO product mismatch")
        values={}
        for key in ("last","bid","ask"):
            if not isinstance(row[key],str):raise AnalysisError("GMO decimal string required")
            value=number(row[key])
            if value<=0:raise AnalysisError("invalid GMO price")
            values[key]=str(value)
        if number(values["bid"])>number(values["ask"]):raise AnalysisError("crossed GMO spread")
        updated=utc(row["timestamp"]);received=utc(payload["responsetime"])
        # Freshness/adoption is caller policy. Never replace clocks with fetch time.
        return {"product":product,"currency":"JPY","unit_price":values["last"],
            "bid":values["bid"],"ask":values["ask"],"observed_at":iso(at),
            "source_updated_at":iso(updated),"provider_response_at":iso(received),
            "source":"gmo_spot_last:NACJPY","kind":"last_trade",
            "source_timestamp_kind":"ticker_timestamp",
            "response_sha256":hashlib.sha256(raw).hexdigest()}
    except Exception:
        raise AnalysisError("invalid GMO ticker") from None

COINCHECK_PRODUCTS={"BTCJPY":"btc_jpy","XLMJPY":"xlm_jpy","IOSTJPY":"iost_jpy"}
ECB_ROOT="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"

def _reference_raw(url,limit):
    request=urllib.request.Request(url,method="GET",headers={"Accept":"application/json,application/xml","User-Agent":"blockchain-portfolio-core/"+__version__})
    try:
        deadline=monotonic()+15;chunks=[];size=0
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect()).open(request,timeout=15) as response:
            if response.status!=200:raise AnalysisError("reference response unavailable")
            while True:
                if monotonic()>=deadline:raise AnalysisError("reference read deadline")
                chunk=response.read1(min(65536,limit+1-size))
                if monotonic()>=deadline:raise AnalysisError("reference read deadline")
                if not chunk:break
                chunks.append(chunk);size+=len(chunk)
                if size>limit:raise AnalysisError("reference size limit")
        return b"".join(chunks)
    except Exception:raise AnalysisError("reference provider unavailable") from None

def coincheck_rate_get(product):
    """Read one fixed public reference rate; account credentials are never used."""
    if product not in COINCHECK_PRODUCTS:raise AnalysisError("unsupported Coincheck public product")
    return _reference_raw("https://coincheck.com/api/rate/"+COINCHECK_PRODUCTS[product],65536)

def coincheck_rate_quote(product,raw,*,at):
    """Receipt-time reference; the provider response has no market update clock."""
    import hashlib
    try:
        if product not in COINCHECK_PRODUCTS or not isinstance(raw,bytes) or len(raw)>65536:raise ValueError()
        def pairs(items):
            d={}
            for k,v in items:
                if k in d:raise ValueError()
                d[k]=v
            return d
        p=json.loads(raw,object_pairs_hook=pairs)
        if set(p)!={"rate"} or not isinstance(p["rate"],str) or number(p["rate"])<=0:raise ValueError()
        return {"product":product,"currency":"JPY","unit_price":str(number(p["rate"])),
            "source":"coincheck_public_rate:"+product,"kind":"reference","observed_at":iso(at),
            "source_updated_at":None,"source_timestamp_kind":"not_provided",
            "response_sha256":hashlib.sha256(raw).hexdigest()}
    except Exception:raise AnalysisError("invalid Coincheck reference rate") from None

def ecb_rates_get():
    """Read the fixed public 90-day official EUR reference-rate document."""
    return _reference_raw(ECB_ROOT,1024*1024)

def ecb_usdjpy_rates(raw):
    """64-significant-digit Decimal cross rates; caller owns publication adoption."""
    from datetime import date
    from decimal import localcontext
    import xml.etree.ElementTree as ET
    try:
        if not isinstance(raw,bytes) or len(raw)>1024*1024 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():raise ValueError()
        root=ET.fromstring(raw);ns="{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"
        days=root.findall(".//"+ns+"Cube[@time]");seen=set();rows=[]
        if not 1<=len(days)<=100:raise ValueError()
        for day in days:
            label=day.attrib['time']
            if date.fromisoformat(label).isoformat()!=label or label in seen:raise ValueError()
            seen.add(label);rates={}
            for cell in day:
                c=cell.attrib['currency']
                if c in rates:raise ValueError()
                rates[c]=number(cell.attrib['rate'])
                if rates[c]<=0:raise ValueError()
            with localcontext() as ctx:
                ctx.prec=64
                rows.append({'rate_date':label,'JPY_per_EUR':str(rates['JPY']),'USD_per_EUR':str(rates['USD']),
                    'JPY_per_USD':str(rates['JPY']/rates['USD'])})
        return sorted(rows,key=lambda r:r['rate_date'])
    except Exception:raise AnalysisError("invalid ECB reference rates") from None
