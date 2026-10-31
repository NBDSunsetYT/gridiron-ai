"""SYNTHETIC HTTP transports only. Never imports or prints a real provider key."""
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from .balldontlie_nfl import (BDLNFLClient, BASE, validated_params, normalize_game_odds,
                             normalize_player_prop, map_player_identity, NoRedirect)
from .sports_data_common import DataProviderError
from .sports_data_gateway import bdl_credential, app
from fastapi.testclient import TestClient

NOW = '2026-11-01T12:00:00Z'
KEY = 'SYNTHETIC-RENDER-ONLY-BDL-KEY'
BRIDGE = 'SYNTHETIC-INTERNAL-BRIDGE-TOKEN-123456789'


class Response(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        super().__init__(raw); self.status = status; self.headers = headers or {}


class Opener:
    def __init__(self, body):
        self.body = body; self.calls = []
    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if isinstance(self.body, Exception): raise self.body
        return Response(self.body)


def odds():
    return {'id': 100, 'game_id': 200, 'vendor': 'draftkings',
            'spread_home_value': '-3.5', 'spread_away_value': '3.5',
            'spread_home_odds': -110, 'spread_away_odds': -105,
            'moneyline_home_odds': -175, 'moneyline_away_odds': 150,
            'total_value': '47.5', 'total_over_odds': -115, 'total_under_odds': -110,
            'updated_at': '2026-11-01T11:59:00Z'}


def prop():
    return {'id': 301, 'game_id': 200, 'player_id': 99, 'vendor': 'draftkings',
            'prop_type': 'receiving_yards', 'line_value': '64.5',
            'market': {'type': 'over_under', 'over_odds': -110, 'under_odds': -115},
            'updated_at': '2026-11-01T11:59:00Z'}


def make(body, credential=lambda: KEY, **options):
    opener = Opener(body)
    return BDLNFLClient(credential, opener=opener, now=lambda: NOW, **options), opener


class BdlProviderTests(unittest.TestCase):
    def test_fixed_host_raw_authorization_header_and_no_credential_url(self):
        client, transport = make({'data': [odds()], 'meta': {}})
        result = client.read('odds', {'game_ids': [200]})
        request, timeout = transport.calls[0]
        self.assertEqual(request.get_header('Authorization'), KEY)
        self.assertTrue(request.full_url.startswith(BASE + '/odds?'))
        self.assertIn('game_ids%5B%5D=200', request.full_url)
        self.assertNotIn(KEY, request.full_url)
        self.assertNotIn(KEY, json.dumps(result))
        self.assertEqual(timeout, 12)
        self.assertEqual(result['status'], 'available')
        self.assertEqual(len(result['items']), 3)

    def test_missing_key_never_makes_provider_request(self):
        client, transport = make({'data': []}, credential=lambda: '')
        result = client.read('teams')
        self.assertEqual(result['diagnostic']['code'], 'credentials_missing')
        self.assertEqual(transport.calls, [])

    def test_tier_and_auth_ambiguity_are_not_reported_as_guessed_bad_credentials(self):
        for resource, params, status, expected in [
                ('teams', {}, 401, 'authentication_or_tier_denied'),
                ('odds', {'game_ids': [200]}, 401, 'authentication_or_tier_denied'),
                ('odds', {'game_ids': [200]}, 403, 'tier_or_access_denied'),
                ('teams', {}, 403, 'access_denied'),
                ('teams', {}, 503, 'source_unavailable')]:
            error = urllib.error.HTTPError(BASE, status, KEY, {}, io.BytesIO(KEY.encode()))
            client, _ = make(error)
            result = client.read(resource, params)
            self.assertEqual(result['diagnostic']['code'], expected)
            self.assertEqual(result['diagnostic']['httpStatus'], status)
            self.assertNotIn(KEY, json.dumps(result))

    def test_rate_limit_uses_observed_retry_header_and_local_budget(self):
        error = urllib.error.HTTPError(BASE, 429, 'SYNTHETIC', {'Retry-After': '25'}, None)
        client, _ = make(error)
        self.assertEqual(client.read('teams')['diagnostic']['retryAfterSeconds'], 25)
        client, transport = make({'data': [], 'meta': {}})
        for value in ['A', 'B', 'C', 'D']:
            self.assertEqual(client.read('teams', {'division': value})['status'], 'available')
        self.assertEqual(client.read('teams', {'division': 'E'})['diagnostic']['code'], 'source_rate_limited')
        self.assertEqual(len(transport.calls), 4)

    def test_cache_does_not_turn_source_refresh_time_into_quote_time(self):
        client, transport = make({'data': [odds()], 'meta': {}})
        one = client.read('odds', {'game_ids': [200]})
        two = client.read('odds', {'game_ids': [200]})
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(two['cacheStatus'], 'hit')
        self.assertEqual(one['items'][0]['sourceUpdatedAt'], '2026-11-01T11:59:00Z')
        self.assertIsNone(one['items'][0]['quotedAt'])
        self.assertFalse(one['items'][0]['executionVerified'])
        self.assertFalse(one['items'][0]['draftKingsPredictionsEquivalent'])

    def test_empty_response_is_distinct_from_access_or_schema_error(self):
        client, _ = make({'data': [], 'meta': {}})
        result = client.read('player-props', {'game_id': 200})
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['diagnostic']['code'], 'no_matching_markets')
        client, _ = make({'message': 'SYNTHETIC no markets'})
        self.assertEqual(client.read('player-props', {'game_id': 200})['diagnostic']['code'], 'unsupported_response')

    def test_secret_echo_invalid_json_nonfinite_data_and_unsupported_pagination_are_withheld(self):
        for body in [b'SYNTHETIC not JSON', json.dumps({'data': [{'secret': KEY}]}).encode(),
                     b'{"data":[{"stat":NaN}]}', b'{"data":[{"stat":1e999}]}']:
            client, _ = make(body)
            result = client.read('teams')
            self.assertEqual(result['status'], 'unavailable')
            self.assertNotIn(KEY, json.dumps(result))
        client, _ = make({'data': [], 'meta': {'next_cursor': 50}})
        self.assertEqual(client.read('player-props', {'game_id': 200})['diagnostic']['code'], 'unsupported_response')

    def test_null_statistics_remain_null(self):
        client, _ = make({'data': [{'player': {'id': 99}, 'passing_interceptions': None}], 'meta': {}})
        result = client.read('stats', {'player_ids': [99]})
        self.assertIsNone(result['records'][0]['passing_interceptions'])

    def test_request_whitelist_rejects_urls_wrong_sport_unbounded_and_undocumented_queries(self):
        client, transport = make({'data': []})
        for resource, params in [('nba', {}), ('teams', {'url': 'https://unrelated.invalid'}),
                                 ('games', {'seasons': [2026], 'per_page': 101}),
                                 ('player-props', {'game_id': 200, 'cursor': 5}),
                                 ('player-props', {'game_id': 200, 'vendors': ['draftkings_predictions']}),
                                 ('odds', {}), ('designations', {'season': 2026})]:
            self.assertEqual(client.read(resource, params)['status'], 'unavailable')
        self.assertEqual(transport.calls, [])

    def test_mutable_prop_ids_do_not_become_native_permanent_contract_ids(self):
        first = normalize_player_prop(prop(), NOW)
        second = normalize_player_prop({**prop(), 'id': 302}, NOW)
        self.assertEqual(first['referenceId'], second['referenceId'])
        self.assertNotEqual(first['sourceRecordId'], second['sourceRecordId'])
        self.assertFalse(first['sourceRecordIdPermanent'])
        self.assertIsNone(first['nativeContractId'])
        self.assertIsNone(first['fees'])
        self.assertIsNone(first['settlementRules'])
        self.assertEqual(first['book']['name'], 'DraftKings Sportsbook')
        self.assertEqual(first['outcomes'][0]['americanOdds'], -110)
        self.assertIsNone(first['projection'])

    def test_unknown_vendor_or_market_is_not_invented_as_predictions(self):
        self.assertIsNone(normalize_player_prop({**prop(), 'vendor': 'draftkings_predictions'}, NOW))
        self.assertIsNone(normalize_player_prop({**prop(), 'market': {'type': 'yes_no', 'odds': 60}}, NOW))
        self.assertEqual(normalize_game_odds({**odds(), 'vendor': 'hardrock'}, NOW), [])
        exchange = normalize_game_odds({**odds(), 'vendor': 'kalshi'}, NOW)[0]
        self.assertEqual(exchange['book']['kind'], 'other_prediction_market')
        self.assertFalse(exchange['draftKingsPredictionsEquivalent'])

    def test_exact_current_name_team_identity_not_provider_integer_or_fuzzy_guess(self):
        player = {'id': 99, 'first_name': 'SYNTHETIC', 'last_name': 'Receiver', 'team': {'abbreviation': 'BUF'}}
        roster = [{'id': '00-0000001', 'name': 'SYNTHETIC Receiver', 'team': 'BUF'}]
        self.assertEqual(map_player_identity(player, roster, ['BUF', 'BAL'])['gsisId'], '00-0000001')
        self.assertEqual(map_player_identity(player, [], ['BUF', 'BAL'])['status'], 'unmapped')
        self.assertEqual(map_player_identity(player, [{**roster[0], 'team': 'BAL'}])['status'], 'unmapped')
        self.assertEqual(map_player_identity(player, [*roster, {**roster[0], 'id': '00-0000002'}])['status'], 'conflict')
        self.assertEqual(map_player_identity(player, [{**roster[0], 'name': 'SYNTHETIC Similar Receiver'}])['status'], 'unmapped')
        self.assertIsNone(map_player_identity(player, [{'id': 99, 'name': 'SYNTHETIC Receiver', 'team': 'BUF'}])['gsisId'])

    def test_redirect_handler_never_forwards_auth_to_another_host(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, 'SYNTHETIC', {}, 'https://unrelated.invalid'))


class GatewayBoundaryTests(unittest.TestCase):
    def test_vercel_runtime_rejects_before_reading_provider_credential(self):
        real_get = os.environ.get
        accesses = []
        def guarded_get(name, default=None):
            accesses.append(name)
            if name == 'BALLDONTLIE_API_KEY':
                raise AssertionError('A provider key must never be read outside Render')
            if name in ('RENDER', 'RENDER_SERVICE_ID'):
                return default
            return real_get(name, default)
        with patch.object(os.environ, 'get', side_effect=guarded_get):
            with self.assertRaises(DataProviderError) as caught:
                bdl_credential()
        self.assertEqual(caught.exception.code, 'render_backend_required')
        self.assertNotIn('BALLDONTLIE_API_KEY', accesses)

    def test_private_gateway_auth_and_status_do_not_claim_premium_access(self):
        from . import sports_data_gateway as gateway
        with patch.dict(os.environ, {'RENDER': 'true', 'RENDER_SERVICE_ID': 'SYNTHETIC-RENDER-SERVICE',
                                    'GRIDIRON_DATA_BRIDGE_TOKEN': BRIDGE,
                                    'BALLDONTLIE_API_KEY': KEY}, clear=True):
            with TestClient(app) as web, patch.object(gateway.client, 'read') as read:
                self.assertEqual(web.get('/data/nfl/status').status_code, 401)
                self.assertEqual(web.get('/data/nfl/status', headers={'Authorization': 'Bearer wrong'}).status_code, 401)
                status = web.get('/data/nfl/status', headers={'Authorization': 'Bearer ' + BRIDGE}).json()
                self.assertEqual(status['diagnostic']['code'], 'credentials_configured_unverified')
                self.assertIsNone(status['diagnostic']['httpStatus'])
                self.assertNotIn(KEY, json.dumps(status))
                read.assert_not_called()
                health = web.get('/health').json()
                self.assertFalse(health['providerAccessVerified'])
                self.assertNotIn(KEY, json.dumps(health))

    def test_render_missing_credential_and_nonrender_are_distinct(self):
        with patch.dict(os.environ, {'GRIDIRON_DATA_BRIDGE_TOKEN': BRIDGE}, clear=True):
            with TestClient(app) as web:
                result = web.get('/data/nfl/status', headers={'Authorization': 'Bearer ' + BRIDGE}).json()
                self.assertEqual(result['diagnostic']['code'], 'render_backend_required')
        with patch.dict(os.environ, {'GRIDIRON_DATA_BRIDGE_TOKEN': BRIDGE, 'RENDER': 'true',
                                    'RENDER_SERVICE_ID': 'SYNTHETIC'}, clear=True):
            with TestClient(app) as web:
                result = web.get('/data/nfl/status', headers={'Authorization': 'Bearer ' + BRIDGE}).json()
                self.assertEqual(result['diagnostic']['code'], 'credentials_missing')


if __name__ == '__main__': unittest.main()
