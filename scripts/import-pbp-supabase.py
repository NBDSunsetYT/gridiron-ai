#!/usr/bin/env python3
"""Import authorized normalized NFL plays through a user's Supabase RLS session.

No service-role key, password, SQL access, destructive operation or token argument.
"""
import argparse
import csv
import getpass
import hashlib
import io
import json
import math
import os
import stat
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (ValueError, TypeError) as error:
        raise ValueError('Actual timezone-aware evidence timestamp required') from error
    if parsed.tzinfo is None:
        raise ValueError('Evidence timestamp requires a timezone')
    return parsed.astimezone(timezone.utc).isoformat()


def numeric(value, name):
    if value in ('', None, 'NA', 'NaN'):
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{name} must be a finite observed number')
    return int(number) if number.is_integer() else number


class SupabaseREST:
    def __init__(self, url, publishable_key, access_token):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' and parsed.hostname not in ('localhost', '127.0.0.1'):
            raise ValueError('Supabase requires HTTPS')
        if not publishable_key or publishable_key.startswith('sb_secret_'):
            raise ValueError('A publishable key is required; service-role/secret keys are forbidden')
        if publishable_key.startswith('eyJ'):
            import base64
            try:
                role = json.loads(base64.urlsafe_b64decode(publishable_key.split('.')[1] + '===')).get('role')
            except (ValueError, IndexError):
                role = None
            if role == 'service_role':
                raise ValueError('Service-role keys are forbidden')
        self.url, self.key, self.token = url.rstrip('/'), publishable_key, access_token
        user = self.request('GET', '/auth/v1/user')
        self.user_id = str(uuid.UUID(user['id']))

    def request(self, method, path, data=None, headers=None):
        request_headers = {'apikey': self.key, 'Authorization': 'Bearer ' + self.token}
        if data is not None:
            request_headers['content-type'] = 'application/json'
        request_headers.update(headers or {})
        request = urllib.request.Request(self.url + path, data=json.dumps(data).encode() if data is not None else None, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            # Do not log request headers, tokens, source rows or user credentials.
            raise ValueError(f'Supabase {method} request rejected (HTTP {error.code}); inspect ownership, schema and input evidence') from None
        except urllib.error.URLError:
            raise ValueError('Supabase network request failed; prior data was not deleted') from None

    def select(self, table, **filters):
        output = []
        for offset in range(0, 200000, 1000):
            query = {'select': '*', 'user_id': 'eq.' + self.user_id, 'order': 'id', 'limit': '1000', 'offset': str(offset), **filters}
            rows = self.request('GET', '/rest/v1/' + table + '?' + urllib.parse.urlencode(query)) or []
            output.extend(rows)
            if len(rows) < 1000:
                return output
        raise ValueError('Lookup exceeds bounded 200,000 rows; partition the dataset rather than silently truncating')

    def insert_ignoring_duplicates(self, table, rows, conflict):
        if not rows:
            return []
        path = '/rest/v1/' + table + '?' + urllib.parse.urlencode({'on_conflict': conflict})
        return self.request('POST', path, rows, {'Prefer': 'resolution=ignore-duplicates,return=representation'}) or []


def mapped_play(row, user_id, game_id, teams, players, source, version, collected_at):
    external = row.get('play_id', '').strip()
    if not external or not row.get('play_type'):
        raise ValueError('Every normalized play requires its actual play_id and play_type')
    event = timestamp(row.get('played_at'))
    available = timestamp(row['available_at']) if row.get('available_at') else None
    collected = timestamp(collected_at)
    if datetime.fromisoformat(event) > datetime.fromisoformat(collected):
        raise ValueError('Historical play event occurs after collection')
    if available and datetime.fromisoformat(available) > datetime.fromisoformat(collected):
        raise ValueError('Source availability occurs after collection')
    if available and datetime.fromisoformat(available) < datetime.fromisoformat(event):
        raise ValueError('An observed play cannot have been available before it occurred')
    down = numeric(row.get('down'), 'down')
    if down is not None and (not isinstance(down, int) or not 1 <= down <= 4):
        raise ValueError('Observed down must be 1..4')
    success = numeric(row.get('success'), 'success')
    if success not in (None, 0, 1):
        raise ValueError('Success must be an observed zero/one or unavailable')
    def team(key):
        value = row.get(key)
        if value and value not in teams:
            raise ValueError('A referenced team has not been imported into this account')
        return teams.get(value)
    def player(key):
        value = row.get(key)
        if value and value not in players:
            raise ValueError('A referenced player identity could not be resolved')
        return players.get(value)
    return {'id': str(uuid.uuid5(uuid.NAMESPACE_URL, user_id + '/play/' + row['game_id'] + '/' + external)),
            'user_id': user_id, 'game_id': game_id, 'external_id': external,
            'offense_team_id': team('offense'), 'defense_team_id': team('defense'),
            'passer_id': player('passer_id'), 'receiver_id': player('receiver_id'), 'rusher_id': player('rusher_id'),
            'play_type': row['play_type'], 'down': down,
            'distance': numeric(row.get('yards_to_go'), 'yards_to_go'), 'yardline': numeric(row.get('yardline_100'), 'yardline_100'),
            'epa': numeric(row.get('epa'), 'EPA'), 'success': None if success is None else bool(success),
            'data': {**row, 'sourceInterpretation': 'Normalized supplied play; absent values remain absent, not independent player guesses'},
            'source': source, 'collected_at': collected, 'event_at': event,
            'available_at': available, 'version': version,
            'reliability_status': 'user_attested_availability' if available else 'unverified_historical_availability'}


def import_plays(client, raw, source, chunk_size=200, dry_run=False, max_plays=100000):
    if not 1 <= chunk_size <= 500 or not 1 <= max_plays <= 100000:
        raise ValueError('chunk_size must be 1..500; max_plays must be 1..100000')
    if not isinstance(source, str) or not 3 <= len(source) <= 2000:
        raise ValueError('Source/license citation required')
    if len(raw.encode()) > 25_000_000:
        raise ValueError('Normalized CSV exceeds 25 MB; partition by actual game')
    rows = list(csv.DictReader(io.StringIO(raw)))
    required = {'game_id', 'play_id', 'played_at', 'offense', 'defense', 'play_type'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('Expected normalized play-by-play columns')
    if len(rows) > max_plays:
        raise ValueError('CSV exceeds max_plays; no data was changed')
    identities = [(r['game_id'], r['play_id']) for r in rows]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate play identity in input; reconcile evidence before importing')
    version = hashlib.sha256(raw.encode()).hexdigest()
    collected = datetime.now(timezone.utc).isoformat()
    teams = {r['external_id']: r['id'] for r in client.select('nfl_teams')}
    games = {}
    for game in sorted(set(r['game_id'] for r in rows)):
        found = client.select('nfl_games', external_id='eq.' + game)
        if len(found) != 1:
            raise ValueError('Every play game must first exist in this account; sync its schedule before importing')
        games[game] = found[0]['id']
    players = {r['external_id']: r['id'] for r in client.select('nfl_players')}
    needed = {}
    for row in rows:
        for field, name_field in [('passer_id', 'passer_name'), ('receiver_id', 'receiver_name'), ('rusher_id', 'rusher_name')]:
            external = row.get(field, '').strip()
            if external and external not in players and external not in needed:
                needed[external] = {'id': str(uuid.uuid5(uuid.NAMESPACE_URL, client.user_id + '/player/' + external)),
                    'user_id': client.user_id, 'external_id': external,
                    'team_id': teams.get(row.get('offense')), 'name': row.get(name_field, '').strip() or 'Name unavailable',
                    'position': row.get(field.replace('_id', '_position')) or None, 'source': source,
                    'collected_at': collected, 'event_at': timestamp(row['played_at']),
                    'available_at': None, 'version': version, 'reliability_status': 'unverified_historical_availability'}
    # Validate every play before writing any player identities or plays.
    provisional = {**players, **{key: value['id'] for key, value in needed.items()}}
    mapped = [mapped_play(row, client.user_id, games[row['game_id']], teams, provisional, source, version, collected) for row in rows]
    inserted_players = 0
    if not dry_run:
        for offset in range(0, len(needed), chunk_size):
            inserted_players += len(client.insert_ignoring_duplicates('nfl_players', list(needed.values())[offset:offset+chunk_size], 'user_id,external_id'))
        # Concurrent imports can have established different UUIDs for the same external ID.
        players = {r['external_id']: r['id'] for r in client.select('nfl_players')}
        mapped = [mapped_play(row, client.user_id, games[row['game_id']], teams, players, source, version, collected) for row in rows]
    inserted = 0
    if not dry_run:
        for offset in range(0, len(mapped), chunk_size):
            inserted += len(client.insert_ignoring_duplicates('nfl_plays', mapped[offset:offset+chunk_size], 'user_id,game_id,external_id'))
    return {'status': 'dry_run' if dry_run else 'completed', 'source': source, 'sourceVersion': version,
            'inputPlays': len(rows), 'games': len(games), 'insertedPlays': inserted,
            'existingPlaysRetained': 0 if dry_run else len(rows)-inserted, 'insertedPlayerIdentities': inserted_players,
            'chunkSize': chunk_size, 'historicalAvailability': 'Null unless explicitly present; no inferred publication times',
            'policy': 'Immutable original play identities retained; conflicts ignored, never overwritten. Partial network failures are safely retryable.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--source', required=True)
    parser.add_argument('--token-file', type=Path, help='Private 0600 file containing this user access token; token itself is never an argument')
    parser.add_argument('--chunk-size', type=int, default=200)
    parser.add_argument('--max-plays', type=int, default=100000)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.token_file:
        if os.name == 'posix' and stat.S_IMODE(args.token_file.stat().st_mode) & 0o077:
            raise ValueError('Token file must be private (0600 or stricter)')
        token = args.token_file.read_text().strip()
    else:
        token = os.environ.get('SUPABASE_USER_JWT') or getpass.getpass('Your current Supabase access token (hidden): ').strip()
    client = SupabaseREST(os.environ.get('SUPABASE_URL', ''), os.environ.get('SUPABASE_PUBLISHABLE_KEY', ''), token)
    if args.csv.stat().st_size > 25_000_000:
        raise ValueError('Normalized CSV exceeds 25 MB; partition by actual game')
    report = import_plays(client, args.csv.read_text(), args.source, args.chunk_size, args.dry_run, args.max_plays)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(str(error)) from None
