"""Offline preregistered structural research. No web/database/provider execution.
First prepare metadata-only cohorts, then fit candidates and grade validation.
"""
import argparse,gzip,hashlib,json,os,resource,sys,time,pickle,random
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.structural_v18.data import packets,build_dataset,stamp
from modeling.structural_v18.models import Projection,FAMILIES,OPPORTUNITY,error_metrics,cluster_delta
OUT=ROOT/'artifacts/structural-v18'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);raw=json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode();encoded=gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw
    if path.exists():
        if path.read_bytes()!=encoded:raise ValueError('Immutable artifact differs: '+str(path))
        return
    with path.open('xb') as f:f.write(encoded)
def verify_sources(protocol):
    for item in protocol['sourceFiles']:
        p=ROOT/item['path']
        if not p.is_file() or digest(p)!=item['sha256']:raise ValueError('Locked source changed or missing: '+item['path'])

def exposed():
    all_games=[]
    for f,key in [('artifacts/engine-v15/selection.json','selection'),('artifacts/engine-v15/nba/selection.json','games'),('artifacts/learning-v16/protocol.json','selection')]:all_games.extend(json.loads((ROOT/f).read_text())[key])
    return {g['id'] for g in all_games}|{'cfb:espn:401858509','cfb:espn:401756926','2025_07_LA_JAX','2025_13_KC_DAL'}
WINDOWS={'NFL':[('2025-09-15','2025-10-01'),('2025-10-15','2025-11-01'),('2025-11-15','2025-12-01')],'CFB':[('2025-09-15','2025-10-01'),('2025-10-15','2025-11-01'),('2025-11-15','2025-12-01')],'NBA':[('2025-11-15','2025-12-01'),('2025-12-01','2025-12-16'),('2025-12-16','2026-01-01')]}
def prepare():
    if (OUT/'protocol.json').exists():raise ValueError('Protocol already locked; do not reselect validation games')
    rng=random.Random(18018);excluded=exposed();selected={};coverage={}
    for sport,windows in WINDOWS.items():
        games=packets(sport);chosen=[];history=defaultdict(int);eligible=[[] for _ in windows]
        for g in games:
            good=min(history[g['home']],history[g['away']])>=3
            for i,(start,end) in enumerate(windows):
                if start<=g['at'][:10]<end and g['id'] not in excluded and good:eligible[i].append(g)
            for team in (g['home'],g['away']):history[team]+=1
        for i,group in enumerate(eligible):
            rng.shuffle(group);cap=24 if sport=='NFL' else 80
            chosen.extend({'id':g['id'],'at':g['at'],'home':g['home'],'away':g['away'],'cohort':i,'sport':sport} for g in group[:cap])
        selected[sport]=sorted(chosen,key=lambda g:(g['at'],g['id']));coverage[sport]=[len(g) for g in eligible]
    protocol={'version':'structural-v18','seed':18018,'selection':selected,'eligiblePerWindow':coverage,'excludedPreviouslyEvaluated':sorted(excluded),'trainEnd':'2025-07-01','families':list(FAMILIES),'structuralHypotheses':['Pace-evidence filters must not discard valid NBA rotation/player box scores.','Past non-participation belongs in opportunity estimation; appearance-conditioned means bias workload.','Opportunity/efficiency factorization and opponent-adjusted regression may outperform play-resampling means.'],'primaryMetrics':{'NBA':'minutes MAE; then points/rebounds/assists MAE','NFL':'passingAttempts, targets, carries and yardage MAE','CFB':'passingAttempts, targets, carries and yardage MAE'},'promotionGate':{'minimumGames':200,'independentWindows':3,'pairedGameBootstrapUpperBelow':0,'maximumImportantCategoryMAERegression':.03,'brierAndLogLossMustNotRegress':True,'verifiedPregameInjuriesAndLineupsRequired':True},'fullGameSubsetPerWindow':3,'simulations':10000,'cpuBudgetSeconds':1800,'wallBudgetSeconds':3000,'prospectiveFinal':{'start':'2026-11-05','gamesPerLeague':30,'status':'reserved_not_observed','requiresSnapshotsBeforeKickoff':True,'historicalBackfillForbidden':True},'historicalPublicationVerified':False,'originalForecastsModified':False,'sourceFiles':[]}
    for p in [ROOT/'artifacts/learning-v16/datasets'/f'{s}-repaired.pickle' for s in ['NFL','CFB','NBA']]+[ROOT/'artifacts/engine-v15/nba/owned-dataset.cache']:protocol['sourceFiles'].append({'path':str(p.relative_to(ROOT)),'sha256':digest(p)})
    save(OUT/'protocol.json',protocol);print(json.dumps({'selected':{s:len(g) for s,g in selected.items()},'eligible':coverage,'protocolSha256':digest(OUT/'protocol.json')}))

def probability_metrics(actual,pred,residual,threshold):
    # Empirical out-of-sample training-residual distribution; not MC games.
    r=np.sort(residual);p=(len(r)-np.searchsorted(r,threshold-pred,side='right'))/len(r);y=np.asarray(actual)>threshold;q=np.clip(p,1e-12,1-1e-12)
    return {'n':len(y),'threshold':threshold,'brier':float(np.mean((p-y)**2)),'logLoss':float(-np.mean(y*np.log(q)+(1-y)*np.log1p(-q))),'method':'training_holdout_residual_distribution','calibrated':False,'historicalMarketLine':False}

def team_win(valid,preds,cal_predictions):
    from modeling.calibration_research import metrics
    va=defaultdict(dict)
    for r in valid:
        if r['player']=='__team__' and r['stat']=='score':va[r['gameId']][bool(r['x'][2])]=r
    results={}
    for family in FAMILIES:
        lookup=preds.get(((True,'score'),family));cp=cal_predictions.get(family)
        if not lookup or not cp:continue
        pairs=defaultdict(dict)
        for r,p in cp:pairs[r['gameId']][bool(r['x'][2])]=(r,p)
        residual=[]
        for pair in pairs.values():
            if len(pair)==2:residual.append(pair[True][0]['y']-pair[False][0]['y']-(pair[True][1]-pair[False][1]))
        if len(residual)<20:continue
        sorted_r=np.sort(residual);prob=[];truth=[];margin_errors=[]
        for pair in va.values():
            if len(pair)!=2:continue
            h,a=pair[True],pair[False];ident=lambda r:(r['gameId'],r['team'],r['player']);margin=lookup[ident(h)]-lookup[ident(a)]
            if h['y']==a['y']:continue
            prob.append(float((len(sorted_r)-np.searchsorted(sorted_r,-margin,side='right'))/len(sorted_r)));truth.append(int(h['y']>a['y']));margin_errors.append(margin-(h['y']-a['y']))
        results[family]={'moneyline':metrics(prob,truth),'margin':error_metrics(np.zeros(len(margin_errors)),margin_errors),'holdoutResidualGames':len(residual),'calibrated':False,'method':'joint_team_margin_training_holdout_residuals'}
    return results

def run_projection(cpu_seconds):
    protocol=json.loads((OUT/'protocol.json').read_text());verify_sources(protocol);started=time.monotonic();cpu=time.process_time();report={'version':'structural-v18','leagues':{},'promoted':[],'finalOpened':False,'protocolSha256':digest(OUT/'protocol.json')}
    for sport in ['NBA','NFL','CFB']:
        selected=protocol['selection'][sport];index={g['id']:g['cohort'] for g in selected};end=max(b for a,b in WINDOWS[sport]);rows,games=build_dataset(sport,end)
        train=[r for r in rows if r['at']<protocol['trainEnd']];valid=[r for r in rows if r['gameId'] in index]
        if not train or not valid:raise ValueError('Chronological coverage insufficient')
        for row in train+valid:
            if stamp(row['featureCutoff'])+6*3600>=stamp(row['at']):raise ValueError('Future information in features')
        train_groups=defaultdict(list);valid_groups=defaultdict(list)
        for r in train:train_groups[(r['player']=='__team__',r['stat'])].append(r)
        for r in valid:valid_groups[(r['player']=='__team__',r['stat'])].append(r)
        models={};preds={};groups={};residuals={};cal_predictions={}
        # Opportunity models are fitted before efficiency factorization.
        keys=sorted(train_groups,key=lambda k:(k[1] not in ('minutes','passingAttempts','targets','carries'),k))
        for key in keys:
            tr=sorted(train_groups[key],key=lambda r:r['at']);va=valid_groups[key]
            if len(tr)<150 or not va:continue
            split_date=sorted({r['at'][:10] for r in tr})[int(len({r['at'][:10] for r in tr})*.8)];core=[r for r in tr if r['at'][:10]<split_date];cal=[r for r in tr if r['at'][:10]>=split_date]
            kind='team' if key[0] else 'player';stat=key[1];group={};ys=np.asarray([r['y'] for r in va]);baseline=np.asarray([r['baseline'] for r in va]);ident=lambda r:(r['gameId'],r['team'],r['player'])
            for family in FAMILIES:
                if time.process_time()-cpu>cpu_seconds:raise TimeoutError('Projection CPU budget reached')
                model=Projection(family).fit(tr);op=None
                if family=='hybrid' and getattr(model,'rate',None) is not None:
                    op_key=(key[0],OPPORTUNITY[stat]);lookup=preds.get((op_key,'ridge'))
                    if lookup is None:raise ValueError('Causal opportunity model is missing')
                    op=np.array([lookup[ident(r)] for r in va])
                p=model.predict(va,op);models[(key,family)]=model;preds[(key,family)]={ident(r):float(v) for r,v in zip(va,p)}
                if family=='hybrid' and getattr(model,'rate',None) is not None:
                    # Residual uncertainty is not available until a separately
                    # held-out opportunity/efficiency chain is evaluated.
                    residual=None
                else:
                    cmodel=Projection(family).fit(core);cp=cmodel.predict(cal);residual=np.asarray([r['y'] for r in cal])-cp
                    if key==(True,'score'):cal_predictions[family]=[(r,float(v)) for r,v in zip(cal,cp)]
                residuals[(key,family)]=residual
                entry={**error_metrics(ys,p),'games':len({r['gameId'] for r in va}),'players':len({r['player'] for r in va}),'pairedVsRolling':cluster_delta(va,baseline,p),'windows':{str(i):error_metrics(ys[[j for j,r in enumerate(va) if index[r['gameId']]==i]],p[[j for j,r in enumerate(va) if index[r['gameId']]==i]]) for i in range(3)}}
                if residual is not None and len(residual)>=20:
                    q=np.quantile(residual,[.05,.95]);entry['interval90Coverage']=float(np.mean((ys>=p+q[0])&(ys<=p+q[1])));entry['intervalResidualGames']=len({r['gameId'] for r in cal})
                    thresholds={'points':20.5,'rebounds':7.5,'assists':5.5,'passingYards':249.5,'rushingYards':59.5,'receivingYards':64.5,'receptions':4.5,'passingAttempts':29.5,'targets':5.5,'carries':14.5}
                    if stat in thresholds:entry['diagnosticThreshold']=probability_metrics(ys,p,residual,thresholds[stat])
                group[family]=entry
            league_mean=np.mean([r['y'] for r in train_groups[(True,stat)]])
            oi=va[0]['featureNames'].index('opponent_allowed_'+stat) if stat in ('score','plays','dropbacks') or 'opponent_allowed_'+stat in va[0]['featureNames'] else None
            if oi is not None and league_mean>0:
                opponent=np.array([r['baseline']*(1+r['x'][1]/(r['x'][1]+8)*(r['x'][oi]/league_mean-1)) for r in va]);group['opponent_rolling']={**error_metrics(ys,opponent),'games':len({r['gameId'] for r in va}),'players':len({r['player'] for r in va}),'pairedVsRolling':cluster_delta(va,baseline,opponent)}
            groups[kind+':'+stat]=group
        # Persist pregame predictions separately from actuals; no unbounded play logs.
        bundle={'sport':sport,'cutoff':protocol['trainEnd'],'rows':[{'gameId':r['gameId'],'team':r['team'],'player':r['player'],'stat':r['stat'],'featureCutoff':r['featureCutoff'],'predictions':{f:preds[((r['player']=='__team__',r['stat']),f)][ident(r)] for f in FAMILIES}} for r in valid if ((r['player']=='__team__',r['stat']),'ridge') in preds]}
        save(OUT/'projections'/f'{sport}.json.gz',bundle)
        with (OUT/f'{sport}-projection-models.pickle').open('xb') as f:pickle.dump(models,f)
        # The following outcome file is only evaluation evidence, not model inputs.
        save(OUT/'actuals'/f'{sport}.json.gz',{'rows':[{'gameId':r['gameId'],'team':r['team'],'player':r['player'],'stat':r['stat'],'actual':r['y']} for r in valid]})
        report['leagues'][sport]={'teamWin':team_win(valid,preds,cal_predictions),'games':len({r['gameId'] for r in valid}),'players':len({r['player'] for r in valid if r['player']!='__team__'}),'trainingGames':len({r['gameId'] for r in train}),'sourceObservations':len(valid),'groups':groups,'injuryStatus':'unknown','pregamePublicationVerified':False};save(OUT/'projection-progress'/f'{sport}.json',report['leagues'][sport]);print(json.dumps({'sport':sport,'games':report['leagues'][sport]['games'],'groups':len(groups),'cpuSeconds':time.process_time()-cpu}),flush=True)
    report['resources']={'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-started,'newMonteCarloRuns':0,'hostingCpu':0};save(OUT/'projection-report.json',report)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','projections']);p.add_argument('--cpu-seconds',type=int,default=300);p.add_argument('--out',type=Path,default=OUT);a=p.parse_args();OUT=a.out.resolve()
    if os.environ.get('VERCEL') or os.environ.get('RENDER'):p.error('This research runner is local only')
    if not 1<=a.cpu_seconds<=600:p.error('Choose a bounded 1..600 second projection budget')
    resource.setrlimit(resource.RLIMIT_CPU,(a.cpu_seconds,a.cpu_seconds+2))
    if a.action=='prepare':prepare()
    else:run_projection(a.cpu_seconds)
