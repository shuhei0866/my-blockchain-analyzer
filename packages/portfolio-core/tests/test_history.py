from datetime import datetime, timedelta, timezone
import copy
import unittest
from blockchain_portfolio import AnalysisError
from blockchain_portfolio.history import parse_zerion_year_chart, require_zerion_chart_chains

NOW = datetime(2026, 2, 3, 12, tzinfo=timezone.utc)
ADDRESS = '0x' + '1' * 40
SOLANA = '11111111111111111111111111111111'

def sample(address=ADDRESS, chains='arbitrum,ethereum,soneium'):
    return {'links': {'self': 'https://api.zerion.io/v1/wallets/' + address + '/charts/year?currency=usd&filter[positions]=only_simple&filter[chain_ids]=' + chains},
            'data': {'id': address + '-year', 'type': 'wallet_chart', 'attributes': {
                'begin_at': '2026-02-01T00:00:00Z', 'end_at': '2026-02-04T00:00:00Z',
                'points': [[1769904000, '0'], [1770076800, '123.1234567890123456789'], [1770163200, '5']]}}}

class HistoryTests(unittest.TestCase):
    def parse(self, raw=None, address=ADDRESS, chains=None, at=NOW):
        return parse_zerion_year_chart(raw or sample(), address, chains or ['ethereum', 'arbitrum', 'soneium'], at=at)

    def test_decimal_zero_gaps_and_rounded_future_endpoint(self):
        raw = sample(); before = copy.deepcopy(raw); report = self.parse(raw)
        self.assertEqual(raw, before)
        self.assertEqual([p['value'] for p in report['points']], ['0', '123.1234567890123456789'])
        self.assertEqual(report['excluded_future_points'], 1)
        self.assertEqual(report['source_sample_count'], 3)
        self.assertEqual(report['points'][0]['at'], '2026-02-01T00:00:00.000000+00:00')
        self.assertEqual(report['chains'], ['arbitrum', 'ethereum', 'soneium'])
        self.assertNotIn('total', report)

    def test_source_identity_currency_family_and_scope_are_exact(self):
        for change in ('identity', 'currency', 'scope', 'chain', 'duplicate_chain', 'extra_filter', 'host', 'period', 'id'):
            raw = sample(); link = raw['links']['self']
            if change == 'identity': link = link.replace(ADDRESS, '0x' + '2' * 40)
            if change == 'currency': link = link.replace('currency=usd', 'currency=jpy')
            if change == 'scope': link = link.replace('only_simple', 'no_filter')
            if change == 'chain': link = link.replace(',soneium', '')
            if change == 'duplicate_chain': link += ',soneium'
            if change == 'extra_filter': link += '&filter[fungible_ids]=eth'
            if change == 'host': link = link.replace('api.zerion.io', 'unrelated.example')
            if change == 'period': link = link.replace('/year?', '/max?')
            if change == 'id': raw['data']['id'] = '0x' + '2' * 40 + '-year'
            raw['links']['self'] = link
            with self.subTest(change=change), self.assertRaises(AnalysisError): self.parse(raw)
        self.assertEqual(self.parse(sample(SOLANA, 'solana'), SOLANA, ['solana'])['chains'], ['solana'])
        with self.assertRaises(AnalysisError): self.parse(sample(SOLANA, 'solana'), SOLANA, ['ethereum'])

    def test_invalid_samples_fail_including_bad_future_value(self):
        for value in (float('nan'), float('inf'), 1.2, True, None, 'NaN', 'Infinity', '1e999'):
            raw = sample(); raw['data']['attributes']['points'][-1][1] = value
            with self.subTest(value=value), self.assertRaises(AnalysisError): self.parse(raw)
        for rows in ([], [[1770076800, '1'], [1770076800, '2']], [[1770076801, '1']], [[2**53-1, '1']], [[True, '1']], [[1770163200, '1']]):
            raw = sample(); raw['data']['attributes']['points'] = rows
            with self.subTest(rows=rows), self.assertRaises(AnalysisError): self.parse(raw)

    def test_future_clock_is_bounded_to_next_day_not_arbitrary_future(self):
        for end in ('2026-02-05T00:00:00Z', '2026-02-04T01:00:00Z'):
            raw = sample(); raw['data']['attributes']['end_at'] = end
            with self.assertRaises(AnalysisError): self.parse(raw)
        with self.assertRaises(AnalysisError): self.parse(at=NOW.replace(hour=0)-timedelta(days=1))
        self.assertEqual(self.parse(at=NOW.replace(hour=0)+timedelta(days=1))['excluded_future_points'], 0)

    def test_chain_capabilities_cannot_silently_drop_a_requested_chain(self):
        row = {'id': 'soneium', 'attributes': {'flags': {'supports_positions': True, 'supports_transactions': True}}}
        require_zerion_chart_chains({'data': [row]}, ['soneium'])
        for rows in ([], [row, row], [{'id': 'soneium', 'attributes': {'flags': {'supports_positions': True}}}]):
            with self.assertRaises(AnalysisError): require_zerion_chart_chains({'data': rows}, ['soneium'])

    def test_errors_do_not_echo_provider_values(self):
        with self.assertRaises(AnalysisError) as caught: self.parse({'links': {'self': 'sensitive-synthetic-text'}})
        self.assertNotIn('sensitive-synthetic-text', str(caught.exception))
