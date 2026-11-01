from datetime import datetime,timezone
from decimal import Decimal
import unittest
from unittest.mock import MagicMock,patch
from blockchain_portfolio import AnalysisError,Asset,Holding,Price,value_holding
from blockchain_portfolio.quotes import kraken_get,kraken_quote
from blockchain_portfolio.quotes import coingecko_get,coingecko_quote,CONTRACT_PRODUCTS
from datetime import timedelta

NOW=datetime(2026,1,1,tzinfo=timezone.utc)

def payload(key="SOLUSD"):
    return {"error":[],"result":{key:[["100.1234567890123456789","1","1767225600.1234567","b","m","",1]],"last":"cursor"}}

class QuoteTests(unittest.TestCase):
    def test_contract_reference_is_exact_asset_not_eth_or_dollar_peg(self):
        for product in CONTRACT_PRODUCTS:
            data={CONTRACT_PRODUCTS[product]:{'usd':'123.1234567890123456789','last_updated_at':1767225600}}
            q=coingecko_quote(product,data,at=NOW)
            self.assertEqual(q['unit_price'],'123.1234567890123456789')
            self.assertEqual(q['kind'],'reference');self.assertEqual(q['product'],product)
            self.assertEqual(q['source_updated_at'],NOW.isoformat(timespec='microseconds'))

    def test_contract_reference_rejects_bad_identity_value_and_clock(self):
        key=CONTRACT_PRODUCTS['STETH']
        bad=[{}, {'untrusted-error':'private'}, {key:{'usd':1.5,'last_updated_at':1767225600}},
             {key:{'usd':'0','last_updated_at':1767225600}}, {key:{'usd':None,'last_updated_at':1767225600}},
             {key:{'usd':'1','last_updated_at':True}}, {key:{'usd':'1','last_updated_at':-1}},
             {CONTRACT_PRODUCTS['USDT']:{'usd':'1','last_updated_at':1767225600}}]
        for data in bad:
            with self.assertRaises(AnalysisError) as error:coingecko_quote('STETH',data,at=NOW)
            self.assertNotIn('private',str(error.exception))

    def test_contract_transport_is_bounded_fixed_and_preserves_decimal_lexeme(self):
        opener=MagicMock();key=CONTRACT_PRODUCTS['STETH']
        opener.open.return_value.__enter__.return_value.read.return_value=(
            '{"'+key+'":{"usd":123.1234567890123456789,"last_updated_at":1767225600}}').encode()
        with patch('urllib.request.build_opener',return_value=opener):
            data=coingecko_get('STETH')
            self.assertEqual(data[key]['usd'],'123.1234567890123456789')
            request=opener.open.call_args.args[0]
            self.assertEqual(request.full_url.count('contract_addresses='),1)
            self.assertNotIn(',',request.full_url)
            self.assertTrue(request.get_header('User-agent').startswith('blockchain-portfolio-core/'))
            self.assertEqual(opener.open.call_args.kwargs['timeout'],10)
            with self.assertRaises(AnalysisError):coingecko_get('https://untrusted.invalid')
            self.assertEqual(opener.open.call_count,1)

    def test_exact_price_timestamp_and_source(self):
        q=kraken_quote("SOLUSD",payload(),at=NOW)
        self.assertEqual(q["unit_price"],"100.1234567890123456789")
        self.assertEqual(q["source_updated_at"],"2026-01-01T00:00:00.123456+00:00")
        self.assertEqual(q["kind"],"last_trade")
        self.assertEqual(kraken_quote("ETHUSD",payload("XETHZUSD"),at=NOW)["product"],"ETHUSD")

    def test_wrong_product_error_zero_float_and_empty_fail_closed(self):
        bad=[payload("OTHER"),{"error":["untrusted-error"]},payload(),payload(),payload()]
        bad[2]["result"]["SOLUSD"][0][0]="0"
        bad[3]["result"]["SOLUSD"][0][2]=1.25
        bad[4]["result"]["SOLUSD"]=[]
        for data in bad:
            with self.assertRaises(AnalysisError) as error:kraken_quote("SOLUSD",data,at=NOW)
            self.assertNotIn("untrusted-error",str(error.exception))

    def test_transport_preserves_json_numeric_lexemes_and_is_allowlisted(self):
        opener=MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value=b'{"timestamp":1767225600.1234567}'
        with patch("urllib.request.build_opener",return_value=opener):
            self.assertEqual(kraken_get("SOLUSD")["timestamp"],"1767225600.1234567")
            with self.assertRaises(AnalysisError):kraken_get("https://untrusted.invalid")
            self.assertEqual(opener.open.call_count,1)

    def test_price_kind_is_validated_and_exported(self):
        a=Asset("solana","native");h=Holding(a,10**9,9,"SOL")
        p=Price(a,"USD",Decimal("1"),NOW.isoformat(),"synthetic",kind="last_trade")
        self.assertEqual(value_holding(h,p,None,at=NOW,max_price_age=timedelta(minutes=15))["price_kind"],"last_trade")
        with self.assertRaises(AnalysisError):Price(a,"USD",Decimal("1"),NOW.isoformat(),"synthetic",kind="other")
