"""Replay an immutable failed run without fitting to its observed result.

Usage: python scripts/diagnose-football-run.py --archive PATH --output PATH
The archive must contain fitted-input.json and diagnostic-result.json. No final
statistics are read by this program. Its report is separate from the archive.
"""
import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modeling.gafie import simulate_gafie


def diagnose(archive, output):
    original_files = {name: hashlib.sha256((archive/name).read_bytes()).hexdigest()
                      for name in ('fitted-input.json', 'diagnostic-result.json')}
    model = json.loads((archive/'fitted-input.json').read_text())
    original = json.loads((archive/'diagnostic-result.json').read_text())
    start = time.process_time()
    replay = simulate_gafie(model, original['home'], original['away'],
                            original['simulations'], original['seed'],
                            original['eventStart'], len(original.get('representativeGames', [])))
    fields = ['scoreDistributions', 'totalDistribution', 'marginDistribution',
              'players', 'gameEnvironment', 'convergence', 'correlations', 'representativeGames']
    checks = {key: replay[key] == original[key] for key in fields}
    if not all(checks.values()):
        raise AssertionError('Original run did not reproduce: '+str(checks))
    teams = {}
    for team in (original['home'], original['away']):
        rows = [r for r in model['rows'] if r['o'] == team and r['kind'] not in ('extra_point', 'two_point')]
        qbs = Counter(r['qb'] for r in rows if r.get('qb') and r['kind'] == 'pass')
        teams[team] = {'plays':len(rows), 'passAttemptsByHistoricalQB':dict(qbs),
                       'zeroClockFraction':sum(r['elapsed'] == 0 for r in rows)/len(rows),
                       'meanRecordedClockDelta':sum(r['elapsed'] for r in rows)/len(rows),
                       'labeledAvailabilityRows':sum(bool(r.get('availability')) for r in rows)}
    report = {'schemaVersion':1, 'originalFiles':original_files, 'replayedGames':replay['simulations'],
              'replayCPUSeconds':time.process_time()-start, 'exactOutputChecks':checks,
              'trainingCutoff':model['asOf'], 'modelVersion':original['modelVersion'],
              'seed':original['seed'], 'teams':teams, 'defects':[
                  {'code':'historical_personnel_not_current_lineup', 'confirmed':True,
                   'evidence':'The sampler returns historical qb/receiver/runner IDs. No current starter allocation step exists.'},
                  {'code':'unmodeled_confirmed_absence', 'confirmed':True,
                   'evidence':'No availability-labeled training rows; the saved run contains passing attempts for a reported-out quarterback.'},
                  {'code':'tempo_not_validated', 'confirmed':True,
                   'evidence':{'meanSimulatedPlays':replay['gameEnvironment']['plays'], 'clockEvidence':teams}},
                  {'code':'opponent_outcome_backoff', 'confirmed':True,
                   'evidence':'Outcome events back off to same-offense/down pools; play-call coefficients do not independently adjust pass/rush efficiency for an unseen defense.'},
                  {'code':'uncalibrated_full_game_model', 'confirmed':True,
                   'evidence':'Held-out play-choice log loss was tested, but full-game score/player distributions were not approved.'},
                  {'code':'retrospective_source_corrections', 'confirmed':True,
                   'evidence':'Source events precede kickoff, but original publication and correction availability timestamps are not established.'}],
              'historicalForecastAltered':False, 'actualBoxScoreUsedForReplay':False,
              'publishedAsValidatedForecast':False}
    for name, digest in original_files.items():
        assert hashlib.sha256((archive/name).read_bytes()).hexdigest() == digest
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    diagnose(args.archive, args.output)
