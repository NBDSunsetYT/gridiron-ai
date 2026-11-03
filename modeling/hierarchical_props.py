"""Chronological validation of partial-pooling player-stat CDFs.

The base measure is fitted to published prior-season role cohorts. Hyperparameters
are selected on later prior-season games; the current-season holdout is never used
for tuning. Source publication histories and executable historical market prices
are not claimed. No calibration or market superiority is asserted.
"""
from collections import defaultdict,Counter
import hashlib,json,math
import numpy as np
from scipy.stats import t,nbinom,poisson,norm

VERSION='hierarchical-player-cdf-12.1.0'
COUNTS={'passingAttempts','completions','interceptions','passingTouchdowns','carries','rushingTouchdowns','targets','receptions','receivingTouchdowns','touchdowns'}


def base_fit(values,stat):
    x=np.asarray(values,dtype=float)
    if len(x)<30 or not np.all(np.isfinite(x)):return None
    mean=float(x.mean());var=float(x.var(ddof=1))
    if var<=0:return None
    if stat in COUNTS:
        if np.any(x<0) or np.any(x!=np.floor(x)) or mean<=0:return None
        if var>mean:return {'family':'negative_binomial','size':mean*mean/(var-mean),'probability':mean/var}
        return {'family':'poisson','mean':mean}
    # Fit a Student-t rather than drop negative yardage or zero-usage games.
    df,loc,scale=t.fit(x)
    if not all(math.isfinite(v) for v in (df,loc,scale)) or df<=0 or scale<=0:return None
    if df>1e6:return {'family':'normal','location':float(loc),'scale':float(scale)}
    return {'family':'student_t','df':float(df),'location':float(loc),'scale':float(scale)}


def base_cdf(base,threshold,side='Under'):
    if base['family'] in ('student_t','normal'):
        boundary=math.ceil(threshold)-.5 if side=='Under' else math.floor(threshold)+.5
        d=t(base['df'],loc=base['location'],scale=base['scale']) if base['family']=='student_t' else norm(base['location'],base['scale']);return float(d.cdf(boundary)) if side=='Under' else float(d.sf(boundary))
    k=math.ceil(threshold)-1 if side=='Under' else math.floor(threshold)
    d=nbinom(base['size'],base['probability']) if base['family']=='negative_binomial' else poisson(base['mean'])
    return float(d.cdf(k)) if side=='Under' else float(d.sf(k))


_cache={}

def pool_candidate(records,stat,position,current_season):
    key=hashlib.sha256(json.dumps([VERSION,stat,position,current_season,[(r['player'],r['game'],r['value']) for r in records if r['stat']==stat and r['position']==position]],sort_keys=True).encode()).hexdigest()
    if key in _cache:return _cache[key]
    result=_pool_candidate(records,stat,position,current_season)
    if len(_cache)>=64:_cache.pop(next(iter(_cache)))
    _cache[key]=result
    return result

def _pool_candidate(records,stat,position,current_season):
    records=sorted([r for r in records if r['stat']==stat and r['position']==position],key=lambda r:(r['season'],r['week'],r['game'],r['player']))
    train=[r for r in records if r['season']<current_season and r['week']<=8]
    tuning=[r for r in records if r['season']<current_season and r['week']>8]
    test=[r for r in records if r['season']==current_season]
    base=base_fit([r['value'] for r in train],stat)
    if base is None:return {'approved':False,'reason':'A prior-season role cohort is unavailable or degenerate.'}
    thresholds=sorted(set(float(v) for v in np.quantile([r['value'] for r in train],[.2,.4,.6,.8])))
    # Half-integer count/yardage targets are fixed using training data alone.
    thresholds=sorted({math.floor(v)+.5 for v in thresholds})
    base_ps=np.array([base_cdf(base,k,'Over') for k in thresholds])
    sufficient_cache={}
    def sufficient(targets,window,starting):
        key=(id(targets),window,id(starting))
        if key in sufficient_cache:return sufficient_cache[key]
        histories=defaultdict(list)
        for r in starting:histories[r['player']].append(r['value'])
        counts=[];sizes=[];outcomes=[];events=[];sample=[]
        for r in targets:
            # All values used here strictly precede this player's held-out game.
            past=np.array(histories[r['player']][-window:],dtype=float)
            if len(past):
                hits=np.count_nonzero(past[:,None]>np.asarray(thresholds)[None,:],axis=0);n=len(past)
                counts.append(hits);sizes.append(n)
                outcomes.extend([int(r['value']>k) for k in thresholds]);events.extend([r['game']]*len(thresholds));sample.extend([n]*len(thresholds))
            histories[r['player']].append(r['value'])
        result=(np.asarray(counts,dtype=float).reshape(-1,len(thresholds)),np.asarray(sizes,dtype=float)[:,None],np.array(outcomes),events,sample)
        sufficient_cache[key]=result
        return result
    def evaluate(targets,strength,window,starting):
        hits,n,y,events,sample=sufficient(targets,window,starting)
        return ((hits+strength*base_ps)/(n+strength)).ravel(),((hits+.5)/(n+1)).ravel(),y,events,sample
    options=[]
    for strength in (.5,2.,8.,32.):
        for window in (4,8,16,24):
            p,b,y,_,_=evaluate(tuning,strength,window,train)
            if len(y)>=100:options.append((float(np.mean((p-y)**2)),strength,window))
    if not options:return {'approved':False,'reason':'Chronological tuning coverage is insufficient.'}
    _,strength,window=min(options);p,b,y,events,sample=evaluate(test,strength,window,train+tuning)
    if len(y)<100 or len(set(events))<8:return {'approved':False,'reason':'Independent current-season holdout coverage is insufficient.','testPredictions':len(y)}
    dif=(p-y)**2-(b-y)**2;grouped=defaultdict(list)
    for event,value in zip(events,dif):grouped[event].append(float(value))
    groups=list(grouped.values());rng=np.random.default_rng(12100)
    sums=np.array([sum(g) for g in groups]);sizes=np.array([len(g) for g in groups]);indices=rng.integers(0,len(groups),(5000,len(groups)))
    means=sums[indices].sum(axis=1)/sizes[indices].sum(axis=1)
    bootstrap_p=(1+int(np.sum(means>=0)))/(len(means)+1)
    interval=np.quantile(means,[.025,.975]).tolist();clip=lambda x:np.clip(x,1e-9,1-1e-9)
    loss=lambda x:float(-np.mean(y*np.log(clip(x))+(1-y)*np.log1p(-clip(x))))
    # Only a statistically supported holdout improvement permits publishing the
    # new distribution. This still does not make its probabilities calibrated.
    approved=interval[1]<0 and loss(p)<=loss(b)
    buckets=[]
    for lo in np.arange(0,1,.1):
        selected=(p>=lo)&(p<lo+.1);count=int(selected.sum())
        if count:buckets.append({'lower':float(lo),'count':count,'predicted':float(p[selected].mean()),'observed':float(y[selected].mean())})
    validation={'chronological':True,'trainingSeason':current_season-1,'tuningWeeks':'9–18 of prior season','testSeason':current_season,'testPredictions':len(y),'testGames':len(groups),'brierScore':float(np.mean((p-y)**2)),'benchmarkBrier':float(np.mean((b-y)**2)),'logLoss':loss(p),'benchmarkLogLoss':loss(b),'pairedGameBootstrapBrierDifference95':interval,'pairedGameBootstrapPValue':bootstrap_p,'calibration':buckets,'calibrated':False,'limitedSampleTestPredictions':sum(n<5 for n in sample),'scope':'Retrospective fixed-threshold player-stat validation; not historical market, first-publication or prospective contract validation.'}
    calibrator=None
    if approved:
        from sklearn.linear_model import LogisticRegression
        tp,tb,ty,te,ts=evaluate(tuning,strength,window,train)
        if len(ty)>=200 and len(set(ty))==2:
            logit=lambda q:np.log(clip(q)/(1-clip(q)))
            x=logit(tp).reshape(-1,1);fit=LogisticRegression(C=1.,solver='lbfgs',max_iter=1000).fit(x,ty)
            intercept=float(fit.intercept_[0]);slope=float(fit.coef_[0,0]);cp=fit.predict_proba(logit(p).reshape(-1,1))[:,1]
            delta=(cp-y)**2-(p-y)**2;score_groups=defaultdict(list)
            for event,value in zip(events,delta):score_groups[event].append(float(value))
            cg=list(score_groups.values());cs=np.array([sum(g) for g in cg]);cn=np.array([len(g) for g in cg]);cm=cs[indices].sum(axis=1)/cn[indices].sum(axis=1)
            cal_p=(1+int(np.sum(cm>=0)))/(len(cm)+1);cal_ci=np.quantile(cm,[.025,.975]).tolist()
            if slope>0 and cal_ci[1]<0 and loss(cp)<=loss(p):
                design=np.column_stack([np.ones(len(tp)),logit(tp)]);fitted=fit.predict_proba(x)[:,1];weights=fitted*(1-fitted)
                bread=np.linalg.pinv(design.T@(design*weights[:,None])+np.diag([0.,1.]))
                scores=defaultdict(lambda:np.zeros(2))
                for event,d,residual in zip(te,design,ty-fitted):scores[event]+=d*residual
                meat=sum(np.outer(v,v) for v in scores.values())
                if len(scores)>1:meat*=len(scores)/(len(scores)-1)*(len(tp)-1)/(len(tp)-2)
                covariance=bread@meat@bread
                calibrator={'method':'regularized_platt','intercept':intercept,'slope':slope,'covariance':covariance.tolist(),'minimumProbability':float(tp.min()),'maximumProbability':float(tp.max()),'validation':{'chronological':True,'fitSeason':current_season-1,'testSeason':current_season,'testPredictions':len(y),'testGames':len(groups),'brierScore':float(np.mean((cp-y)**2)),'rawBrierScore':float(np.mean((p-y)**2)),'logLoss':loss(cp),'rawLogLoss':loss(p),'pairedGameBootstrapBrierDifference95':cal_ci,'pairedGameBootstrapPValue':cal_p,'scope':'Retrospective conditional player-stat recalibration; not prospective market accuracy.'}}
    return {'approved':bool(approved),'reason':'Supported chronological holdout improvement.' if approved else 'Holdout improvement over the empirical benchmark was not established.','base':base,'strength':strength,'window':window,'validation':validation,'calibrator':calibrator,'version':VERSION,'artifactId':hashlib.sha256(json.dumps([VERSION,stat,position,current_season,base,strength,window,validation],sort_keys=True).encode()).hexdigest()}


def attach_models(players,catalog,records,season,sport='NFL'):
    positions={p['id']:p.get('position') for p in catalog};artifacts={}
    for pid,stats in players.items():
        for stat,distribution in stats.items():
            pos=positions.get(pid) if sport=='NFL' else 'CFB_'+('PASSING' if stat in ('passingYards','passingAttempts','completions','interceptions','passingTouchdowns') else 'RECEIVING' if stat in ('receivingYards','receptions','receivingTouchdowns','targets') else 'RUSHING')
            if not pos or sport=='NFL' and pos not in ('QB','RB','WR','TE'):continue
            key=stat+':'+pos
            if key not in artifacts:artifacts[key]=pool_candidate(records,stat,pos,season)
            artifact=artifacts[key]
            # Fixed predeclared sport families prevent choosing favorable
            # subgroups after looking at the held-out results.
            if artifact.get('validation'):
                family=52 if sport=='NFL' else 13
                artifact['validation'].update(familywiseAlpha=.025,familywiseMethod='Bonferroni over predeclared sport/stat/role families',familySize=family,familywiseAdjustedPValue=min(1.,artifact['validation']['pairedGameBootstrapPValue']*family))
                artifact['approved']=bool(artifact['approved'] and artifact['validation']['familywiseAdjustedPValue']<=.025)
                artifact['artifactId']=hashlib.sha256(json.dumps([VERSION,stat,pos,season,artifact['base'],artifact['strength'],artifact['window'],artifact['validation'],artifact.get('calibrator')],sort_keys=True).encode()).hexdigest()
                if artifact.get('calibrator'):
                    cal=artifact['calibrator'];cal['validation'].update(familySize=family,familywiseAlpha=.025,familywiseAdjustedPValue=min(1.,cal['validation']['pairedGameBootstrapPValue']*family))
                    if cal['validation']['familywiseAdjustedPValue']>.025:artifact['calibrator']=None
                if not artifact['approved']:artifact['reason']='Chronological improvement did not pass the conservative familywise publication gate.'
            if artifact.get('approved'):
                # The deployment computes exact arbitrary thresholds from these
                # actual observation counts and the validated parametric base CDF.
                selected=sorted([r for r in records if r['player']==pid and r['stat']==stat],key=lambda r:(r['season'],r['week'],r['game']))[-artifact['window']:]
                if not selected:continue
                bins=Counter(r['value'] for r in selected);distribution.update(histogram=[{'value':v,'count':n} for v,n in sorted(bins.items())],sampleSize=len(selected),historicalGameIds=[r['game'] for r in selected])
                distribution['hierarchical']={**{k:artifact[k] for k in ('base','strength','window','validation','version','artifactId','calibrator')},'sport':sport,'statistic':stat,'position':pos}
    return artifacts
