"""Expected value, median and probability champions are different decisions."""
from pathlib import Path
import numpy as np
from ..stat_models import metrics
from ...overnight_v20.state import atomic,digest,read

def evaluate(rows,point,draws,thresholds):
    result=metrics(rows,point,draws);y=np.array([r['y'] for r in rows]);draws=np.asarray(draws);n=draws.shape[1]
    cover={}
    for level in (.5,.8,.9,.95):
        lo,hi=np.quantile(draws,[(1-level)/2,(1+level)/2],axis=1);cover[str(level)]=float(np.mean((y>=lo)&(y<=hi)))
    if thresholds:
        # Jeffreys smoothing only stabilizes finite empirical CDF estimates; it
        # is NOT an independently validated probability calibrator.
        p=np.stack([(np.sum(draws<=line,axis=1)+.5)/(n+1) for line in thresholds],axis=1);truth=np.stack([y<=line for line in thresholds],axis=1).astype(float)
        brier=np.mean((p-truth)**2);logloss=np.mean(-truth*np.log(p)-(1-truth)*np.log1p(-p));flat=p.ravel();obs=truth.ravel();bins=np.minimum(9,(flat*10).astype(int));ece=sum(np.mean(bins==b)*abs(float(np.mean(flat[bins==b])-np.mean(obs[bins==b]))) for b in range(10) if np.any(bins==b))
    else:brier=logloss=ece=None
    result=result|{'coverage':cover,'cdfBrier':None if brier is None else float(brier),'cdfLogLoss':None if logloss is None else float(logloss),'cdfECE':ece,'thresholds':list(thresholds),'calibrationScope':'Training-quantile CDF diagnostics, not verified market lines','probabilityCalibrator':None}
    if rows[0]['stat'] in ('moneyline','doubleDouble','tripleDouble'):
        p=np.clip(point,1e-8,1-1e-8);result['brier']=float(np.mean((p-y)**2));result['logLoss']=float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p)));result['crps']=result['brier'];result['cdfBrier']=result['brier'];result['cdfLogLoss']=result['logLoss'];result['calibrationScope']='Raw Bernoulli probability, no approved calibrator; ties ungraded'
    return result

def paired_loss(rows,before,after,*,loss='absolute',alpha=.05/159,seed=240241,bootstraps=20000):
    ids=sorted({r['gameId'] for r in rows});y=np.array([r['y'] for r in rows]);a=np.asarray(before);b=np.asarray(after)
    if loss=='absolute':delta=np.abs(b-y)-np.abs(a-y)
    elif loss=='squared':delta=(b-y)**2-(a-y)**2
    elif loss=='provided':delta=b-a
    else:raise ValueError('Unknown loss')
    d=np.array([np.mean(delta[[i for i,r in enumerate(rows) if r['gameId']==g]]) for g in ids]);rng=np.random.default_rng(seed)
    means=np.mean(d[rng.integers(0,len(d),size=(bootstraps,len(d)))],axis=1)
    return {'games':len(ids),'meanGameLossDelta':float(np.mean(d)),'CI95':np.quantile(means,[.025,.975]).tolist(),'adjustedCI':np.quantile(means,[alpha/2,1-alpha/2]).tolist(),'alpha':alpha,'bootstrapReplicates':bootstraps,'cluster':'game','loss':loss,'negativeFavorsCandidate':True}

def choose(inner,estimands,purpose):
    if purpose not in ('expected_value','median','distribution'):raise ValueError('Explicit objective required')
    eligible=[f for f in inner if purpose!='expected_value' or estimands[f]=='conditional_mean']
    if purpose=='distribution':eligible=[f for f in eligible if estimands[f]!='conditional_median']
    if not eligible:raise ValueError('No appropriate model for objective')
    metric={'expected_value':'rmse','median':'mae','distribution':'crps'}[purpose]
    return min(eligible,key=lambda f:(inner[f][metric],f))

def decision(windows,purpose,*,strict=False,production_reference=False):
    reasons=[]
    if len(windows)<2 or any(w.get('games',0)<30 for w in windows):reasons.append('insufficient_independent_windows')
    if any(w.get('paired',{}).get('adjustedCI',[0,1])[1]>=0 for w in windows):reasons.append('paired_improvement_not_established_in_every_window')
    if purpose=='distribution':
        if any(w['candidate']['cdfBrier']>w['reference']['cdfBrier']+.005 or w['candidate']['cdfLogLoss']>w['reference']['cdfLogLoss']+.01 for w in windows):reasons.append('probability_regression')
        if any(w['candidate']['coverage']['0.9']<w['reference']['coverage']['0.9']-.03 for w in windows):reasons.append('interval_coverage_regression')
    if any(w.get('criticalQualityFailure') for w in windows):reasons.append('critical_quality_failure')
    if any(w.get('converged') is False for w in windows):reasons.append('unconverged_fit')
    if purpose=='expected_value' and any(w.get('productionSourceReference',{}).get('paired',{}).get('adjustedCI',[-1,-1])[1]>=0 for w in windows):reasons.append('improvement_against_production_source_replay_not_established')
    established=not reasons
    return {'conditionalImprovementEstablished':established,'reasons':reasons,'strictPregameEvidence':strict,'productionReferenceCompared':production_reference,'jointReplacementAllowed':False,'productionPromotionEligible':False,'status':'conditional_candidate' if established else 'retain_reference','promotionBlockers':([] if strict else ['point_in_time_injury_lineup_and_publication_missing'])+([] if production_reference else ['production_reference_not_available'])+['model_bound_joint_validation_required']}

def joint_probability_gate(model,match,certificate):
    from ...integration_v22.datasets import protected
    from ...accuracy_v20.quality import aware
    probability=certificate.get('jointProbabilityValidation',{});windows=probability.get('windows',[])
    if probability.get('modelHash')!=model.get('sha256') or len(windows)<2:raise ValueError('Independent model-bound joint probability validation required')
    seen=set();banned=protected()
    for window in windows:
        ids=window.get('gameIds',[])
        if len(set(ids))<30 or seen.intersection(ids) or set(ids)&banned:raise ValueError('Two independent, unprotected joint-probability game windows required')
        seen.update(ids)
        if not window.get('end') or aware(window['end'])>=aware(match['cutoff']):raise ValueError('Future validation cannot qualify a historical forecast')
        if window.get('brierDeltaCI95',[0,1])[1]>.005 or window.get('logLossDeltaCI95',[0,1])[1]>.01 or window.get('coverage90Regression',1)>.03 or window.get('calibrationAccepted') is not True:raise ValueError('Joint probability calibration/coverage regression guard failed')

class Registry:
    """Content-addressed immutable records, with independent objective slots.

    Conditional point wins cannot modify probability or production champions.
    """
    REQUIRED={'sport','stat','family','modelVersion','trainingCutoff','sourceVersions','sampleSize','metrics','uncertainty','purpose','estimand','decision','modelSHA256'}
    def __init__(self,path):self.path=Path(path)
    def register(self,record):
        if self.REQUIRED-set(record):raise ValueError('Incomplete research model manifest')
        from ...accuracy_v20.quality import aware
        cutoffs=record['trainingCutoff'] if isinstance(record['trainingCutoff'],list) else [record['trainingCutoff']]
        if not cutoffs:raise ValueError('Training cutoff required')
        for cutoff in cutoffs:aware(cutoff)
        if record['purpose']=='expected_value' and record['estimand']!='conditional_mean':raise ValueError('A median cannot become an expected-value head')
        if record.get('productionPromotion') is not False or record['decision'].get('productionPromotionEligible'):raise ValueError('Research cannot promote production')
        if not record['sourceVersions'] or record['sampleSize'].get('games',0)<1:raise ValueError('Versioned independent evidence required')
        reviewed=decision(record['metrics'],record['purpose'],strict=record['decision']['strictPregameEvidence'],production_reference=record['decision']['productionReferenceCompared'])
        if reviewed!=record['decision']:raise ValueError('Registry decision does not match independently checked validation metrics')
        entry={**record,'id':digest(record)};s=read(self.path,{'versions':[],'researchChampions':{}})
        if any(r['id']==entry['id'] for r in s['versions']):return entry['id']
        s['versions'].append(entry)
        if entry['decision']['conditionalImprovementEstablished']:s['researchChampions'][':'.join([entry['sport'],entry['stat'],entry['purpose']])]=entry['id']
        atomic(self.path,s);return entry['id']
    def joint_heads(self,sport,*,model=None,match=None,ctx=None,evidence=None,certificate=None):
        # A compound model hash binds the chosen heads to the exact mechanics
        # certificate and point-in-time input evidence. Marginal MAE is not a
        # substitute for any of those checks.
        if any(v is None for v in (model,match,ctx,evidence,certificate)):raise ValueError('Point-in-time evidence and model-bound joint certificate required')
        from ...fullgame_v23.forecast import require
        require(model,match,ctx,evidence,certificate)
        joint_probability_gate(model,match,certificate)
        versions={r['id']:r for r in read(self.path,{'versions':[]})['versions']};ids=model.get('specializedHeadIds',[])
        if not ids or len(set(ids))!=len(ids):raise ValueError('Explicit unique specialized head versions required')
        result={}
        for key in ids:
            r=versions.get(key)
            if not r or r['sport']!=sport or r['purpose']!='expected_value' or r['estimand']!='conditional_mean' or not r['decision']['conditionalImprovementEstablished'] or not r['decision']['strictPregameEvidence']:raise ValueError('Specialized head lacks appropriate independent pregame validation')
            from ...accuracy_v20.quality import aware
            cutoffs=r['trainingCutoff'] if isinstance(r['trainingCutoff'],list) else [r['trainingCutoff']]
            if any(aware(c)>=aware(match['cutoff']) for c in cutoffs):raise ValueError('Specialized training must precede forecast cutoff')
            if not r.get('validationWindows') or any(aware(w['end'])>=aware(match['cutoff']) for w in r['validationWindows']):raise ValueError('Specialized validation must be complete before forecast cutoff')
            if r['stat'] in result:raise ValueError('One expected-value model per statistic')
            result[r['stat']]=r
        return result
