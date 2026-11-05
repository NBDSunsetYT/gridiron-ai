"""Controlled NFL/CFB/NBA research queue. Never imported by an app endpoint.
Both football leagues fit concurrently; forecasts execute in league round-robin
order. No retraining on the final test and no automatic production promotion.
"""
import sys,os,json,gzip,time,copy,resource,hashlib,importlib.util,traceback
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18.data import archives,packets
from modeling import football_v15,nba_v15
from modeling.structural_v18 import nba as nba18
from modeling.reconstruction_v19 import football,football_fit,nba,nba_fit
from modeling.reconstruction_v19.evidence import aware
from modeling.reconstruction_v19.runtime import local_only
from modeling.iterative_learning import freeze_json,digest,unrealism_flags
from modeling.reproducibility import derive_draw_order,restore_draw_order
OUT=ROOT/'artifacts/parallel-v19'
spec=importlib.util.spec_from_file_location('v18grader',ROOT/'scripts/backtest-structural-v18.py');grader=importlib.util.module_from_spec(spec);spec.loader.exec_module(grader)
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save_model(m,rows=None):
    p=OUT/'models'/(m['sha256']+'.json.gz');freeze_json(p,m)
    if rows is not None:freeze_json(OUT/'models'/(m['sha256']+'.order.json.gz'),derive_draw_order(m,rows))
    return str(p.relative_to(ROOT))

def fit_football(sport,data,games,cohort):
    cutoff=(aware(min(g['at'] for g in games))-timedelta(hours=6)).isoformat();index=OUT/'fit-index'/(sport+'-'+str(cohort)+'.json')
    if index.exists():
        stored=read(index);models={k:restore_draw_order(read(ROOT/p),read((ROOT/p).with_name(Path(p).name.replace('.json.gz','.order.json.gz')))) for k,p in stored['models'].items()};return models,stored
    eligible={gid for gid,g in data['games'].items() if aware(g['lastObservedAt'])+timedelta(hours=6)<aware(cutoff)};rows=[r for r in data['rows'] if r['game'] in eligible and r['at']<cutoff];started=time.thread_time();base=football_v15.fit_football(rows,sport,cutoff,'parallel-v19-owned-caches');enriched=football_fit.enrich(base,rows);frail=copy.deepcopy(enriched);frail['variant']='team_eb_frailty';frail['sha256']=digest({k:v for k,v in frail.items() if k!='sha256'});models={'frozen_reference':base,'team_eb':enriched,'team_eb_frailty':frail};paths={k:save_model(m,rows) for k,m in models.items()};report={'sport':sport,'cutoff':cutoff,'cohort':cohort,'trainingGames':len(eligible),'trainingRows':len(rows),'cpuThreadSeconds':time.thread_time()-started,'models':paths,'frailtySD':frail['completionFrailtySD']};freeze_json(index,report);return models,report

def fit_basketball(data,games,cohort,minutes):
    cutoff=(aware(min(g['at'] for g in games))-timedelta(hours=6)).isoformat();index=OUT/'fit-index'/('NBA-'+str(cohort)+'.json')
    if index.exists():
        r=read(index);return {k:read(ROOT/p) for k,p in r['models'].items()},r
    started=time.process_time();base=nba_v15.fit_nba(data,cutoff,'parallel-v19-owned-box-and-trip-caches');rotation=nba18.fit_nba(data,cutoff,'parallel-v19-owned-box-and-trip-caches','rotation_bootstrap');recent=nba_fit.enrich(rotation,data,cutoff);models={'frozen_reference':base,'v18_joint_rotation':rotation,'recency_usage_eb':recent};r={'sport':'NBA','cohort':cohort,'cutoff':cutoff,'cpuSeconds':time.process_time()-started,'models':{k:save_model(m) for k,m in models.items()},'usageEvidence':recent['usageEvidence']};freeze_json(index,r);return models,r

def lineup_for(g,contexts,model):
    context=contexts.get(g['sport'],{}).get(g['id']);result={};cutoff=aware(g['at'])-timedelta(hours=1)
    if not context:return result
    for row in context['accepted']:
        if row['kind']!='starting_quarterback' or not row['player_id'] or aware(row['published_at'])>=cutoff:continue
        result[row['team_id']]={'quarterback':row['player_id'],'source':row['source'],'availableAt':row['published_at'],'projectedSourceVerified':True,'confirmedStarter':row['confidence']=='official_confirmed' and row['value'].get('confirmedStarter') is True,'injuriesComplete':False,'inactive':[]}
    return result

def main():
    local_only();protocol=read(OUT/'protocol.json');plan=read(OUT/'compute-plan.json');projection=read(OUT/'projection-results.json');prior_cpu=projection['cpuSeconds'];budget=max(1,int(protocol['maxCpuSeconds']-prior_cpu));resource.setrlimit(resource.RLIMIT_CPU,(budget,budget+2));started=time.monotonic();cpu=time.process_time()
    for item in protocol['sourceFiles']:
        if sha(ROOT/item['path'])!=item['sha256']:raise ValueError('Frozen source changed')
    evidence=read(OUT/'evidence.json.gz');contexts={s:{c['eventId']:c for c in cs} for s,cs in evidence['contexts'].items()};raw={s:archives(s) for s in ['NFL','CFB','NBA']};actual={s:{g['id']:g for g in packets(s)} for s in raw};selected={}
    for s,gs in protocol['selection'].items():selected[s]=sum(([g for g in gs if g['cohort']==c][:plan['fullGameSubsetPerWindow']] for c in range(3)),[])
    minutes={}
    for r in read(OUT/'projections/NBA.json.gz')['rows']:
        if r['stat']=='minutes' and r['player']!='__team__':minutes.setdefault(r['gameId'],{}).setdefault(r['team'],{})[r['player']]=r['predictions']['ridge']
    fit_reports=[];runs=[];failures=[];stop='predeclared_candidates_and_windows_completed';count=0;last_cost={'NFL':12.,'CFB':20.,'NBA':22.}
    variants={'NFL':['frozen_reference','team_eb','team_eb_frailty'],'CFB':['frozen_reference','team_eb','team_eb_frailty'],'NBA':plan['nbaVariants']}
    for cohort in range(3):
        if budget-(time.process_time()-cpu)<220:stop='insufficient_budget_for_next_balanced_cohort';break
        cohort_games={s:[g for g in selected[s] if g['cohort']==cohort] for s in raw};models={}
        # Both football pipelines start before either can finish evaluation.
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs={s:pool.submit(fit_football,s,raw[s],cohort_games[s],cohort) for s in ['NFL','CFB']}
            for s,job in jobs.items():models[s],report=job.result();fit_reports.append(report);print(json.dumps({'stage':'fitted','sport':s,'cohort':cohort,'trainingGames':report['trainingGames'],'cpuSeconds':time.process_time()-cpu}),flush=True)
        models['NBA'],report=fit_basketball(raw['NBA'],cohort_games['NBA'],cohort,minutes);fit_reports.append(report)
        exhausted=False
        for ordinal in range(plan['fullGameSubsetPerWindow']):
          for tier in range(3):
            if budget-(time.process_time()-cpu)<sum(last_cost.values())+20:stop='remaining_budget_below_complete_round_robin_group';exhausted=True;break
            for sport in ['NFL','CFB','NBA']:
                g=cohort_games[sport][ordinal];candidate=variants[sport][tier];base=OUT/'runs'/sport/candidate/g['id'].replace(':','_');fp=base.with_suffix('.forecast.json.gz');ep=base.with_suffix('.evaluation.json.gz');begin=time.process_time()
                try:
                    if fp.exists():archive=read(fp);f=archive['forecast']
                    else:
                        m=copy.deepcopy(models[sport][candidate]);lineups=None
                        if sport=='NBA' and candidate!='frozen_reference':m['projectedMinutes']=minutes[g['id']];m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});save_model(m)
                        if sport!='NBA' and candidate!='frozen_reference':lineups=lineup_for(g,contexts,m)
                        seed=19005+cohort*100+ordinal
                        if sport=='NBA':engine=nba_v15 if candidate=='frozen_reference' else nba18 if candidate=='v18_joint_rotation' else nba;f=engine.simulate_nba(m,g['home'],g['away'],g['at'],10000,seed)
                        else:engine=football_v15 if candidate=='frozen_reference' else football;f=engine.simulate_football(m,g['home'],g['away'],g['at'],10000,seed,lineups=lineups,representative_games=0)
                        flags=unrealism_flags(f)
                        if flags:raise ValueError('Simulation accounting audit: '+str(flags))
                        ctx=contexts.get(sport,{}).get(g['id']);snapshot={'model':m['sha256'],'eventId':g['id'],'sport':sport,'seed':seed,'trials':10000,'lineups':lineups,'evidenceContext':ctx['sha256'] if ctx else None,'informationCutoff':(aware(g['at'])-timedelta(hours=1)).isoformat()};archive={'game':g,'candidate':candidate,'forecast':f,'snapshot':snapshot,'snapshotId':digest(snapshot),'protocolSha256':sha(OUT/'protocol.json'),'codeFrozenBeforeValidation':'See research branch commit before this run','cpuSeconds':time.process_time()-begin,'retrospective':True,'originalPublicationComplete':False,'createdAt':datetime.now(timezone.utc).isoformat(),'dependencies':{k:__import__(k).__version__ for k in ['numpy','scipy','sklearn']}};freeze_json(fp,archive);count+=1
                    e=grader.evaluate(f,actual[sport][g['id']]);e['candidate']=candidate;freeze_json(ep,e);runs.append({'sport':sport,'candidate':candidate,'gameId':g['id'],'cohort':cohort,'forecastPath':str(fp.relative_to(ROOT)),'forecastSha256':sha(fp),'cpuSeconds':archive['cpuSeconds']});last_cost[sport]=max(5.,archive['cpuSeconds']);print(json.dumps({'stage':'complete','sport':sport,'candidate':candidate,'game':g['id'],'cpuSeconds':time.process_time()-cpu}),flush=True)
                except (ValueError,KeyError,AssertionError) as e:failure={'sport':sport,'candidate':candidate,'gameId':g['id'],'error':str(e)};failures.append(failure);freeze_json(OUT/'failures'/(sport+'-'+candidate+'-'+g['id'].replace(':','_')+'.json'),failure);print(json.dumps(failure),flush=True)
            if exhausted:break
          if exhausted:break
        if exhausted:break
        freeze_json(OUT/'progress'/('cohort-'+str(cohort)+'.json'),{'completedRuns':len(runs),'cpuSeconds':time.process_time()-cpu,'failures':failures})
    report={'runs':runs,'newRuns':count,'completeGamesSimulated':count*10000,'fitReports':fit_reports,'failures':failures,'stop':stop,'cpuSeconds':time.process_time()-cpu,'priorProjectionCpuSeconds':prior_cpu,'totalInstrumentedCpuSeconds':prior_cpu+time.process_time()-cpu,'wallSeconds':time.monotonic()-started,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'hostedSimulationRequests':0,'financialDatabaseOperations':0,'promoted':[]};freeze_json(OUT/'run-results.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('runs','fitReports')}),flush=True)
if __name__=='__main__':main()
