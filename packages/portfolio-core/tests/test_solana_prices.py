from datetime import datetime,timezone
from decimal import Decimal
import unittest
from unittest.mock import MagicMock,patch
from blockchain_portfolio import AnalysisError,Price,Asset
from blockchain_portfolio.quotes import (coingecko_solana_matches,coingecko_coin_list_get,
    coingecko_coin_prices_get,coingecko_coin_quote)

NOW=datetime(2026,1,1,tzinfo=timezone.utc)
A='2'+'A'*43
B='2'+'a'*43

def coin(key='synthetic',mint=A,symbol='SYN'):
    return {'id':key,'name':'Synthetic token','symbol':symbol,'platforms':{'solana':mint}}

class SolanaPriceTests(unittest.TestCase):
    def test_exact_case_sensitive_mint_not_symbol_or_other_chain(self):
        data=[coin(),{**coin('other-chain'), 'platforms':{'ethereum':B}}]
        rows=coingecko_solana_matches([A,B],data)
        self.assertEqual(rows[0]['coin_id'],'synthetic')
        self.assertEqual(rows[1],{'reference':B,'state':'unlisted'})

    def test_ambiguous_mint_is_never_selected(self):
        self.assertEqual(coingecko_solana_matches([A],[coin(),coin('other')]),
                         [{'reference':A,'state':'ambiguous'}])

    def test_bad_scope_coin_id_and_labels_rejected(self):
        for mints,data in [([A,A],[]),(['https://invalid'],[]),([A],[coin('../secret')]),
                           ([A],[{**coin(),'symbol':'bad\nlabel'}])]:
            with self.assertRaises(AnalysisError):coingecko_solana_matches(mints,data)

    def test_batch_quote_retains_exact_decimal_source_and_clock(self):
        q=coingecko_coin_quote('synthetic',{'synthetic':{'usd':'1.1234567890123456789','last_updated_at':1767225600}},at=NOW)
        self.assertEqual(q['unit_price'],'1.1234567890123456789')
        self.assertEqual(q['kind'],'reference');self.assertEqual(q['source'],'coingecko_coin:synthetic')
        self.assertEqual(q['source_updated_at'],NOW.isoformat(timespec='microseconds'))
        for row in [{}, {'usd':'0','last_updated_at':1767225600},
                    {'usd':1.2,'last_updated_at':1767225600}, {'usd':'1','last_updated_at':True}]:
            with self.assertRaises(AnalysisError):coingecko_coin_quote('synthetic',{'synthetic':row},at=NOW)
        with self.assertRaises(AnalysisError):coingecko_coin_quote('synthetic',{'other':{}},at=NOW)

    def test_transport_uses_only_fixed_public_paths_and_one_bounded_batch(self):
        opener=MagicMock();response=opener.open.return_value.__enter__.return_value
        response.read.return_value=b'{"synthetic":{"usd":1.1234567890123456789,"last_updated_at":1767225600}}'
        with patch('urllib.request.build_opener',return_value=opener):
            data=coingecko_coin_prices_get(['synthetic'])
            self.assertEqual(data['synthetic']['usd'],'1.1234567890123456789')
            request=opener.open.call_args.args[0]
            self.assertEqual(request.full_url,'https://api.coingecko.com/api/v3/simple/price?ids=synthetic&vs_currencies=usd&include_last_updated_at=true')
            self.assertEqual(opener.open.call_args.kwargs['timeout'],20)
            for ids in [[],['synthetic','synthetic'],['https://invalid']]:
                with self.assertRaises(AnalysisError):coingecko_coin_prices_get(ids)
            self.assertEqual(opener.open.call_count,1)
            response.read.return_value=b'[]';coingecko_coin_list_get()
            self.assertEqual(opener.open.call_args.args[0].full_url,'https://api.coingecko.com/api/v3/coins/list?include_platform=true')
            self.assertEqual(response.read.call_args.args[0],32*1024*1024+1)

    def test_long_coin_id_provenance_is_accepted_by_price_model(self):
        key='a'*100
        q=coingecko_coin_quote(key,{key:{'usd':'1.1','last_updated_at':1767225600}},at=NOW)
        p=Price(Asset('solana',A),'USD',Decimal(q['unit_price']),q['observed_at'],q['source'],q['source_updated_at'],kind=q['kind'])
        self.assertLessEqual(len(p.source),96);self.assertEqual(q['product'],key)

if __name__=='__main__':unittest.main()
