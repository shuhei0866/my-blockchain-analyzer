from datetime import datetime,timezone
import json,unittest
from unittest.mock import patch
from blockchain_portfolio.model import AnalysisError,number
from blockchain_portfolio.quotes import coincheck_rate_quote,coincheck_rate_get,ecb_usdjpy_rates,ecb_rates_get
AT=datetime(2026,1,1,tzinfo=timezone.utc)
XML=b'<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref"><Cube><Cube time="2025-12-31"><Cube currency="USD" rate="1.25"/><Cube currency="JPY" rate="190"/></Cube></Cube></gesmes:Envelope>'
class ReferenceQuotesTest(unittest.TestCase):
    def test_rate_exact_and_unknown_source_time(self):
        q=coincheck_rate_quote('BTCJPY',b'{"rate":"123.4567890123456789"}',at=AT)
        self.assertEqual(q['unit_price'],'123.4567890123456789');self.assertIsNone(q['source_updated_at']);self.assertEqual(q['kind'],'reference')
    def test_bad_rate_rejected(self):
        for raw in [b'{"rate":1.5}',b'{"rate":"NaN"}',b'{"rate":"0"}',b'{"rate":"2","rate":"2"}',b'{"rate":"2","secret":"echo"}']:
            with self.assertRaises(AnalysisError):coincheck_rate_quote('BTCJPY',raw,at=AT)
    def test_fixed_products_and_no_auth(self):
        with patch('blockchain_portfolio.quotes._reference_raw') as get:
            coincheck_rate_get('IOSTJPY');self.assertEqual(get.call_args.args[0],'https://coincheck.com/api/rate/iost_jpy')
            with self.assertRaises(AnalysisError):coincheck_rate_get('NACJPY')
            ecb_rates_get();self.assertTrue(get.call_args.args[0].endswith('/eurofxref-hist-90d.xml'))
    def test_ecb_cross_rate_is_decimal(self):
        rows=ecb_usdjpy_rates(XML);self.assertEqual(rows[0]['JPY_per_USD'],'152')
    def test_nonterminating_cross_rate_roundtrips_numeric_contract(self):
        raw=XML.replace(b'rate="1.25"',b'rate="3"').replace(b'rate="190"',b'rate="1"')
        value=ecb_usdjpy_rates(raw)[0]['JPY_per_USD']
        self.assertEqual(len(number(value).as_tuple().digits),64)
        self.assertTrue(value.startswith('0.333333333333333333'))
    def test_ecb_duplicate_future_shape_and_entity_rejected(self):
        for raw in [XML.replace(b'currency="JPY"',b'currency="USD"'),XML.replace(b'rate="190"',b'rate="0"'),b'<!DOCTYPE x>'+XML,b'bad',XML.replace(b'time="2025-12-31"',b'time="2025-12-32"')]:
            with self.assertRaises(AnalysisError):ecb_usdjpy_rates(raw)
if __name__=='__main__':unittest.main()
