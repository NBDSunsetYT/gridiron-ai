"""Aggregate recorded results with explicit estimands and separate evidence tiers."""
import sys,json,gzip,pickle,hashlib,gc
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.stat_data import packets,records
from modeling.overnight_v20.state import atomic,read

def run():
    event=read(OUT/'sequential/results.json');base=read(OUT/'tournament/leaderboard.json');extra=read(OUT/'supplement/tournament/leaderboard.json');heads={s:dict(hs) for s,hs in base['leagues'].items()}
    for s in ('NFL','CFB'):
        for stat,h in extra['leagues'][s].items():
            if h.get('status')=='conditional_research_ranked':heads[s][stat]=h|{'cohort':'supplement_new_games'}
    dynamic_decisions={}
    for sport,windows in event['leagues'].items():
        dynamic_decisions[sport]={}
        for task in ('actions','shots') if sport=='NBA' else ('actions','drives'):
            ws=[w['tasks'].get(task,{}) for w in windows];valid=all(w.get('status')=='evaluated' for w in ws)
            c=valid and all(w['pairedLogLoss']['B_C']['familywiseCI'][1]<0 and w['metrics']['C']['brier']<=w['metrics']['B']['brier']+.002 and w['metrics']['C']['ECE']<=w['metrics']['B']['ECE']+.02 for w in ws)
            b=valid and all(w['pairedLogLoss']['A_B']['familywiseCI'][1]<0 and w['metrics']['B']['brier']<=w['metrics']['A']['brier']+.002 for w in ws)
            dynamic_decisions[sport][task]={'conditionalCImprovementSupported':bool(c),'conditionalBImprovementSupported':bool(b),'productionPromotion':False,'jointGameImprovement':False,'momentumInterpretation':'NBA action benefit is nonlinear within-possession event history; it is NOT evidence of physiological fatigue or hot-hand shooting.' if sport=='NBA' and task=='actions' else 'No repeatable incremental momentum improvement established.'}
    leaderboard=[]
    for s,hs in heads.items():
        for stat,h in hs.items():
            if h.get('status')!='conditional_research_ranked':leaderboard.append({'sport':s,'stat':stat,'status':'insufficient_evidence','reason':'Missing outcome data, insufficient chronological support or no qualified joint model/verified historical market definition','productionPromotion':False});continue
            family=h['family'];point_kind='conditional_median' if family=='quantile' else 'conditional_probability' if stat in ('doubleDouble','tripleDouble') else 'conditional_mean';prob_guard=all(w['candidate']['crps']<=w['baseline']['crps'] and w['candidate']['zeroEventBrier']<=w['baseline']['zeroEventBrier']+.002 and w['candidate']['interval90Coverage']>=max(.85,w['baseline']['interval90Coverage']-.03) for w in h['windows']);leaderboard.append({'sport':s,'stat':stat,'status':'conditional_evaluated','baseline':'rolling5','bestFirstWindowFamily':family,'pointEstimand':point_kind,'pointResearchCandidate':bool(h.get('accepted')),'distributionGuardDescriptivelyPasses':prob_guard,'probabilityChampionAccepted':False,'reasonProbabilityWithheld':'No paired CRPS/tail/verified-line confirmation; a marginal head cannot replace the joint-game model','windows':h['windows'],'productionPromotion':False,'cohort':h.get('cohort','initial')})
    attr=[]
    for sport,stat in [('NFL','passingYards'),('CFB','passingYards'),('NBA','rebounds')]:
        gs=packets(sport);rr=records(gs,sport);indexed={(r['gameId'],r['player']):r for r in rr if r['stat']==stat};prefix=OUT/'tournament' if sport=='NBA' else OUT/'supplement/tournament'
        for folder in sorted((prefix/sport).glob('*')):
            fp=folder/stat/'hybrid-forecasts.json.gz';mp=folder/stat/'hybrid-model.pickle'
            if not fp.exists() or not mp.exists():continue
            f=json.loads(gzip.decompress(fp.read_bytes()));m=pickle.loads(mp.read_bytes());rows=[indexed[(g,p)] for g,p in zip(f['gameIds'],f['playerIds']) if (g,p) in indexed];rows=[r for r in rows if r.get('y') is not None and r.get('opportunity') is not None and r['opportunity']>0]
            if not rows:continue
            z=m.design(rows);op=np.maximum(0,m.model.predict(z));eff=np.maximum(0,m.efficiency.predict(z));actualop=np.array([r['opportunity'] for r in rows]);actualeff=np.array([r['y']/r['opportunity'] for r in rows]);volume=(op-actualop)*(eff+actualeff)/2;rate=(eff-actualeff)*(op+actualop)/2;total=op*eff-np.array([r['y'] for r in rows]);assert np.max(abs(volume+rate-total))<1e-7;attr.append({'sport':sport,'stat':stat,'window':folder.name,'observations':len(rows),'meanSignedError':float(total.mean()),'opportunitySignedContribution':float(volume.mean()),'efficiencySignedContribution':float(rate.mean()),'meanAbsoluteOpportunityContribution':float(np.mean(abs(volume))),'meanAbsoluteEfficiencyContribution':float(np.mean(abs(rate))),'decompositionIdentityVerified':True,'interpretation':'Algebraic symmetric opportunity/rate decomposition, not causal attribution. NBA opportunity is minutes; pace/lineup/injury causes remain unidentified.'})
        del gs,rr,indexed;gc.collect()
    # Repeated windows are counted once; sealed games never enter selections.
    point_ids=defaultdict(set)
    for specfile in [OUT/'specs/tournament-r2.json',OUT/'supplement/specs/supplement-r2.json']:
        for s,ws in read(specfile)['selection'].items():
            for w in ws:point_ids[s].update(w['games'])
    summary={'version':24,'branch':'research/dynamic-v24','asOf':datetime.now(timezone.utc).isoformat(),'pointValidationGames':{s:len(ids) for s,ids in point_ids.items()},'sequentialValidationGames':{s:[w['validationGames'] for w in ws] for s,ws in event['leagues'].items()},'sequential':event['leagues'],'eventDecisions':dynamic_decisions,'leaderboard':leaderboard,'errorAttribution':attr,'strictPregameForecasts':0,'strictLiveReplayForecasts':0,'fullGameAccuracy':None,'marketThresholdsGraded':0,'jointModelPromotions':0,'productionPromotions':0,'medianCorrection':'Legacy experimental quantile files named the point array mean. The numbers are preserved; those arrays are conditional medians, not means. New snapshots explicitly record the estimand. Lower MAE alone is not better mean or probability accuracy.','blocks':['Publication-complete injuries/lineups/participation and source edition arrival times missing','CFB administrative/runoff and pace certificate incomplete','Forward NBA lineups after period boundaries remain incomplete; no future lineup smoothing used','No eligible 10,000-game full-game or strict-live cohort','No verified historical market thresholds/settlement rules acquired']};atomic(OUT/'analysis/summary.json',summary);target=ROOT/'docs/research';target.mkdir(exist_ok=True);atomic(target/'dynamic-v24-results.json',summary);return summary
if __name__=='__main__':r=run();print(json.dumps({'pointGames':r['pointValidationGames'],'pointCandidates':sum(h.get('pointResearchCandidate',False) for h in r['leaderboard']),'eventDecisions':r['eventDecisions']},indent=2))
