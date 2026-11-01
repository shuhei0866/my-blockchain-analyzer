"""Pure single-position arithmetic; no latest-price lookup, policy, IO or clock."""
from datetime import timedelta
from decimal import localcontext
from .model import AnalysisError, Holding, Price, CostBasis, iso, utc
from . import __version__, SCHEMA_VERSION

def value_holding(holding: Holding, price: Price | None, basis: CostBasis | None, *,
                  at, max_price_age):
    at=utc(at)
    if not isinstance(max_price_age,timedelta) or max_price_age.total_seconds()<0:
        raise AnalysisError("invalid price freshness limit")
    result={"asset_id":holding.asset.key,"quantity":str(holding.quantity),
            "currency":price.currency if price else None,"market_value":None,"unrealized_pnl":None,
            "price_state":"missing","basis_state":"missing" if basis is None else "unverified",
            "analyzer_version":__version__,"schema_version":SCHEMA_VERSION,"calculated_at":iso(at)}
    if price is None:return result
    if price.asset!=holding.asset:raise AnalysisError("price asset mismatch")
    result.update(price_source=price.source,price_observed_at=iso(price.observed_at),
                  price_source_updated_at=iso(price.source_updated_at) if price.source_updated_at else None,
                  price_proxy_of=price.proxy_of,price_kind=price.kind)
    age=(at-utc(price.observed_at)).total_seconds()
    source_age=(at-utc(price.source_updated_at)).total_seconds() if price.source_updated_at else None
    if age<0 or (source_age is not None and source_age<0):
        result["price_state"]="future";return result
    if age>max_price_age.total_seconds() or (source_age is not None and source_age>max_price_age.total_seconds()):
        result["price_state"]="stale";return result
    result["price_state"]="observed" if source_age is not None else "source_time_unknown"
    with localcontext() as ctx:
        ctx.prec=2048
        value=holding.quantity*price.unit_price*(1 if holding.side=="asset" else -1)
        result["market_value"]=str(value)
        if basis is None:return result
        if (basis.asset!=holding.asset or basis.currency!=price.currency or basis.quantity!=holding.quantity
                or utc(basis.as_of)>at or holding.side!="asset"):
            result["basis_state"]="mismatch";return result
        result.update(basis_state="provided",basis_source=basis.source,basis_as_of=iso(basis.as_of),
                      cost_basis=str(basis.total_cost),unrealized_pnl=str(value-basis.total_cost))
    return result
