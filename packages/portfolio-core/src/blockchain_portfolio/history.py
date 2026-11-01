"""Pure parsing of explicitly scoped, saved provider wallet charts.

No credentials, transport, persistence, ownership or portfolio aggregation.
Amounts are provider-reported USD valuations, not reconstructed token lots/PnL.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, parse_qs
from .model import AnalysisError, evm_address, solana_key, number, utc, iso

EVM_CHAINS = {'ethereum', 'arbitrum', 'soneium'}

def zerion_scope(address, chains):
    evm = isinstance(address, str) and address.startswith('0x')
    identity = evm_address(address) if evm else solana_key(address)
    if not isinstance(chains, (list, tuple)) or not 1 <= len(chains) <= 3 or any(not isinstance(c, str) for c in chains):
        raise AnalysisError('invalid wallet history chain scope')
    if len(set(chains)) != len(chains) or set(chains) - (EVM_CHAINS if evm else {'solana'}):
        raise AnalysisError('unsupported wallet history chain scope')
    return identity, sorted(chains)

def require_zerion_chart_chains(raw, chains):
    if not isinstance(raw, dict) or not isinstance(raw.get('data'), list) or len(raw['data']) > 512:
        raise AnalysisError('invalid chain capability response')
    if not isinstance(chains, (list, tuple)) or not 1 <= len(chains) <= 4 or any(not isinstance(c, str) or c not in EVM_CHAINS | {'solana'} for c in chains):
        raise AnalysisError('unsupported chart chain scope')
    for chain in chains:
        matches = [r for r in raw['data'] if isinstance(r, dict) and r.get('id') == chain]
        if len(matches) != 1:
            raise AnalysisError('missing unique chart chain capability')
        attributes = matches[0].get('attributes')
        flags = attributes.get('flags') if isinstance(attributes, dict) else None
        if not isinstance(flags, dict) or any(flags.get(k) is not True for k in ('supports_positions', 'supports_transactions')):
            raise AnalysisError('chain does not support wallet charts')

def _source_link(link, identity, chains):
    if not isinstance(link, str) or len(link) > 4096:
        raise AnalysisError('invalid wallet chart source')
    u = urlsplit(link)
    expected = '/v1/wallets/' + identity + '/charts/year'
    path = u.path.lower() if identity.startswith('0x') else u.path
    if u.scheme != 'https' or u.netloc != 'api.zerion.io' or u.fragment or path != expected:
        raise AnalysisError('wallet chart source identity mismatch')
    query = parse_qs(u.query, keep_blank_values=True, strict_parsing=True, max_num_fields=8)
    values = query.get('filter[chain_ids]')
    if not values or len(values) != 1 or sorted(values[0].split(',')) != chains:
        raise AnalysisError('wallet chart source chain mismatch')
    query['filter[chain_ids]'] = [','.join(chains)]
    if query != {'currency': ['usd'], 'filter[positions]': ['only_simple'], 'filter[chain_ids]': [','.join(chains)]}:
        raise AnalysisError('wallet chart source filter mismatch')

def parse_zerion_year_chart(raw, address, chains, *, at):
    """Validate identity/filters/day grid; exclude rounded future endpoints.

    ``at`` must be the caller's saved receipt time, never an invented chart
    close time. The caller separately verifies the chain capability response.
    Values require precise JSON decoding (integer/str/Decimal, never float).
    """
    try:
        identity, chains = zerion_scope(address, chains)
        at = utc(at)
        _source_link(raw['links']['self'], identity, chains)
        data = raw['data']
        chart_id = data['id'].lower() if identity.startswith('0x') else data['id']
        if data['type'] != 'wallet_chart' or chart_id != identity + '-year':
            raise AnalysisError('wallet chart identity mismatch')
        attributes = data['attributes']
        begin, end = utc(attributes['begin_at']), utc(attributes['end_at'])
        midnight = at.replace(hour=0, minute=0, second=0, microsecond=0)
        ceiling = midnight if at == midnight else midnight + timedelta(days=1)
        if not at - timedelta(days=367) <= begin <= at or not begin <= end <= ceiling or end - begin > timedelta(days=367):
            raise AnalysisError('invalid wallet chart range')
        if any(t.hour or t.minute or t.second or t.microsecond for t in (begin, end)):
            raise AnalysisError('wallet chart is not daily aligned')
        rows = attributes['points']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
            raise AnalysisError('invalid wallet chart sample count')
        previous = None
        points = []
        excluded = 0
        for row in rows:
            if not isinstance(row, list) or len(row) != 2 or type(row[0]) is not int or not 0 < row[0] < 2**53:
                raise AnalysisError('invalid wallet chart sample')
            stamp, value = row[0], str(number(row[1]))
            instant = datetime.fromtimestamp(stamp, timezone.utc)
            if stamp % 86400 or not begin <= instant <= end or previous is not None and stamp <= previous:
                raise AnalysisError('invalid wallet chart sample clock')
            previous = stamp
            if instant > at:
                excluded += 1
            else:
                points.append({'at': iso(instant), 'value': value})
        if not points:
            raise AnalysisError('wallet chart has no past samples')
        return {'provider': 'Zerion', 'currency': 'USD', 'scope': 'simple_wallet_tokens',
                'chains': chains, 'reported_at': iso(at), 'begin_at': iso(begin), 'end_at': iso(end),
                'source_sample_count': len(rows), 'excluded_future_points': excluded, 'points': points}
    except (KeyError, TypeError, AttributeError, OverflowError, OSError, ValueError):
        raise AnalysisError('invalid scoped Zerion year chart') from None
