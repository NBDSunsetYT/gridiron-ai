"""Documented BALLDONTLIE NFL API adapter, strictly separate from DK Predictions.

Docs verified: https://nfl.balldontlie.io and official /openapi/nfl.yml.
Source odds are sportsbook references, not executable native event contracts.
"""
import copy
import hashlib
import json
import math
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable

from .sports_data_common import DataProviderError, utc_now

BASE = 'https://api.balldontlie.io/nfl/v1'
DOCS = 'https://nfl.balldontlie.io'
MAX_BYTES = 5_000_000
MAX_ROWS = 10_000
ARRAYS = {'team_ids', 'player_ids', 'game_ids', 'seasons', 'weeks', 'dates', 'season_types', 'vendors'}
PAGE = {'cursor', 'per_page'}
RESOURCES = {
    'teams': ('teams', 'Free', {'division', 'conference'}, 86400),
    'players': ('players', 'Free', PAGE | {'team_ids', 'player_ids', 'search', 'first_name', 'last_name'}, 900),
    'games': ('games', 'Free', PAGE | {'dates', 'team_ids', 'seasons', 'season_types', 'weeks'}, 60),
    'stats': ('stats', 'ALL-STAR', PAGE | {'player_ids', 'game_ids', 'seasons', 'season_type'}, 300),
    'injuries': ('player_injuries', 'ALL-STAR', PAGE | {'team_ids', 'player_ids'}, 120),
    'snap-counts': ('snap_counts', 'ALL-STAR', PAGE | {'player_ids', 'team_ids', 'game_ids', 'seasons', 'season_type'}, 600),
    'designations': ('player_designations', 'GOAT', PAGE | {'season', 'week', 'season_types', 'team_ids'}, 60),
    'odds': ('odds', 'GOAT', PAGE | {'season', 'week', 'season_types', 'game_ids'}, 20),
    'opening-odds': ('odds/opening', 'GOAT', PAGE | {'season', 'week', 'season_types', 'game_ids'}, 3600),
    'player-props': ('odds/player_props', 'GOAT', {'game_id', 'player_id', 'prop_type', 'vendors'}, 20),
    'opening-player-props': ('odds/player_props/opening', 'GOAT', {'game_id', 'player_id', 'prop_type', 'vendors'}, 3600),
}
BOOKS = {'draftkings': ('DraftKings Sportsbook', 'sportsbook'),
         'fanduel': ('FanDuel', 'sportsbook'), 'betmgm': ('BetMGM', 'sportsbook'),
         'betrivers': ('BetRivers', 'sportsbook'), 'caesars': ('Caesars Sportsbook', 'sportsbook'),
         'fanatics': ('Fanatics Sportsbook', 'sportsbook'),
         'kalshi': ('Kalshi reference odds', 'other_prediction_market'),
         'polymarket': ('Polymarket reference odds', 'other_prediction_market')}
PROP_BOOKS = {'betrivers', 'caesars', 'draftkings', 'fanatics', 'fanduel'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _integer(value, minimum=1, maximum=2_147_483_647):
    if isinstance(value, bool) or not re.fullmatch(r'\d{1,10}', str(value)):
        raise DataProviderError('invalid_request', 'A bounded integer parameter is required.')
    number = int(value)
    if not minimum <= number <= maximum:
        raise DataProviderError('invalid_request', 'A request parameter is outside its supported range.')
    return number


def validated_params(resource, params):
    if resource not in RESOURCES:
        raise DataProviderError('unsupported_resource', 'This NFL data resource is not supported.')
    if not isinstance(params, dict):
        raise DataProviderError('invalid_request', 'NFL query parameters must be an object.')
    allowed = RESOURCES[resource][2]
    output = []
    seen = set()
    values = {}
    for raw_key, value in params.items():
        key = raw_key[:-2] if raw_key.endswith('[]') else raw_key
        if key not in allowed or key in seen:
            raise DataProviderError('invalid_request', 'An unsupported or duplicate NFL query parameter was supplied.')
        seen.add(key)
        if key in ARRAYS:
            source = value if isinstance(value, list) else [value]
            if not source or len(source) > 100:
                raise DataProviderError('invalid_request', 'An NFL query array exceeds its bounded size.')
            normalized = []
            for item in source:
                if key == 'dates':
                    text = str(item)
                    try:
                        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
                            raise ValueError()
                        datetime.strptime(text, '%Y-%m-%d')
                    except ValueError:
                        raise DataProviderError('invalid_request', 'An exact calendar date is required.') from None
                elif key == 'vendors':
                    text = str(item)
                    if text not in PROP_BOOKS:
                        raise DataProviderError('unsupported_vendor', 'Player-prop vendor is not a documented supported sportsbook.')
                else:
                    text = str(_integer(item, 1, 2100 if key == 'seasons' else 2_147_483_647))
                    if key == 'seasons' and int(text) < 2002 or key == 'season_types' and int(text) not in (1, 2, 3) or key == 'weeks' and int(text) > 30:
                        raise DataProviderError('invalid_request', 'The NFL season, phase or week is unsupported.')
                normalized.append(text)
                output.append((key + '[]', text))
            values[key] = normalized
        elif key in {'search', 'first_name', 'last_name', 'division', 'conference', 'prop_type'}:
            text = str(value)
            if not text or len(text) > 80 or any(ord(c) < 32 for c in text):
                raise DataProviderError('invalid_request', 'A bounded text query is required.')
            output.append((key, text)); values[key] = text
        else:
            number = _integer(value, 0 if key == 'cursor' else 1)
            if key == 'per_page' and number > 100 or key == 'season' and not 2002 <= number <= 2100 or key == 'week' and number > 30 or key == 'season_type' and number not in (1, 2, 3):
                raise DataProviderError('invalid_request', 'The NFL page, season, phase or week is unsupported.')
            output.append((key, str(number))); values[key] = number
    if resource in ('odds', 'opening-odds') and not (values.get('game_ids') or values.get('season') and values.get('week')):
        raise DataProviderError('invalid_request', 'Game IDs or an NFL season and week are required for odds.')
    if resource in ('player-props', 'opening-player-props') and not values.get('game_id'):
        raise DataProviderError('invalid_request', 'An exact BALLDONTLIE NFL game ID is required for player props.')
    if resource == 'designations' and bool(values.get('season')) != bool(values.get('week')):
        raise DataProviderError('invalid_request', 'NFL designation season and week must be supplied together.')
    if resource == 'designations' and values.get('season_types') and not (values.get('season') and values.get('week')):
        raise DataProviderError('invalid_request', 'NFL season types require an exact season and week.')
    return sorted(output)


def _stamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _line(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,6}(?:\.\d{1,8})?', value):
        return None
    try:
        return value if Decimal(value).is_finite() else None
    except InvalidOperation:
        return None


def _american(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value != 0 and abs(value) <= 10_000_000 else None


def _positive_id(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 < value <= 2_147_483_647 else None


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _base_reference(row, observed_at, market_type, statistic, outcomes, line=None):
    game_id = _positive_id(row.get('game_id')); source_id = _positive_id(row.get('id'))
    vendor = row.get('vendor')
    if not game_id or not source_id or vendor not in BOOKS or not outcomes:
        return None
    name, venue_type = BOOKS[vendor]
    identity = {'sport': 'NFL', 'provider': 'BALLDONTLIE', 'gameId': game_id, 'book': vendor,
                'type': market_type, 'statistic': statistic, 'line': line,
                'playerId': row.get('player_id'), 'outcomeLines': [(v['side'], v.get('line')) for v in outcomes]}
    reference_id = _hash(identity)
    updated = _stamp(row.get('updated_at'))
    period = 'unspecified'
    if isinstance(statistic, str):
        match = re.search(r'_(1h|2h|[1-4]q)$', statistic)
        if match:
            period = match.group(1)
    return {'referenceId': reference_id, 'id': _hash([reference_id, outcomes]),
            'provider': 'BALLDONTLIE', 'sport': 'NFL', 'dataFamily': 'sportsbook_reference',
            'sourceRecordId': source_id, 'sourceRecordIdPermanent': False,
            'gameId': game_id, 'nflverseGameId': None,
            'book': {'key': vendor, 'name': name, 'kind': venue_type},
            'market': {'type': market_type, 'statistic': statistic, 'line': line, 'period': period,
                       'overtimeIncluded': None, 'settlementVerified': False},
            'outcomes': outcomes, 'sourceUpdatedAt': updated, 'quotedAt': None,
            'observedAt': observed_at, 'executionVerified': False,
            'exactOfferMapping': False, 'nativeContractId': None,
            'fees': None, 'settlementRules': None,
            'draftKingsPredictionsEquivalent': False,
            'sourceUrl': BASE + ('/odds/player_props' if row.get('player_id') else '/odds'),
            'timestampMeaning': 'updated_at is provider refresh time, not sportsbook quote publication or price-change time.',
            'availabilityMeaning': 'Reference odds only. BALLDONTLIE does not guarantee exact sportsbook offer mapping or current executable availability.',
            'projection': None, 'projectionStatus': 'identity_and_settlement_evidence_required'}


def normalize_game_odds(row, observed_at):
    if not isinstance(row, dict):
        return []
    output = []
    for kind, fields in [('moneyline', [('home', 'moneyline_home_odds', None), ('away', 'moneyline_away_odds', None)]),
                         ('spread', [('home', 'spread_home_odds', 'spread_home_value'), ('away', 'spread_away_odds', 'spread_away_value')]),
                         ('total', [('over', 'total_over_odds', 'total_value'), ('under', 'total_under_odds', 'total_value')])]:
        outcomes = []
        for side, odds_key, line_key in fields:
            odds = _american(row.get(odds_key)); line = _line(row.get(line_key)) if line_key else None
            if odds is not None and (line_key is None or line is not None):
                outcomes.append({'side': side, 'americanOdds': odds, 'line': line})
        item = _base_reference(row, observed_at, kind, 'team_points' if kind != 'moneyline' else 'game_winner', outcomes,
                               _line(row.get('total_value')) if kind == 'total' else None)
        if item:
            output.append(item)
    return output


def normalize_player_prop(row, observed_at):
    if not isinstance(row, dict) or not _positive_id(row.get('player_id')) or row.get('vendor') not in PROP_BOOKS:
        return None
    line = _line(row.get('line_value')); market = row.get('market'); statistic = row.get('prop_type')
    if line is None or not isinstance(market, dict) or not isinstance(statistic, str) or not statistic or len(statistic) > 80:
        return None
    kind = market.get('type'); outcomes = []
    if kind == 'over_under':
        for side in ('over', 'under'):
            odds = _american(market.get(side + '_odds'))
            if odds is not None:
                outcomes.append({'side': side, 'americanOdds': odds, 'line': line})
    elif kind == 'milestone':
        odds = _american(market.get('odds'))
        if odds is not None:
            outcomes.append({'side': 'milestone', 'americanOdds': odds, 'line': line})
    else:
        return None
    item = _base_reference(row, observed_at, kind, statistic, outcomes, line)
    if item:
        item['player'] = {'bdlId': row['player_id'], 'gsisId': None, 'name': None, 'team': None,
                          'mapping': {'status': 'unmapped', 'method': 'verified_current_roster_exact_name_team_required',
                                      'reason': 'BALLDONTLIE player ID is not a GSIS player ID. A verified roster identity is required.'}}
    return item


def canonical_team(value):
    return {'LAR': 'LA', 'JAC': 'JAX', 'WSH': 'WAS'}.get(str(value), str(value))


def canonical_name(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value)).replace('’', "'").split()).casefold()


def map_player_identity(provider_player, roster, allowed_teams=None):
    """No fuzzy matching, provider integer coercion to GSIS, or missing-as-zero."""
    unknown = {'status': 'unmapped', 'gsisId': None, 'method': 'exact_current_roster_name_and_team',
               'reason': 'A unique verified current NFL roster identity is unavailable.'}
    if not isinstance(provider_player, dict) or not isinstance(roster, list):
        return unknown
    team = canonical_team((provider_player.get('team') or {}).get('abbreviation', ''))
    name = canonical_name(str(provider_player.get('first_name', '')) + ' ' + str(provider_player.get('last_name', '')))
    if not team or not name or allowed_teams is not None and team not in {canonical_team(t) for t in allowed_teams}:
        return unknown
    matches = [p for p in roster if isinstance(p, dict) and canonical_team(p.get('team', '')) == team
               and re.fullmatch(r'00-\d{7}', str(p.get('id', '')))
               and name in {canonical_name(n) for n in [p.get('name', ''), *(p.get('aliases') if isinstance(p.get('aliases'), list) else [])]}]
    if len(matches) != 1:
        return {**unknown, 'status': 'conflict' if len(matches) > 1 else 'unmapped'}
    return {'status': 'verified', 'gsisId': matches[0]['id'], 'name': provider_player.get('first_name', '') + ' ' + provider_player.get('last_name', ''),
            'team': team, 'method': 'exact_current_roster_name_and_team', 'reason': None}


class BDLNFLClient:
    def __init__(self, credential: Callable[[], str], *, opener=None, clock=time.monotonic, now=utc_now, requests_per_minute=4):
        self._credential = credential
        self._opener = opener or urllib.request.build_opener(NoRedirect())
        self._clock = clock; self._now = now
        self._rate = min(max(int(requests_per_minute), 1), 4)  # Unknown account/trial: never assume paid throughput.
        self._calls = deque(); self._cache = {}; self._cache_bytes = 0; self._lock = threading.Lock()

    def _take_request(self):
        with self._lock:
            current = self._clock()
            while self._calls and self._calls[0] <= current - 60:
                self._calls.popleft()
            if len(self._calls) >= self._rate:
                raise DataProviderError('source_rate_limited', 'The conservative licensed-data request budget is temporarily used.',
                                        retryable=True, retry_after=max(1, math.ceil(60 - (current - self._calls[0]))))
            self._calls.append(current)

    def read(self, resource, params=None):
        checked = self._now()
        try:
            query = validated_params(resource, params or {})
            key = self._credential()
            if not key or len(key) < 8 or any(ord(c) < 33 for c in key):
                raise DataProviderError('credentials_missing', 'BALLDONTLIE credentials are not configured on the Render data gateway.', requires_operator=True)
            cache_id = _hash([resource, query, hashlib.sha256(key.encode()).hexdigest()])
            cached = self._cache.get(cache_id)
            if cached and cached['until'] > self._clock():
                result = copy.deepcopy(cached['value']); result['cacheStatus'] = 'hit'; result['checkedAt'] = checked
                return result
            self._take_request()
            path, tier, _, ttl = RESOURCES[resource]
            url = BASE + '/' + path + ('?' + urllib.parse.urlencode(query) if query else '')
            request = urllib.request.Request(url, headers={'Authorization': key, 'Accept': 'application/json', 'User-Agent': 'GRIDIRON-AI/8.0 licensed NFL reference'})
            try:
                with self._opener.open(request, timeout=12) as response:
                    status = response.status
                    if int(response.headers.get('Content-Length') or 0) > MAX_BYTES:
                        raise DataProviderError('unsupported_response', 'The provider response exceeds its safe ingestion bound.', http_status=status)
                    raw = response.read(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES or key.encode() in raw:
                        raise DataProviderError('unsupported_response', 'The provider response could not be safely verified.', http_status=status)
                    try:
                        body = json.loads(raw)
                        json.dumps(body, allow_nan=False)
                    except (ValueError, UnicodeDecodeError, RecursionError):
                        raise DataProviderError('unsupported_response', 'The provider did not return a valid JSON dataset.', http_status=status) from None
            except urllib.error.HTTPError as exc:
                code = exc.code
                if code == 401:
                    raise DataProviderError('authentication_or_tier_denied', 'BALLDONTLIE returned HTTP401; its documented meaning includes either credentials or account-tier access. The exact cause is not assumed.', http_status=code, requires_operator=True, required_tier=tier) from None
                if code == 403:
                    raise DataProviderError('tier_or_access_denied' if tier != 'Free' else 'access_denied', 'BALLDONTLIE denied access to this documented NFL resource. Account entitlement must be verified without bypassing access controls.', http_status=code, requires_operator=True, required_tier=tier) from None
                if code == 429:
                    value = exc.headers.get('Retry-After') if exc.headers else None
                    wait = min(int(value), 86400) if value and re.fullmatch(r'\d{1,6}', value) else 60
                    raise DataProviderError('source_rate_limited', 'BALLDONTLIE temporarily rate limited this request.', http_status=code, retryable=True, retry_after=wait) from None
                raise DataProviderError('source_unavailable' if code >= 500 else 'source_request_failed', 'The documented BALLDONTLIE NFL request could not be completed.', http_status=code, retryable=code >= 500, requires_operator=code < 500) from None
            except (TimeoutError, urllib.error.URLError, OSError):
                raise DataProviderError('source_network_error', 'No verified response was received from the NFL data provider.', retryable=True) from None
            if not isinstance(body, dict) or not isinstance(body.get('data'), list) or len(body['data']) > MAX_ROWS or any(not isinstance(row, dict) for row in body['data']):
                raise DataProviderError('unsupported_response', 'The documented NFL response schema could not be verified.', http_status=status)
            meta = body.get('meta') or {}
            if not isinstance(meta, dict):
                raise DataProviderError('unsupported_response', 'The NFL pagination metadata is unsupported.', http_status=status)
            cursor = meta.get('next_cursor')
            if cursor is not None:
                cursor = _integer(cursor, 0)
            if resource in ('player-props', 'opening-player-props') and cursor is not None:
                raise DataProviderError('unsupported_response', 'The documented player-prop resource does not support pagination.', http_status=status)
            items = []; rejected = 0
            if resource in ('odds', 'opening-odds'):
                for row in body['data']:
                    values = normalize_game_odds(row, checked); items.extend(values); rejected += int(not values)
            elif resource in ('player-props', 'opening-player-props'):
                for row in body['data']:
                    item = normalize_player_prop(row, checked)
                    if item: items.append(item)
                    else: rejected += 1
            is_market = resource in ('odds', 'opening-odds', 'player-props', 'opening-player-props')
            result = {'provider': 'BALLDONTLIE', 'sport': 'NFL', 'resource': resource,
                      'dataFamily': 'sportsbook_reference' if is_market else 'nfl_statistics_reference',
                      'status': 'partial' if cursor is not None or rejected else 'available',
                      'checkedAt': checked, 'observedAt': checked, 'cacheStatus': 'miss',
                      'items': items, 'records': [] if is_market else body['data'],
                      'complete': cursor is None, 'nextCursor': cursor,
                      'source': {'url': BASE + '/' + path, 'documentationUrl': DOCS,
                                 'collectedAt': checked, 'version': hashlib.sha256(raw).hexdigest(),
                                 'providerAvailabilityAt': None, 'requiredTier': tier},
                      'diagnostic': {'code': 'no_matching_markets' if is_market and not body['data'] else 'no_matching_records' if not body['data'] else 'unsupported_records' if rejected else 'available',
                                     'message': 'Verified provider response; unsupported reference rows remain withheld. American odds are not DraftKings Predictions percentage prices.' if is_market else 'Verified provider response. Missing reported values remain missing, not zero.',
                                     'httpStatus': status, 'retryable': False, 'requiresOperator': False,
                                     'checkedAt': checked, 'requiredTier': tier,
                                     'counts': {'received': len(body['data']), 'accepted': len(items) if is_market else len(body['data']), 'rejected': rejected}},
                      'limitations': ['Provider IDs are scoped to BALLDONTLIE; they are not GSIS or native DraftKings Predictions contract IDs.',
                                      'Provider refresh timestamps do not establish executable sportsbook availability or original publication time.',
                                      'No event-contract fee, settlement rules or prediction-market probability is inferred.']}
            with self._lock:
                size = len(json.dumps(result, allow_nan=False, separators=(',', ':')).encode())
                # A free Render gateway must not accumulate one large cache per
                # caller. Oversized verified responses may be returned once,
                # but are never silently truncated or cached without bounds.
                if size <= 6_000_000:
                    old = self._cache.pop(cache_id, None)
                    if old: self._cache_bytes -= old['size']
                    while self._cache and (len(self._cache) >= 16 or self._cache_bytes + size > 12_000_000):
                        old = self._cache.pop(next(iter(self._cache))); self._cache_bytes -= old['size']
                    self._cache[cache_id] = {'until': self._clock() + ttl, 'value': copy.deepcopy(result), 'size': size}
                    self._cache_bytes += size
            return result
        except DataProviderError as exc:
            return {'provider': 'BALLDONTLIE', 'sport': 'NFL', 'resource': resource,
                    'dataFamily': 'sportsbook_reference' if resource in ('odds', 'opening-odds', 'player-props', 'opening-player-props') else 'nfl_statistics_reference',
                    'status': 'unavailable', 'checkedAt': checked, 'items': [], 'records': [], 'complete': False,
                    'nextCursor': None, 'diagnostic': exc.diagnostic(checked),
                    'source': {'documentationUrl': DOCS},
                    'limitations': ['No alternate provider or invented data was substituted.']}
