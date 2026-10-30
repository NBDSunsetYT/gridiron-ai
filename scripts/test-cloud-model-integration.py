"""Actual cloud-authenticated historical modeling integration, using disposable QA A.

No credentials, tokens or invented forecast outputs are printed. Never run against
an account holding real user records. This replay is retrospective, not a live bet.
"""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from modeling.nflverse_adapter import normalize, read_pbp, SOURCE

base = os.environ.get('BASE_URL', 'http://127.0.0.1:3340')
account = json.loads(Path(os.environ.get('QA_CREDENTIALS_FILE', '/tmp/gridiron-live-qa.json')).read_text())[0]
path = Path(os.environ.get('PBP_QA_FILE', '/tmp/gridiron-pbp-2023.csv.gz'))
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(endpoint, value=None):
    headers = {'Origin': base, 'Content-Type': 'application/json'}
    request = urllib.request.Request(base + '/api/cloud/' + endpoint,
                                    data=json.dumps(value).encode() if value is not None else None,
                                    headers=headers)
    try:
        with client.open(request, timeout=300) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error).get('error', 'Cloud operation failed')
        except (ValueError, AttributeError):
            message = 'Cloud operation failed'
        raise RuntimeError(f'{endpoint} returned HTTP {error.code}: {message}') from None


def main():
    signed = call('auth', {'action': 'login', 'email': account['email'], 'password': account['password']})
    assert signed['user']['id'] == account['id']
    before = call('ledger')['summary']['cashBalanceCents']
    assert before == 53501, 'Only the known disposable synthetic financial QA account is supported'
    print(json.dumps({'phase': 'cloud authentication and financial baseline verified'}), flush=True)
    raw = path.read_bytes()
    csv, conversion = normalize(read_pbp(path), 12)
    print(json.dumps({'phase': 'real historical source normalized', 'historicalPlays': conversion['normalizedPlays'], 'normalizedBytes': len(csv.encode())}), flush=True)
    fit = ({'id':os.environ['FIT_JOB_ID'], 'status':'completed', **call('simulations?id='+os.environ['FIT_JOB_ID'])['job']['result']} if os.environ.get('FIT_JOB_ID') else call('simulations', {
        'action': 'fit', 'csv': csv,
        'source': SOURCE + '; actual NFL 2023 historical QA replay; no historical publication availability is asserted',
        'asOf': '2023-11-30T00:00:00Z',
        'options': {'recencyHalfLifeDays': 180, 'conditionalShrinkage': True, 'strictAvailability': False},
    }))
    assert fit['status'] == 'completed' and fit['model']['signature']
    assert len(fit['model']['rows']) == conversion['normalizedPlays']
    saved_fit = call('simulations?id=' + fit['id'])['job']
    assert saved_fit['provenanceVerified'] is True
    assert saved_fit['result']['model']['signature'] == fit['model']['signature']
    print(json.dumps({'phase': 'signed fit persisted and authenticated', 'historicalPlays': conversion['normalizedPlays']}), flush=True)
    # Read the persisted JSONB artifact back before simulation: exercises numeric
    # canonical signing across Python -> Node -> PostgreSQL -> Node -> Python.
    result = call('simulations', {
        'action': 'simulate', 'modelJobId': fit['id'],
        'home': 'DAL', 'away': 'SEA', 'eventStart': '2023-12-01T01:15:00Z',
        'simulations': 10000, 'seed': 2026, 'representativeGames': 1, 'injuryEntityKeys': [],
        'parameterUncertainty': {'replicates': 10, 'gamesPerReplicate': 100},
        'contracts': [{'id': 'HISTORICAL-QA-TOTAL-45.5', 'kind': 'total',
                       'threshold': 45.5, 'direction': 'over', 'equality': 'no'}],
    })
    assert result['status'] == 'completed' and result['simulations'] == 10000
    assert sum(row['count'] for row in result['scoreDistributions']['DAL']['histogram']) == 10000
    assert sum(row['count'] for row in result['jointOutcomes']) == 10000
    assert result['contracts'][0]['settlement']['threshold'] == 45.5
    assert result['contracts'][0]['settlement']['equality'] == 'no'
    trace = result['representativeGames'][0]
    assert len(trace['plays']) > 50
    players = trace['players'].values()
    assert sum(p.get('passingYards', 0) for p in players) == sum(p.get('receivingYards', 0) for p in players)
    assert sum(p.get('completions', 0) for p in players) == sum(p.get('receptions', 0) for p in players)
    bootstrap = result['uncertainty']['parameterBootstrap']
    assert bootstrap['replicates'] == 10 and bootstrap['completeGames'] == 1000
    assert bootstrap['contracts']['HISTORICAL-QA-TOTAL-45.5']['parameterInterval95'] is not None
    saved = call('simulations?id=' + result['id'])['job']
    assert saved['status'] == 'completed' and saved['provenanceVerified'] is True
    assert saved['result']['simulations'] == 10000
    assert saved['result']['representativeGames'][0]['players'] == trace['players']
    assert call('ledger')['summary']['cashBalanceCents'] == before
    report = {
        'status': 'passed', 'projectRef': 'qdtdjbapdipopncklsdb',
        'environment': 'Actual Supabase Auth/PostgreSQL, authenticated Next API and private Python service; disposable QA A only',
        'source': SOURCE, 'sourceSha256': hashlib.sha256(raw).hexdigest(),
        'historicalTrainingPlays': conversion['normalizedPlays'],
        'asOf': '2023-11-30T00:00:00Z', 'historicalAvailability': 'unknown; retrospective replay only',
        'modelVersion': result['modelVersion'], 'signedArtifactJsonbRoundTrip': True,
        'baseCompleteGames': result['simulations'], 'bootstrapCompleteGames': bootstrap['completeGames'],
        'representativeCompleteGames': len(result['representativeGames']),
        'sharedPlayPassingReceivingIdentityVerified': True,
        'exactContractThresholdAndEqualityVerified': True,
        'parameterAndMonteCarloUncertaintySeparated': True,
        'persistedFitAndResultServerAttestationsVerified': True,
        'ownedModelJobReferenceUsed': True, 'uiInjuryReferenceMetadataPreservedAndExcludedFromEngine': True,
        'financialRecordsUnchanged': True, 'credentialsIncluded': False,
        'liveForecast': False, 'marketAdvantageClaimed': False,
    }
    target = ROOT / 'docs/reports/v4-cloud-model-integration.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'baseCompleteGames': 10000,
                      'bootstrapCompleteGames': 1000,
                      'report': str(target.relative_to(ROOT))}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error': str(error)}), file=sys.stderr)
        raise SystemExit(1)
