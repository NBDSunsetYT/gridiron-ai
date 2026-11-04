"""Bounded LOCAL iterative learning. No Vercel/Render compute or database writes.

Prepare freezes chronological samples, candidate definitions, code/data hashes
and stopping rules before evaluating any target. Run resumes immutable artifacts.
Final tests unlock ONCE after validation decisions; they never select a model.
"""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
import argparse
import csv
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import importlib.util
import json
import pickle
from pathlib import Path
import random
import resource
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.audit_storage import snapshot_claim
from modeling.iterative_learning import VERSION,CANDIDATES,THRESHOLDS,digest,freeze_json,evaluate_forecast,summary,paired_gate,stop_reason

OUT=ROOT/'artifacts/learning-v16'
DATA={}
CODE=['modeling/iterative_learning.py','modeling/football_data_v15.py','modeling/football_data_v16.py','modeling/football_v15.py','modeling/football_v16.py','modeling/nba_v15.py','modeling/nba_v16.py','scripts/train-evaluate-engines.py']


def read(path):
    path=Path(path);return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())


def load_data(sport,repaired=True):
    key=(sport,repaired)
    if key in DATA:return DATA[key]
    cache=OUT/'datasets'/(sport+('-repaired' if repaired else '-reference')+'.pickle')
    if cache.exists():data=pickle.load(cache.open('rb')) # owned local cache; no uploaded/untrusted pickle
    elif sport=='NBA':
        from modeling.nba_v15 import load_nba
        data=load_nba('/tmp/gridiron-nba-player_box_2026.parquet','/tmp/gridiron-nba-team_box_2026.parquet','/tmp/gridiron-nba-pbp-2026.parquet')
        cache.parent.mkdir(parents=True,exist_ok=True);pickle.dump(data,cache.open('wb'))
    elif not repaired:
        cache=ROOT/'artifacts/engine-v15'/(sport+'-snap-start-clock-and-personnel-v15.1.cache')
        if not cache.exists():raise ValueError('Run the pinned v15 data audit first; reference dataset missing')
        data=pickle.load(cache.open('rb'))
    else:
        from modeling.football_data_v16 import load_football
        data={'sport':sport,'rows':[],'games':{},'sources':[]}
        for year in (2024,2025):
            source=Path('/tmp/gridiron-'+('cfb-public-pbp-' if sport=='CFB' else 'nfl-pbp-')+str(year)+'.parquet')
            d=load_football(source,sport);data['rows'].extend(d['rows']);data['games'].update(d['games']);data['sources'].append({'year':year,'sha256':d['sourceSha256'],'rejections':d['rejected']})
        cache.parent.mkdir(parents=True,exist_ok=True);pickle.dump(data,cache.open('wb'))
    DATA[key]=data;return data


def prepare(args):
    if (OUT/'protocol.json').exists():raise ValueError('Protocol already frozen. Resume it; never reselect a test after observing results.')
    OUT.mkdir(parents=True,exist_ok=True)
    previous=read(ROOT/'docs/reports/v15-validation.json');quarantine={r['gameId'] for r in previous['inventory'] if r['phase']=='test'}
    quarantine.update(['cfb:espn:401858509','cfb:espn:401756926','2025_07_LA_JAX','2025_13_KC_DAL'])
    windows={'NFL':[('2025-09-01','2025-09-15'),('2025-10-01','2025-10-15'),('2025-11-01','2025-11-15')],
             'CFB':[('2025-09-01','2025-09-15'),('2025-10-01','2025-10-15'),('2025-11-01','2025-11-15')],
             'NBA':[('2026-01-01','2026-01-15'),('2026-02-01','2026-02-15'),('2026-03-01','2026-03-15')]}
    final={'NFL':('2026-01-01','2026-02-10',16),'CFB':('2026-01-01','2026-02-10',8),'NBA':('2026-04-01','2026-05-01',16)}
    selection=[];coverage=[];rng=random.Random(args.seed)
    for sport in ('NFL','CFB','NBA'):
        d=load_data(sport);games=list(d.values()) if sport=='NBA' else list(d['games'].values())
        for i,(start,end,count) in enumerate([(*w,args.cohort_size) for w in windows[sport]]+[final[sport]]):
            phase='test' if i==3 else 'validation';candidates=[]
            for g in sorted(games,key=lambda g:g['id']):
                at=g['at'] if sport=='NBA' else g['firstObservedAt']
                if not start<=at[:10]<end or g['id'] in quarantine:continue
                if sport=='NBA':
                    if len(g['teams'])!=2 or any(not 1<=int(t)<=30 for t in g['teams']):continue
                    home=next((t for t,v in g['teams'].items() if v['team_home_away']=='home'),None);away=next((t for t in g['teams'] if t!=home),None)
                    if not home or not away:continue
                    history=[p for p in games if p['at']<start]
                    if any(sum(t in p['teams'] for p in history)<10 for t in (home,away)):continue
                else:
                    if g['plays']<50:continue
                    home,away=g['home'],g['away'];history=[p for p in games if p['lastObservedAt']<start]
                    if any(sum(t in (p['home'],p['away']) for p in history)<3 for t in (home,away)):continue
                candidates.append({'id':g['id'],'sport':sport,'home':home,'away':away,'at':at,'phase':phase,'cohort':str(i),
                                   'cutoff':start+'T00:00:00+00:00','season':g['season']})
            rng.shuffle(candidates);selection.extend(candidates[:count]);coverage.append({'sport':sport,'phase':phase,'cohort':str(i),'start':start,'end':end,'requested':count,'eligible':len(candidates),'selected':min(count,len(candidates))})
    files=[]
    for name in ['gridiron-nfl-pbp-2024.parquet','gridiron-nfl-pbp-2025.parquet','gridiron-cfb-public-pbp-2024.parquet','gridiron-cfb-public-pbp-2025.parquet','gridiron-nba-player_box_2026.parquet','gridiron-nba-team_box_2026.parquet','gridiron-nba-pbp-2026.parquet']:
        p=Path('/tmp')/name;files.append({'name':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    protocol={'version':VERSION,'createdAt':datetime.now(timezone.utc).isoformat(),'seed':args.seed,'simulations':10000,'batchSize':2000,'workers':2,
              'limits':{'cpuSeconds':args.cpu_budget,'wallSeconds':args.wall_budget,'patience':3,'maxIterations':3},
              'candidates':CANDIDATES,'thresholds':THRESHOLDS,'selection':selection,'coverage':coverage,'quarantinedExposedFinalIds':sorted(quarantine),
              'code':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in CODE},'sources':files,
              'dependencies':{n:__import__(n).__version__ for n in ('numpy','scipy','sklearn','pyarrow')},
              'python':sys.version,'promotionScope':'research_only','productionChampion':None,'strictPregameQualifiedGames':0,
              'availabilityLimitations':'Events precede cutoff, but original publication/correction, lineup, injury and weather archives are incomplete. No verified historical market lines available.'}
    protocol['sha256']=digest(protocol);freeze_json(OUT/'protocol.json',protocol)
    print(json.dumps({'status':'protocol_frozen','selection':len(selection),'coverage':coverage,'limits':protocol['limits']}),flush=True)


def budget(delta=0):
    """One durable budget across local workers and restarts. No paid resources."""
    path=OUT/'budget.json';lock=OUT/'budget.lock'
    with lock.open('a+b') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        state=read(path) if path.exists() else {'cpuSeconds':0,'startedAt':time.time()}
        state['cpuSeconds']+=delta;temporary=path.with_suffix('.partial');temporary.write_text(json.dumps(state));os.replace(temporary,path)
        return state


def allowed(protocol):
    state=budget();return state['cpuSeconds']<protocol['limits']['cpuSeconds'] and time.time()-state['startedAt']<protocol['limits']['wallSeconds']


def model_for(sport,candidate,cutoff,protocol):
    key=digest([sport,candidate,cutoff,protocol['sha256']]);path=OUT/'models'/(key+'.json.gz')
    if path.exists():return read(path)
    d=load_data(sport,candidate['id']!='reference-v15');source=digest(protocol['sources'])
    if sport=='NBA':
        if candidate['id']=='reference-v15':from modeling.nba_v15 import fit_nba
        else:from modeling.nba_v16 import fit_nba
        m=fit_nba(d,cutoff,source,**({} if candidate['id']=='reference-v15' else {'config':candidate['nba']}))
    else:
        from modeling.football_data_v15 import training_before
        if candidate['id']=='reference-v15':from modeling.football_v15 import fit_football
        else:from modeling.football_v16 import fit_football
        rows=training_before(d,cutoff);rows=[r for r in rows if r['at'][:4]>=str(int(cutoff[:4])-1)]
        m=fit_football(rows,sport,cutoff,source,**({} if candidate['id']=='reference-v15' else {'config':candidate['football']}))
    freeze_json(path,m);return m


def actual_and_baseline(game):
    sport=game['sport'];data=load_data(sport);cutoff=game['cutoff'];home,away=game['home'],game['away']
    if sport!='NBA':
        spec=importlib.util.spec_from_file_location('v15_historical_retrieval',ROOT/'scripts/backtest-engine-v15.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.OUT=OUT;module.dataset=lambda sport:load_data(sport)
        scores,players,source=module.final_stats({**game,'fitCutoff':cutoff,'firstObservedAt':game['at']})
        # Positions are evaluation labels only. Never feed a target box score
        # or its participation/position back into forecast preparation.
        if sport=='NFL':
            path=OUT/'actuals'/('nfl-'+str(game['season'])+'.csv.gz')
            with gzip.open(path,'rt') as handle:
                for row in csv.DictReader(handle):
                    if row.get('game_id')==game['id'] and row.get('player_id') in players:players[row['player_id']]['position']=row.get('position') or 'unknown'
        else:
            raw=read(OUT/'actuals'/(game['id'].replace(':','_')+'.json'))
            for team in raw.get('boxscore',{}).get('players',[]):
                for group in team.get('statistics',[]):
                    for row in group.get('athletes',[]):
                        athlete=row.get('athlete',{});pid='cfb:espn:'+str(athlete.get('id'))
                        if pid in players:players[pid]['position']=athlete.get('position',{}).get('abbreviation','unknown')
        base=module.baseline(data,{**game,'fitCutoff':cutoff});base={'scores':{home:base['home'],away:base['away']},'players':base['players']}
        return scores,players,source,base
    g=data[game['id'].split(':')[-1]];folder=OUT/'actuals';folder.mkdir(exist_ok=True);path=folder/(game['id'].replace(':','_')+'.json')
    if path.exists():header=read(path)
    else:
        with urllib.request.urlopen('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+game['id'].split(':')[-1],timeout=25) as response:header=json.load(response)['header']
        freeze_json(path,header)
    comp=header['competitions'][0]
    if str(header['id'])!=game['id'].split(':')[-1] or not comp['status']['type']['completed']:raise ValueError('NBA final identity/status not verified')
    scores={str(t['team']['id']):int(t['score']) for t in comp['competitors']}
    if set(scores)!={home,away} or any(scores[t]!=g['teams'][t]['team_score'] for t in scores):raise ValueError('NBA final source mismatch')
    if 'nba-position-evaluation-only' not in DATA:
        import pyarrow.parquet as pq
        DATA['nba-position-evaluation-only']={str(p['athlete_id']):p['athlete_position_abbreviation'] for p in pq.read_table('/tmp/gridiron-nba-player_box_2026.parquet',columns=['athlete_id','athlete_position_abbreviation']).to_pylist()}
    players={};mapped={'points':'points','assists':'assists','three_point_field_goals_made':'threePointersMade','steals':'steals','blocks':'blocks','turnovers':'turnovers'}
    for p in g['players']:
        if not p.get('minutes'):continue
        ss={v:float(p[k]) for k,v in mapped.items()};ss['rebounds']=float(p['offensive_rebounds']+p['defensive_rebounds'])
        for stat,parts in [('pointsReboundsAssists',['points','rebounds','assists']),('pointsRebounds',['points','rebounds']),('pointsAssists',['points','assists']),('reboundsAssists',['rebounds','assists'])]:ss[stat]=sum(ss[k] for k in parts)
        ss['doubleDouble']=int(sum(ss[k]>=10 for k in ['points','rebounds','assists','steals','blocks'])>=2);ss['tripleDouble']=int(sum(ss[k]>=10 for k in ['points','rebounds','assists','steals','blocks'])>=3)
        players['nba:espn:'+str(p['athlete_id'])]={'team':str(p['team_id']),'stats':ss,'position':DATA['nba-position-evaluation-only'].get(str(p['athlete_id'])) or 'unknown'}
    base={'scores':{},'players':{}}
    for team in (home,away):
        prior=sorted((p for p in data.values() if team in p['teams'] and p['at']<cutoff),key=lambda p:p['at'])[-10:]
        base['scores'][team]=sum(p['teams'][team]['team_score'] for p in prior)/len(prior)
    return scores,players,'ESPN final status/scores and sportsdataverse NBA box scores',base


def run_group(job):
    sport,candidate,selection,protocol=job;start=time.process_time();last=start;results=[];model=None
    for game in selection:
        folder=OUT/'runs'/candidate['id']/sport;folder.mkdir(parents=True,exist_ok=True);stem=folder/game['id'].replace(':','_');path=stem.with_suffix('.forecast.json.gz');evalpath=stem.with_suffix('.evaluation.json.gz')
        if evalpath.exists():results.append(read(evalpath));continue
        if not allowed(protocol):break
        with snapshot_claim(path) as acquired:
            if not acquired:continue
            try:
                if model is None:model=model_for(sport,candidate,game['cutoff'],protocol)
                if path.exists():archive=read(path);forecast=archive['forecast']
                else:
                    if sport=='NBA':
                        if candidate['id']=='reference-v15':from modeling.nba_v15 import simulate_nba as simulate
                        else:from modeling.nba_v16 import simulate_nba as simulate
                    else:
                        if candidate['id']=='reference-v15':from modeling.football_v15 import simulate_football as simulate
                        else:from modeling.football_v16 import simulate_football as simulate
                    if sport!='NBA' and game['id'] in model['trainingGameIds']:raise ValueError('Target game leaked into training')
                    forecast=simulate(model,game['home'],game['away'],game['at'],10000,protocol['seed'],batch_size=2000,**({} if sport=='NBA' else {'representative_games':0}))
                    archive={'protocol':protocol['sha256'],'candidate':candidate,'game':game,'inputVersion':model['sha256'],'forecast':forecast,
                             'mode':'retrospective','publicationVerified':False,'dependencies':protocol['dependencies']}
                    freeze_json(path,archive) # Must finish before fetching/reading target actuals.
                scores,players,source,base=actual_and_baseline(game)
                result=evaluate_forecast(forecast,scores,players,game,base)|{'candidateId':candidate['id'],'source':source,'status':'evaluated',
                        'inputVersion':model['sha256'],'forecastSha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'simulations':forecast['simulations'],'modelVersion':forecast['modelVersion']}
                freeze_json(evalpath,result);results.append(result)
                print(json.dumps({'sport':sport,'candidate':candidate['id'],'phase':game['phase'],'game':game['id'],'status':'evaluated'}),flush=True)
            except Exception as error:
                errorpath=stem.with_suffix('.failure.json')
                if not errorpath.exists():freeze_json(errorpath,{'game':game,'error':str(error),'candidate':candidate['id']})
                print(json.dumps({'sport':sport,'candidate':candidate['id'],'game':game['id'],'status':'failed','error':str(error)}),flush=True)
            current=time.process_time();budget(current-last);last=current
    if time.process_time()>last:budget(time.process_time()-last)
    return {'sport':sport,'candidate':candidate['id'],'completed':len(results),'cpuSeconds':time.process_time()-start,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def rows(candidate,sport,phase):
    return [r for p in (OUT/'runs'/candidate/sport).glob('*.evaluation.json.gz') if (r:=read(p))['phase']==phase]


def execute(candidate,phase,protocol,sports):
    groups=defaultdict(list)
    for game in protocol['selection']:
        if game['phase']==phase and game['sport'] in sports:groups[(game['sport'],game['cutoff'])].append(game)
    with ProcessPoolExecutor(max_workers=2) as pool:
        for result in pool.map(run_group,[(s,candidate,gs,protocol) for (s,_),gs in groups.items()]):print(json.dumps(result),flush=True)


def run():
    protocol=read(OUT/'protocol.json')
    for file,sha in protocol['code'].items():
        if hashlib.sha256((ROOT/file).read_bytes()).hexdigest()!=sha:raise ValueError('Code changed after protocol freeze: '+file+'. Start a NEW versioned experiment; never silently change this one.')
    with snapshot_claim(OUT/'orchestrator') as acquired:
        if not acquired:raise ValueError('Another local orchestrator is already running')
        budget();reference=CANDIDATES[0];execute(reference,'validation',protocol,['NFL','CFB','NBA'])
        active=['NFL','CFB','NBA'];selected={s:reference['id'] for s in active};nonimproving={s:0 for s in active};iterations=[];stops={}
        for i,candidate in enumerate(CANDIDATES[1:],1):
            if not active:break
            execute(candidate,'validation',protocol,active)
            for sport in active[:]:
                old=rows(selected[sport],sport,'validation');new=rows(candidate['id'],sport,'validation');gate=paired_gate(old,new)
                record={'iteration':i,'sport':sport,'challenger':candidate['id'],'incumbent':selected[sport],'gate':gate,
                        'incumbentMetrics':summary(old),'challengerMetrics':summary(new)}
                freeze_json(OUT/'decisions'/(sport+'-'+str(i)+'.json'),record);iterations.append(record)
                if gate['passed']:selected[sport]=candidate['id'];nonimproving[sport]=0
                else:nonimproving[sport]+=1
                state=budget();reason=stop_reason(i,nonimproving[sport],state['cpuSeconds'],time.time()-state['startedAt'],protocol['limits'])
                if reason:stops[sport]=reason;active.remove(sport)
        # The final period is consulted only after ALL selection decisions are frozen.
        # Also lock one explicitly unpromoted diagnostic finalist when the
        # conservative gate rejects every challenger. Its later test result
        # may report weaknesses, but cannot change selection or promotion.
        finalists={}
        for sport in selected:
            eligible=[c['id'] for c in CANDIDATES if len(rows(c['id'],sport,'validation'))==24]
            finalists[sport]=min(eligible,key=lambda c:summary(rows(c,sport,'validation'))['scoreCRPS']) if eligible else reference['id']
        lock={'protocol':protocol['sha256'],'selected':selected,'diagnosticFinalists':finalists,'stops':stops,'finalTestMayNotSelectModels':True}
        freeze_json(OUT/'final-selection-lock.json',lock)
        for candidate in CANDIDATES:
            sports=[s for s in selected if candidate['id'] in (reference['id'],selected[s],finalists[s])]
            if sports and allowed(protocol):execute(candidate,'test',protocol,sports)
        allrows=[read(p) for p in (OUT/'runs').glob('*/*/*.evaluation.json.gz')];state=budget()
        report={'version':VERSION,'protocolSha256':protocol['sha256'],'generatedAt':datetime.now(timezone.utc).isoformat(),
                'uniqueGames':len({r['gameId'] for r in allrows}),'forecastVersions':len(allrows),'completeSimulatedGames':sum(r['simulations'] for r in allrows),
                'budget':state|{'wallSeconds':time.time()-state['startedAt'],'limits':protocol['limits']},'stoppingConditions':stops,
                'iterations':iterations,'researchSelectedModels':selected,'diagnosticFinalists':finalists,'productionChampion':None,'productionPromotions':0,
                'finalTest':{s:{c:summary(rows(c,s,'test')) for c in sorted(set([reference['id'],selected[s],finalists[s]]))} for s in selected},
                'finalFailures':[read(p) for p in (OUT/'runs').glob('*/*/*.failure.json')],
                'finalTestComplete':all(len(rows(c,s,'test'))==sum(g['sport']==s and g['phase']=='test' for g in protocol['selection']) for s in selected for c in set([reference['id'],selected[s],finalists[s]])),
                'strictPregameQualifiedGames':0,'limitations':[protocol['availabilityLimitations'],
                    'Past exposed v15 final tests are quarantined; these final periods are new. Final test results never train or select a candidate.',
                    'Position labels absent in these source schemas remain unknown; no guessed positional accuracy.',
                    'Research CDF grids and correlated-event diagnostics are not actual historical sportsbook lines or event contracts.',
                    'No raw simulation probability is labeled calibrated. Production remains on existing models.',
                    'Sparse cohorts and incomplete availability archives may preclude statistical promotion even after mechanical repairs.'],
                'coverage':protocol['coverage']}
        freeze_json(OUT/'completed-report.json',report)
        dest=ROOT/'docs/reports/v16-iterative-learning.json';dest.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'status':'stopped','uniqueGames':report['uniqueGames'],'forecasts':len(allrows),'cpuSeconds':state['cpuSeconds'],'stops':stops}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--run',action='store_true');p.add_argument('--cohort-size',type=int,default=8);p.add_argument('--seed',type=int,default=16001);p.add_argument('--cpu-budget',type=float,default=7200);p.add_argument('--wall-budget',type=float,default=7200);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.output:OUT=a.output.resolve()
    if a.prepare:
        if a.cohort_size<8 or a.cpu_budget<60 or a.wall_budget<60:p.error('At least eight games/cohort and sixty seconds required')
        prepare(a)
    elif a.run:run()
    else:p.error('Choose --prepare or --run')
