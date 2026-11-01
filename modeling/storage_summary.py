"""Bounded, reproducible run metadata. Never retains per-run games or plays."""
from collections import Counter
from functools import lru_cache
import hashlib
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
    names = ['simulator.py', 'cfb_simulator.py', 'fit.py', 'cfb.py', 'storage_summary.py', 'artifact_archive.py', 'public_research.py', 'cfb_public_research.py', 'nflverse_adapter.py']
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
