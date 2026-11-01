"""Fixed read RPCs. Caller supplies identity and clock; no config, keys or persistence."""
from http.client import HTTPException
import json
import re
import urllib.request
from .model import (AnalysisError, Asset, Holding, Coverage, canonical, digest,
                    evm_address, solana_key, iso)
from . import __version__, SCHEMA_VERSION

EVM = {
 "ethereum":{"url":"https://ethereum-rpc.publicnode.com","chain_id":1,
             "usdc":"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"},
 "arbitrum":{"url":"https://arb1.arbitrum.io/rpc","chain_id":42161,
             "usdc":"0xaf88d065e77c8cc2239327c5edb3a432268e5831"},
}
SOLANA="https://api.mainnet-beta.solana.com"
# Public program IDs, not credentials: https://solana.com/docs/references/terminology
TOKEN_PROGRAMS={"spl_legacy":"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                "token_2022":"TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"}
READ_ERRORS=(OSError,ValueError,TypeError,KeyError,AttributeError,HTTPException)

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def rpc(url,method,params):
    methods={"eth_chainId","eth_blockNumber","eth_getBalance","eth_call","getBalance","getTokenAccountsByOwner"}
    if url not in {v["url"] for v in EVM.values()}|{SOLANA} or method not in methods:
        raise AnalysisError("unsupported public read RPC")
    request=urllib.request.Request(url,data=canonical({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode(),
                                   headers={"Content-Type":"application/json",
                                            "User-Agent":"blockchain-portfolio-core/"+__version__})
    opener=urllib.request.build_opener(_NoRedirect())
    with opener.open(request,timeout=10) as response:data=response.read(8*1024*1024+1)
    if len(data)>8*1024*1024:raise AnalysisError("RPC response too large")
    result=json.loads(data)
    if not isinstance(result,dict) or result.get("id")!=1 or "error" in result or "result" not in result:
        raise AnalysisError("public RPC read failed")
    return result["result"]

def hex_uint(value):
    if not isinstance(value,str) or not re.fullmatch("0x[0-9a-fA-F]+",value):
        raise AnalysisError("invalid RPC integer")
    return int(value,16)

def observation(source,user,at,holdings,coverage,**extra):
    return {"source":source,"identity_hash":digest(source+":"+user),"observed_at":iso(at),
            "holdings":[h.to_dict() for h in holdings],"coverage":[c.to_dict() for c in coverage],
            "analyzer_version":__version__,"schema_version":SCHEMA_VERSION,**extra}

def read_evm(user,networks,*,at,call=rpc):
    user=evm_address(user)
    if not networks or len(networks)!=len(set(networks)) or set(networks)-set(EVM):
        raise AnalysisError("unsupported or duplicate EVM network")
    holdings=[];coverage=[];blocks={}
    for network in networks:
        spec=EVM[network]
        try:
            if hex_uint(call(spec["url"],"eth_chainId",[]))!=spec["chain_id"]:
                raise AnalysisError("RPC chain identity mismatch")
            block=call(spec["url"],"eth_blockNumber",[]);hex_uint(block)
        except READ_ERRORS:
            coverage.extend(Coverage(network,c,"failed") for c in ("native_eth","usdc"))
        else:
            blocks[network]=block
            reads=(("native_eth","eth_getBalance",[user,block],"native",18,"ETH"),
                   ("usdc","eth_call",[{"to":spec["usdc"],"data":"0x70a08231"+user[2:].rjust(64,"0")},block],spec["usdc"],6,"USDC"))
            for category,method,params,reference,decimals,symbol in reads:
                try:
                    units=hex_uint(call(spec["url"],method,params))
                    holdings.append(Holding(Asset(network,reference),units,decimals,symbol))
                    coverage.append(Coverage(network,category,"succeeded"))
                except READ_ERRORS:coverage.append(Coverage(network,category,"failed"))
        coverage.extend([Coverage(network,"other_tokens","unsupported"),Coverage(network,"defi","unsupported")])
    return observation("evm_public_rpc",user,at,holdings,coverage,network_blocks=blocks)

def read_solana(user,*,at,call=rpc):
    user=solana_key(user);holdings=[];coverage=[];slots={}
    try:
        native=call(SOLANA,"getBalance",[user,{"commitment":"finalized"}])
        holding=Holding(Asset("solana","native"),native["value"],9,"SOL")
        slot=native["context"]["slot"]
        if type(slot) is not int or slot<0:raise AnalysisError("invalid Solana slot")
        holdings.append(holding);slots["native"]=slot
        coverage.append(Coverage("solana","native_sol","succeeded"))
    except READ_ERRORS:coverage.append(Coverage("solana","native_sol","failed"))
    for category,program in TOKEN_PROGRAMS.items():
        try:
            tokens=call(SOLANA,"getTokenAccountsByOwner",[user,{"programId":program},{"encoding":"jsonParsed","commitment":"finalized"}])
            slot=tokens['context']['slot']
            if type(slot) is not int or slot<0:raise AnalysisError('invalid Solana slot')
            amounts={}
            for row in tokens["value"]:
                info=row["account"]["data"]["parsed"]["info"]
                if info["owner"]!=user:raise AnalysisError("token owner mismatch")
                mint=solana_key(info["mint"]);raw=info["tokenAmount"]
                if not isinstance(raw["amount"],str) or not re.fullmatch(r"[0-9]+",raw["amount"]):
                    raise AnalysisError("invalid token base units")
                unit=Holding(Asset("solana",mint),int(raw["amount"]),raw["decimals"],"SPL")
                prior=amounts.get(mint)
                if prior and prior.decimals!=unit.decimals:raise AnalysisError("token decimals mismatch")
                amounts[mint]=Holding(unit.asset,unit.units+(prior.units if prior else 0),unit.decimals,"SPL")
            if any(h.asset==unit.asset for h in holdings for unit in amounts.values()):
                raise AnalysisError("duplicate token across programs")
            holdings.extend(h for h in amounts.values() if h.units)
            slots[category]=slot
            coverage.append(Coverage("solana",category,"succeeded"))
        except READ_ERRORS:coverage.append(Coverage("solana",category,"failed"))
    coverage.extend([Coverage("solana","defi","unsupported"),Coverage("solana","nft_valuation","unsupported")])
    return observation("solana_public_rpc",user,at,holdings,coverage,slots=slots)
