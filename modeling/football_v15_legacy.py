"""Original possession/state football candidate, separately fitted per league.

Regularized play choice and dropback models, player/defense outcome regression,
empirical residuals and snap-to-snap clocks. Current participants are allocated
BEFORE outcomes; an old quarterback is never returned by a historical play.
No market input enters training. Production eligibility is deliberately false
until independent full-game validation and current-lineup checks pass.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from scipy.sparse import csr_matrix, hstack

from .fit import utc
from .simulator import histogram_summary, wilson, STATS

VERSION='football-possession-hurdle-candidate-15.1.0'
KINDS=('pass','rush','punt','field_goal','kneel','penalty')
NUMERIC=13


def numeric(down, distance, field, clock, diff, home):
    down,distance,field,clock,diff,home=np.broadcast_arrays(down,distance,field,clock,diff,home)
    half=np.where(clock>1800,clock-1800,clock)
    return np.stack([*(down==i for i in (1,2,3,4)),distance/10,field/100,
        half/1800,np.clip(diff,-42,42)/21,(diff<0)*(half<=120),
        (diff>0)*(half<=120),field<=20,home,clock/3600],axis=-1).astype(float)


def fit_component(rows, labels, teams, participants=None, regression=False,field_transform=None):
    x=numeric(*[np.array([r[k] for r in rows]) for k in ('down','distance','field','clock','script','home')])
    if field_transform=='log':x[:,5]=np.log1p(100*x[:,5])/np.log(101)
    ti={t:i for i,t in enumerate(teams)};pi={p:i for i,p in enumerate(sorted(set(participants or [])))}
    ids=[];cols=[]
    for i,r in enumerate(rows):
        ids.extend((i,i));cols.extend((ti[r['o']],len(teams)+ti[r['d']]))
        if participants is not None and participants[i]:ids.append(i);cols.append(2*len(teams)+pi[participants[i]])
    one=csr_matrix((np.ones(len(ids)),(ids,cols)),shape=(len(rows),2*len(teams)+len(pi)))
    design=hstack((csr_matrix(x),one),format='csr')
    if regression:
        fitted=Ridge(alpha=100.,solver='lsqr').fit(design,labels)
        coeff=np.atleast_2d(fitted.coef_);inter=np.atleast_1d(fitted.intercept_);classes=None
    else:
        fitted=LogisticRegression(C=1.,max_iter=400,solver='lbfgs').fit(design,labels)
        coeff=fitted.coef_;inter=fitted.intercept_;classes=[int(v) for v in fitted.classes_]
        if len(classes)==2:
            coeff=np.vstack((np.zeros(coeff.shape[1]),coeff[0]));inter=np.array([0.,inter[0]])
    artifact={'coefficients':coeff.tolist(),'intercepts':inter.tolist(),'classes':classes,'teams':teams,
              'participants':list(pi),'trainingRows':len(rows),'regularization':100. if regression else 1.,'fieldTransform':field_transform}
    if regression:
        residual=np.asarray(labels)-np.asarray(fitted.predict(design))
        artifact['residuals']={str(z):residual[np.array([min(2,r['field']//20) for r in rows])==z].tolist() for z in range(3)}
        artifact['allResiduals']=residual.tolist()
    return artifact


def fit_football(rows, sport, cutoff, source_version):
    cutoff=utc(cutoff)
    if sport not in ('NFL','CFB') or not rows or any(r['sport']!=sport or utc(r['at'])>=cutoff for r in rows):
        raise ValueError('Separate league evidence strictly before the fitting cutoff is required')
    plays=[r for r in rows if r['kind'] in KINDS or r['kind']=='sack']
    if len(plays)<1000 or len({r['game'] for r in plays})<12:
        raise ValueError('At least twelve real games and 1,000 supported plays required')
    teams=sorted({r[k] for r in plays for k in ('o','d')})
    choice=[KINDS.index('pass' if r['kind']=='sack' else r['kind']) for r in plays]
    drops=[r for r in plays if r['kind'] in ('pass','sack')]
    outcome=[0 if r['kind']=='sack' else 1 if r['int'] else 3 if r['complete'] else 2 for r in drops]
    passing=[r for r in drops if r['kind']=='pass' and r['complete']]
    rushing=[r for r in plays if r['kind']=='rush']
    pass_td=[int(r['yards']>=r['field'] and not r['fumble']) for r in passing]
    rush_td=[int(r['yards']>=r['field'] and not r['fumble']) for r in rushing]
    pass_non_td=[r for r,td in zip(passing,pass_td) if not td]
    rush_non_td=[r for r,td in zip(rushing,rush_td) if not td]
    if min(len(passing),len(rushing))<200 or len(set(outcome))<4:
        raise ValueError('Completion/run/sack/interception evidence is incomplete')
    fg=[r for r in plays if r['kind']=='field_goal'];conversions={}
    for kind in ('extra_point','two_point'):
        rs=[r for r in rows if r['kind']==kind]
        if len(rs)<3 or len({r['made'] for r in rs})<2:
            raise ValueError('Actual league conversion successes and failures required')
        conversions[kind]={'made':sum(r['made'] for r in rs),'n':len(rs)}
    histories={}
    for r in plays:
        g=histories.setdefault(r['o'],{}).setdefault(r['game'],{'at':r['at'],'qb':Counter(),'receiver':Counter(),'runner':Counter()})
        g['at']=max(g['at'],r['at'])
        for role,condition in [('qb',r['kind'] in ('pass','sack')),('receiver',r['kind']=='pass'),('runner',r['kind'] in ('rush','kneel'))]:
            if condition and r.get(role):g[role][r[role]]+=1
    histories={t:{g:{k:dict(v) if isinstance(v,Counter) else v for k,v in h.items()} for g,h in hs.items()} for t,hs in histories.items()}
    clock={kind:[r['elapsed'] for r in plays if r['kind']==kind] for kind in (*KINDS,'sack')}
    starts=defaultdict(list);seen=set()
    for r in plays:
        key=(r['game'],r['o'],r.get('drive'))
        if key not in seen:starts[r['o']].append(r['field']);seen.add(key)
    evidence_cutoff=max(utc(r['at']) for r in rows)+timedelta(microseconds=1)
    model={'version':VERSION,'sport':sport,'asOf':evidence_cutoff.isoformat(),'fittingCutoff':cutoff.isoformat(),'sourceVersion':source_version,
        'publicationAvailabilityVerified':False,'productionEligible':False,'trainingGames':len({r['game'] for r in plays}),
        'trainingPlays':len(plays),'trainingGameIds':sorted({r['game'] for r in plays}),'teams':teams,
        'play':fit_component(plays,choice,teams),
        'dropback':fit_component(drops,outcome,teams,[r['qb'] for r in drops]),
        'passYards':fit_component(pass_non_td,[r['yards'] for r in pass_non_td],teams,[r['receiver'] for r in pass_non_td],True),
        'rushYards':fit_component(rush_non_td,[r['yards'] for r in rush_non_td],teams,[r['runner'] for r in rush_non_td],True),
        'passTouchdown':fit_component(passing,pass_td,teams,[r['receiver'] for r in passing],field_transform='log'),
        'rushTouchdown':fit_component(rushing,rush_td,teams,[r['runner'] for r in rushing],field_transform='log'),
        'clock':clock,'conversion':conversions,'histories':histories,'starts':dict(starts),
        'sackYards':[r['yards'] for r in drops if r['kind']=='sack' and r['yards']<0],
        'puntNet':[r['puntNet'] for r in plays if r['kind']=='punt' and 0<r['puntNet']<100],
        'fumble':{'n':len(passing)+len(rushing),'lost':sum(r['fumble'] for r in passing+rushing)},
        'penalties':[{'yards':r['yards'],'first':r['firstDownPenalty']} for r in plays if r['kind']=='penalty'],
        'fg':{'fields':[r['field'] for r in fg],'made':[r['made'] for r in fg]},
        'observedGamePlays':dict(Counter(r['game'] for r in plays)),
        'method':'Fixed regularized state/identity classifiers; explicit field-conditioned touchdown hurdle, non-touchdown ridge means plus empirical residuals; pregame participant allocation; independent leagues.'}
    if not model['sackYards'] or not model['puntNet'] or not fg:
        raise ValueError('Observed sacks, punts and field goals required')
    model['sha256']=hashlib.sha256(json.dumps(model,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return model


class Predictor:
    def __init__(self,a):
        self.a=a;self.co=np.asarray(a['coefficients']);self.inter=np.asarray(a['intercepts']);self.ti={t:i for i,t in enumerate(a['teams'])};self.pi={p:i for i,p in enumerate(a['participants'])}
    def predict(self,x,off,defense,participant=None):
        if self.a.get('fieldTransform')=='log':x=x.copy();x[:,5]=np.log1p(x[:,5]*100)/np.log(101)
        result=x@self.co[:,:NUMERIC].T+self.inter
        for values,offset in [(off,NUMERIC),(defense,NUMERIC+len(self.ti))]:
            ii=np.array([self.ti.get(v,-1) for v in values]);ok=ii>=0
            result[ok]+=self.co[:,offset+ii[ok]].T
        if participant is not None:
            ii=np.array([self.pi.get(v,-1) for v in participant]);ok=ii>=0
            result[ok]+=self.co[:,NUMERIC+2*len(self.ti)+ii[ok]].T
        return result
    def probabilities(self,x,off,defense,participant=None):
        logits=self.predict(x,off,defense,participant);p=np.exp(logits-logits.max(axis=1)[:,None]);return p/p.sum(axis=1)[:,None]
    def bind(self,teams,players):
        """Exact algebraic factoring of fixed identity terms (no model change)."""
        self.team_bias=np.stack([self.inter+self.co[:,NUMERIC+self.ti[t]]+self.co[:,NUMERIC+len(self.ti)+self.ti[teams[1-side]]] for side,t in enumerate(teams)])
        self.player_bias=np.zeros((len(players),self.co.shape[0]))
        for i,p in enumerate(players):
            if p in self.pi:self.player_bias[i]=self.co[:,NUMERIC+2*len(self.ti)+self.pi[p]]
    def fast(self,x,side,participant=None,probabilities=False):
        if self.a.get('fieldTransform')=='log':x=x.copy();x[:,5]=np.log1p(x[:,5]*100)/np.log(101)
        value=x@self.co[:,:NUMERIC].T+self.team_bias[side]
        if participant is not None:value+=self.player_bias[participant]
        if probabilities:
            value=np.exp(value-value.max(axis=1)[:,None]);value/=value.sum(axis=1)[:,None]
        return value


def participant_roles(model,team,lineup,event_start):
    history=model['histories'].get(team,{})
    if len(history)<3:raise ValueError('Three prior team games required for participant allocation')
    latest=sorted(history.values(),key=lambda h:h['at'])[-3:]
    current=lineup or {};verified=bool(current.get('verified'))
    if verified and (not current.get('source') or not str(current['source']).startswith('https://') or not current.get('availableAt') or utc(current['availableAt'])>=utc(event_start)):
        raise ValueError('Verified lineup requires a source and availability timestamp before kickoff')
    unavailable=set(current.get('inactive',[]))
    qbs=Counter();receivers=Counter();runners=Counter()
    for h in latest:qbs.update(h['qb']);receivers.update(h['receiver']);runners.update(h['runner'])
    # Starter inference is an EXPLICIT uncertainty, not verified availability.
    last_qb=Counter(latest[-1]['qb']);qb=current.get('quarterback') or (last_qb.most_common(1)[0][0] if last_qb else None)
    if not qb or qb in unavailable:raise ValueError('A supported available starting quarterback must be identified')
    if qb not in qbs and not verified:raise ValueError('Unverified quarterback has no prior participation evidence')
    for p in unavailable:receivers.pop(p,None);runners.pop(p,None)
    for p in qbs:
        if p!=qb:runners.pop(p,None)
    if not receivers or not runners:raise ValueError('Supported active receiver and rushing opportunity pools required')
    return {'quarterback':qb,'receivers':dict(receivers),'runners':dict(runners),'verified':verified,
        'injuriesComplete':bool(current.get('injuriesComplete')),'source':current.get('source'),
        'availableAt':current.get('availableAt'),'inactive':sorted(unavailable),
        'priorQuarterbackDropbacks':qbs[qb],
        'assumption':'Observed recent opportunity shares conditional on listed unavailable players; redistribution is a structural scenario, not a validated causal injury effect.'}


def _sample(rng,p):
    return (rng.random(len(p))[:,None]>np.cumsum(p,axis=1)).sum(axis=1).clip(max=p.shape[1]-1)


def _hist(v):
    values,counts=np.unique(v,return_counts=True)
    return Counter({int(x):int(n) for x,n in zip(values,counts)})


def simulate_football(model,home,away,event_start,simulations=10000,seed=15001,lineups=None,batch_size=1000,contracts=None,representative_games=1):
    if model.get('version')!=VERSION or home==away or not all(t in model['teams'] for t in (home,away)):
        raise ValueError('Exact fitted league and two distinct supported teams required')
    if utc(event_start)<=utc(model['asOf']):raise ValueError('Kickoff must follow every training observation')
    if isinstance(simulations,bool) or not isinstance(simulations,int) or not 1000<=simulations<=100000:
        raise ValueError('Choose 1,000–100,000 complete games')
    if not isinstance(seed,int) or isinstance(seed,bool) or not 0<=seed<2**53:raise ValueError('A reproducible nonnegative seed is required')
    if batch_size<1 or batch_size>2000:raise ValueError('Batch bound must be 1..2000')
    teams=[home,away];roles=[participant_roles(model,t,(lineups or {}).get(t),event_start) for t in teams]
    ids=sorted(set(p for r in roles for p in [r['quarterback'],*r['receivers'],*r['runners']]))
    if len(ids)>100:raise ValueError('Current skill roster exceeds bounded model capacity')
    idx={p:i for i,p in enumerate(ids)};stats=list(STATS);si={s:i for i,s in enumerate(stats)}
    pred={k:Predictor(model[k]) for k in ('play','dropback','passYards','rushYards','passTouchdown','rushTouchdown')}
    for predictor in pred.values():predictor.bind(teams,ids)
    qbi=np.asarray([idx[r['quarterback']] for r in roles])
    opportunities={}
    for side in (0,1):
        for role in ('receivers','runners'):
            c=roles[side][role];w=np.asarray(list(c.values()),float);opportunities[(side,role)]=(np.asarray([idx[p] for p in c]),w/w.sum())
    rng=np.random.default_rng(seed);hist=[Counter(),Counter()];total_hist=Counter();margin_hist=Counter();ph={p:{s:Counter() for s in stats} for p in ids};trace=[];env=Counter();wins=0;ties=0;convergence=[]
    arrays={k:np.asarray(v,dtype=int) for k,v in model['clock'].items() if v}
    residuals={name:{str(z):np.asarray(model[name]['residuals'][str(z)] or model[name]['allResiduals']) for z in range(3)} for name in ['passYards','rushYards']}
    sack_yards=np.asarray(model['sackYards']);punt_net=np.asarray(model['puntNet'])
    fgp=np.asarray(model['fg']['fields']);fgm=np.asarray(model['fg']['made'])
    for offset in range(0,simulations,batch_size):
        n=min(batch_size,simulations-offset);scores=np.zeros((n,2),dtype=np.int32);ps=np.zeros((n,len(ids),len(stats)),dtype=np.int32)
        clock=np.full(n,3600);off=rng.integers(0,2,n);first=off.copy();down=np.ones(n,dtype=int);distance=np.full(n,10);field=np.full(n,75);plays=np.zeros(n,dtype=int);drives=np.ones(n,dtype=int);done=np.zeros(n,dtype=bool)
        for side in (0,1):
            mask=off==side;field[mask]=rng.choice(model['starts'][teams[side]],mask.sum());distance[mask]=np.minimum(10,field[mask])
        def add(mask,participants,name,values=1):
            loc=np.flatnonzero(mask)
            if len(loc):
                who=participants[mask]
                np.add.at(ps,(loc,who,np.full(len(loc),si[name])),np.broadcast_to(values,(n,))[mask])
        def reset(mask):
            for side in (0,1):
                m=mask&(off==side)
                if m.any():field[m]=rng.choice(model['starts'][teams[side]],m.sum())
            down[mask]=1;distance[mask]=np.minimum(10,field[mask]);drives[mask]+=1
        iterations=0
        while not done.all():
            iterations+=1
            if iterations>800:raise ValueError('Game clock/transition quality gate failed: more than 800 plays')
            active=~done;oi=off.copy();di=1-oi;ix=np.arange(n);diff=scores[ix,oi]-scores[ix,di]
            x=numeric(down,distance,field,clock,diff,oi==0)
            probs=pred['play'].fast(x,oi,probabilities=True);classes=model['play']['classes']
            half=np.where(clock>1800,clock-1800,clock)
            for col,kind in enumerate(classes):
                if KINDS[kind]=='punt':probs[:,col]*=down==4
                if KINDS[kind]=='field_goal':probs[:,col]*=((down==4)|(half<=10))&(field<=int(fgp.max()))
                if KINDS[kind]=='kneel':probs[:,col]*=(half<=120)&(diff>=0)
            probs/=probs.sum(axis=1)[:,None];kind=np.asarray(classes)[_sample(rng,probs)]
            qb=qbi[oi];receiver=np.empty(n,dtype=int);runner=np.empty(n,dtype=int)
            for side in (0,1):
                m=oi==side
                for key,target in [('receivers',receiver),('runners',runner)]:
                    choices,weights=opportunities[(side,key)];target[m]=rng.choice(choices,m.sum(),p=weights)
            pass_mask=active&(kind==KINDS.index('pass'));run=active&(kind==KINDS.index('rush'));kneel=active&(kind==KINDS.index('kneel'));punt=active&(kind==KINDS.index('punt'));fg=active&(kind==KINDS.index('field_goal'));penalty=active&(kind==KINDS.index('penalty'))
            outcome=np.full(n,-1)
            if pass_mask.any():
                drops=pred['dropback'].fast(x[pass_mask],oi[pass_mask],qb[pass_mask],True)
                outcome[pass_mask]=np.asarray(model['dropback']['classes'])[_sample(rng,drops)]
            sack=pass_mask&(outcome==0);interception=pass_mask&(outcome==1);complete=pass_mask&(outcome==3)
            yards=np.zeros(n,dtype=int)
            for name,mask,participant in [('passYards',complete,receiver),('rushYards',run,runner)]:
                if mask.any():
                    mean=pred[name].fast(x[mask],oi[mask],participant[mask])[:,0];res=np.empty(mask.sum())
                    for z in range(3):
                        zm=np.minimum(2,field[mask]//20)==z;res[zm]=rng.choice(residuals[name][str(z)],zm.sum())
                    yards[mask]=np.rint(mean+res).astype(int).clip(-99,99)
                    td_name='passTouchdown' if name=='passYards' else 'rushTouchdown'
                    td_probs=pred[td_name].fast(x[mask],oi[mask],participant[mask],True)
                    td=(np.asarray(model[td_name]['classes'])[_sample(rng,td_probs)]==1)
                    sampled=yards[mask];sampled=np.minimum(sampled,field[mask]-1);sampled[td]=field[mask][td];yards[mask]=sampled
            if sack.any():yards[sack]=rng.choice(sack_yards,sack.sum())
            if kneel.any():
                pool=[r for r in model['clock'].get('kneel',[])];yards[kneel]=-1 # kneel yard is a rule-accounting approximation, explicitly disclosed.
            gain=np.minimum(yards,field);gain=np.maximum(gain,field-100)
            add(pass_mask&~sack,qb,'passingAttempts');add(complete,qb,'completions');add(complete,qb,'passingYards',gain);add(pass_mask&~sack,receiver,'targets');add(complete,receiver,'receptions');add(complete,receiver,'receivingYards',gain);add(interception,qb,'interceptions')
            add(run,runner,'carries');add(run,runner,'rushingYards',gain);add(kneel,qb,'carries');add(kneel,qb,'rushingYards',gain)
            if model['sport']=='CFB':add(sack,qb,'carries');add(sack,qb,'rushingYards',gain)
            duration=np.zeros(n,dtype=int)
            for k in KINDS:
                km=active&(kind==KINDS.index(k))&~sack;pool=arrays.get(k)
                if km.any():
                    if pool is None:raise ValueError('No observed clock evidence for selected play type')
                    duration[km]=rng.choice(pool,km.sum())
            if sack.any():duration[sack]=rng.choice(arrays['sack'],sack.sum())
            previous_clock=clock.copy();quarter_remaining=np.where(clock%900==0,900,clock%900);clock[active]-=np.minimum(quarter_remaining[active],duration[active]);plays[active]+=1
            live=pass_mask|run|kneel;fumble=live&~sack&~interception&(rng.random(n)<model['fumble']['lost']/model['fumble']['n'])
            field[live]-=gain[live]
            touchdown=live&(field<=0)&~interception&~fumble;safety=live&(field>=100)&~interception
            scores[ix[touchdown],oi[touchdown]]+=6;scores[ix[safety],di[safety]]+=2
            conversion=model['conversion']['extra_point'];xp=touchdown&(rng.random(n)<conversion['made']/conversion['n']);scores[ix[xp],oi[xp]]+=1
            add(touchdown&complete,qb,'passingTouchdowns');add(touchdown&complete,receiver,'receivingTouchdowns');add(touchdown&run,runner,'rushingTouchdowns')
            changed=touchdown|safety|interception|fumble|punt|fg
            missed_fg=np.zeros(n,dtype=bool)
            if fg.any():
                # Nearest observed kick-distance cohort; no unsupported fixed FG percentage.
                for f in np.unique(field[fg]):
                    m=fg&(field==f);delta=np.abs(fgp-f);nearest=np.sort(delta)[min(29,len(delta)-1)];values=fgm[delta<=nearest];made=m&(rng.random(n)<values.mean());scores[ix[made],oi[made]]+=3;missed_fg|=m&~made
            if punt.any():
                net=100-field[punt]+rng.choice(punt_net,punt.sum())
                field[punt]=np.where(net>=100,80,np.clip(net,1,99))
            turnover=interception|fumble
            field[turnover]=np.clip(100-field[turnover],1,99)
            field[missed_fg]=np.clip(100-field[missed_fg]-7,1,80)
            if penalty.any():
                if not model['penalties']:raise ValueError('Enforced penalty evidence unavailable')
                samples=rng.integers(0,len(model['penalties']),n);py=np.asarray([model['penalties'][v]['yards'] for v in samples]);pf=np.asarray([model['penalties'][v]['first'] for v in samples]);field[penalty]=np.clip(field[penalty]-py[penalty],1,99);distance[penalty]=np.maximum(1,distance[penalty]-py[penalty]);firstdown=penalty&pf;down[firstdown]=1;distance[firstdown]=np.minimum(10,field[firstdown])
            ordinary=live&~changed;firstdown=ordinary&(gain>=distance);down[firstdown]=1;distance[firstdown]=np.minimum(10,field[firstdown]);advance=ordinary&~firstdown;down[advance]+=1;distance[advance]=np.maximum(1,distance[advance]-gain[advance]);failed=ordinary&(down>4);changed|=failed;field[failed]=100-field[failed]
            off[changed]=di[changed];down[changed]=1;distance[changed]=np.minimum(10,field[changed]);drives[changed]+=1
            reset(touchdown|safety|(fg&~missed_fg))
            halftime=active&(previous_clock>1800)&(clock<=1800);off[halftime]=1-first[halftime];reset(halftime)
            if offset==0 and representative_games and iterations<=800:
                for i in range(min(representative_games,n)):
                    if active[i]:trace.append({'game':i,'play':int(plays[i]),'clock':int(clock[i]),'offense':teams[oi[i]],'down':int(down[i]),'kind':'sack' if sack[i] else KINDS[kind[i]],'yards':int(gain[i]),'passerId':ids[qb[i]] if pass_mask[i] else None,'receiverId':ids[receiver[i]] if pass_mask[i] else None,'rusherId':ids[runner[i]] if run[i] else None,'score':scores[i].tolist()})
            done=clock<=0
        # Sport-specific overtime, using fitted red-zone rates and actual
        # conversion evidence. OT drives use the same state transitions below.
        tied=np.flatnonzero(scores[:,0]==scores[:,1])
        if len(tied):
            _overtime(model,rng,scores,ps,idx,si,tied,teams,roles,pred)
        # Internal accounting is checked for EVERY completed simulated game.
        if not np.array_equal(ps[:,:,si['passingYards']].sum(axis=1),ps[:,:,si['receivingYards']].sum(axis=1)) or not np.array_equal(ps[:,:,si['completions']].sum(axis=1),ps[:,:,si['receptions']].sum(axis=1)):
            raise AssertionError('Passing/receiving accounting did not reconcile')
        ps[:,:,si['touchdowns']]=ps[:,:,si['rushingTouchdowns']]+ps[:,:,si['receivingTouchdowns']]
        for side in (0,1):hist[side].update(_hist(scores[:,side]))
        total_hist.update(_hist(scores.sum(axis=1)));margin_hist.update(_hist(scores[:,0]-scores[:,1]));wins+=int((scores[:,0]>scores[:,1]).sum());ties+=int((scores[:,0]==scores[:,1]).sum())
        for p,i in idx.items():
            for s,j in si.items():ph[p][s].update(_hist(ps[:,i,j]))
        env.update(plays=int(plays.sum()),drives=int(drives.sum()),overtimeGames=len(tied));completed=offset+n;p=wins/completed;convergence.append({'simulations':completed,'homeWinProbability':p,'monteCarloSE':math.sqrt(p*(1-p)/completed)})
    p=wins/simulations
    return {'schemaVersion':1,'modelVersion':VERSION,'sport':model['sport'],'modelStatus':'experimental_unpromoted',
        'home':home,'away':away,'eventStart':event_start,'evidenceCutoff':model['asOf'],'inputDataVersion':model['sha256'],
        'simulations':simulations,'seed':seed,'homeWinProbability':p,'awayWinProbability':(simulations-wins-ties)/simulations,'tieProbability':ties/simulations,
        'monteCarloSE':math.sqrt(p*(1-p)/simulations),'monteCarloInterval95':wilson(wins,simulations),'calibratedProbability':None,
        'scoreDistributions':{t:histogram_summary(hist[i],simulations) for i,t in enumerate(teams)},
        'totalDistribution':histogram_summary(total_hist,simulations),'marginDistribution':histogram_summary(margin_hist,simulations),
        'players':{p:{s:histogram_summary(ph[p][s],simulations) for s in stats} for p in ids},
        'gameEnvironment':{k:v/simulations for k,v in env.items()},'convergence':convergence,'representativePlays':trace,
        'participantAssumptions':dict(zip(teams,roles)),'quality':{'productionEligible':False,'lineupsVerified':all(r['verified'] for r in roles),'injuriesComplete':all(r['injuriesComplete'] for r in roles),'allGamesAccountingReconciled':True},
        'uncertainty':{'sampling':'Wilson 95%; conditional on fitted assumptions.','modelInterval':None,'model':'Parameter, roster, weather and structural uncertainty are not fully quantified.'},
        'limitations':['Experimental candidate; no calibration or accuracy improvement is implied.','Current QB allocation uses a supplied verified lineup or explicitly uncertain last-game starter inference.',
            'Remaining active usage is conditioned on historical opportunity shares; causal injury redistribution, OL/coverage impacts and weather adjustments are not independently fitted.',
            'Outcome regressions use ridge shrinkage and empirical residuals, not a validated mechanistic depth/YAC model.',
            'Only observed standalone no-play penalties are modeled; live-ball penalties, laterals, defensive scores and rare special-teams events remain outside coverage.',
            'Kneel yardage is approximated as one lost yard. Overtime and return-position approximations require independent rules/distribution validation.',
            'Retrospectively collected source corrections do not establish original pregame publication availability.'],
        'createdAt':datetime.now(timezone.utc).isoformat()}


def _overtime(model,rng,scores,ps,idx,si,tied,teams,roles,pred):
    """Paired NCAA 25-yard drives; NFL paired possessions then sudden death.

    Uses the same fitted play/outcome models and credits participants. Bounded
    NCAA alternating tries prevent a fabricated tie. NFL regular-season ties
    remain possible after the clock. No score is sampled independently.
    """
    xp=model['conversion']['extra_point'];two=model['conversion']['two_point']
    # Pure representation optimization: Generator.choice makes the same draw
    # from these arrays as from the original lists. Avoid rebuilding tens of
    # thousands of historical values for every single overtime snap.
    clock_pools={k:np.asarray(v) for k,v in model['clock'].items() if v}
    start_pools={t:np.asarray(model['starts'][t]) for t in teams}
    sack_pool=np.asarray(model['sackYards']);pass_residuals=np.asarray(model['passYards']['allResiduals']);rush_residuals=np.asarray(model['rushYards']['allResiduals']);fg_fields=np.asarray(model['fg']['fields']);fg_made=np.asarray(model['fg']['made'])
    for game in tied:
        nfl_clock=600;first=int(rng.integers(2))
        for period in range(1,31):
            for turn in (first,1-first):
                if model['sport']=='CFB' and period>=3:
                    scores[game,turn]+=2*int(rng.random()<two['made']/two['n']);continue
                field=25 if model['sport']=='CFB' else int(rng.choice(start_pools[teams[turn]]));down=1;distance=min(10,field);elapsed=0
                for _ in range(40):
                    x=numeric(np.array([down]),np.array([distance]),np.array([field]),np.array([min(600,max(1,nfl_clock))]),np.array([scores[game,turn]-scores[game,1-turn]]),np.array([turn==0]));off=np.array([teams[turn]]);defense=np.array([teams[1-turn]]);pr=pred['play'].probabilities(x,off,defense)[0]
                    for col,k in enumerate(model['play']['classes']):
                        if KINDS[k] in ('kneel','penalty') or down<4 and KINDS[k] in ('punt','field_goal'):pr[col]=0
                    pr/=pr.sum();kind=KINDS[int(rng.choice(model['play']['classes'],p=pr))];qb=roles[turn]['quarterback'];target=None;who=None;yards=0;touchdown=False
                    clocks=clock_pools.get(kind,clock_pools['pass']);elapsed+=int(rng.choice(clocks))
                    if kind in ('punt','field_goal'):
                        if kind=='field_goal':
                            dist=np.abs(fg_fields-field);nearest=np.sort(dist)[min(29,len(dist)-1)];success=fg_made[dist<=nearest].mean();scores[game,turn]+=3*int(rng.random()<success)
                        break
                    if kind=='pass':
                        out=pred['dropback'].probabilities(x,off,defense,np.array([qb]))[0];o=int(rng.choice(model['dropback']['classes'],p=out))
                        if o==0:
                            yards=int(rng.choice(sack_pool))
                            if model['sport']=='CFB':ps[game,idx[qb],si['carries']]+=1;ps[game,idx[qb],si['rushingYards']]+=yards
                        else:
                            ps[game,idx[qb],si['passingAttempts']]+=1
                            if o==1:ps[game,idx[qb],si['interceptions']]+=1;break
                            rc=roles[turn]['receivers'];w=np.array(list(rc.values()),float);target=str(rng.choice(list(rc),p=w/w.sum()));ps[game,idx[target],si['targets']]+=1
                            if o==3:
                                mean=pred['passYards'].predict(x,off,defense,np.array([target]))[0,0];yards=int(round(mean+rng.choice(pass_residuals)));prob=pred['passTouchdown'].probabilities(x,off,defense,np.array([target]))[0];td=int(rng.choice(model['passTouchdown']['classes'],p=prob))==1;yards=field if td else min(field-1,max(field-100,yards));ps[game,idx[qb],si['completions']]+=1;ps[game,idx[qb],si['passingYards']]+=yards;ps[game,idx[target],si['receptions']]+=1;ps[game,idx[target],si['receivingYards']]+=yards
                    else:
                        rc=roles[turn]['runners'];w=np.array(list(rc.values()),float);who=str(rng.choice(list(rc),p=w/w.sum()));mean=pred['rushYards'].predict(x,off,defense,np.array([who]))[0,0];yards=int(round(mean+rng.choice(rush_residuals)));prob=pred['rushTouchdown'].probabilities(x,off,defense,np.array([who]))[0];td=int(rng.choice(model['rushTouchdown']['classes'],p=prob))==1;yards=field if td else min(field-1,max(field-100,yards));ps[game,idx[who],si['carries']]+=1;ps[game,idx[who],si['rushingYards']]+=yards
                    field-=yards
                    if field<=0:
                        scores[game,turn]+=6
                        if target:ps[game,idx[qb],si['passingTouchdowns']]+=1;ps[game,idx[target],si['receivingTouchdowns']]+=1
                        elif who:ps[game,idx[who],si['rushingTouchdowns']]+=1
                        c=two if model['sport']=='CFB' and period>=2 else xp;scores[game,turn]+=(2 if c is two else 1)*int(rng.random()<c['made']/c['n']);break
                    if yards>=distance:down=1;distance=min(10,field)
                    else:down+=1;distance=max(1,distance-yards)
                    if down>4 or field>=100:break
                    if model['sport']=='NFL' and elapsed>=nfl_clock:break
                if model['sport']=='NFL':nfl_clock-=elapsed
                if model['sport']=='NFL' and period>=2 and scores[game,0]!=scores[game,1]:break
            if scores[game,0]!=scores[game,1] or model['sport']=='NFL' and nfl_clock<=0:break
            first=1-first
        else:raise ValueError('Overtime failed to resolve within the bounded protocol')
