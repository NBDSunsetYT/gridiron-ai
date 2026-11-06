"""Registered ABC next-event experiments; no pregame qualification bypass."""
import sys,json,gzip,hashlib,pickle,gc
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pyarrow.parquet as pq
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.sequence import football_game,nba_game,NFL_COLUMNS,CFB_COLUMNS,NBA_COLUMNS
from modeling.dynamic_v24.event_models import EventModel,EmpiricalReference,V23PlayReference,categorical_metrics,paired_losses,VARIANTS
from modeling.dynamic_v24.stat_data import excluded_validation
from modeling.integration_v22.datasets import protected
from modeling.overnight_v20.data import archives
from modeling.overnight_v20.state import atomic,read,digest
from modeling.iterative_learning import freeze_json
WINDOWS={'NFL':[('2023-10-01','2023-12-01'),('2024-09-15','2024-11-01')],'CFB':[('2024-10-01','2024-12-01'),('2025-09-15','2025-11-01')],'NBA':[('2025-01-01','2025-03-01'),('2025-11-01','2026-02-01')]}
def sources(sport):
    return [OUT/f'external/NFL-pbp-{y}.parquet' for y in (2022,2023)]+[Path('/tmp/gridiron-nfl-pbp-2024.parquet')] if sport=='NFL' else [Path(f'/tmp/gridiron-cfb-public-pbp-{y}.parquet') for y in (2024,2025)] if sport=='CFB' else [Path(f'/tmp/gridiron-nba-pbp-{y}.parquet') for y in (2025,2026)]
def index(sport):
    result={};key='game_date' if sport=='NFL' else 'wallclock' if sport=='CFB' else 'game_date_time'
    for p in sources(sport):
        if not p.exists():continue
        rows=pq.read_table(p,columns=['game_id',key]).to_pylist()
        for r in rows:
            v=r[key]
            if v is None:continue
            at=v.isoformat() if hasattr(v,'isoformat') else str(v);gid=str(r['game_id']) if sport=='NFL' else ('cfb:espn:' if sport=='CFB' else 'nba:espn:')+str(int(r['game_id']))
            if gid not in result or at<result[gid]['at']:result[gid]={'id':gid,'at':at,'path':str(p)}
    return result
def register():
    excluded=excluded_validation();banned=protected();rng=np.random.default_rng(24024);selection={};versions={}
    for s,windows in WINDOWS.items():
        ix=index(s);selection[s]=[]
        for start,end in windows:
            eligible=[g for g in ix.values() if start<=g['at']<end and g['id'] not in excluded];rng.shuffle(eligible);val=sorted(eligible[:40],key=lambda g:(g['at'],g['id']));prior=[g for g in ix.values() if g['at']<start and g['id'] not in banned];prior=sorted(prior,key=lambda g:(g['at'],g['id']))[-180:];selection[s].append({'start':start,'end':end,'train':prior,'validation':val,'eligible':len(eligible)})
        for p in sources(s):
            if p.exists():versions[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    files=[Path(__file__),ROOT/'modeling/dynamic_v24/sequence.py',ROOT/'modeling/dynamic_v24/event_models.py',ROOT/'modeling/dynamic_v24/state.py'];freeze_json(OUT/'specs/sequential-r4.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'sourceHashes':versions,'inputHashes':versions,'selection':selection,'variants':VARIANTS,'seed':24024,'primaryTasks':6,'familywiseAlpha':.05/6,'variantsA':'Exact V23 prior-only play pool for football action; empirical prior-only reference for drive/shot tasks where V23 has no next-event API','notFullGamePredictiveValidation':True,'noFinalBoxesUsedForRates':True,'NBAConditioning':'Observed starting-five identity and release shooter/location; later unknown lineups not backfilled from future events','maximumTrainingEventsPerTask':30000});print({s:[len(w['validation']) for w in ws] for s,ws in selection.items()})
def load_games(sport,games):
    byfile=defaultdict(list);group=defaultdict(list);columns={'NFL':NFL_COLUMNS,'CFB':CFB_COLUMNS,'NBA':NBA_COLUMNS}[sport]
    for g in games:byfile[g['path']].append(g['id'])
    for path,ids in byfile.items():
        selected=ids if sport=='NFL' else [int(i.split(':')[-1]) for i in ids];available=pq.ParquetFile(path).schema.names;raw=pq.read_table(path,columns=[c for c in columns if c in available],filters=[('game_id','in',selected)]).to_pylist()
        for r in raw:
            gid=str(r['game_id']) if sport=='NFL' else ('cfb:espn:' if sport=='CFB' else 'nba:espn:')+str(int(r['game_id']));group[gid].append(r)
    result={};nba={g['id']:g for g in archives('NBA').values()} if sport=='NBA' else None
    for g in games:
        if not group[g['id']]:continue
        if sport=='NBA' and g['id'] not in nba:continue
        result[g['id']]=nba_game(group[g['id']],nba[g['id']]) if sport=='NBA' else football_game(group[g['id']],sport)
    return result
def run():
    spec=read(OUT/'specs/sequential-r4.json');summary={};banned=protected();excluded=excluded_validation()
    for sport,windows in spec['selection'].items():
        league=[]
        for wi,w in enumerate(windows):
            folder=OUT/'sequential'/sport/(str(wi)+'-converged-r4');path=folder/'results.json'
            if path.exists():league.append(read(path));continue
            assert not {g['id'] for g in w['validation']}&excluded;assert not {g['id'] for g in w['train']}&banned
            train_games=load_games(sport,w['train']);val_games=load_games(sport,w['validation']);report={'trainingGames':len(train_games),'validationGames':len(val_games),'tier':'conditional_next_event','sourceErrors':dict(sum((Counter(g['errors']) for g in val_games.values()),Counter())),'tasks':{}}
            for task in (('actions','shots') if sport=='NBA' else ('actions','drives')):
                train=[r for g in train_games.values() for r in g.get(task,[])];val=[r for g in val_games.values() for r in g.get(task,[])]
                if len(train)>30000:
                    rng=np.random.default_rng(24024);train=[train[i] for i in sorted(rng.choice(len(train),30000,replace=False))]
                if len(train)<200 or len(val)<30:report['tasks'][task]={'status':'insufficient_events'};continue
                reference=V23PlayReference() if sport!='NBA' and task=='actions' else EmpiricalReference();reference.fit(train);frozen=[]
                # A source-support failure is a common-row exclusion, not a
                # convenient failure charged only to the baseline.
                supported=[];ref_probs=[];excluded_rows=0
                for r in val:
                    try:p=reference.predict([r])[0]
                    except ValueError:excluded_rows+=1;continue
                    if r['y'] not in reference.classes:excluded_rows+=1;continue
                    supported.append(r);ref_probs.append(p)
                val=supported
                if not val:report['tasks'][task]={'status':'baseline_support_unavailable'};continue
                fitted={'A':reference};predictions={'A':np.array(ref_probs)}
                for variant in ('B','C','B_momentum','B_fatigue'):
                    m=EventModel(variant).fit(train);p=m.predict(val)
                    if m.classes!=reference.classes:p=p[:,[m.classes.index(c) for c in reference.classes]]
                    fitted[variant]=m;predictions[variant]=p
                freeze_json(folder/(task+'-forecasts.json.gz'),{'gameIds':[r['gameId'] for r in val],'eventIds':[r['eventId'] for r in val],'classes':reference.classes,'probabilities':{k:v.tolist() for k,v in predictions.items()},'fitBefore':w['start'],'numericRepair':'Same rows, hyperparameters and objective; optimizer maximum raised to 2000, unconverged candidates rejected','sourceHashes':spec['sourceHashes'],'allFeaturesPreOutcome':True,'sequentialContextNotPregameEvidence':True});modelpath=folder/(task+'-models.pickle');modelpath.write_bytes(pickle.dumps(fitted,protocol=5));scores={k:categorical_metrics(val,p,reference.classes) for k,p in predictions.items()};comparisons={a+'_'+b:paired_losses(val,scores[a]['losses'],scores[b]['losses']) for a,b in [('A','B'),('B','C'),('B','B_momentum'),('B','B_fatigue')]};report['tasks'][task]={'status':'evaluated','events':len(val),'games':len({r['gameId'] for r in val}),'commonExcludedUnsupportedRows':excluded_rows,'metrics':{k:{name:v for name,v in m.items() if name not in ('losses','brierRows')} for k,m in scores.items()},'pairedLogLoss':comparisons,'pregameScoreMAE':None,'playerStatMAE':None,'predictionIntervalCoverage':None,'fullGameBrier':None,'referenceScope':spec['variantsA']};print(json.dumps({'league':sport,'window':wi,'task':task,'events':len(val),'logLoss':{k:v['logLoss'] for k,v in scores.items()}}),flush=True)
            atomic(path,report);league.append(report);gc.collect()
        summary[sport]=league;atomic(OUT/'sequential/results.json',{'leagues':summary,'productionPromotions':0,'strictPregameForecasts':0,'liveRemainingGameAccuracy':None})
    return {'leagues':{s:[w['validationGames'] for w in ws] for s,ws in summary.items()},'primaryTasks':6,'productionPromotions':0}
if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:print(json.dumps(job('sequential-r4',run,cpu=1800,wall=2400),indent=2))
