from datetime import datetime,timezone
import copy,json,unittest
from unittest.mock import patch
from blockchain_portfolio.model import AnalysisError
from blockchain_portfolio.quotes import gmo_ticker_get,gmo_ticker_quote,GMO_LIMIT

AT=datetime(2026,1,1,tzinfo=timezone.utc)
def payload():
    return {'status':0,'data':[{'symbol':'NAC','last':'12.34567890123456789','bid':'12','ask':'13','timestamp':'2026-01-01T00:00:00Z'}],'responsetime':'2026-01-01T00:00:01Z'}
def parse(p):return gmo_ticker_quote('NACJPY',json.dumps(p).encode(),at=AT)

class GMOTest(unittest.TestCase):
    def test_exact_decimal_and_both_clocks(self):
        q=parse(payload());self.assertEqual(q['unit_price'],'12.34567890123456789')
        self.assertEqual(q['currency'],'JPY');self.assertEqual(q['kind'],'last_trade')
        self.assertNotEqual(q['provider_response_at'],q['source_updated_at'])

    def test_product_status_count_and_numeric_rejections(self):
        changes=[lambda p:p.update(status=True),lambda p:p.update(status=1),
            lambda p:p.update(data=[]),lambda p:p['data'].append(p['data'][0]),
            lambda p:p['data'][0].update(symbol='BTC'),lambda p:p['data'][0].update(last=1.5),
            lambda p:p['data'][0].update(last='NaN'),lambda p:p['data'][0].update(bid='14'),
            lambda p:p['data'][0].update(ask='0'),lambda p:p['data'][0].update(timestamp='2026-01-01'),
            lambda p:p['data'][0].pop('last')]
        for change in changes:
            with self.subTest(change=change):
                p=payload();change(p)
                with self.assertRaises(AnalysisError):parse(p)
        for raw in [b'{"status":0,"status":0}',b'bad',b' '* (GMO_LIMIT+1)]:
            with self.assertRaises(AnalysisError):gmo_ticker_quote('NACJPY',raw,at=AT)

    def test_unknown_product_never_networks(self):
        with patch('urllib.request.build_opener') as opener:
            with self.assertRaises(AnalysisError):gmo_ticker_get('BTCJPY')
            opener.assert_not_called()

    def test_fixed_get_and_sanitized_read_error(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=TimeoutError('private error body')
            with self.assertRaisesRegex(AnalysisError,'^GMO ticker unavailable$'):gmo_ticker_get('NACJPY')
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url,'https://api.coin.z.com/public/v1/ticker?symbol=NAC')
            self.assertEqual(req.get_method(),'GET');self.assertEqual(set(k.lower() for k in req.headers),{'accept','user-agent'})

class GMOTransportTest(unittest.TestCase):
    def test_exact_bytes_and_size_cap(self):
        for data,valid in [(b'{"source":"unchanged"}',True),(b'x'*(GMO_LIMIT+1),False)]:
            with patch('urllib.request.build_opener') as opener:
                response=opener.return_value.open.return_value.__enter__.return_value
                response.status=200
                cursor=[0]
                def read(size):
                    part=data[cursor[0]:cursor[0]+size];cursor[0]+=len(part);return part
                response.read1.side_effect=read
                if valid:self.assertEqual(gmo_ticker_get('NACJPY'),data)
                else:
                    with self.assertRaises(AnalysisError):gmo_ticker_get('NACJPY')

    def test_non_200_is_not_followed_or_parsed(self):
        with patch('urllib.request.build_opener') as opener:
            response=opener.return_value.open.return_value.__enter__.return_value
            response.status=302
            with self.assertRaises(AnalysisError):gmo_ticker_get('NACJPY')
            response.read1.assert_not_called()

if __name__=='__main__':unittest.main()
