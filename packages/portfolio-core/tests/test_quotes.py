from datetime import datetime,timezone
from decimal import Decimal
import unittest
from unittest.mock import MagicMock,patch
from blockchain_portfolio import AnalysisError,Asset,Holding,Price,value_holding
from blockchain_portfolio.quotes import kraken_get,kraken_quote
from datetime import timedelta

NOW=datetime(2026,1,1,tzinfo=timezone.utc)

def payload(key="SOLUSD"):
    return {"error":[],"result":{key:[["100.1234567890123456789","1","1767225600.1234567","b","m","",1]],"last":"cursor"}}

class QuoteTests(unittest.TestCase):
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
