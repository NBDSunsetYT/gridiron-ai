"""Conservative chronological gate for player-stat distribution candidates.

No candidate becomes a production model by being fitted. Callers must persist a
reviewed artifact with sport/market/training cutoff and independent validation.
This module does not overwrite deployed models or pretend small cohorts suffice.
"""
import math
import numpy as np
from scipy.stats import poisson,nbinom,lognorm


def probability(values,threshold,direction,method):
    x=np.asarray(values,dtype=float)
    if len(x)<10 or not np.all(np.isfinite(x)):raise ValueError('At least ten finite prior observations required')
    if method=='empirical':p=(sum(x>threshold)+.5)/(len(x)+1) if direction=='over' else (sum(x<threshold)+.5)/(len(x)+1)
    elif method in ('poisson','negative_binomial'):
        if np.any(x<0) or np.any(x!=np.floor(x)):raise ValueError('Count candidates require nonnegative integer outcomes')
        mean=float(x.mean());variance=float(x.var(ddof=1))
        if mean<=0:raise ValueError('A nondegenerate count cohort is required')
        if method=='negative_binomial':
            if variance<=mean:raise ValueError('Negative binomial needs supported overdispersion')
            size=mean*mean/(variance-mean);distribution=nbinom(size,size/(size+mean))
        else:distribution=poisson(mean)
        p=float(distribution.sf(math.floor(threshold))) if direction=='over' else float(distribution.cdf(math.ceil(threshold)-1))
    elif method=='lognormal':
        if np.any(x<=0):raise ValueError('Strictly positive observed yardage is required; zeros/negative yards cannot be dropped')
        logs=np.log(x);sigma=float(logs.std(ddof=1))
        if sigma<=0:raise ValueError('A nondegenerate positive yardage cohort is required')
        d=lognorm(sigma,scale=math.exp(float(logs.mean())))
        p=float(d.sf(threshold)) if direction=='over' else float(d.cdf(threshold))
    else:raise ValueError('Unsupported candidate distribution')
    return min(1-1e-9,max(1e-9,float(p)))


def validate_candidate(ordered_values,threshold,direction,method,minimum_test=100):
    """Expanding chronological backtest at a predeclared threshold, no shuffle.

    Block bootstrap preserves short serial dependence. This diagnostic alone is
    not prospective contract validation when historical publication is unknown.
    """
    if direction not in ('over','under') or not math.isfinite(threshold):raise ValueError('An exact predeclared threshold/direction is required')
    values=[float(v) for v in ordered_values]
    if len(values)<20+minimum_test:return {'approved':False,'status':'insufficient_chronological_sample','testPredictions':max(0,len(values)-20)}
    predictions=[];baseline=[];outcomes=[]
    try:
        for i in range(20,len(values)):
            predictions.append(probability(values[:i],threshold,direction,method));baseline.append(probability(values[:i],threshold,direction,'empirical'))
            outcomes.append(int(values[i]>threshold if direction=='over' else values[i]<threshold))
    except ValueError as error:return {'approved':False,'status':'unsupported_distribution','reason':str(error)}
    p,b,y=map(np.asarray,(predictions,baseline,outcomes));differences=(p-y)**2-(b-y)**2
    rng=np.random.default_rng(12000);blocks=[differences[i:i+5] for i in range(0,len(y),5)];means=[]
    for _ in range(1000):means.append(float(np.concatenate([blocks[i] for i in rng.integers(0,len(blocks),len(blocks))]).mean()))
    ci=[float(v) for v in np.quantile(means,[.025,.975])]
    loss=lambda q:float(-np.mean(y*np.log(q)+(1-y)*np.log1p(-q)))
    improved=ci[1]<0 and loss(p)<loss(b)
    return {'approved':False,'candidateImproved':bool(improved),'status':'requires_independent_prospective_validation',
            'testPredictions':len(y),'chronological':True,'brierScore':float(np.mean((p-y)**2)),
            'baselineBrier':float(np.mean((b-y)**2)),'logLoss':loss(p),'baselineLogLoss':loss(b),
            'pairedBlockBootstrapBrierDifference95':ci,'method':method,
            'reason':'This retrospective diagnostic does not establish historical source/contract availability. No automatic production promotion.'}
