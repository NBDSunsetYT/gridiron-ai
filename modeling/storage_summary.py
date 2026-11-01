"""Bounded, reproducible run metadata. Never retains per-run games or plays."""
from collections import Counter
from functools import lru_cache
import hashlib
import base64
import array
import gzip
import io
import importlib.metadata
import json
import math
import platform
import os
from pathlib import Path
import sys


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


@lru_cache(maxsize=1)
def code_environment():
    root = Path(__file__).parent
    names = ['simulator.py', 'cfb_simulator.py', 'fit.py', 'cfb.py', 'storage_summary.py', 'artifact_archive.py', 'public_research.py', 'cfb_public_research.py', 'nflverse_adapter.py', 'prop_research.py', 'game_research.py']
    files = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names if (root/name).is_file()}
    versions = {}
    for name in ['numpy', 'scipy', 'scikit-learn', 'pyarrow', 'fastapi']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {'codeSha256': hashlib.sha256(canonical(files)).hexdigest(), 'files': files,
            'gitCommit': os.environ.get('VERCEL_GIT_COMMIT_SHA') or os.environ.get('RENDER_GIT_COMMIT'), 'python': sys.version, 'platform': platform.platform(), 'dependencies': versions,
            'randomGenerator': 'python.random.Random / MT19937'}


def run_manifest(model, home, away, count, seed, event_start, contracts, scenario,
                 representative_games, parameter_uncertainty, selected_outcomes, sport,
                 postseason=False, parameter_player_ids=None):
    config = {'sport': sport, 'home': home, 'away': away, 'simulations': count, 'seed': seed,
              'eventStart': event_start, 'contracts': contracts or [], 'scenario': scenario,
              'representativeGames': representative_games, 'parameterUncertainty': parameter_uncertainty,
              'selectedOutcomes': selected_outcomes, 'postseason': postseason,
              'injuryAssumptions': {'scenario':scenario,'availabilityProbabilitiesInvented':False},
              'weatherAssumptions': {'fittedAdjustment':False,'reason':'No independently validated conditional weather model is connected.'},
              'parameterPlayerIds': parameter_player_ids}
    artifact_sha = hashlib.sha256(canonical(model)).hexdigest()
    environment = code_environment()
    identity = hashlib.sha256(canonical({'config': config, 'artifact': artifact_sha,
                                         'code': environment['codeSha256'], 'dependencies': environment['dependencies']})).hexdigest()
    return {'schemaVersion': 1, 'replayScope':'Statistical outputs; wall-clock timestamps, elapsed durations and archival receipts are not reproducible.', 'replayKey': identity, 'configuration': config,
            'inputArtifactSha256': artifact_sha, 'inputDataVersion': model.get('sha256'),
            'modelVersion': model.get('version'), 'modelParameters': {'teamMinPlays':model.get('teamMinPlays'),'options':model.get('modelOptions',{}),'shrinkageFit':model.get('shrinkageFit'),'rulesVersion':model.get('rulesVersion')},
            'evidenceCutoff': model.get('asOf'), 'dataSources': model.get('source'),
            'environment': environment, 'storage': {'format': 'aggregate_histograms_v1',
                'allGamesRetained': False, 'allPlaysRetained': False, 'representativeGames': representative_games},
            'exactReplay': {'availableFromThisRecordAlone': False,
                'reason': 'Replay also requires the exact fitted input artifact matching inputArtifactSha256. '
                          'This record does not assert that the artifact has been archived. '
                          'A mutable provider URL or matching version label alone is insufficient. '
                          'Runtime/dependency/architecture changes can prevent bit-for-bit replay.'}}


class CorrelationSummary:
    """Streaming sufficient statistics: memory is independent of game count."""
    def __init__(self, rows):
        pairs = Counter((r.get('qb'), r.get('receiver')) for r in rows if r.get('qb') and r.get('receiver'))
        self.pairs = [pair for pair, _ in sorted(pairs.items(), key=lambda p: (-p[1], p[0]))[:16]]
        self.moments = {pair: [0, 0., 0., 0., 0., 0.] for pair in [('homeScore', 'awayScore'), *self.pairs]}

    def add(self, scores, players):
        for pair, moment in self.moments.items():
            if pair == ('homeScore', 'awayScore'):
                x, y = scores
            else:
                x = players.get(pair[0], {}).get('passingYards', 0)
                y = players.get(pair[1], {}).get('receivingYards', 0)
            moment[0] += 1
            moment[1] += x
            moment[2] += y
            moment[3] += x*x
            moment[4] += y*y
            moment[5] += x*y

    def summary(self):
        output = []
        for pair, (n, sx, sy, sxx, syy, sxy) in self.moments.items():
            vx, vy = n*sxx-sx*sx, n*syy-sy*sy
            correlation = max(-1., min(1., (n*sxy-sx*sy)/math.sqrt(vx*vy))) if vx > 0 and vy > 0 else None
            output.append({'variables': list(pair), 'kind': 'team_scores' if pair == ('homeScore', 'awayScore') else 'quarterback_passing_vs_receiver_receiving_yards',
                           'games': n, 'pearson': correlation,
                           'method': 'Shared simulated plays; streaming cross moments. Zero-opportunity games count as zero.'})
        return output


def compact_parameter_evidence(result):
    """Persist replicate distributions, not ordered generated-game frames.

    Marginal player histograms support exact single-threshold sensitivity only.
    Score-pair histograms retain joint team outcomes. They are never used to
    manufacture cross-player joint probabilities from marginal distributions.
    """
    bootstrap = result.get('uncertainty', {}).get('parameterBootstrap')
    if not isinstance(bootstrap, dict):
        return result
    reps, games = bootstrap.get('replicates'), bootstrap.get('gamesPerReplicate')

    def values(sample, width):
        expected = reps*games*width*4
        if not 10 <= reps <= 40 or not 100 <= games <= 2000 or expected > 8_000_000 or sample.get('uncompressedBytes') != expected:
            raise ValueError('Invalid bounded bootstrap frame')
        compressed = base64.b64decode(sample['dataBase64'], validate=True)
        if len(compressed) != sample.get('compressedBytes') or len(compressed) > 2_000_000:
            raise ValueError('Invalid compressed bootstrap frame')
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(expected+1)
        if len(raw) != expected:
            raise ValueError('Bootstrap frame size mismatch')
        decoded = array.array('i')
        if decoded.itemsize != 4:
            raise ValueError('Unsupported integer representation')
        decoded.frombytes(raw)
        if sys.byteorder != 'little':decoded.byteswap()
        return decoded

    sample = bootstrap.pop('playerSamples', None)
    if sample is not None:
        compact = {'status': 'unavailable', 'reason': sample.get('reason', 'Player parameter evidence could not be compacted.')}
        try:
            if sample.get('status') == 'available':
                players, stats = sample['players'], sample['stats']
                if sample.get('encoding') != 'gzip_base64_int32le_shared_player_stats_v1' or sample.get('valueType') != 'int32le' or sample.get('shape') != [reps,games,len(players),len(stats)] or not players or len(players)>256 or not stats or len(stats)>13:
                    raise ValueError('Unsupported player frame')
                raw = values(sample, len(players)*len(stats))
                histograms = []
                touchdowns = [stats.index(k) for k in ('touchdowns','rushingTouchdowns','receivingTouchdowns')] if all(k in stats for k in ('touchdowns','rushingTouchdowns','receivingTouchdowns')) else None
                for replicate in range(reps):
                    group = []
                    for player in range(len(players)):
                        counters = [Counter() for _ in stats]
                        for game in range(games):
                            offset = ((replicate*games+game)*len(players)+player)*len(stats)
                            row = raw[offset:offset+len(stats)]
                            if touchdowns and row[touchdowns[0]] != row[touchdowns[1]]+row[touchdowns[2]]:
                                raise ValueError('Touchdown conservation failed')
                            for column,value in enumerate(row):counters[column][value] += 1
                        group.append([[[value,count] for value,count in sorted(counter.items())] for counter in counters])
                    histograms.append(group)
                compact = {'status':'available','format':'per_replicate_player_histograms_v1','players':players,'stats':stats,
                           'shape':[reps,len(players),len(stats)],'gamesPerReplicate':games,'histograms':histograms,
                           'touchdownConservationVerified':bool(touchdowns),'jointPlayerSamplesRetained':False,
                           'zeroSemantics':sample.get('zeroSemantics'),
                           'method':'Exact marginal frequencies within each whole-game parameter replicate. Cross-player joint research requires a shared-game target simulation.'}
        except (ValueError,TypeError,KeyError,IndexError,OverflowError,OSError):
            pass
        bootstrap['playerHistograms'] = compact
    sample = bootstrap.pop('gameSamples', None)
    if sample is not None:
        compact = {'status':'unavailable','reason':sample.get('reason','Score parameter evidence could not be compacted.')}
        try:
            if sample.get('status') == 'available':
                if sample.get('encoding') != 'gzip_base64_int32le_shared_game_scores_v1' or sample.get('valueType') != 'int32le' or sample.get('shape') != [reps,games,2] or sample.get('teams') != [result['home'],result['away']]:
                    raise ValueError('Unsupported score frame')
                raw = values(sample,2)
                histograms = []
                for replicate in range(reps):
                    counter = Counter((raw[(replicate*games+game)*2],raw[(replicate*games+game)*2+1]) for game in range(games))
                    histograms.append([[home,away,count] for (home,away),count in sorted(counter.items())])
                compact = {'status':'available','format':'per_replicate_score_pair_histograms_v1','teams':sample['teams'],
                           'shape':[reps,2],'gamesPerReplicate':games,'histograms':histograms,'coverage':sample['coverage'],
                           'method':'Exact joint home/away score frequencies within each original complete-game parameter replicate.'}
        except (ValueError,TypeError,KeyError,IndexError,OverflowError,OSError):
            pass
        bootstrap['gameHistograms'] = compact
    bootstrap['orderedGameFramesRetained'] = False
    return result


def _replicate_header(result, field):
    bootstrap = result.get('uncertainty', {}).get('parameterBootstrap', {})
    evidence = bootstrap.get(field)
    r,g = bootstrap.get('replicates'),bootstrap.get('gamesPerReplicate')
    if not isinstance(evidence,dict) or evidence.get('status')!='available' or isinstance(r,bool) or isinstance(g,bool) or not isinstance(r,int) or not isinstance(g,int) or not 10<=r<=40 or not 100<=g<=2000 or bootstrap.get('completeGames')!=r*g or not isinstance(bootstrap.get('historicalGameBlocks'),int) or bootstrap['historicalGameBlocks']<8 or evidence.get('gamesPerReplicate')!=g:
        raise ValueError('Unreconciled parameter histogram header')
    if not isinstance(evidence.get('histograms'),list) or len(evidence['histograms'])!=r:
        raise ValueError('Missing parameter replicates')
    return evidence,r,g


def player_parameter_histograms(result,player_id,stat):
    evidence,r,g=_replicate_header(result,'playerHistograms')
    players,stats=evidence.get('players'),evidence.get('stats')
    allowed={'passingAttempts','completions','passingYards','passingTouchdowns','interceptions','targets','receptions','receivingYards','receivingTouchdowns','carries','rushingYards','rushingTouchdowns','touchdowns'}
    if evidence.get('format')!='per_replicate_player_histograms_v1' or not isinstance(players,list) or not players or len(players)>256 or any(not isinstance(p,str) or not p or len(p)>120 for p in players) or len(set(players))!=len(players) or not isinstance(stats,list) or not stats or any(s not in allowed for s in stats) or len(set(stats))!=len(stats) or evidence.get('shape')!=[r,len(players),len(stats)] or player_id not in players or stat not in stats:
        raise ValueError('Unsupported player histogram')
    if stat=='touchdowns' and evidence.get('touchdownConservationVerified') is not True:
        raise ValueError('Missing touchdown conservation evidence')
    output=[];p,s=players.index(player_id),stats.index(stat)
    for group in evidence['histograms']:
        if not isinstance(group,list) or len(group)!=len(players) or not isinstance(group[p],list) or len(group[p])!=len(stats):raise ValueError('Invalid player axes')
        rows=group[p][s]
        if not isinstance(rows,list) or not 1<=len(rows)<=g:raise ValueError('Invalid marginal histogram')
        seen=set();total=0
        for row in rows:
            if not isinstance(row,list) or len(row)!=2 or any(isinstance(v,bool) or not isinstance(v,int) for v in row) or abs(row[0])>60000 or row[0]<0 and stat not in {'passingYards','receivingYards','rushingYards'} or row[1]<=0 or row[0] in seen:raise ValueError('Invalid marginal frequency')
            seen.add(row[0]);total+=row[1]
        if total!=g:raise ValueError('Marginal games do not reconcile')
        output.append(rows)
    return output,r,g


def game_parameter_histograms(result):
    evidence,r,g=_replicate_header(result,'gameHistograms')
    if evidence.get('format')!='per_replicate_score_pair_histograms_v1' or evidence.get('shape')!=[r,2] or evidence.get('teams')!=[result['home'],result['away']] or result['home']==result['away'] or evidence.get('coverage')!='full_game_including_overtime':raise ValueError('Unsupported paired score histogram')
    for rows in evidence['histograms']:
        if not isinstance(rows,list) or not 1<=len(rows)<=g:raise ValueError('Invalid paired score histogram')
        seen=set();total=0
        for row in rows:
            if not isinstance(row,list) or len(row)!=3 or any(isinstance(v,bool) or not isinstance(v,int) for v in row) or not 0<=row[0]<=1000 or not 0<=row[1]<=1000 or row[2]<=0 or tuple(row[:2]) in seen:raise ValueError('Invalid paired score frequency')
            seen.add(tuple(row[:2]));total+=row[2]
        if total!=g:raise ValueError('Paired games do not reconcile')
    return evidence['histograms'],r,g
