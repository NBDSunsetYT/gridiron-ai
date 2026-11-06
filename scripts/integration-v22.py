"""Register and run bounded research-only V22 integration and comparisons.

No service calls, production writes, automatic promotion or final-test grading.
Resume: python scripts/integration-v22.py --run integration|components
"""
import sys,json,gzip,pickle,hashlib,random,types
from pathlib import Path
from collections import defaultdict
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pyarrow.parquet as pq
from modeling.integration_v22.io import OUT
from modeling.integration_v22.datasets import all_packets,cfb_packets,protected,examined
from modeling.integration_v22.runtime import job
from modeling.integration_v22.inputs import integrate
from modeling.integration_v22.passing import PassingChain
from modeling.integration_v22.control import replay
from modeling.integration_v22.metrics import paired
from modeling.integration_v22.clock import RuntimeClock
from modeling.integration_v22.gates import audit,REQUIRED
from modeling.overnight_v20.state import read,atomic,digest
from modeling.overnight_v20 import data
from modeling.overnight_v20.cohort import training_rows
from modeling.accuracy_v20.projections import LeagueOpportunityModels
from modeling.accuracy_v20.quality import aware
from modeling.evidence_v21.opportunities import LineupMinutes
from modeling.evidence_v21.rebounds import CourtRebounds
from modeling.evidence_v21.protection import assert_unexposed
from modeling.iterative_learning import freeze_json

def unpack(p):return json.loads(gzip.decompress(p.read_bytes()))
def code():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/integration_v22').glob('*.py'))]}
def register():
    if (OUT/'protocol.json').exists():raise ValueError('V22 protocol exists; never overwrite evaluated selection')
    packets,raw,coverage=all_packets();excluded=examined();selection={}
    for s,windows in {'NFL':[('2023-10-01','2023-11-01'),('2023-11-01','2023-12-01'),('2023-12-01','2024-01-01')],'CFB':[('2025-09-15','2025-10-01'),('2025-10-01','2025-11-01')],'NBA':[('2025-02-01','2025-03-01'),('2025-11-01','2025-12-01'),('2026-01-01','2026-02-01')]}.items():
        selection[s]=[]
        for wi,(start,end) in enumerate(windows):
            candidates=sorted([g for g in packets[s] if start<=g['at'][:10]<end and g['id'] not in excluded],key=lambda g:g['id']);random.Random(22220+wi).shuffle(candidates)
            selection[s].append([{k:g[k] for k in ['id','at','end','season','home','away','sport']}|{'window':wi} for g in sorted(candidates[:20 if s=='NFL' else 30 if s=='CFB' else 24],key=lambda g:g['at'])])
    protocol={'version':22,'selection':selection,'protectedIds':sorted(protected()),'excludedSelectionHash':digest(sorted(excluded)),'seed':22220,'fitting':'At first game minus 6h in each window; preceding completed appearances embargoed 6h; protected games removed before lags and fit','trainingMaxGames':500,'hypotheses':{'NFL':'Re-test unchanged hurdle vs active production history/partial-pooling algorithm replay, not merely rolling5. No historical current-roster qualification claim.','CFB':'Corrected team ATT budget, regularized multinomial QB allocation including unassigned bucket, binomial completion and Ridge YPC vs unchanged repaired-history hurdle.','NBA':'Starter-state minutes and historical on-court rebound exposure vs hurdle; no final starters supplied for forecasts.'},'parameters':'Fixed PassingChain L2=100/C=.05/Ridge100; unchanged V21 minutes/court/hurdle; 2000 paired game-cluster bootstrap draws','untouchedFinalTest':False,'sealedFinalOpened':False,'strictEligibilityRequiredForFullGames':True,'productionPromotionAllowed':False,'newCompleteGamesRequested':10000,'noAutomaticSimulationBypass':True,'numericCode':code(),'sourceVersions':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((OUT/'external').glob('*.parquet'))}}
    atomic(OUT/'protocol.json',protocol);atomic(OUT/'initial-coverage.json',coverage)
    for name in ['integration','components']:atomic(OUT/'specs'/(name+'.json'),{'name':name,'numericCode':protocol['numericCode'],'protocolHash':digest(protocol),'noPromotion':True})
    print(json.dumps({'registeredGames':{s:[len(g) for g in ws] for s,ws in selection.items()},'excludedProtected':len(protected())}),flush=True)

def integration():
    packets,coverage=cfb_packets();clock=pickle.load((ROOT/'artifacts/overnight-v21/clock/censored_drive_em2.pickle').open('rb'));base=unpack(ROOT/'artifacts/overnight-v20/experiments/r1/cohorts/CFB-0/simulation-model.json.gz');cutoff='2025-09-01T00:00:00Z';eligible={g['id'] for g in packets if aware(g['end'])+timedelta(hours=6)<aware(cutoff)};ints=defaultdict(float)
    for year in [2024,2025]:
        for r in pq.read_table(ROOT/f'artifacts/overnight-v21/external/CFB-player_box_{year}.parquet').to_pylist():
            if r['category']=='passing' and 'cfb:espn:'+str(int(r['game_id'])) in eligible:ints['cfb:espn:'+str(int(r['team_id']))]+=float(r['interceptions'])
    m=integrate(base,packets,clock,cutoff,protected(),data.archives('CFB')['rows'],ints);folder=OUT/'integration';folder.mkdir(exist_ok=True);freeze_json(folder/'simulation-model.json.gz',m)
    rt=RuntimeClock(m['censoredClock'],'2025-09-02T00:00:00Z');contexts=0
    for k,prob in clock.pools.items():np.testing.assert_allclose(np.diff(np.r_[0.,rt.cdf(*k)]),prob,atol=1e-14);contexts+=1
    credits=sum(sum(abs(v) for v in c.values()) for gs in m['historicalUnassignedTeamCredits'].values() for c in gs.values());cert={'modelHash':m['sha256'],'scope':'synthetic_mechanics_and_input_bridge_only','checks':{k:k in ['per_team_stat_reconciliation','regulation_clock_conservation','possession_counting'] for k in REQUIRED},'independentGames':[],'fixtureTests':'modeling.test_integration_v22','historicalValidationClaimed':False,'remaining':m['integrationAudit']['unresolved']};cert['sha256']=digest(cert);atomic(folder/'consistency-certificate.json',cert)
    protocol=read(OUT/'protocol.json');g=protocol['selection']['CFB'][0][0];q=audit(m,g|{'cutoff':(aware(g['at'])-timedelta(minutes=30)).isoformat()},{},cert);atomic(folder/'gate-decision.json',q)
    result={'reconciledHistoricalGames':m['integrationAudit']['reconciledGames'],'completionOffsetTeams':len(m['completionOffsets']),'completionOffsetFailures':m['integrationAudit']['completionOffsetFailures'],'unassignedTeamCreditAbsoluteTotal':credits,'anonymousAttemptsAssignedToQB':False,'serializedClockContextChecks':contexts,'timedZeroChargesAllowed':False,'newStrictEligibleFullGames':0,'fullGameGateReleased':False,'withheldReasons':q['reasons'],'modelHash':m['sha256'],'baseTrainingProtectedOverlap':0,'clockTrainingProtectedOverlap':len(set(clock.metadata['trainingGames'])&protected()),'currentGateIsNotAnAccuracyResult':True};atomic(folder/'results.json',result);return result

def augment(rows,packets):
    by={g['id']:g for g in packets}
    for r in rows:
        p=by[r['gameId']]['teams'][r['team']]['players'].get(r['player']);stats=p['stats'] if p else {};r.update(actualAttempts=stats.get('passingAttempts',0),actualCompletions=stats.get('completions',0),actualStarter=p.get('starter') if p else False)
    return rows

def components():
    protocol=read(OUT/'protocol.json');packets,raw,coverage=all_packets();result={'tier':'conditional_corrected_history_component','strictEligibleFullGames':0,'newCompleteGameSimulations':0,'promotions':0,'leagues':{},'moneylineBrier':None,'logLoss':None,'intervalCoverage':None,'probabilityMetricReason':'No joint forecast cleared unchanged input and historical full-game consistency gates; point heads do not fabricate outcome distributions.'};nba_raw=data.archives('NBA');exposures={}
    for p in (ROOT/'artifacts/overnight-v21/court-exposures').glob('*.json.gz'):
        e=unpack(p)
        if e.get('gameId') and e.get('complete'):exposures[e['gameId']]=e
    for sport in ['NFL','CFB','NBA']:
        league=[];results=[];history=defaultdict(list)
        for g in packets[sport]:
            for team in [g['home'],g['away']]:history[team].append(g)
        all_by={g['id']:g for g in packets[sport]}
        for wi,games in enumerate(protocol['selection'][sport]):
            if not games:continue
            folder=OUT/'components'/sport/str(wi);folder.mkdir(parents=True,exist_ok=True);cutoff=(min(aware(g['at']) for g in games)-timedelta(hours=6)).isoformat();path=folder/'forecasts.json.gz'
            if path.exists():snapshot=unpack(path);pred=snapshot['rows']
            else:
                train,ids=training_rows(packets[sport],cutoff);assert_unexposed(ids,protected());stats=['minutes','rebounds'] if sport=='NBA' else ['passingAttempts','passingYards'];train=augment([r for r in train if r['stat'] in stats],packets[sport]);hurdle=LeagueOpportunityModels(sport).fit(train,cutoff);chain=PassingChain().fit(train,cutoff) if sport=='CFB' else None;head=LineupMinutes().fit(train,cutoff) if sport=='NBA' else None;court={};court_failures=[]
                if sport=='NBA':
                    previous=[g for g in nba_raw.values() if g['id'] not in protected() and aware(g['at'])+timedelta(hours=6)<aware(cutoff)]
                    for name,mode in [('identified_court',True),('minutes_proxy',False)]:
                        try:court[name]=CourtRebounds(mode).fit(previous,exposures,cutoff)
                        except ValueError as e:court_failures.append(str(e))
                pred=[];failures=[];budgets=[];control_cache={};control_artifacts={}
                for g in games:
                    if sport=='NFL':
                        week=int(g['id'].split('_')[1]);key=(g['season'],week)
                        if key not in control_cache:control_cache[key],control_artifacts[str(key)]=replay(raw,g['season'],week,(aware(g['at'])-timedelta(minutes=30)).isoformat())
                    for team in [g['home'],g['away']]:
                        frame=[r for r in data.features_for(g,team,history,sport) if r['stat'] in stats];grouped=defaultdict(list)
                        for r in frame:
                            if r['player']!='__team__':grouped[r['stat']].append(r)
                        extra={};factors={}
                        if sport=='CFB':
                            try:extra,details=chain.predict_team(frame);factors=details['factors'];budgets.append({'eventId':g['id'],'team':team,**details})
                            except ValueError as e:failures.append({'eventId':g['id'],'team':team,'reason':str(e),'stage':'opportunity_chain'})
                        if sport=='NBA' and grouped['minutes']:
                            try:
                                mins=head.predict_team(grouped['minutes']);estimated=dict(zip([r['player'] for r in grouped['minutes']],map(float,mins)))
                                for pid,v in estimated.items():extra[(pid,'minutes')]=v
                                own=[];opponent=[]
                                for tid,seq in [(team,own),(g['away'] if team==g['home'] else g['home'],opponent)]:
                                    for prev in [p for p in history[tid] if aware(p['end'])+timedelta(hours=6)<aware(g['at'])][-5:]:
                                        actual=nba_raw[prev['id']];t=actual['teams'][tid];seq.append((t,actual['teams'][str(t['opponent_team_id'])]))
                                for name,m in court.items():
                                    vals,detail=m.predict_team(estimated,own,opponent)
                                    for pid,v in vals.items():extra[(pid,name)]=v
                                budgets.append({'eventId':g['id'],'team':team,'minutes':sum(estimated.values()),'regulationOnly':True})
                            except (ValueError,KeyError) as e:failures.append({'eventId':g['id'],'team':team,'reason':str(e),'stage':'nba_state_or_rebound'})
                        for stat,rs in grouped.items():
                            values=hurdle.predict(stat,rs)
                            for r,v in zip(rs,values):
                                out={k:r[k] for k in ['gameId','at','team','player','stat','role','featureCutoff','highVolume']};out['predictions']={'hurdle':float(v),'rolling5':r['baseline']};out['factors']=factors.get(r['player']) if stat=='passingYards' else None
                                if (r['player'],stat) in extra:out['predictions']['chain' if sport=='CFB' else 'starter_state']=extra[(r['player'],stat)]
                                if sport=='NBA' and stat=='rebounds':
                                    for name in court:
                                        if (r['player'],name) in extra:out['predictions'][name]=extra[(r['player'],name)]
                                if sport=='NFL' and stat=='passingYards' and r['player'] in control_cache[(g['season'],week)]:
                                    control=control_cache[(g['season'],week)][r['player']];out['predictions']['production_source_replay']=control['mean'];out['control']=control
                                if not all(np.isfinite(v) for v in out['predictions'].values()):raise ValueError('Non-finite head prediction')
                                pred.append(out)
                snapshot={'rows':pred,'fitCutoff':cutoff,'trainingIds':sorted(ids),'trainingRows':len(train),'forecastsFrozenBeforeGrading':True,'strictAvailability':'unknown; not healthy by default','failures':failures,'budgets':budgets,'productionControlArtifacts':control_artifacts,'controlScope':'Production source algorithm on prior weekly QB appearances; historical roster and injury qualification unrecovered; no live artifact verification','courtFailures':court_failures,'fullGameSimulations':0};freeze_json(path,snapshot)
                with (folder/'models.pickle').open('xb') as f:pickle.dump({'hurdle':hurdle,'chain':chain,'starter_state':head,'court':court},f)
            # Only now grade the committed-in-time in-memory forecast file.
            grades=[]
            for row in pred:
                g=all_by[row['gameId']];p=g['teams'][row['team']]['players'].get(row['player']);stats=p['stats'] if p else {};y=stats.get(row['stat'],0.);grades.append(row|{'actual':y,'actualAttempts':stats.get('passingAttempts',0),'actualCompletions':stats.get('completions',0),'actualParticipation':p is not None,'actualStarter':p.get('starter') if p else False})
            gp=folder/'grades.json.gz'
            if not gp.exists():freeze_json(gp,grades)
            cats={}
            for stat in sorted({r['stat'] for r in grades}):
                rs=[r for r in grades if r['stat']==stat];cats[stat]={f:paired(rs,f,'hurdle') for f in sorted({f for r in rs for f in r['predictions']}) if f!='hurdle'}
                if sport=='NFL' and stat=='passingYards':cats[stat]['hurdle_vs_production']=paired(rs,'hurdle','production_source_replay');cats[stat]['high_volume_hurdle_vs_production']=paired([r for r in rs if r['highVolume']>=100],'hurdle','production_source_replay')
            r={'window':wi,'selectedGames':len(games),'gradedGames':len({r['gameId'] for r in grades}),'observations':len(grades),'categories':cats,'failures':snapshot['failures'],'trainingRows':snapshot['trainingRows'],'decision':'No promotion; conditional component diagnostics, joint calibration and availability unresolved'};atomic(folder/'results.json',r);results.append(r);league.extend(grades);print(json.dumps({'league':sport,'window':wi,'gradedGames':r['gradedGames'],'rows':len(grades),'stage':'completed'}),flush=True)
        result['leagues'][sport]={'windows':results,'gradedGames':len({r['gameId'] for r in league}),'observations':len(league),'aggregate':{stat:{family:paired([r for r in league if r['stat']==stat],family,'production_source_replay' if sport=='NFL' and stat=='passingYards' and family=='hurdle' else 'hurdle') for family in sorted({f for r in league if r['stat']==stat for f in r['predictions']})} for stat in sorted({r['stat'] for r in league})}}
    atomic(OUT/'components/results.json',result);return {'gradedGames':{s:r['gradedGames'] for s,r in result['leagues'].items()},'strictEligibleGames':0,'newCompleteGameSimulations':0,'promotions':0}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--register',action='store_true');p.add_argument('--run',choices=['integration','components']);a=p.parse_args()
    if a.register:register()
    elif a.run:print(json.dumps(job(a.run,{'integration':integration,'components':components}[a.run],cpu=1200,wall=2400),indent=2))
    else:p.error('--register or --run required')
