"""Immutable, local-only specialized-head completion. No cloud/DB writes.

Register once, then execute each bounded league job. Inner selection precedes
both new outer windows. Final-test and locked-confirmation IDs stay excluded.
"""
import sys,json,re,gzip,pickle,hashlib,warnings,gc
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job,verify_parent
from modeling.dynamic_v24.stat_data import excluded_validation
from modeling.dynamic_v24.stat_models import FAMILIES
from modeling.dynamic_v24.registry import catalogue
from modeling.dynamic_v24.completion.data import packets,enrich_packets,records,features_only,EXTRA_FOOT,EXTRA_NBA
from modeling.dynamic_v24.completion.models import candidate,MixtureModel
from modeling.dynamic_v24.completion.selection import evaluate,choose,paired_loss,decision,Registry
from modeling.integration_v22.datasets import protected
from modeling.overnight_v20.state import atomic,read,digest
from modeling.iterative_learning import freeze_json

REV='completion-r4';DEST=OUT/REV;SEED=240241
WINDOWS={'NFL':[('2022-11-01','2022-12-01'),('2023-10-01','2023-12-01')],
         'CFB':[('2025-09-15','2025-11-01'),('2026-10-01','2026-11-01')],
         'NBA':[('2025-01-01','2025-03-01'),('2025-11-01','2026-02-01')]}
FAMILY_LIST=tuple(FAMILIES)+('opportunity_pooling','minutes_rebound_opportunity','v20_hurdle_refit')

def old_evaluations():
    excluded=set(excluded_validation())
    def visit(v):
        if isinstance(v,str) and (re.match(r'^\d{4}_\d{2}_[A-Z]+_[A-Z]+$',v) or re.match(r'^(cfb|nba):espn:\d+$',v)):excluded.add(v)
        elif isinstance(v,dict):
            for k,x in v.items():visit(k);visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    for p in OUT.glob('**/specs/*.json'):
        if REV in p.parts:continue
        value=read(p)
        if isinstance(value,dict):visit(value.get('selection',{}))
    return excluded

def code():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py')),*sorted((ROOT/'modeling/dynamic_v24').glob('*.py')),ROOT/'modeling/integration_v22/control.py',ROOT/'modeling/prop_history.py',ROOT/'modeling/hierarchical_props.py']}
def register():
    excluded=old_evaluations();selection={};rng=np.random.default_rng(SEED)
    for sport,windows in WINDOWS.items():
        gs=packets(sport);selection[sport]=[]
        for start,end in windows:
            eligible=[g['id'] for g in gs if start<=g['at']<end and g['id'] not in excluded];rng.shuffle(eligible);selected=sorted(eligible[:40]);selection[sport].append({'start':start,'end':end,'games':selected,'pool':len(eligible)})
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folders in ['artifacts/overnight-v21/external','artifacts/integration-v22/external','artifacts/fullgame-v23/sources','artifacts/learning-v16/datasets','artifacts/engine-v15/nba'] for p in (ROOT/folders).glob('*') if p.is_file() and (p.suffix in ('.parquet','.pickle') or p.name=='owned-dataset.cache')}
    for p in [ROOT/'artifacts/overnight-v21/source-repair/CFB-2026-normalized.pickle',ROOT/'artifacts/parallel-v19/sources/nfl-games.csv']:sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    protocol={'revision':REV,'numericCode':code(),'selection':selection,'sourceVersions':sources,'seed':SEED,'excludedValidationIds':sorted(excluded),'protectedIds':sorted(protected()),'families':FAMILY_LIST,'trainingGamesMaximum':500,'chronologicalBlocks':[.65,.15,.20],'distributionDraws':128,'theseAreNotMonteCarloGames':True,'innerSelectionOnly':True,'secondWindowFamilyFixedBeforeItsOutcomes':'First window inner selector fixes family; updated earlier training is allowed, no outer tuning','strictForecastsAllowed':False,'productionWrites':0,'ensemble':'Mixture, not an average of marginal draws','comparisonAlpha':.05/159,'bootstrapReplicates':20000,'hypotheses':['Shared team opportunities and shrunk player shares reduce football attempt errors','NBA prior-starter and missed-shot exposure features improve minutes/rebounds','Selecting expected-value and distribution heads separately avoids median/mean and probability regressions']}
    freeze_json(DEST/'protocol.json',protocol)
    for sport in WINDOWS:freeze_json(OUT/'specs'/('completion-'+sport.lower()+'-r4.json'),{'numericCode':code(),'inputHashes':sources,'protocol':digest(protocol),'league':sport})
    print(json.dumps({'selection':{s:[len(w['games']) for w in ws] for s,ws in selection.items()},'sourceVersions':len(sources),'strictForecasts':0}))

def crps_rows(draws,y):
    s=np.sort(draws,axis=1);n=s.shape[1];return np.mean(abs(s-y[:,None]),axis=1)-np.sum((2*np.arange(1,n+1)-n-1)*s,axis=1)/(n*n)

def attribution(rows,point,factors):
    if not factors:return None
    observed=np.array([r['opportunity'] if r.get('opportunity') is not None else np.nan for r in rows]);y=np.array([r['y'] for r in rows]);op=factors['exposure'];rate=factors['efficiency']
    if factors.get('reboundProxy'):
        observed=observed/48*np.array([r.get('actualGameMisses') or np.nan for r in rows])
    good=np.isfinite(observed)&(observed>0);actual_rate=y[good]/observed[good];a=.5*(rate[good]+actual_rate)*(op[good]-observed[good]);b=.5*(op[good]+observed[good])*(rate[good]-actual_rate)
    if not np.allclose(a+b,np.asarray(point)[good]-y[good]):raise AssertionError('Opportunity/efficiency error attribution does not reconcile')
    return {'observations':int(good.sum()),'opportunityComponentMAE':float(np.mean(abs(a))) if good.any() else None,'efficiencyComponentMAE':float(np.mean(abs(b))) if good.any() else None,'opportunitySignedBias':float(np.mean(a)) if good.any() else None,'efficiencySignedBias':float(np.mean(b)) if good.any() else None,'interpretation':'Exact symmetric product-error decomposition, not causal attribution; absolute components can cancel','reboundExposureProxy':bool(factors.get('reboundProxy'))}

def production_source_reference(sport,stat,rows,folder):
    if sport!='NFL' or stat!='passingYards':return None
    from modeling.integration_v22.datasets import nfl_packets
    from modeling.integration_v22.control import replay
    raw=nfl_packets()[1];lookup={};pred=[]
    for r in features_only(rows):
        key=(int(r['season']),int(r['gameId'].split('_')[1]))
        if key not in lookup:lookup[key]=replay(raw,*key,r['at'])[0]
        pred.append(lookup[key].get(r['player'],{}).get('mean'))
    freeze_json(folder/stat/'production-source-reference.json',{'gameIds':[r['gameId'] for r in rows],'playerIds':[r['player'] for r in rows],'pointEstimate':pred,'sourceCodeHash':hashlib.sha256((ROOT/'modeling/integration_v22/control.py').read_bytes()).hexdigest(),'scope':'Actual production source algorithm replay on earlier QB appearances, not a deployed pregame snapshot; availability and publication still unverified','currentOutcomeUsed':False})
    return pred

def run(sport):
    spec=read(DEST/'protocol.json');windows=spec['selection'][sport];gs=enrich_packets(packets(sport),sport);rows=records(gs,sport);by_stat=defaultdict(list)
    for r in rows:by_stat[r['stat']].append(r)
    heads=list(catalogue()[sport])+list(EXTRA_NBA if sport=='NBA' else EXTRA_FOOT);registry=Registry(DEST/'registry.json');reports=[];fixed={};models_evaluated=0
    for wi,window in enumerate(windows):
        folder=DEST/sport/str(wi);existing=read(folder/'results.json')
        if existing:
            reports.append(existing)
            if wi==0:fixed={stat:v.get('selected',{}) for stat,v in existing.items()}
            continue
        from modeling.accuracy_v20.quality import aware
        earlier=[g for g in gs if g['at']<window['start']][-500:];times=sorted({aware(g['at']) for g in earlier});first=times[int(len(times)*.65)];second=times[int(len(times)*.8)];ids=[{g['id'] for g in earlier if aware(g['at'])<first},{g['id'] for g in earlier if first<=aware(g['at'])<second},{g['id'] for g in earlier if aware(g['at'])>=second}];outer=set(window['games']);report={}
        if (set.union(*ids)|outer)&protected() or outer&set(spec['excludedValidationIds']):raise ValueError('Protected or reused validation cohort')
        for stat in heads:
            rr=by_stat.get(stat,[]);blocks=[[r for r in rr if r['gameId'] in index and r['y'] is not None] for index in ids];train,cal,select=blocks;future=[r for r in rr if r['gameId'] in outer];usable=[i for i,r in enumerate(future) if r['y'] is not None];x=features_only(future);grade=[future[i] for i in usable]
            if min(map(len,blocks),default=0)<30 or len(train)<100 or len(usable)<30:
                report[stat]={'status':'insufficient_evidence','training':len(train),'residualCalibration':len(cal),'innerSelection':len(select),'gradedObservations':len(usable),'games':len({r['gameId'] for r in grade}),'reason':'Insufficient chronological labels; unverified categories are not filled with zeros'};continue
            if max(aware(r['at']) for r in train)>=min(aware(r['at']) for r in cal) or max(aware(r['at']) for r in cal)>=min(aware(r['at']) for r in select) or max(aware(r['at']) for r in select)>=min(aware(r['at']) for r in future):raise ValueError('Chronological block overlap')
            thresholds=np.unique(np.quantile([r['y'] for r in train],[.1,.25,.5,.75,.9])).tolist();thresholds=[float(t) for t in thresholds];inner={};estimands={};predictions={};draws={};scores={};failures={};factors={};model_paths={};trained_models={}
            for family in FAMILY_LIST:
                if family=='minutes_rebound_opportunity' and (sport!='NBA' or stat!='rebounds'):continue
                if stat in ('moneyline','doubleDouble','tripleDouble','teamPoints','spread','total') and family in ('opportunity_pooling','minutes_rebound_opportunity','v20_hurdle_refit'):continue
                try:
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always',ConvergenceWarning);model=candidate(family,stat,train,cal)
                    if any(isinstance(w.message,ConvergenceWarning) for w in caught):raise ValueError('Fit did not converge; not eligible for selection')
                    trained_models[family]=model
                    sx=features_only(select);sp=model.predict(sx);sd=model.samples(sx,SEED,128);inner[family]=evaluate(select,sp,sd,thresholds);estimands[family]=model.estimand
                    pred=model.predict(x);sample=model.samples(x,SEED,128);path=folder/stat/(family+'-model.pickle');path.parent.mkdir(parents=True,exist_ok=True)
                    if path.exists():raise ValueError('Orphan model: register a new revision, do not overwrite')
                    path.write_bytes(pickle.dumps(model,protocol=5));model_sha=hashlib.sha256(path.read_bytes()).hexdigest();model_paths[family]={'path':str(path.relative_to(ROOT)),'sha256':model_sha}
                    freeze_json(folder/stat/(family+'-forecast.json.gz'),{'sport':sport,'stat':stat,'family':family,'modelVersion':digest({'code':spec['numericCode'],'trainIds':sorted(ids[0]),'calibrationIds':sorted(ids[1]),'family':family,'stat':stat,'sport':sport}),'modelSHA256':model_sha,'gameIds':[r['gameId'] for r in x],'playerIds':[r['player'] for r in x],'teamIds':[r['team'] for r in x],'pointEstimate':pred.tolist(),'estimand':model.estimand,'interval90':np.quantile(sample,[.05,.95],axis=1).T.tolist(),'trainingThrough':max(r['at'] for r in train),'residualCalibrationThrough':max(r['at'] for r in cal),'selectionThrough':max(r['at'] for r in select),'featureInputHash':digest(x),'sourceVersions':spec['sourceVersions'],'seed':SEED,'marginalDistributionDraws':128,'completeGamesSimulated':0,'scope':'conditional_corrected_history','calibratedProbability':None,'labelsReadByPrediction':False})
                    # Forecasts now frozen. Only here may current labels be joined.
                    predictions[family]=pred[usable];draws[family]=sample[usable];scores[family]=evaluate(grade,pred[usable],sample[usable],thresholds);models_evaluated+=1
                    if hasattr(getattr(model,'point',None),'factors'):
                        ff=model.point.factors(x);factors[family]={k:v[usable] for k,v in ff.items()};factors[family]['reboundProxy']=model.point.rebound
                except (ValueError,RuntimeError,FloatingPointError) as e:failures[family]=str(e)
            components=sorted([f for f in inner if estimands[f]!='conditional_median'],key=lambda f:inner[f]['crps'])[:3]
            if len(components)>=2:
                weights=1/np.maximum(1e-6,[inner[f]['crps'] for f in components]);weights=weights/weights.sum();model=MixtureModel([trained_models[f] for f in components],weights,stat);family='inner_mixture';sx=features_only(select);inner[family]=evaluate(select,model.predict(sx),model.samples(sx,SEED,128),thresholds);estimands[family]=model.estimand;pred=model.predict(x);sample=model.samples(x,SEED,128)
                path=folder/stat/(family+'-model.pickle');path.write_bytes(pickle.dumps(model,protocol=5));sha=hashlib.sha256(path.read_bytes()).hexdigest();model_paths[family]={'path':str(path.relative_to(ROOT)),'sha256':sha}
                freeze_json(folder/stat/(family+'-forecast.json.gz'),{'sport':sport,'stat':stat,'family':family,'estimand':model.estimand,'components':components,'weights':weights.tolist(),'weightsFitOn':'Chronological inner-selection data only','gameIds':[r['gameId'] for r in x],'playerIds':[r['player'] for r in x],'teamIds':[r['team'] for r in x],'pointEstimate':pred.tolist(),'interval90':np.quantile(sample,[.05,.95],axis=1).T.tolist(),'modelSHA256':sha,'featureInputHash':digest(x),'scope':'conditional_marginal_mixture_not_joint_games','seed':SEED,'calibratedProbability':None})
                predictions[family]=pred[usable];draws[family]=sample[usable];scores[family]=evaluate(grade,pred[usable],sample[usable],thresholds);models_evaluated+=1
            if 'rolling5' not in inner:raise ValueError('Rolling reference unavailable')
            selected={purpose:choose(inner,estimands,purpose) for purpose in ('median','distribution')}
            if any(v=='conditional_mean' for v in estimands.values()):selected['expected_value']=choose(inner,estimands,'expected_value')
            if wi==0:fixed[stat]=selected
            else:selected=fixed.get(stat,{})
            checks={};y=np.array([r['y'] for r in grade])
            for purpose,family in selected.items():
                if family not in predictions:checks[purpose]={'status':'unsupported_fixed_family','family':family};continue
                if purpose=='distribution':
                    if stat in ('moneyline','doubleDouble','tripleDouble'):before=(predictions['rolling5']-y)**2;after=(predictions[family]-y)**2
                    else:before=crps_rows(draws['rolling5'],y);after=crps_rows(draws[family],y)
                    paired=paired_loss(grade,before,after,loss='provided')
                else:paired=paired_loss(grade,predictions['rolling5'],predictions[family],loss='squared' if purpose=='expected_value' else 'absolute')
                checks[purpose]={'family':family,'games':scores[family]['games'],'observations':len(grade),'reference':scores['rolling5'],'candidate':scores[family],'paired':paired,'converged':True}
            prod=production_source_reference(sport,stat,grade,folder);prod_report={'status':'unavailable','reason':'No matching immutable point-in-time production head snapshot for these new game/player keys; refitted V20 hurdle is not production'}
            if prod is not None:
                pi=[i for i,p in enumerate(prod) if p is not None];yy=np.array([grade[i]['y'] for i in pi]);pp=np.array([prod[i] for i in pi]);prod_report={'status':'conditional_production_source_algorithm_replay','games':len({grade[i]['gameId'] for i in pi}),'observations':len(pi),'referenceMAE':float(np.mean(abs(pp-yy))),'referenceRMSE':float(np.sqrt(np.mean((pp-yy)**2))),'candidateComparisons':{f:paired_loss([grade[i] for i in pi],pp,predictions[f][pi]) for f in set(selected.values()) if f in predictions},'strictPregameSnapshot':False,'probabilityCalibration':None}
                if len(pi)==len(grade) and 'expected_value' in checks:
                    family=checks['expected_value']['family'];checks['expected_value']['productionSourceReference']={'mae':prod_report['referenceMAE'],'rmse':prod_report['referenceRMSE'],'paired':paired_loss(grade,pp,predictions[family],loss='squared'),'scope':'Source algorithm replay, not recovered deployed historical snapshot'}
            report[stat]={'status':'conditional_evaluated','selected':selected,'checks':checks,'candidates':scores,'innerMetrics':inner,'estimands':estimands,'failures':failures,'modelArtifacts':model_paths,'ungradedMissingOutcomes':len(future)-len(usable),'trainingThrough':max(r['at'] for r in train),'attribution':{f:attribution(grade,predictions[f],v) for f,v in factors.items()},'productionChampionComparison':prod_report,'v23ReferenceComparison':{'status':'mechanics_only','reason':'Final-conditioned V23 mechanics rates cannot be graded as pregame predictions'}}
            print(json.dumps({'league':sport,'window':wi,'stat':stat,'candidates':len(scores),'games':scores['rolling5']['games'],'selected':selected}),flush=True)
            atomic(folder/'progress.json',{'completedStats':list(report),'modelsEvaluatedThisInvocation':models_evaluated})
        atomic(folder/'results.json',report);reports.append(report)
    leaderboard=[]
    for stat in heads:
        for purpose in ('expected_value','median','distribution'):
            checks=[r.get(stat,{}).get('checks',{}).get(purpose) for r in reports]
            if not all(c and 'paired' in c for c in checks):
                if purpose=='median':continue
                leaderboard.append({'sport':sport,'stat':stat,'purpose':purpose,'winningFamily':None,'improvementEstablished':False,'reason':'Insufficient category or chronological confirmation evidence','jointSimulationEligible':False,'productionPromotionEligible':False});continue
            verdict=decision(checks,purpose);family=checks[0]['family'];entry={'sport':sport,'stat':stat,'family':family,'purpose':purpose,'estimand':reports[0][stat]['estimands'][family],'modelVersion':digest({'revision':REV,'sport':sport,'stat':stat,'family':family,'purpose':purpose,'code':spec['numericCode']}),'trainingCutoff':[r[stat]['trainingThrough'] for r in reports],'validationWindows':[{'start':w['start']+'T00:00:00+00:00','end':w['end']+'T00:00:00+00:00'} for w in windows],'sourceVersions':spec['sourceVersions'],'sampleSize':{'games':sum(c['games'] for c in checks),'observations':sum(c['observations'] for c in checks)},'metrics':checks,'uncertainty':[c['paired'] for c in checks],'decision':verdict,'modelSHA256':[r[stat]['modelArtifacts'][family]['sha256'] for r in reports],'productionPromotion':False};registry.register(entry)
            leaderboard.append({'sport':sport,'stat':stat,'purpose':purpose,'winningFamily':family if verdict['conditionalImprovementEstablished'] else None,'fixedCandidateFamily':family,'improvementEstablished':verdict['conditionalImprovementEstablished'],'referenceMAE':[c['reference']['mae'] for c in checks],'candidateMAE':[c['candidate']['mae'] for c in checks],'referenceRMSE':[c['reference']['rmse'] for c in checks],'candidateRMSE':[c['candidate']['rmse'] for c in checks],'independentGames':[c['games'] for c in checks],'observations':[c['observations'] for c in checks],'referenceCalibration':[c['reference']['cdfBrier'] for c in checks],'candidateCalibration':[c['candidate']['cdfBrier'] for c in checks],'candidateLogLoss':[c['candidate']['cdfLogLoss'] for c in checks],'intervalCoverage':[c['candidate']['coverage'] for c in checks],'pairedUncertainty':[c['paired'] for c in checks],'decision':verdict,'jointSimulationEligible':False,'productionPromotionEligible':False})
    atomic(DEST/sport/'leaderboard.json',leaderboard);return {'sport':sport,'modelsEvaluatedThisInvocation':models_evaluated,'newOuterMatchups':[len(w['games']) for w in windows],'conditionalEstablishedHeads':sum(x['improvementEstablished'] for x in leaderboard),'strictPregameForecasts':0,'productionPromotions':0}

if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:
        sport=next((s for s in WINDOWS if '--'+s.lower() in sys.argv),None)
        if sport is None:raise SystemExit('Select --register, --nfl, --cfb or --nba')
        print(json.dumps(job('completion-'+sport.lower()+'-r4',lambda:run(sport),cpu=1200,wall=1800),indent=2))
