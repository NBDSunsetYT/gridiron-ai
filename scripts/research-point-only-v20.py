"""Bounded accuracy-first walk-forward benchmark; zero Monte Carlo runs.

Original V19/V20 forecasts remain untouched. Each new cohort freezes all
projection heads and evidence decisions before opening its official grades.
Missing evidence suppresses unconditional forecasts, not honest diagnostic
comparisons. The separate sealed final IDs are never selected for grading.
"""
import sys,os,time,pickle,json,gzip,signal,resource,hashlib,argparse
from pathlib import Path
from collections import defaultdict
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import Campaign,process_identity,read,atomic,digest
from modeling.overnight_v20.sources import protocol
from modeling.overnight_v20.cohort import training_rows,point_fit,point_predict,point_grade,official_box,lineup
from modeling.overnight_v20 import data
from modeling.accuracy_v20.quality import aware
from modeling.accuracy_v20.projections import LeagueOpportunityModels
from modeling.accuracy_v20.benchmarks import OpponentAdjustedRolling
from modeling.accuracy_v20.snapshots import ResearchSnapshots
from modeling.iterative_learning import freeze_json
from modeling.reconstruction_v19.runtime import local_only
local_only();p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');p.add_argument('--register-only',action='store_true');args=p.parse_args();OUT=ROOT/'artifacts/overnight-v20';FOLDER=OUT/'point-only';FOLDER.mkdir(exist_ok=True);start=time.monotonic();before=time.process_time();definition={'id':'accuracy-first-point-suite-20.1','sourceProtocol':digest(protocol()),'qualityPolicySha256':hashlib.sha256((ROOT/'modeling/accuracy_v20/quality.py').read_bytes()).hexdigest(),'families':['rolling5','opponent_adjusted_rolling','ridge','hierarchical','boosted','hybrid','opportunity_hurdle'],'fitMaximumGames':500,'developmentWindows':[0],'validationWindows':[1,2,3],'maximumCpuSeconds':900,'maximumWallSeconds':1800,'reservedFinalOpened':False,'productionWrites':0,'simulations':0,'missingCriticalEvidence':'withhold_unconditional_forecast; conditional research comparisons only','code':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'modeling/opportunity_hurdle_v20.py',*(ROOT/'modeling/accuracy_v20').glob('*.py')]}}
if (FOLDER/'protocol.json').exists() and read(FOLDER/'protocol.json')!=definition:
    original=read(FOLDER/'protocol.json')
    def numeric(v):
        v=dict(v);v['code']={k:h for k,h in v['code'].items() if k.endswith(('/opportunity_hurdle_v20.py','/quality.py','/projections.py','/benchmarks.py'))};return v
    if numeric(original)!=numeric(definition):raise RuntimeError('Numerical method or evidence policy changed. Preserve original experiment and use a new research revision.')
    audit=FOLDER/('non-numerical-compatibility-'+digest(definition)+'.json')
    if not audit.exists():freeze_json(audit,{'original':original,'observed':definition,'numericalInputsUnchanged':True,'noRefittingImplied':True})
    definition=original
if not (FOLDER/'protocol.json').exists():freeze_json(FOLDER/'protocol.json',definition)
if args.register_only:print(json.dumps(definition,indent=2));sys.exit(0)
if (FOLDER/'receipt.json').exists():print(json.dumps(read(FOLDER/'receipt.json'),indent=2));sys.exit(0)
campaign=Campaign(OUT/'runtime');stop=False
def handle(sig,frame):
    global stop
    stop=True
signal.signal(signal.SIGTERM,handle);signal.signal(signal.SIGINT,handle)
with campaign.lease():
    campaign.begin();ok,why=campaign.may_start(900)
    if not ok:campaign.end(why);raise RuntimeError(why)
    resource.setrlimit(resource.RLIMIT_CPU,(int(time.process_time())+900,int(time.process_time())+905));campaign.claim('accuracy-first-point-suite',process_identity(os.getpid()),900,definition);receipt={'status':'interrupted','productionWrites':0,'simulations':0,'reservedFinalOpened':False};cache={};completed=[];pending=[]
    try:
        quality=read(OUT/'accuracy-first/report.json');quality_path=next(p for p in (OUT/'accuracy-first').glob('quality-*.json.gz') if hashlib.sha256(p.read_bytes()).hexdigest()==quality['qualityArtifactSha256']);quality_rows=json.loads(gzip.decompress(quality_path.read_bytes()))['rows'];quality_map={(q['sport'],q['eventId'],q['playerId']):q for q in quality_rows};store=ResearchSnapshots(OUT/'accuracy-first/snapshots.sqlite')
        for cohort in range(4):
            for sport in ['NFL','CFB','NBA']:
                campaign.heartbeat()
                if stop or time.monotonic()-start>1780:break
                games=[g for g in protocol()['selection'][sport] if g['cohort']==cohort];folder=FOLDER/'cohorts'/(sport+'-'+str(cohort));folder.mkdir(parents=True,exist_ok=True)
                if not games:continue
                if (folder/'grades.json.gz').exists():completed.append(folder.name);continue
                if sport not in cache:cache[sport]={'packets':data.packets(sport),'evidence':json.loads(gzip.decompress((OUT/'evidence'/(sport+'-aligned-v3.json.gz')).read_bytes()))}
                packets=cache[sport]['packets'];evidence=cache[sport]['evidence'];cutoff=(min(aware(g['at']) for g in games)-timedelta(hours=6)).isoformat();rows,training_ids=training_rows(packets,cutoff)
                forecast_path=folder/'forecasts.json.gz'
                if forecast_path.exists():forecasts=json.loads(gzip.decompress(forecast_path.read_bytes()))['rows']
                else:
                    original=OUT/'experiments/r1/cohorts'/folder.name/'point-forecasts.json.gz';fitted_path=folder/'models.pickle'
                    if original.exists():base=json.loads(gzip.decompress(original.read_bytes()))['rows'];references={'baseForecast':str(original.relative_to(ROOT)),'sha256':hashlib.sha256(original.read_bytes()).hexdigest()};fits=None
                    else:fits=point_fit(rows);base,_=point_predict(fits,games,packets,evidence);references={'baseForecast':None}
                    heads=LeagueOpportunityModels(sport).fit(rows,cutoff);opps={};grouped=defaultdict(list)
                    for r in rows:
                        if r['player']!='__team__':grouped[r['stat']].append(r)
                    for stat,rs in grouped.items():
                        try:opps[stat]=OpponentAdjustedRolling().fit(rs)
                        except ValueError:pass
                    history=defaultdict(list)
                    for g in packets:
                        for team in [g['home'],g['away']]:history[team].append(g)
                    generated={}
                    for g in games:
                        lf=lineup(g,evidence)
                        for team in [g['home'],g['away']]:
                            by=defaultdict(list)
                            for r in data.features_for(g,team,history,sport):
                                if r['player']!='__team__' and not r['player'].split(':')[-1].startswith('-'):by[r['stat']].append(r)
                            for stat,rs in by.items():
                                models={}
                                if stat in heads.models:models['opportunity_hurdle']=heads.predict(stat,rs)
                                if stat in opps:models['opponent_adjusted_rolling']=opps[stat].predict(rs)
                                for i,r in enumerate(rs):generated[(g['id'],team,r['player'],stat)]={name:0. if r['player'] in lf[team]['inactive'] else float(values[i]) for name,values in models.items()}
                    forecasts=[]
                    for row in base:
                        if row['player']=='__team__':continue
                        q=quality_map[(sport,row['gameId'],row['player'])];forecasts.append({**row,'predictions':{**row['predictions'],**generated.get((row['gameId'],row['team'],row['player'],row['stat']),{})},'researchDecision':q['decision'],'pointInTimeEvidenceScore':q['pointInTimeEvidenceScore'],'missingEvidence':q['missingDomains'],'unconditionalPublicationSuppressed':True})
                    freeze_json(forecast_path,{'sport':sport,'cohort':cohort,'fitCutoff':cutoff,'trainingGameIds':sorted(training_ids),'models':references,'qualityArtifactSha256':quality['qualityArtifactSha256'],'historicalReplay':True,'phase':'development' if cohort==0 else 'validation','frozenBeforeThisCohortGrading':True,'simulations':0,'modelVersion':definition['id'],'runnerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'dependencies':{name:__import__(name).__version__ for name in ['numpy','scipy','sklearn']},'rows':forecasts})
                    with fitted_path.open('xb') as f:pickle.dump({'base':fits,'opportunityEfficiency':heads,'opponentRolling':opps},f)
                for g in games:
                    path=folder/'input-snapshots'/(g['id'].replace(':','_')+'.json');body={'sport':sport,'eventId':g['id'],'eventStart':g['at'],'predictionAsOf':(aware(g['at'])-timedelta(minutes=30)).isoformat(),'modelVersion':definition['id'],'inputHash':hashlib.sha256(forecast_path.read_bytes()).hexdigest(),'phase':'historical_replay','playerIds':sorted({('nba:espn:'+r['player'] if sport=='NBA' else r['player']) for r in forecasts if r['gameId']==g['id']}),'forecastReference':str(forecast_path.relative_to(ROOT)),'selectionDecision':'withhold_unconditional_forecast','simulations':0};freeze_json(path,body);store.freeze(body)
                print(json.dumps({'stage':'forecasts_frozen','sport':sport,'cohort':cohort,'rows':len(forecasts),'cpuSeconds':time.process_time()-before}),flush=True)
                boxes={}
                for g in games:
                    campaign.heartbeat()
                    if stop or time.monotonic()-start>1780:break
                    try:boxes[g['id']]=official_box(g,packets)
                    except Exception as e:pending.append({'sport':sport,'eventId':g['id'],'error':str(e),'stage':'official_outcome_pending'})
                if stop:break
                freeze_json(folder/'grades.json.gz',point_grade(forecasts,boxes,sport));completed.append(folder.name);print(json.dumps({'stage':'graded','sport':sport,'cohort':cohort,'verifiedOutcomes':len(boxes),'cpuSeconds':time.process_time()-before}),flush=True)
            if stop or time.monotonic()-start>1780:break
        store.close();receipt.update(status='interrupted' if stop else 'completed',completedCohorts=completed,pendingOutcomes=pending,cpuSeconds=time.process_time()-before,activeSeconds=time.monotonic()-start,stopReason='user_or_slice_checkpoint' if stop else 'predefined_point_benchmarks_completed_full_game_tuning_still_evidence_gated')
        if not stop:freeze_json(FOLDER/'receipt.json',receipt)
    finally:
        receipt.setdefault('cpuSeconds',time.process_time()-before);campaign.finish('accuracy-first-point-suite',receipt);campaign.end(receipt.get('stopReason','point_benchmark_checkpoint'))
