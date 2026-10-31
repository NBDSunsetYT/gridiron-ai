"""Automatic, source-cited NFL research for the private compute service.

Only fixed, public nflverse release assets are fetched. An app user never sends
a dataset or an upstream URL. Personal records and administrative DB keys do not
enter this module. Cached files are disposable; the web service persists results.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request

from .fit import fit_csv, utc
from .nflverse_adapter import normalize, number
from .simulator import Evidence, simulate, evaluate_contract

VERSION = 'automatic-nfl-research-6.0.0'
BASE = 'https://github.com/nflverse/nflverse-data/releases/download'
TEAMS = {'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB','HOU','IND','JAX','KC','LA','LAC','LV','MIA','MIN','NE','NO','NYG','NYJ','PHI','PIT','SEA','SF','TB','TEN','WAS'}
ALIASES = {'LAR':'LA','WSH':'WAS','JAC':'JAX','OAK':'LV','SD':'LAC'}
ASSETS = {'pbp': ('pbp','play_by_play'), 'injuries': ('injuries','injuries'),
          'snaps': ('snap_counts','snap_counts'), 'rosters': ('rosters','roster'),
          'depth': ('depth_charts','depth_charts'), 'player_stats':('stats_player','stats_player_week'),
          'team_stats':('stats_team','stats_team_week')}
REQUIRED_COLUMNS = {'pbp':{'game_id','play_id','time_of_day','posteam','defteam','play_type','season','week'},
                    'injuries':{'team','week','gsis_id','report_status','practice_status'},
                    'snaps':{'game_id','pfr_player_id','team','offense_snaps','defense_snaps'},
                    'rosters':{'team','week','gsis_id','pfr_id','status','full_name'},
                    'depth':{'dt','team','gsis_id','pos_abb','pos_rank'},
                    'player_stats':{'player_id','team','week','season_type','targets','carries'},
                    'team_stats':{'team','week','season_type','targets','carries'}}
MAX_COMPRESSED = 35_000_000
MAX_EXPANDED = 240_000_000
MAX_ROWS = 1_000_000
_download_locks = defaultdict(threading.Lock)
_models = {}
_model_lock = threading.Lock()


class ResearchUnavailable(ValueError):
    """Evidence is unavailable; callers must not replace it with guessed data."""
    def __init__(self,message,*,retryable=False,upstream_status_code=None):
        super().__init__(message)
        self.retryable=bool(retryable)
        self.status_code=503 if self.retryable else 422
        self.upstream_status_code=upstream_status_code


def stamp():
    return datetime.now(timezone.utc).isoformat()


def team_id(value):
    value = ALIASES.get(value, value)
    if value not in TEAMS:
        raise ResearchUnavailable('The matchup must use recognized NFL team identifiers.')
    return value


def validate_game(value, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(value, dict) or not isinstance(value.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value['id']):
        raise ResearchUnavailable('A trusted scheduled NFL game is required.')
    home, away = team_id(value.get('home')), team_id(value.get('away'))
    if home == away:
        raise ResearchUnavailable('A matchup needs two distinct NFL teams.')
    event = utc(value.get('startTime'))
    if event <= now:
        raise ResearchUnavailable('This engine estimates pre-game outcomes. Kickoff has passed; no live-game probability was invented.')
    season, week = value.get('season'), value.get('week')
    if isinstance(season, bool) or not isinstance(season, int) or not now.year-1 <= season <= now.year+1:
        raise ResearchUnavailable('The scheduled NFL season is outside automatic source coverage.')
    if isinstance(week, bool) or not isinstance(week, int) or not 1 <= week <= 22:
        raise ResearchUnavailable('A valid scheduled NFL week is required.')
    return {**value, 'home':home, 'away':away, 'startTime':event.isoformat(), 'season':season, 'week':week}


@dataclass
class Dataset:
    path: Path
    metadata: dict

    def rows(self):
        with self.path.open('rb') as handle:
            source = gzip.GzipFile(fileobj=handle) if self.path.name.endswith('.gz') else handle
            with io.TextIOWrapper(io.BufferedReader(BoundedReader(source)), encoding='utf-8-sig', newline='') as text:
                for index, row in enumerate(csv.DictReader(text)):
                    if index >= MAX_ROWS:
                        raise ResearchUnavailable('The public source exceeds its validated row bound. No truncated dataset was fitted.')
                    yield row


class BoundedReader(io.RawIOBase):
    def __init__(self, source):
        self.source, self.count = source, 0

    def readable(self):
        return True

    def readinto(self, target):
        content = self.source.read(len(target))
        self.count += len(content)
        if self.count > MAX_EXPANDED:
            raise ResearchUnavailable('The public source exceeds its validated expansion bound.')
        target[:len(content)] = content
        return len(content)


def source_url(kind, season):
    if kind not in ASSETS or isinstance(season, bool) or not isinstance(season, int) or not 1999 <= season <= datetime.now(timezone.utc).year+1:
        raise ResearchUnavailable('Unsupported automatic source.')
    tag, prefix = ASSETS[kind]
    return f'{BASE}/{tag}/{prefix}_{season}.csv.gz'


def fetch_dataset(kind, season, ttl=900):
    """Bounded atomic cache. No user-controlled URLs, keys, cookies or scraping."""
    url = source_url(kind, season)
    root = Path(os.environ.get('GRIDIRON_PUBLIC_CACHE_DIR', '/tmp/gridiron-public-research'))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()
    path, manifest = root/(key+'.csv.gz'), root/(key+'.json')
    with _download_locks[key]:
        if path.exists() and manifest.exists():
            try:
                meta = json.loads(manifest.read_text())
                if meta.get('schemaVerified') and 0 <= time.time()-utc(meta['checkedAt']).timestamp() < ttl and path.stat().st_size <= MAX_COMPRESSED:
                    # A newly queued job may reflect a verified upstream change
                    # before the local TTL expires. Revalidate cached bytes, so a
                    # new input fingerprint cannot publish an old roster/model.
                    probe = urllib.request.Request(url, method='HEAD', headers={'User-Agent':'GRIDIRON-AI/5.0 (+https://github.com/NBDSunsetYT/gridiron-ai)'})
                    try:
                        with urllib.request.urlopen(probe, timeout=10) as response:
                            etag = response.headers.get('ETag')
                            unchanged = bool(etag and meta.get('etag') and etag == meta['etag'])
                        if unchanged:
                            meta['lastCheckedAt'] = stamp()
                            return Dataset(path, meta)
                    except (OSError, ValueError):
                        # Fetch current bytes below if a HEAD cannot establish
                        # identity; never silently publish a stale cached asset.
                        pass
            except (OSError, ValueError, KeyError, TypeError):
                pass
        temporary = root/(key+'.'+str(threading.get_ident())+'.part')
        request = urllib.request.Request(url, headers={'User-Agent':'GRIDIRON-AI/5.0 (+https://github.com/NBDSunsetYT/gridiron-ai)', 'Accept':'application/octet-stream'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response, temporary.open('wb') as target:
                os.chmod(temporary, 0o600)
                digest, size = hashlib.sha256(), 0
                while True:
                    chunk = response.read(1_000_000)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_COMPRESSED:
                        raise ResearchUnavailable('Public source exceeds the validated download bound.')
                    digest.update(chunk)
                    target.write(chunk)
                headers = response.headers
            with temporary.open('rb') as check:
                magic = check.read(2)
            if size < 20 or magic != b'\x1f\x8b':
                raise ResearchUnavailable('The public source did not return a valid gzip data asset.')
            with gzip.open(temporary,'rt',encoding='utf-8-sig',newline='') as first:
                columns = set(next(csv.reader(first),[]))
            if not REQUIRED_COLUMNS[kind].issubset(columns):
                raise ResearchUnavailable(f'nflverse {kind} source schema changed; unsupported fields were not guessed.')
            modified = headers.get('Last-Modified')
            try:
                modified = parsedate_to_datetime(modified).astimezone(timezone.utc).isoformat() if modified else None
            except (TypeError, ValueError):
                modified = None
            meta = {'id':'nflverse-'+kind, 'name':'nflverse '+{'pbp':'play-by-play','snaps':'snap counts','depth':'depth charts'}.get(kind,kind),
                    'kind':kind, 'url':url, 'season':season, 'checkedAt':stamp(), 'sourceUpdatedAt':modified,
                    'version':digest.hexdigest(), 'etag':headers.get('ETag'), 'bytes':size,
                    'status':'available', 'schemaVerified':True, 'access':'Public nflverse release asset; upstream attribution and source terms apply.',
                    'publicationAt':None, 'reliability':'retrieved_and_schema_checked; historical first-publication time unknown'}
            os.replace(temporary, path)
            manifest.write_text(json.dumps(meta))
            os.chmod(manifest, 0o600)
            return Dataset(path, meta)
        except urllib.error.HTTPError as error:
            retryable=error.code in (408,429) or 500<=error.code<=599
            raise ResearchUnavailable(f'nflverse {kind} source returned HTTP {error.code}; no substitute data was invented.',
                                      retryable=retryable,upstream_status_code=error.code) from None
        except (OSError, EOFError) as error:
            raise ResearchUnavailable(f'nflverse {kind} source is temporarily unavailable.',retryable=True) from None
        finally:
            temporary.unlink(missing_ok=True)


def _integer(value, default=0):
    try:
        n = float(value)
        return int(n) if math.isfinite(n) and n.is_integer() else default
    except (TypeError, ValueError):
        return default


def _number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


PBP_FIELDS = {'season_type','season','week','game_id','play_id','posteam','defteam','play_type','no_play','penalty','extra_point_attempt','two_point_attempt','sack','qb_kneel','qb_spike','time_of_day','down','yardline_100','game_half','game_seconds_remaining','passer_player_id','receiver_player_id','rusher_player_id','passer_player_name','receiver_player_name','rusher_player_name','complete_pass','lateral_reception','lateral_rush','lateral_return','fixed_drive','drive','field_goal_result','extra_point_result','two_point_conv_result','ydstogo','score_differential','yards_gained','elapsed_seconds','interception','fumble_lost','kick_distance','return_yards','epa','success','air_yards','yards_after_catch'}


def select_plays(dataset, teams, cutoff, max_games=10):
    candidates, latest, names = [], {}, {}
    for raw in dataset.rows():
        if raw.get('season_type') != 'REG' or raw.get('posteam') not in teams and raw.get('defteam') not in teams:
            continue
        try:
            at = utc(raw.get('time_of_day'))
        except ValueError:
            continue
        if at >= cutoff:
            continue
        row = {key:raw.get(key,'') for key in PBP_FIELDS}
        for optional in ('epa','success','air_yards','yards_after_catch'):
            if _number(row.get(optional)) is None:
                row[optional] = ''
        for prefix in ('passer','receiver','rusher'):
            if raw.get(prefix+'_player_id') and raw.get(prefix+'_player_name'):
                names[raw[prefix+'_player_id']] = raw[prefix+'_player_name']
        latest[row['game_id']] = max(latest.get(row['game_id'],at),at)
        candidates.append(row)
    chosen = set()
    for team in teams:
        games = {row['game_id'] for row in candidates if row['posteam']==team}
        chosen.update(sorted(games, key=lambda key:latest[key], reverse=True)[:max_games])
    return [row for row in candidates if row['game_id'] in chosen], names


def current_rosters(rows, teams, week):
    selected = [row for row in rows if row.get('team') in teams and _integer(row.get('week')) <= week and row.get('gsis_id')]
    latest = {team:max((_integer(row.get('week')) for row in selected if row.get('team')==team), default=0) for team in teams}
    return {row['gsis_id']:row for row in selected if _integer(row.get('week'))==latest[row['team']]}, min(latest.values(),default=0)


def injury_records(rows, teams, week, source):
    selected = [row for row in rows if row.get('team') in teams and _integer(row.get('week'))==week]
    output = []
    for row in selected:
        status = row.get('report_status','').strip()
        practice = row.get('practice_status','').strip()
        if not status and not practice and not row.get('report_primary_injury') and not row.get('practice_primary_injury'):
            continue
        output.append({'playerId':row.get('gsis_id') or None, 'player':row.get('full_name') or None, 'name':row.get('full_name') or None,
                       'team':row.get('team'), 'position':row.get('position') or None, 'status':status.lower().replace(' ','_') if status else 'practice_report_only',
                       'designation':status or None, 'practiceParticipation':practice or None,
                       'injury':row.get('report_primary_injury') or row.get('practice_primary_injury') or None,
                       'week':week, 'source':source['url'], 'sourceName':'nflverse injury-report dataset', 'publicationAt':None,
                       'sourceUpdatedAt':source.get('sourceUpdatedAt'), 'checkedAt':source['checkedAt'],
                       'confirmedInactive':False, 'availability':{'out':1,'active':0,'limited':0} if status.lower()=='out' else None,
                       'availabilityAssessment':'Reported OUT designation; game-day inactive list not supplied.' if status.lower()=='out' else 'Availability uncertain; no calibrated probability was invented.'})
    return output


def availability_labels(raw_rows, injuries, snaps, roster):
    """Exact stable-ID joins only. Missing plays/snaps are never an OUT label."""
    pfr_to_gsis = {row.get('pfr_id'):pid for pid,row in roster.items() if row.get('pfr_id')}
    game_info = {row['game_id']:(_integer(row.get('season')),_integer(row.get('week')),{row.get('posteam'),row.get('defteam')}) for row in raw_rows}
    participants = defaultdict(set)
    for row in raw_rows:
        for field in ('passer_player_id','receiver_player_id','rusher_player_id'):
            if row.get(field):
                participants[row['game_id']].add(row[field])
    labels = defaultdict(dict)
    for row in snaps:
        player = pfr_to_gsis.get(row.get('pfr_player_id'))
        if player and row.get('game_id') in game_info and any((_number(row.get(key)) or 0)>0 for key in ('offense_snaps','defense_snaps','st_snaps')):
            labels[row['game_id']][player] = 'active'
    conflicts = 0
    for row in injuries:
        if row.get('report_status','').lower() != 'out' or not row.get('gsis_id'):
            continue
        player = row['gsis_id']
        for game,(season,week,teams) in game_info.items():
            if season==_integer(row.get('season')) and week==_integer(row.get('week')) and row.get('team') in teams:
                if player in participants[game] or labels[game].get(player)=='active':
                    conflicts += 1
                    continue
                labels[game][player] = 'inactive'
    return dict(labels), conflicts


def normalized_evidence(raw_rows, labels, source_version, collected_at):
    text, report = normalize(raw_rows, 18)
    rows = list(csv.DictReader(io.StringIO(text)))
    for row in rows:
        row['availability'] = json.dumps(labels.get(row['game_id'],{}),separators=(',',':'))
        row['available_at'] = collected_at
        row['collected_at'] = collected_at
        row['source_version'] = source_version
        row['reliability'] = 'verified'
    target = io.StringIO()
    fields = list(rows[0]) if rows else list(csv.DictReader(io.StringIO(text)).fieldnames or [])
    writer = csv.DictWriter(target,fieldnames=fields)
    writer.writeheader();writer.writerows(rows)
    report['availabilityProvenance'] = 'Actual explicit OUT reports and exact PFR-to-GSIS positive snap participation. Missing data never means inactive; active means observed participation, not unrestricted usage.'
    return target.getvalue(), report


def player_usage(model, roster, snap_rows, injuries, names, teams):
    excluded = {row['playerId']:row['availabilityAssessment'] for row in injuries if row.get('playerId') and row['status'] in ('out','questionable','doubtful','injured_reserve')}
    latest_game = defaultdict(str)
    for row in model['rows']:
        if row['o'] in teams:
            latest_game[row['o']] = max(latest_game[row['o']],row['at'])
    pfr_to_gsis = {r.get('pfr_id'):pid for pid,r in roster.items() if r.get('pfr_id')}
    snap_values = defaultdict(list)
    for row in snap_rows:
        pid = pfr_to_gsis.get(row.get('pfr_player_id'))
        if pid and row.get('team') in teams:
            snap_values[pid].append({'gameId':row.get('game_id'),'week':_integer(row.get('week')),'offenseSnaps':_number(row.get('offense_snaps')),'offenseShare':_number(row.get('offense_pct')),'defenseShare':_number(row.get('defense_pct'))})
    output = {}
    for pid,row in roster.items():
        names[pid] = row.get('full_name') or names.get(pid,pid)
        if row.get('status') != 'ACT':
            excluded.setdefault(pid,'Current roster does not list this player as active; a participation scenario is not supported.')
        relevant = [r for r in model['rows'] if pid in (r['qb'],r['receiver'],r['runner'])]
        if not relevant:
            continue
        team = row.get('team')
        features = model.get('teamResearch',{}).get(team,{})
        output[pid] = {'playerId':pid,'name':names[pid],'team':team,'position':row.get('position'),
                       'targetShare':features.get('targetShares',{}).get(pid), 'rushingShare':features.get('carryShares',{}).get(pid),
                       'recentSnaps':sorted(snap_values[pid],key=lambda x:x['week'],reverse=True)[:4],
                       'lastObservedPlayAt':max(r['at'] for r in relevant),'historicalGames':len({r['game'] for r in relevant}),
                       'status':row.get('status'), 'projectionWithheld':pid in excluded,'withheldReason':excluded.get(pid),
                       'routeParticipation':None}
    return output, excluded


STAT_FIELDS = ('completions','attempts','passing_yards','passing_tds','passing_interceptions','sacks_suffered',
               'carries','rushing_yards','rushing_tds','targets','receptions','receiving_yards','receiving_tds',
               'passing_air_yards','receiving_air_yards','passing_epa','rushing_epa','receiving_epa')


def verified_statistics(player_rows, team_rows, teams, upcoming_week):
    """Published weekly totals, kept separate from selected-play model features."""
    team_logs = defaultdict(list)
    players = defaultdict(list)
    for row in team_rows:
        if row.get('team') in teams and row.get('season_type')=='REG' and 0<_integer(row.get('week'))<upcoming_week:
            team_logs[row['team']].append({'gameId':row.get('game_id'),'week':_integer(row['week']),
                                           'statistics':{key:_number(row.get(key)) for key in STAT_FIELDS}})
    for row in player_rows:
        if row.get('team') in teams and row.get('player_id') and row.get('season_type')=='REG' and 0<_integer(row.get('week'))<upcoming_week:
            players[row['player_id']].append({'gameId':row.get('game_id'),'week':_integer(row['week']),'team':row['team'],
                                               'name':row.get('player_display_name') or row.get('player_name'),
                                               'statistics':{key:_number(row.get(key)) for key in STAT_FIELDS}})
    def totals(logs):
        return {key:sum(row['statistics'][key] for row in logs if row['statistics'][key] is not None)
                if any(row['statistics'][key] is not None for row in logs) else None for key in STAT_FIELDS}
    team_output = {team:{'totals':totals(logs),'games':len(logs),'recentGameLogs':sorted(logs,key=lambda r:r['week'],reverse=True)[:4]}
                   for team,logs in team_logs.items()}
    output = {}
    for pid,logs in players.items():
        observed = totals(logs)
        target_denominator = sum((team_output.get(team,{}).get('totals',{}).get('targets') or 0) for team in {r['team'] for r in logs})
        carry_denominator = sum((team_output.get(team,{}).get('totals',{}).get('carries') or 0) for team in {r['team'] for r in logs})
        output[pid] = {'totals':observed,'games':len(logs),'name':logs[-1].get('name'),
                       'targetShare':observed['targets']/target_denominator if observed['targets'] is not None and target_denominator else None,
                       'rushingShare':observed['carries']/carry_denominator if observed['carries'] is not None and carry_denominator else None,
                       'recentGameLogs':sorted(logs,key=lambda r:r['week'],reverse=True)[:4]}
    return output, team_output


def analyze_public(data, fetcher=fetch_dataset, now=None):
    started = time.monotonic()
    now = now or datetime.now(timezone.utc)
    if not isinstance(data,dict) or set(data)-{'game','simulations','seed','inputContext'}:
        raise ResearchUnavailable('Supply a trusted game, supported simulation count and research context only.')
    game = validate_game(data.get('game'),now)
    count = data.get('simulations',10000)
    if isinstance(count,bool) or not isinstance(count,int) or count not in (10000,50000,100000):
        raise ResearchUnavailable('Automatic research supports 10,000, 50,000 or 100,000 complete games.')
    seed = data.get('seed',int(hashlib.sha256(game['id'].encode()).hexdigest()[:12],16))
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=2**53-1:
        raise ResearchUnavailable('A finite reproducible integer seed is required.')
    context = data.get('inputContext') or {}
    if not isinstance(context,dict):
        raise ResearchUnavailable('Research context must be an object.')
    what_if = context.get('whatIf')
    if what_if is not None and (not isinstance(what_if,dict) or set(what_if)!={'playerId','status'} or
            not isinstance(what_if.get('playerId'),str) or not what_if['playerId'] or
            what_if.get('status') not in ('active','limited','inactive')):
        raise ResearchUnavailable('A hypothetical availability scenario requires only an exact playerId and active|limited|inactive status. Unsupported snap, pace, weather and efficiency multipliers are not applied.')
    datasets, sources = {}, []
    with ThreadPoolExecutor(max_workers=5) as pool:
        pending = {pool.submit(fetcher,kind,game['season']):kind for kind in ASSETS}
        for future in as_completed(pending):
            kind = pending[future]
            try:
                datasets[kind] = future.result()
                sources.append(datasets[kind].metadata)
            except (ValueError,OSError,EOFError) as error:
                # A temporary provider outage must not become a permanent
                # insufficient-evidence result (or a completed partial cache).
                # Retrying the existing fenced job can recheck current bytes.
                if isinstance(error,ResearchUnavailable) and error.retryable:
                    raise error
                if isinstance(error,(OSError,EOFError)):
                    raise ResearchUnavailable('A published NFL research source is temporarily unavailable.',retryable=True) from None
                if kind=='pbp':
                    if isinstance(error,ResearchUnavailable):raise error
                    raise ResearchUnavailable(str(error)) from None
                sources.append({'id':'nflverse-'+kind,'kind':kind,'url':source_url(kind,game['season']),'status':'unavailable','checkedAt':stamp(),'reason':str(error)[:300]})
    teams = {game['home'],game['away']}
    raw, names = select_plays(datasets['pbp'],teams,now,10)
    injury_rows = list(datasets['injuries'].rows()) if 'injuries' in datasets else []
    snap_rows = [row for row in datasets['snaps'].rows() if row.get('team') in teams] if 'snaps' in datasets else []
    roster, roster_week = current_rosters(datasets['rosters'].rows(),teams,game['week']) if 'rosters' in datasets else ({},0)
    labels, conflicts = availability_labels(raw,injury_rows,snap_rows,roster)
    pbp_source = datasets['pbp'].metadata
    evidence_version = hashlib.sha256(json.dumps({'rows':raw,'labels':labels},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    normalized, conversion = normalized_evidence(raw,labels,evidence_version,pbp_source['checkedAt'])
    as_of = stamp()
    if utc(as_of)>=utc(game['startTime']):
        raise ResearchUnavailable('Kickoff occurred during research. No new pre-game forecast was published.')
    cache_key = hashlib.sha256(json.dumps([VERSION,game['home'],game['away'],evidence_version,as_of[:10]]).encode()).hexdigest()
    with _model_lock:
        fit = _models.get(cache_key)
    if fit is None:
        fit = fit_csv(normalized,pbp_source['url']+'; automatically retrieved current public source; historical first-publication times unknown',as_of,
                      options={'recencyHalfLifeDays':90,'conditionalShrinkage':True,'strictAvailability':True})
        with _model_lock:
            if len(_models)>=8:
                _models.pop(next(iter(_models)))
            _models[cache_key] = fit
    reports = injury_records(injury_rows,teams,game['week'],datasets['injuries'].metadata) if 'injuries' in datasets else []
    usage, withheld = player_usage(fit['model'],roster,snap_rows,reports,names,teams)
    player_statistics, team_statistics = verified_statistics(
        datasets['player_stats'].rows() if 'player_stats' in datasets else [],
        datasets['team_stats'].rows() if 'team_stats' in datasets else [],teams,game['week'])
    for pid,statistics in player_statistics.items():
        if statistics.get('name'):
            names[pid] = statistics['name']
        if pid in usage:
            usage[pid]['seasonStatistics'] = statistics
            usage[pid]['targetShare'] = statistics['targetShare']
            usage[pid]['rushingShare'] = statistics['rushingShare']
    # A current roster is essential for publishing current-player projections.
    if not roster or roster_week<game['week']-1:
        for row in fit['model']['rows']:
            for field in ('qb','receiver','runner'):
                if row[field]:
                    withheld.setdefault(row[field],'Current roster coverage is unavailable or stale.')
    else:
        for row in fit['model']['rows']:
            for field in ('qb','receiver','runner'):
                if row[field] and row[field] not in roster:
                    withheld.setdefault(row[field],'Historical player is not on the current verified team roster.')
    scenario, scenario_audit = None, []
    confirmed = [r for r in reports if r['status']=='out' and r.get('playerId')]
    # Preserve the existing evidence-conditioned engine. Unsupported joint or
    # small-cohort injuries remain explicit limitations, never multipliers.
    if len(confirmed)==1:
        candidate = {'playerId':confirmed[0]['playerId'],'status':'inactive'}
        try:
            cohort = Evidence(fit['model'],game['home'],game['away'],candidate)
            scenario = candidate
            scenario_audit.append({'playerId':candidate['playerId'],'status':'applied','historicalGames':len(cohort.games),'method':'Complete games from explicitly labeled inactive historical evidence.'})
        except ValueError as error:
            scenario_audit.append({'playerId':candidate['playerId'],'status':'withheld','reason':str(error)})
    elif confirmed:
        scenario_audit.append({'status':'withheld','reason':'Joint availability effects for multiple reported OUT players have no validated joint historical cohort.'})
    if what_if is not None:
        if what_if['playerId'] not in roster:
            raise ResearchUnavailable('The hypothetical player is not on the current verified matchup roster.')
        if any(report['playerId']!=what_if['playerId'] for report in confirmed):
            raise ResearchUnavailable('A hypothetical change combined with another reported OUT player requires a validated joint availability cohort; no combined multiplier was invented.')
        try:
            cohort = Evidence(fit['model'],game['home'],game['away'],what_if)
        except ValueError as error:
            raise ResearchUnavailable('This hypothetical availability scenario has insufficient historical evidence: '+str(error)) from None
        scenario = dict(what_if)
        scenario_audit.append({'playerId':scenario['playerId'],'status':'hypothetical_applied',
                               'assumedAvailability':scenario['status'],'historicalGames':len(cohort.games),
                               'method':'Conditioned on explicitly labeled historical availability. Current reports are unchanged.'})
        if scenario['status'] in ('active','limited'):
            withheld.pop(scenario['playerId'],None)
            if scenario['playerId'] in usage:
                usage[scenario['playerId']].update(projectionWithheld=False,withheldReason=None,
                                                  hypotheticalAvailability=scenario['status'])
    definitions = context.get('contractDefinitions') or []
    if not isinstance(definitions,list) or len(definitions)>32:
        raise ResearchUnavailable('Verified contract definitions exceed the supported research bound.')
    accepted, withheld_contracts = [], []
    for definition in definitions:
        if not isinstance(definition,dict):
            raise ResearchUnavailable('A verified contract definition must be an object.')
        if definition.get('period','full_game_including_overtime') not in ('full_game_including_overtime','full_game'):
            withheld_contracts.append({'id':definition.get('id'),'reason':'Only full-game outcomes including overtime are modeled; regulation-only, half and quarter settlement rules are unsupported.'})
            continue
        if definition.get('kind')=='player' and definition.get('stat')=='touchdowns' and definition.get('touchdownScope')!='offensive_rushing_receiving_only':
            withheld_contracts.append({'id':definition.get('id'),'reason':'This engine does not attribute player return or defensive touchdowns. Verified offensive rushing/receiving-only settlement scope is required.'})
            continue
        if definition.get('kind')=='player' and (definition.get('playerId') in withheld or definition.get('playerId') not in roster):
            withheld_contracts.append({'id':definition.get('id'),'reason':'Current player availability or roster evidence does not support a forecast.'})
            continue
        try:
            evaluate_contract(definition,[0,0],{})
        except ValueError as error:
            withheld_contracts.append({'id':definition.get('id'),'reason':str(error)})
            continue
        accepted.append(definition)
    definitions = accepted
    if time.monotonic()-started>140 and count>10000:
        raise ResearchUnavailable('Data collection used the available research budget; request the standard 10,000-game mode or retry cached data.')
    selected_outcomes = context.get('selectedOutcomes')
    result = simulate(fit['model'],game['home'],game['away'],count,seed,game['startTime'],definitions or None,scenario,
                      postseason=game['week']>18,parameter_uncertainty={'replicates':10,'gamesPerReplicate':100},representative_games=1,
                      selected_outcomes=selected_outcomes,parameter_player_ids=sorted(pid for pid in roster if pid not in withheld))
    if what_if is not None:
        result['hypothetical'] = {'kind':'availability_what_if','assumptions':dict(what_if),
                                  'currentReportsChanged':False,'calibratedAvailabilityMixture':False,
                                  'message':'A user-requested hypothetical availability cohort, not a statement of current player availability.'}
    hidden = {pid:reason for pid,reason in withheld.items() if pid in result['players']}
    for pid in hidden:
        del result['players'][pid]
    depth, latest_depth = [], {}
    if 'depth' in datasets:
        for row in datasets['depth'].rows():
            if row.get('team') not in teams:
                continue
            try:
                at = utc(row.get('dt'))
            except ValueError:
                continue
            if at>now:
                continue
            team = row['team']
            if team not in latest_depth or at>latest_depth[team]:
                latest_depth[team] = at
                depth = [item for item in depth if item['team']!=team]
            if at==latest_depth[team]:
                depth.append({'playerId':row.get('gsis_id') or None,'player':row.get('player_name'),'team':row.get('team'),'position':row.get('pos_abb'),'rank':_integer(row.get('pos_rank')),'observedAt':row.get('dt')})
    unresolved = [r for r in reports if r['status'] in ('out','questionable','doubtful','injured_reserve')]
    injury_adjusted = bool(scenario) and not any(r['status'] in ('questionable','doubtful') for r in unresolved)
    limitations = list(conversion['limitations'])+[
        'A research baseline, not a validated professional market model. Current-source collection proves present availability, not historical first-publication times.',
        'Player distributions with unresolved injury availability or missing current roster evidence are withheld; the representative game remains a complete shared-play audit trace.',
        'Positive snap participation labels do not establish unrestricted health. Official game-day inactive lists and calibrated questionable-player availability probabilities are not supplied.',
        'Weather and defensive-personnel effects are reported as evidence; unvalidated numerical adjustments are not applied.',
        'Parameter bootstrap uncertainty does not measure roster, structural or all scenario uncertainty.']
    if not injury_adjusted:
        limitations.append('Team probabilities are not fully injury-adjusted: validated availability cohorts are insufficient or incomplete.')
    result['uncertainty']['injuryAdjustment'] = 'evidence_conditioned_single_scenario' if injury_adjusted else 'not_fully_adjusted; see sourced reports and withheld player forecasts'
    result['uncertainty']['weatherAdjustment'] = 'not_applied_without_validated_weather_model'
    result['publicPlayerForecastsWithheld'] = hidden
    result['publicLimitations'] = limitations
    catalog = []
    for pid,player in roster.items():
        actual_names = [player.get('full_name'),player.get('football_name'),player.get('display_name'),
                        ' '.join(str(player.get(key) or '') for key in ('first_name','last_name')).strip()]
        actual_names = list(dict.fromkeys(value.strip() for value in actual_names if isinstance(value,str) and value.strip()))
        catalog.append({'id':pid,'name':player.get('full_name') or names.get(pid) or None,
                        'team':player.get('team'),'position':player.get('position'),
                        'jersey':player.get('jersey_number') or None,'aliases':actual_names,
                        'rosterStatus':player.get('status'),'rosterWeek':_integer(player.get('week')) or None,
                        'source':datasets['rosters'].metadata['url'] if 'rosters' in datasets else None})
    research = {'version':VERSION,'teams':fit['model'].get('teamResearch',{}),'players':usage,'playerNames':names,
                'playerCatalog':sorted(catalog,key=lambda player:(player['team'] or '',player['name'] or '',player['id'])),
                'playerStatistics':player_statistics,'teamStatistics':team_statistics,
                'injuries':reports,'practiceReports':reports,'confirmedInactives':[],
                'injuryCoverage':{'status':'available' if reports else 'not_yet_reported' if 'injuries' in datasets else 'unavailable',
                                  'requestedWeek':game['week'],'latestSourceWeek':max((_integer(r.get('week')) for r in injury_rows if r.get('team') in teams),default=None),
                                  'individualPublicationTimesKnown':False,'gameDayInactivesConfirmed':False},
                'injuryImpact':{'fullyAdjusted':injury_adjusted,'availabilityWeightsCalibrated':False,'scenario':scenario,'scenarioAudit':scenario_audit,'withheldPlayers':hidden},
                'weather':context.get('weather'),'weatherImpact':{'applied':False,'reason':'No independently validated conditional weather model is connected.'},
                'depthCharts':depth,'depthObservedAt':{team:at.isoformat() for team,at in latest_depth.items()},
                'contractPredictionsWithheld':withheld_contracts,
                'snapCounts':{'status':'available' if 'snaps' in datasets else 'unavailable','source':datasets['snaps'].metadata['url'] if 'snaps' in datasets else None},
                'sources':sources,'training':{**fit['summary'],**conversion,'selectedMatchupPlays':len(raw),'evidenceVersion':evidence_version,'rosterWeek':roster_week,'availabilityConflictsExcluded':conflicts},
                'availability':{'collectionVerifiedAt':pbp_source['checkedAt'],'historicalFirstPublicationVerified':False,'currentSourceBeforeKickoff':True},'limitations':limitations}
    if what_if is not None:
        research['whatIf'] = result['hypothetical']
    summary = {'kind':'calculated_research_digest','aiGenerated':False,
               'text':f"{count:,} complete games were simulated from {fit['summary']['plays']:,} verified historical play records. "
                      f"The fitted baseline estimates {game['home']} at {result['homeWinProbability']*100:.1f}% to win. "
                      f"{len(reports)} sourced injury/practice records were checked. "
                      +('A supported inactive-player cohort was applied. ' if injury_adjusted else 'Injury effects are not fully modeled; unsupported player distributions were withheld. ')
                      +'These estimates remain research-only and are not guarantees.',
               'citations':[{'url':s['url'],'checkedAt':s.get('checkedAt'),'sourceUpdatedAt':s.get('sourceUpdatedAt')} for s in sources if s.get('status')=='available']}
    input_version = hashlib.sha256(json.dumps({'evidenceVersion':evidence_version,'scenario':scenario,
        'injuries':[{k:r.get(k) for k in ('playerId','team','status','practiceParticipation','injury','week')} for r in reports],
        'rosters':sorted((pid,r.get('team'),r.get('status')) for pid,r in roster.items()),'contracts':definitions,
        'whatIf':what_if,'selectedOutcomes':selected_outcomes},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'result':result,'research':research,'summary':summary,'inputVersion':input_version,'modelVersion':fit['model']['version'],
            'calculatedAt':stamp(),'asOf':fit['model']['asOf'],'elapsedSeconds':time.monotonic()-started,'source':'automatic_public_nflverse','requiresDatasetUpload':False}
