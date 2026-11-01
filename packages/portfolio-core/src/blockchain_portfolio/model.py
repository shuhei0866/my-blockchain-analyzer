"""Versioned primitives. Ownership, custody policy and persistence belong to callers."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import re

class AnalysisError(ValueError):
    """Fixed, non-sensitive contract error; never include provider exception bodies."""

def number(value):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise AnalysisError("numeric values must be Decimal, integer or string")
    try:
        result = Decimal(value)
    except (ValueError, InvalidOperation):
        raise AnalysisError("invalid numeric value") from None
    if not result.is_finite() or len(result.as_tuple().digits)>256 or abs(result.adjusted())>512:
        raise AnalysisError("unsupported numeric value")
    return result

def utc(value):
    if isinstance(value,str):
        try:value=datetime.fromisoformat(value.replace("Z","+00:00"))
        except ValueError:raise AnalysisError("invalid timestamp") from None
    if not isinstance(value,datetime) or value.tzinfo is None:
        raise AnalysisError("timestamp requires timezone")
    return value.astimezone(timezone.utc)

def iso(value):
    return utc(value).isoformat(timespec="microseconds")

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def evm_address(value):
    if not isinstance(value,str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}",value) or int(value[2:],16)==0:
        raise AnalysisError("invalid public account identity")
    return value.lower()

def solana_key(value):
    alphabet="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if not isinstance(value,str) or not 32<=len(value)<=44 or any(c not in alphabet for c in value):
        raise AnalysisError("invalid Solana public identity")
    number_=0
    for c in value:number_=number_*58+alphabet.index(c)
    length=(number_.bit_length()+7)//8+len(value)-len(value.lstrip("1"))
    if length!=32:raise AnalysisError("invalid Solana public identity")
    return value

@dataclass(frozen=True)
class Asset:
    network: str
    reference: str

    def __post_init__(self):
        if not isinstance(self.network,str) or not isinstance(self.reference,str) or not re.fullmatch(r"[a-z0-9:_-]+",self.network) or not self.reference or "/" in self.reference or any(c.isspace() for c in self.reference):
            raise AnalysisError("invalid asset identifier")
        evm_networks={'ethereum','arbitrum','soneium','base','optimism','polygon','bsc','avalanche'}
        if (self.network in evm_networks or self.network.startswith('eip155:')) and self.reference.startswith('0x'):
            object.__setattr__(self,'reference',evm_address(self.reference))

    @property
    def key(self):
        return self.network+"/"+self.reference

@dataclass(frozen=True)
class Holding:
    asset: Asset
    units: int
    decimals: int
    symbol: str
    side: str = "asset"

    def __post_init__(self):
        if type(self.units) is not int or not 0<=self.units<2**256:
            raise AnalysisError("invalid base units")
        if type(self.decimals) is not int or not 0<=self.decimals<=255:
            raise AnalysisError("invalid decimals")
        if self.side not in {"asset","liability"}:
            raise AnalysisError("invalid position side")

    @property
    def quantity(self):
        with localcontext() as ctx:
            ctx.prec=400
            return Decimal(self.units).scaleb(-self.decimals)

    def to_dict(self):
        return {"network":self.asset.network,"reference":self.asset.reference,
                "units":str(self.units),"decimals":self.decimals,"symbol":self.symbol,"side":self.side}

@dataclass(frozen=True)
class Price:
    asset: Asset
    currency: str
    unit_price: Decimal
    observed_at: str
    source: str
    source_updated_at: str | None = None
    proxy_of: str | None = None
    kind: str = "unspecified"

    def __post_init__(self):
        if not isinstance(self.unit_price,Decimal) or number(self.unit_price)<0:
            raise AnalysisError("invalid price")
        utc(self.observed_at)
        if self.source_updated_at is not None:utc(self.source_updated_at)
        if not isinstance(self.currency,str) or not re.fullmatch(r'[A-Z][A-Z0-9]{1,11}',self.currency) or not isinstance(self.source,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,96}',self.source):
            raise AnalysisError("price provenance missing")
        if self.proxy_of is not None and not isinstance(self.proxy_of,str):
            raise AnalysisError("invalid price proxy reference")
        if self.kind not in {"unspecified","last_trade","mid","bid","ask","manual"}:
            raise AnalysisError("invalid price kind")

@dataclass(frozen=True)
class CostBasis:
    asset: Asset
    quantity: Decimal
    total_cost: Decimal
    currency: str
    as_of: str
    source: str

    def __post_init__(self):
        if not isinstance(self.quantity,Decimal) or not isinstance(self.total_cost,Decimal):
            raise AnalysisError("basis requires Decimal values")
        if number(self.quantity)<0 or number(self.total_cost)<0 or not isinstance(self.currency,str) or not re.fullmatch(r'[A-Z][A-Z0-9]{1,11}',self.currency) or not isinstance(self.source,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,96}',self.source):
            raise AnalysisError("invalid cost basis")
        utc(self.as_of)

@dataclass(frozen=True)
class Coverage:
    network: str
    category: str
    state: str

    def __post_init__(self):
        if self.state not in {"succeeded","failed","unsupported"}:
            raise AnalysisError("invalid coverage state")

    def to_dict(self):return {"network":self.network,"category":self.category,"state":self.state}
