import importlib
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from blockchain_portfolio import Asset,Holding,Price,CostBasis,AnalysisError,value_holding
from blockchain_portfolio.model import number
from blockchain_portfolio.providers import read_evm,read_solana

NOW=datetime(2026,1,1,tzinfo=timezone.utc)
ADDRESS="0x"+"1"*40
SOL="1"*32

class CoreTests(unittest.TestCase):
    def value(self,h,p,b,*,at):
        return value_holding(h,p,b,at=at,max_price_age=timedelta(minutes=15))

    def setUp(self):
        self.asset=Asset("ethereum","native")
        self.holding=Holding(self.asset,1234567890123456789,18,"ETH")
        self.price=Price(self.asset,"USD",Decimal("2000.123456789"),NOW.isoformat(),"synthetic")

    def test_exact_arithmetic_and_explicit_basis(self):
        result=self.value(self.holding,self.price,None,at=NOW)
        self.assertEqual(Decimal(result['market_value']),Decimal('2469.288196034430724788750190521'))
        self.assertIsNone(result['unrealized_pnl'])
        basis=CostBasis(self.asset,self.holding.quantity,Decimal('2000'),'USD',NOW.isoformat(),'synthetic')
        result=self.value(self.holding,self.price,basis,at=NOW)
        self.assertEqual(Decimal(result['unrealized_pnl']),Decimal('469.288196034430724788750190521'))

    def test_missing_stale_future_prices_and_wrong_asset_are_not_zero(self):
        self.assertIsNone(self.value(self.holding,None,None,at=NOW)['market_value'])
        self.assertEqual(self.value(self.holding,self.price,None,at=NOW+timedelta(hours=1))['price_state'],'stale')
        self.assertEqual(self.value(self.holding,self.price,None,at=NOW-timedelta(seconds=1))['price_state'],'future')
        wrong=Price(Asset('arbitrum','native'),'USD',Decimal('2000'),NOW.isoformat(),'synthetic')
        with self.assertRaises(AnalysisError):self.value(self.holding,wrong,None,at=NOW)

    def test_basis_must_cover_same_quantity_currency_and_time(self):
        for qty,currency,at in [(Decimal('1'),'USD',NOW),(self.holding.quantity,'JPY',NOW),
                                (self.holding.quantity,'USD',NOW+timedelta(days=1))]:
            basis=CostBasis(self.asset,qty,Decimal('1'),currency,at.isoformat(),'synthetic')
            result=self.value(self.holding,self.price,basis,at=NOW)
            self.assertIsNone(result['unrealized_pnl']);self.assertEqual(result['basis_state'],'mismatch')

    def test_liability_value_is_signed_but_not_an_acquisition_gain(self):
        debt=Holding(self.asset,10**18,18,'ETH','liability')
        result=self.value(debt,self.price,None,at=NOW)
        self.assertLess(Decimal(result['market_value']),0);self.assertIsNone(result['unrealized_pnl'])

    def test_float_nonfinite_and_invalid_units_rejected(self):
        for value in (True,1.1,'NaN','Infinity'):
            with self.subTest(value=value),self.assertRaises(AnalysisError):number(value)
        for units,decimals in [(True,18),(-1,18),(1,-1),(1,True)]:
            with self.assertRaises(AnalysisError):Holding(self.asset,units,decimals,'ETH')

    def test_evm_reference_case_canonical_but_solana_case_preserved(self):
        self.assertEqual(Asset('ethereum','0x'+'A'*40),Asset('ethereum','0x'+'a'*40))
        self.assertNotEqual(Asset('solana','TokenAbc'),Asset('solana','tokenabc'))

    def test_untrusted_timestamps_and_sources_do_not_echo_values(self):
        from blockchain_portfolio.model import utc
        with self.assertRaises(AnalysisError) as error:utc('synthetic-private-marker')
        self.assertNotIn('synthetic-private-marker',str(error.exception))
        with self.assertRaises(AnalysisError):
            Price(self.asset,'USD',Decimal('1'),NOW.isoformat(),'https://provider/?key=synthetic')

    def test_evm_same_block_and_failure_coverage_is_retained(self):
        calls=[]
        def call(url,method,params):
            calls.append((method,params))
            return {'eth_chainId':'0x1','eth_blockNumber':'0x10','eth_getBalance':hex(10**18),'eth_call':hex(10**6)}[method]
        result=read_evm(ADDRESS,['ethereum','arbitrum'],at=NOW,call=call)
        self.assertEqual(len(result['holdings']),2)
        self.assertEqual(result['holdings'][0]['units'],str(10**18))
        self.assertTrue(any(c['state']=='failed' and c['network']=='arbitrum' for c in result['coverage']))
        for method,params in calls:
            if method in ('eth_getBalance','eth_call'):self.assertEqual(params[-1],'0x10')
        failed=read_evm(ADDRESS,['ethereum'],at=NOW,call=lambda *a:[])
        self.assertEqual(failed['holdings'],[]);self.assertEqual(failed['coverage'][0]['state'],'failed')

    def test_solana_base_units_not_float_and_token2022_partial(self):
        from blockchain_portfolio.providers import TOKEN_PROGRAMS
        def call(url,method,params):
            if method=='getBalance':return {'context':{'slot':12},'value':1000000000}
            if params[1]['programId']==TOKEN_PROGRAMS['token_2022']:raise OSError('private error must not escape')
            return {'context':{'slot':13},'value':[{'account':{'data':{'parsed':{'info':{'owner':SOL,'mint':'2'+'1'*43,
                    'tokenAmount':{'amount':'1234567890123456789','decimals':18}}}}}}]}
        result=read_solana(SOL,at=NOW,call=call)
        self.assertEqual(result['holdings'][1]['units'],'1234567890123456789')
        self.assertEqual(result['slots']['spl_legacy'],13)
        self.assertTrue(any(c['category']=='token_2022' and c['state']=='failed' for c in result['coverage']))
        self.assertNotIn('private error',str(result))

    def test_token_slots_retained_when_native_read_fails(self):
        def call(url,method,params):
            if method=='getBalance':raise OSError('unavailable')
            return {'context':{'slot':42},'value':[]}
        result=read_solana(SOL,at=NOW,call=call)
        self.assertEqual(result['slots'],{'spl_legacy':42,'token_2022':42})
        self.assertEqual(result['coverage'][0]['state'],'failed')

    def test_import_does_not_read_private_config_or_start_network(self):
        code="""from pathlib import Path
import urllib.request
Path.home=lambda: (_ for _ in ()).throw(RuntimeError('home read'))
urllib.request.urlopen=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network'))
import blockchain_portfolio
import blockchain_portfolio.providers
assert 'blockchain_analyzer' not in __import__('sys').modules
assert 'web.app' not in __import__('sys').modules
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
