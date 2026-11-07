"""New immutable NBA research revision; preserve all V26/V27 snapshots.

Refreshes source editions and existing V24 heads, without model fitting or
claiming joint eligibility. Rotation appendix is explicitly conditional.
"""
import sys,json,gzip,runpy,hashlib,time,resource
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.completion.bank import HeadBank
from modeling.dynamic_v24.completion.data import packets,enrich_packets,features_only
from modeling.dynamic_v24.completion.additional_data import recent_nba_packets
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.fullgame_v23.rotation import MinutesPrior,draw_minutes,lineup_tape
from modeling.fullgame_v23.modes import context,Mode
from modeling.integration_v22.datasets import protected
from modeling.accuracy_v20.quality import aware
from modeling.overnight_v20.state import digest
from modeling.iterative_learning import freeze_json
from modeling.accuracy_v25.joint_session import bounded_call
OUT=ROOT/'artifacts/forecast-certification-v28'

def run():
    cpu=time.process_time();start=time.monotonic();source=runpy.run_path(str(ROOT/'scripts/v28-sources.py'));parser=runpy.run_path(str(ROOT/'scripts/v26-forecast.py'));prior_snapshot=json.loads(gzip.decompress((ROOT/'docs/research/V27_PROSPECTIVE_R1.json.gz').read_bytes()));target=next(g for g in prior_snapshot['games'] if g['sport']=='NBA');eid=target['eventId'];gid='nba:espn:'+eid
    if gid in protected():raise ValueError('Protected target excluded')
    b,r=source['fetch']('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+eid)
    if b is None:raise ValueError('Current pregame event unavailable')
    preview=json.loads(b);comp=preview['header']['competitions'][0]
    if str(preview['header']['id'])!=eid or comp['status']['type']['state']!='pre':raise ValueError('No final target inputs permitted')
    receipts=[r];rosters={}
    for t in target['teams']:
        b,rr=source['fetch']('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/'+t['teamId']+'/roster?season=2027')
        if b is None:raise ValueError('Current full team roster unavailable')
        d=json.loads(b)
        if str(d['team']['id'])!=t['teamId'] or d['team']['displayName']!=t['name']:raise ValueError('Exact league/team roster identity mismatch')
        rosters[t['teamId']]=parser['roster_players'](d);receipts.append(rr)
    cutoff=datetime.now(timezone.utc).isoformat()
    if aware(cutoff)>=aware(comp['date']):raise ValueError('Prospective capture must precede tipoff')
    banned=protected()|{gid}
    for name in ('V26_PROSPECTIVE_R1.json.gz','V26_PROSPECTIVE_R2.json.gz'):
        snap=json.loads(gzip.decompress((ROOT/'docs/research'/name).read_bytes()));banned.update('nba:espn:'+g['eventId'] for g in snap['games'] if g['sport']=='NBA')
    old=enrich_packets(packets('NBA'),'NBA');fresh,meta=recent_nba_packets(source_folder=OUT/'fresh-nba',exclude=banned);history=sorted({g['id']:g for g in old+fresh if g['id'] not in banned and aware(g['at'])<aware(cutoff)}.values(),key=lambda g:(g['at'],g['id']))
    sides={t['side']:t['teamId'] for t in target['teams']};shell={'id':gid,'sport':'NBA','at':comp['date'],'season':2027,'home':sides['home'],'away':sides['away'],'teams':{tid:{'opponent':next(x for x in rosters if x!=tid),'players':{},'totals':{'score':0}} for tid in rosters}}
    frames=features_only(records(sorted(history+[shell],key=lambda g:(g['at'],g['id'])),'NBA',{gid}));allowed={'minutes','points','rebounds','assists','fieldGoalAttempts','threePointAttempts','freeThrowAttempts','steals','blocks','turnovers'};frames=[f for f in frames if f['stat'] in allowed and f['player']!='__team__']
    if any(aware(f['featureLastGame'])>=aware(cutoff) for f in frames):raise ValueError('Future history rejected')
    path=ROOT/'artifacts/dynamic-v24/completion-final/bank.json';bank=HeadBank(path,ROOT);ctx=context(Mode.CONDITIONAL,'NBA',gid,[{'source':'https://github.com/sportsdataverse/sportsdataverse-data','sourceVersion':digest(meta)}]);bundle=bank.bundle('NBA',frames,cutoff,ctx);people={};checks=[];prior=MinutesPrior().fit(history,cutoff)
    for pid,values in bundle['estimates'].items():
        tid=bundle['playerTeams'][pid]
        if pid in rosters.get(tid,{}):people[pid]={'teamId':tid,'name':rosters[tid][pid]['name'],'expectedValues':values,'availability':'unknown','probabilities':None}
    rotation=[]
    for tid,roster in rosters.items():
        ps=prior.project({pid:p|{'teamId':tid} for pid,p in roster.items()},history,cutoff);selected=sorted(ps,key=lambda p:ps[p]['mean'],reverse=True)[:15];d=draw_minutes(ps,{}, {p:p in selected for p in ps},n=512,seed=280028,hurdle=True)
        rotation.append({'teamId':tid,'players':{p:{'name':ps[p]['name'],'historyGames':ps[p]['historyGames'],'previousTeams':ps[p]['previousTeams'],'availability':'unknown','conditionalActive':p in selected,'conditionalMean':float(d['draws'][:,i].mean()),'conditionalInterval90':np.quantile(d['draws'][:,i],[.05,.95]).tolist()} for i,p in enumerate(d['players'])},'teamMinuteBudget':240,'allDrawsBudgetExact':bool(np.all(d['draws'].sum(axis=1)==240)),'Rhat':d['maximumRhat'],'samplerConverged':d['samplerConverged'],'scenarioWeights':None,'predictiveEligibility':False,'scope':'Rejected/unproven research rotation component; NOT a validated final-stat forecast'})
        values=[p['expectedValues'] for p in people.values() if p['teamId']==tid];checks.append({'teamId':tid,'rosterPlayers':len(roster),'admittedExistingHeadPlayers':len(values),'playersWithoutHead':len(roster)-len(values),'rawHeadMinuteSum':sum(v.get('minutes',0) for v in values),'rawHeadFGA':sum(v.get('fieldGoalAttempts',0) for v in values),'jointIntegrated':False,'rawHeadsRescaled':False})
    report={'version':'V28-existing-bank-new-season-prospective-1','sport':'NBA','eventId':eid,'eventAt':comp['date'],'featureAsOf':cutoff,'createdAt':datetime.now(timezone.utc).isoformat(),'sourceEditions':[{'source':x['url'],'sourceVersion':x['sourceVersion'],'retrievedAt':x['retrievedAt']} for x in receipts],'dataSources':meta,'historicalInputSHA256':digest(history),'historicalInputIds':[g['id'] for g in history],'priorHistoryEnd':max(g['at'] for g in history),'featureSHA256':digest(frames),'modelBankSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'selectedHeads':bundle['manifest']['heads'],'players':people,'jointOpportunityChecks':checks,'conditionalRotationAppendix':rotation,'strictFullGameQualified':False,'completeGamesSimulated':0,'winProbabilities':None,'spreadProbabilities':None,'totalProbabilities':None,'marketPrices':None,'scope':'Conditional prospective marginal expected-value heads; no validated joint probabilities','blockers':['Complete pregame availability/active list and restrictions unavailable','Joint rotation candidate did not establish independent improvement','Shot/rebound joint compatibility and full distribution calibration not certified'],'V26V27SnapshotsChanged':False,'modelPromotion':False,'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss};report['sha256']=digest(report);freeze_json(OUT/'prospective-nba-r1.json',report);freeze_json(ROOT/'docs/research/V28_NBA_PROSPECTIVE_R1.json.gz',report);print(json.dumps({'eventId':eid,'admittedPlayers':len(people),'checks':checks,'strictFullGameQualified':False,'cpuSeconds':report['cpuSeconds']}))

if __name__=='__main__':
    with bounded_call(120,180):run()
