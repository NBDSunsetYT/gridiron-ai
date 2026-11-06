"""Bounded per-stat conditional tournament, never a production promotion."""
import sys,json,gzip,hashlib,pickle,gc,time
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.stat_data import packets,records,excluded_validation
from modeling.dynamic_v24.stat_models import StatModel,FAMILIES,metrics,paired
from modeling.dynamic_v24.registry import catalogue,decision,Registry
from modeling.overnight_v20.state import atomic,digest,read
from modeling.iterative_learning import freeze_json
from modeling.integration_v22.datasets import protected
WINDOWS={'NFL':[('2023-10-01','2023-12-01'),('2024-10-15','2025-02-01')],'CFB':[('2024-10-01','2024-12-01'),('2025-09-15','2025-11-01')],'NBA':[('2025-01-01','2025-03-01'),('2025-11-01','2026-02-01')]}
def code():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/dynamic_v24').glob('*.py'))]}
def register():
    rng=np.random.default_rng(24024);excluded=excluded_validation();selection={};sources=[]
    for sport,windows in WINDOWS.items():
        gs=packets(sport);selection[sport]=[]
        for start,end in windows:
            eligible=[g for g in gs if start<=g['at']<end and g['id'] not in excluded];rng.shuffle(eligible);chosen=sorted(eligible[:40],key=lambda g:(g['at'],g['id']));selection[sport].append({'start':start,'end':end,'games':[g['id'] for g in chosen],'newUnexaminedEligible':len(eligible)})
    spec={'numericCode':code(),'selection':selection,'seed':24024,'families':FAMILIES,'modelsPerStatSeparatelyFit':True,'maximumTrainingGames':200,'innerCalibrationFraction':.25,'innerCalibrationNotUsedForOuterSelection':True,'ordinaryFamilyHyperparameters':'Fixed in stat_models.py; no grid search','bootstrapGameClusters':2000,'familywiseAlpha':.05/48,'repeatedOldCohortsUsedForValidation':False,'protectedIds':sorted(protected()),'strictPregameForecasts':0,'jointMonteCarloGate':'Unchanged; zero qualified historical joint games','featuresUseOnlyEarlierCompletedAppearances':'48-hour conservative date embargo; original publication is NOT verified','continuationOf':'tournament-r1; completed NFL/CFB windows retained, missing-ID source failure fixed for later feature construction','winnerSelection':'First validation window only; second window confirms fixed family, never used for family selection'};freeze_json(OUT/'specs/tournament-r2.json',spec);print({s:[len(w['games']) for w in ws] for s,ws in selection.items()})
def run():
    spec=read(OUT/'specs/tournament-r2.json');leaderboard=catalogue();registry=Registry(OUT/'registry.json');summary={};all_candidates=0
    for sport,windows in spec['selection'].items():
        gs=packets(sport);rows=records(gs,sport);game_at={g['id']:g['at'] for g in gs};by_stat=defaultdict(list)
        for r in rows:by_stat[r['stat']].append(r)
        reports=[]
        for wi,window in enumerate(windows):
            folder=OUT/'tournament'/sport/str(wi);path=folder/'results.json'
            if path.exists():reports.append(read(path));continue
            chosen=set(window['games']);start=window['start'];before=[g['id'] for g in gs if g['at']<start][-200:];cut=int(len(before)*.75);fit_ids=set(before[:cut]);cal_ids=set(before[cut:]);report={};assert not (fit_ids|cal_ids|chosen)&protected();assert not chosen&excluded_validation()
            for stat in leaderboard[sport]:
                rr=by_stat.get(stat,[]);train=[r for r in rr if r['gameId'] in fit_ids and r['y'] is not None];cal=[r for r in rr if r['gameId'] in cal_ids and r['y'] is not None];future=[r for r in rr if r['gameId'] in chosen];usable=[i for i,r in enumerate(future) if r['y'] is not None];stripped=[{k:v for k,v in r.items() if k not in ('y','opportunity')} for r in future]
                if len(train)<100 or len(cal)<30 or len(usable)<30:
                    report[stat]={'status':'insufficient_evidence','trainingRows':len(train),'calibrationRows':len(cal),'gradedRows':len(usable),'forecasts':len(future),'reason':'Missing verified outcome category or insufficient chronological support; moneyline/spread/total require a qualified joint forecast, not independent marginal draws.'};continue
                candidates={};preds={};draws={};failures={}
                for family in FAMILIES:
                    name=family;forecast_path=folder/stat/(name+'-forecasts.json.gz')
                    try:
                        if forecast_path.exists():
                            payload=json.loads(gzip.decompress(forecast_path.read_bytes()));pred=np.array(payload.get('pointEstimate',payload['mean']));model_path=ROOT/payload['modelPath']
                            if hashlib.sha256(model_path.read_bytes()).hexdigest()!=payload['modelSHA256']:raise ValueError('Frozen model checksum mismatch')
                            model=pickle.loads(model_path.read_bytes());sample=model.samples(stripped)
                        else:
                            model=StatModel(family,stat).fit(train).calibrate_distribution(cal);pred=model.predict(stripped);sample=model.samples(stripped)
                            model_path=folder/stat/(name+'-model.pickle');model_path.parent.mkdir(parents=True,exist_ok=True)
                            if model_path.exists():raise ValueError('Orphaned immutable model requires review/new revision')
                            model_path.write_bytes(pickle.dumps(model,protocol=5));payload={'tier':'conditional_box_history','modelFamily':family,'stat':stat,'sport':sport,'modelVersion':digest({'sport':sport,'stat':stat,'family':family,'trainIds':sorted(fit_ids),'calIds':sorted(cal_ids),'code':spec['numericCode']}),'gameIds':[r['gameId'] for r in stripped],'playerIds':[r['player'] for r in stripped],'mean':pred.tolist() if model.estimand!='conditional_median' else None,'pointEstimate':pred.tolist(),'pointEstimand':model.estimand,'distributionMean':np.mean(sample,axis=1).tolist(),'interval90':np.quantile(sample,[.05,.95],axis=1).T.tolist(),'zeroProbability':np.mean(sample==0,axis=1).tolist(),'modelPath':str(model_path.relative_to(ROOT)),'modelSHA256':hashlib.sha256(model_path.read_bytes()).hexdigest(),'distributionSeed':24024,'distributionDraws':96,'rawDrawsStored':False,'trainingIds':sorted(fit_ids),'distributionCalibrationIds':sorted(cal_ids),'fitBefore':start,'currentOutcomeReadByPredictor':False,'missingAvailabilityIsHealthy':False,'marginalSamplesAreNotGameSimulations':True};freeze_json(forecast_path,payload)
                        # Only after immutable prediction storage, join outer truth.
                        grade=[future[i] for i in usable];p=pred[usable];d=sample[usable];candidates[name]=metrics(grade,p,d);preds[name]=p;draws[name]=d;all_candidates+=1
                    except (ValueError,RuntimeError,FloatingPointError) as e:failures[name]=str(e)
                # Inner-calibration-weighted ensemble, with no outer outcome fit.
                ensemble_families=[f for f in ['opponent_ridge','hierarchical','hurdle'] if f in preds]
                if len(ensemble_families)>=2:
                    inner=[]
                    for f in ensemble_families:
                        m=StatModel(f,stat).fit(train);inner.append(np.mean(abs(m.predict(cal)-np.array([r['y'] for r in cal]))))
                    weights=1/np.maximum(.001,inner);weights/=weights.sum();p=sum(w*preds[f] for w,f in zip(weights,ensemble_families));d=sum(w*draws[f] for w,f in zip(weights,ensemble_families));name='ensemble';freeze_json(folder/stat/'ensemble-forecast.json',{'weights':dict(zip(ensemble_families,weights.tolist())),'gameIds':[future[i]['gameId'] for i in usable],'mean':p.tolist(),'weightsFitOn':'inner calibration only','distributionInterpretation':'Weighted common-index marginal draw combination; never a shared-game ensemble'});candidates[name]=metrics([future[i] for i in usable],p,d);preds[name]=p;all_candidates+=1
                baseline=preds.get('rolling5');comparisons={f:paired([future[i] for i in usable],baseline,p) for f,p in preds.items() if baseline is not None and f!='rolling5'};report[stat]={'status':'conditional_evaluated','trainingRows':len(train),'innerCalibrationRows':len(cal),'forecasts':len(future),'ungradedMissingOutcomes':len(future)-len(usable),'candidates':candidates,'comparisonsAgainstRolling':comparisons,'unsupportedFamilies':failures,'joint_monte_carlo':'withheld: no strict pregame-qualified cohort'};print(json.dumps({'league':sport,'window':wi,'stat':stat,'candidates':len(candidates),'observations':len(usable)}),flush=True)
            atomic(path,report);reports.append(report);atomic(OUT/'tournament/progress.json',{'league':sport,'windowCompleted':wi,'candidateFitsOrReused':all_candidates,'productionWrites':0})
        for stat in leaderboard[sport]:
            windows_for=[w.get(stat,{}) for w in reports];complete=all(w.get('status')=='conditional_evaluated' for w in windows_for)
            if not complete:leaderboard[sport][stat].update(status='insufficient_evidence',windows=windows_for);continue
            families=set.intersection(*(set(w['candidates']) for w in windows_for));ranked=sorted(families,key=lambda f:windows_for[0]['candidates'][f]['mae']);best=ranked[0];checks=[]
            for w in windows_for:
                comparison=w['comparisonsAgainstRolling'].get(best,{'games':w['candidates'][best]['games'],'deltaCIAdjusted':[0,0]});checks.append(comparison|{'intervalCoverageRegression':max(0,w['candidates']['rolling5']['interval90Coverage']-w['candidates'][best]['interval90Coverage'])})
            verdict=decision(checks);record={'sport':sport,'stat':stat,'family':best,'accepted':verdict['accepted'],'productionPromotion':False,'jointReplacementAllowed':False,'decision':verdict,'windows':[{'baseline':w['candidates']['rolling5'],'candidate':w['candidates'][best],'paired':c} for w,c in zip(windows_for,checks)]};registry.register(record);leaderboard[sport][stat].update(status='conditional_research_ranked',**record)
        summary[sport]={'windowGames':[len(w['games']) for w in windows],'supportedHeads':sum(v['status']=='conditional_research_ranked' for v in leaderboard[sport].values()),'acceptedConditionalHeads':sum(v.get('accepted',False) for v in leaderboard[sport].values()),'strictPregameForecasts':0};atomic(OUT/'tournament/leaderboard.json',{'leagues':leaderboard,'summary':summary,'candidateFitsOrReused':all_candidates,'strictPregameForecasts':0,'productionPromotions':0});del rows,gs,by_stat;gc.collect()
    return {'leagues':summary,'candidateFitsOrReused':all_candidates,'productionPromotions':0}
if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:print(json.dumps(job('tournament-r2',run,cpu=2400,wall=3000),indent=2))
