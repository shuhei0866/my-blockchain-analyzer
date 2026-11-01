import importlib
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock,patch

from blockchain_portfolio import Asset,Holding,Price,CostBasis,AnalysisError,value_holding,__version__
from blockchain_portfolio.model import number
from blockchain_portfolio.providers import read_evm,read_solana,rpc,SOLANA,_NoRedirect

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

    def test_proxy_reference_type_is_checked(self):
        with self.assertRaises(AnalysisError):
            Price(self.asset,'USD',Decimal('1'),NOW.isoformat(),'synthetic',proxy_of={'untrusted':'value'})

    def test_transport_refuses_redirects_and_unknown_endpoints(self):
        self.assertIsNone(_NoRedirect().redirect_request(None,None,302,'',{},'https://untrusted.invalid'))
        opener=MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value=b'{"id":1,"result":{}}'
        with patch('urllib.request.build_opener',return_value=opener) as build:
            self.assertEqual(rpc(SOLANA,'getBalance',[]),{})
            self.assertIsInstance(build.call_args.args[0],_NoRedirect)
            request=opener.open.call_args.args[0]
            self.assertEqual(dict(request.header_items()),{
                'Content-type':'application/json',
                'User-agent':'blockchain-portfolio-core/'+__version__})
            self.assertEqual(opener.open.call_args.kwargs['timeout'],10)
            with self.assertRaises(AnalysisError):rpc('https://untrusted.invalid','getBalance',[])
            self.assertEqual(opener.open.call_count,1)

    def test_soneium_mainnet_bridged_usdc_is_distinct_and_same_block(self):
        from blockchain_portfolio.providers import EVM
        calls=[]
        def call(url,method,params):
            calls.append((url,method,params))
            return {'eth_chainId':'0x74c','eth_blockNumber':'0x42',
                    'eth_getBalance':hex(1234567890123456789),'eth_call':hex(1234567)}[method]
        result=read_evm(ADDRESS,['soneium'],at=NOW,call=call)
        self.assertEqual(result['network_blocks'],{'soneium':'0x42'})
        self.assertTrue(all(c[0]=='https://rpc.soneium.org/' for c in calls))
        self.assertTrue(all(c[2][-1]=='0x42' for c in calls if c[1] in {'eth_call','eth_getBalance'}))
        token=result['holdings'][1]
        self.assertEqual(token['symbol'],'USDC.e');self.assertEqual(token['decimals'],6)
        self.assertEqual(token['reference'],EVM['soneium']['usdc_e'])
        self.assertEqual(token['units'],'1234567')
        self.assertIn({'network':'soneium','category':'usdc_e','state':'succeeded'},result['coverage'])
        self.assertEqual(Asset('soneium',token['reference'].upper().replace('0X','0x')).reference,token['reference'])
        wrong=read_evm(ADDRESS,['soneium'],at=NOW,call=lambda *a:'0x1')
        self.assertEqual(wrong['holdings'],[])
        self.assertEqual([c['category'] for c in wrong['coverage'] if c['state']=='failed'],['native_eth','usdc_e'])

    def test_evm_same_block_and_failure_coverage_is_retained(self):
        calls=[]
        def call(url,method,params):
            calls.append((method,params))
            return {'eth_chainId':'0x1','eth_blockNumber':'0x10','eth_getBalance':hex(10**18),'eth_call':hex(10**6)}[method]
        result=read_evm(ADDRESS,['ethereum','arbitrum'],at=NOW,call=call)
        self.assertEqual(len(result['holdings']),4)
        self.assertEqual(result['holdings'][0]['units'],str(10**18))
        self.assertTrue(any(c['state']=='failed' and c['network']=='arbitrum' for c in result['coverage']))
        for method,params in calls:
            if method in ('eth_getBalance','eth_call'):self.assertEqual(params[-1],'0x10')
        failed=read_evm(ADDRESS,['ethereum'],at=NOW,call=lambda *a:[])
        self.assertEqual(failed['holdings'],[]);self.assertEqual(failed['coverage'][0]['state'],'failed')

    def test_evm_partial_reads_preserve_each_success_independently(self):
        for failed_method,expected_symbols in [('eth_call',['ETH']),('eth_getBalance',['USDC','stETH','USDT'])]:
            def call(url,method,params):
                if method==failed_method:raise OSError('unavailable')
                return {'eth_chainId':'0x1','eth_blockNumber':'0x10','eth_getBalance':'0x1','eth_call':'0x1'}[method]
            result=read_evm(ADDRESS,['ethereum'],at=NOW,call=call)
            self.assertEqual([h['symbol'] for h in result['holdings']],expected_symbols)
            self.assertEqual(result['network_blocks'],{'ethereum':'0x10'})
            self.assertEqual(sorted(c['state'] for c in result['coverage'] if c['category'] in ('native_eth','usdc')),['failed','succeeded'])

    def test_steth_usdt_exact_base_units_and_independent_failures(self):
        from blockchain_portfolio.providers import ERC20
        tokens={symbol:(contract,decimals) for category,contract,decimals,symbol in ERC20['ethereum']}
        calls=[]
        def call(url,method,params):
            calls.append((method,params))
            if method=='eth_call':
                if params[0]['to']==tokens['stETH'][0]:return hex(1234567890123456789)
                if params[0]['to']==tokens['USDT'][0]:return hex(1234567)
                return '0x0'
            return {'eth_chainId':'0x1','eth_blockNumber':'0x42','eth_getBalance':'0x0'}[method]
        result=read_evm(ADDRESS,['ethereum'],at=NOW,call=call)
        hs={h['symbol']:h for h in result['holdings']}
        self.assertEqual((hs['stETH']['units'],hs['stETH']['decimals']),('1234567890123456789',18))
        self.assertEqual((hs['USDT']['units'],hs['USDT']['decimals']),('1234567',6))
        self.assertTrue(all(params[-1]=='0x42' for method,params in calls if method in {'eth_call','eth_getBalance'}))
        def partial(url,method,params):
            if method=='eth_call' and params[0]['to']==tokens['stETH'][0]:raise OSError('synthetic failure')
            return call(url,method,params)
        result=read_evm(ADDRESS,['ethereum'],at=NOW,call=partial)
        self.assertEqual([h['symbol'] for h in result['holdings']],['ETH','USDC','USDT'])
        self.assertIn({'network':'ethereum','category':'steth','state':'failed'},result['coverage'])

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
