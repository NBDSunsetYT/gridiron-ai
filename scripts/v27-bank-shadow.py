"""Use the existing V24 bank on one NEW NBA prospective event, no fitting.

Expected-value heads remain conditional research. Check roster membership and
shared opportunity constraints; do not force the marginals into a joint game.
"""
import sys,json,gzip,hashlib,time,resource
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.completion.bank import HeadBank
from modeling.dynamic_v24.completion.data import packets,enrich_packets,features_only
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.fullgame_v23.modes import Mode,context
from modeling.overnight_v20.state import digest
from modeling.iterative_learning import freeze_json
from modeling.integration_v22.datasets import protected
from modeling.accuracy_v20.quality import aware
from modeling.accuracy_v25.joint_session import bounded_call


def nba_roster_source(editions,team):
    prefix='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/'+team+'/roster?'
    matches=[r['source'] for r in editions if r['source'].startswith(prefix)]
    if len(set(matches))!=1:raise ValueError('Exactly one league-qualified NBA team roster source required')
    return matches[0]


def run():
    out=ROOT/'artifacts/evidence-and-joint-v27';original=json.loads(gzip.decompress((ROOT/'docs/research/V27_PROSPECTIVE_R1.json.gz').read_bytes()));target=next(g for g in original['games'] if g['sport']=='NBA');cutoff=datetime.now(timezone.utc).isoformat()
    if aware(cutoff)>=aware(target['eventAt']):raise ValueError('Actual pregame capture required')
    v26=json.loads(gzip.decompress((ROOT/'docs/research/V26_PROSPECTIVE_R1.json.gz').read_bytes()));banned=protected()|{'nba:espn:'+g['eventId'] for g in v26['games'] if g['sport']=='NBA'};gid='nba:espn:'+target['eventId']
    if gid in banned:raise ValueError('Protected/V26 target excluded')
    history=[g for g in packets('NBA') if g['id'] not in banned and aware(g['at'])<aware(cutoff)];history=enrich_packets(history,'NBA')
    sides={t['side']:t['teamId'] for t in target['teams']};shell={'id':gid,'sport':'NBA','at':target['eventAt'],'season':2027,'home':sides['home'],'away':sides['away'],'teams':{t['teamId']:{'opponent':next(x['teamId'] for x in target['teams'] if x['teamId']!=t['teamId']),'players':{},'totals':{'score':0}} for t in target['teams']}}
    # Current outcome values are absent. The existing feature-only adapter
    # strips the label placeholders before calling any model.
    frames=features_only(records(sorted(history+[shell],key=lambda g:(g['at'],g['id'])),'NBA',{gid}));allowed={'minutes','points','rebounds','assists','fieldGoalAttempts','threePointAttempts','freeThrowAttempts','steals','blocks','turnovers'};frames=[r for r in frames if r['stat'] in allowed and r['player']!='__team__']
    if not frames or any(aware(r['featureLastGame'])>=aware(cutoff) for r in frames):raise ValueError('Only real earlier-history features are eligible')
    bank_path=ROOT/'artifacts/dynamic-v24/completion-final/bank.json';bank=HeadBank(bank_path,ROOT);ctx=context(Mode.CONDITIONAL,'NBA',gid,[{'source':'https://github.com/sportsdataverse/sportsdataverse-data','sourceVersion':digest(history)}])
    bundle=bank.bundle('NBA',frames,cutoff,ctx);current_rosters={};source_refs=[]
    import runpy
    parser=runpy.run_path(str(ROOT/'scripts/v26-forecast.py'))
    for team in target['teams']:
        tid=team['teamId'];url=nba_roster_source(original['sourceEditions'],tid);receipt=json.load(open(out/'source-probes'/(hashlib.sha256(url.encode()).hexdigest()+'.json')))
        body=parser['body'](receipt)
        if str(body['team']['id'])!=tid or body['team']['displayName']!=team['name']:raise ValueError('NBA roster identity/name mismatch')
        current_rosters[tid]=parser['roster_players'](body);source_refs.append(receipt)
    estimates={};withheld=[];checks=[]
    for pid,values in bundle['estimates'].items():
        team=bundle['playerTeams'][pid]
        if pid not in current_rosters.get(team,{}):withheld.append({'playerId':pid,'teamId':team,'reason':'Earlier role is not current verified roster membership; no silent trade/availability inference'});continue
        estimates[pid]={'teamId':team,'name':current_rosters[team][pid]['name'],'expectedValues':values,'availability':'unknown','confirmedStarter':None,'probabilities':None,'predictionIntervals':None}
    for team,roster in current_rosters.items():
        values=[r['expectedValues'] for r in estimates.values() if r['teamId']==team];minutes=sum(v.get('minutes',0) for v in values);fga=sum(v.get('fieldGoalAttempts',0) for v in values);three=sum(v.get('threePointAttempts',0) for v in values)
        checks.append({'teamId':team,'rawMarginalMinutes':minutes,'regulationMinuteBudget':240,'minuteBudgetExact':abs(minutes-240)<1e-6,'fieldGoalAttempts':fga,'threePointAttempts':three,'shotBudgetPossible':three<=fga,'rosterWithoutEarlierHeadCount':len(set(roster)-set(estimates)),'jointIntegrationAllowed':False,'reason':'No complete pregame participation/rotation law or independently validated distribution-compatibility certificate; marginals were not forcibly rescaled'})
    report={'version':'existing-V24-bank-prospective-shadow-27.0','eventId':target['eventId'],'canonicalEventId':gid,'sport':'NBA','eventAt':target['eventAt'],'capturedAt':datetime.now(timezone.utc).isoformat(),'featureAsOf':cutoff,'modelBankSHA256':hashlib.sha256(bank_path.read_bytes()).hexdigest(),'selectedHeads':bundle['manifest']['heads'],'featureSnapshotSHA256':digest(frames),'earlierHistorySHA256':digest(history),'priorHistoryEnd':max(r['featureLastGame'] for r in frames),'rosterSourceEditions':[{'source':r['url'],'sourceVersion':r['sourceVersion'],'capturedAt':r['retrievedAt']} for r in source_refs],'players':estimates,'withheldPlayers':withheld,'jointOpportunityChecks':checks,'modelFits':0,'MonteCarloGames':0,'productionPromotion':False,'strictFullGameQualified':False,'scope':'conditional prospective marginal expected values, NOT validated probabilities or joint forecasts','V26ForecastChanges':False,'V26TargetOutcomesUsed':False}
    revision=sys.argv[sys.argv.index('--revision')+1] if '--revision' in sys.argv else 'R1'
    if revision not in ('R1','R2'):raise ValueError('Explicit immutable bank shadow revision required')
    report['revision']=revision;report['sha256']=digest(report);freeze_json(out/('bank-prospective-'+revision.lower()+'.json'),report);freeze_json(ROOT/'docs/research'/('V27_BANK_SHADOW_'+revision+'.json.gz'),report)
    print(json.dumps({'event':target['eventId'],'heads':len(report['selectedHeads']),'players':len(estimates),'withheldPlayers':len(withheld),'opportunityChecks':checks,'strictFullGameQualified':False}))


if __name__=='__main__':
    start=time.monotonic();cpu=time.process_time()
    with bounded_call(120,180):run()
    print(json.dumps({'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
