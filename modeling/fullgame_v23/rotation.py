"""Pregame roster-aware, empirical-Bayes NBA minutes and feasible lineups.

Unknown availability requires an explicit conditional scenario. Pairwise Gibbs
sampling conditions ALL modeled participants on the team-minute budget; it does
not stretch an incomplete subset of old player heads. No win/prop probability
or full-game predictive eligibility is established by these rotation draws.
"""
from collections import defaultdict
import math
import numpy as np
from ..accuracy_v20.quality import aware
from ..overnight_v20.state import digest
VERSION='roster-global-history-rotation-28.0'


class MinutesPrior:
    def fit(self,games,cutoff):
        if not games or any(aware(g['at'])>=aware(cutoff) for g in games):raise ValueError('Every minutes-prior fit game must strictly precede cutoff')
        groups=defaultdict(list);player=defaultdict(list)
        for g in games:
            for team in g['teams'].values():
                for pid,p in team['players'].items():
                    value=p['stats'].get('minutes')
                    if value is None:continue
                    role='starter' if p.get('starter') is True else 'reserve' if p.get('starter') is False else 'unknown'
                    groups[role].append(float(value));groups['all'].append(float(value));player[pid].append(float(value))
        if len(groups['all'])<50:raise ValueError('Insufficient observed population for hierarchical minutes priors')
        self.groups={k:{'mean':float(np.mean(v)),'variance':float(np.var(v,ddof=1)),'observations':len(v)} for k,v in groups.items() if len(v)>=20}
        within=[np.var(v,ddof=1) for v in player.values() if len(v)>2];between=np.var([np.mean(v) for v in player.values() if len(v)>2],ddof=1)
        self.within=float(np.mean(within)) if within else self.groups['all']['variance'];self.strength=self.within/max(float(between),1e-6)
        self.cutoff=cutoff;self.games=[g['id'] for g in games];self.modelHash=digest({'version':VERSION,'cutoff':cutoff,'trainingDataSHA256':digest(games),'trainingGames':self.games,'groups':self.groups,'within':self.within,'priorStrength':self.strength});return self
    def project(self,roster,history,cutoff):
        if aware(self.cutoff)>aware(cutoff) or any(aware(g['at'])>=aware(cutoff) for g in history):raise ValueError('Future history or prior cannot enter rotation projection')
        by_player=defaultdict(list);populations=defaultdict(list)
        for g in sorted(history,key=lambda g:(g['at'],g['id'])):
            for tid,t in g['teams'].items():
                for pid,p in t['players'].items():
                    if p['stats'].get('minutes') is not None:
                        by_player[pid].append((g,tid,p));role='starter' if p.get('starter') is True else 'reserve' if p.get('starter') is False else 'unknown';populations[role].append(float(p['stats']['minutes']));populations['all'].append(float(p['stats']['minutes']))
        out={}
        for pid,person in roster.items():
            records=by_player[pid][-5:];values=[float(p['stats']['minutes']) for _,_,p in records];starts=[p['starter'] for _,_,p in records if isinstance(p.get('starter'),bool)]
            role='starter' if starts and np.mean(starts)>=.5 else 'reserve' if starts else 'unknown';prior=self.groups.get(role,self.groups['all']);n=len(values);strength=self.strength
            mean=(sum(values)+strength*prior['mean'])/(n+strength);variance=self.within+(prior['variance']/(n+strength))
            if variance<=0 or not math.isfinite(variance):raise ValueError('Minutes uncertainty cannot be invented from a degenerate prior')
            # Observed zero-minute mass is NOT an injury/health probability.
            # Its causes remain confounded in corrected historical boxes.
            population=populations.get(role,populations['all'])
            positive=[v for v in values if v>0];poppos=[v for v in population if v>0]
            if not poppos:raise ValueError('Positive-minute history unavailable for fitted role')
            zero=(sum(v==0 for v in values)+strength*np.mean(np.asarray(population)==0))/(n+strength)
            pmean=(sum(positive)+strength*np.mean(poppos))/(len(positive)+strength)
            out[pid]={'name':person.get('name',pid),'teamId':person.get('teamId'),'mean':float(np.clip(mean,0,48)),'sd':float(math.sqrt(variance)),'zeroMinuteProbability':float(zero),'positiveMean':float(np.clip(pmean,0,48)),'positiveSD':float(math.sqrt(variance)),'zeroMassMeaning':'Observed historical nonparticipation, NOT health; causes unverified','historyGames':n,'priorRole':role,'priorStrength':strength,'sourceGameIds':[g['id'] for g,_,_ in records],'previousTeams':sorted({t for _,t,_ in records}),'lastObservedAt':records[-1][0]['at'] if records else None,'cutoff':cutoff,'availability':'unknown','sparseHistory':n<3}
        return out


def draw_minutes(priors,statuses,decisions,*,n=512,seed=280028,duration=48.,step=.5,burn=40,thin=2,hurdle=False):
    """Discrete Gaussian product conditioned on caps and exact total minutes.

    Four chains use exact pair-conditional categorical updates. Sparse players
    have learned wider priors. Source-backed restrictions lower individual caps.
    Availability probabilities are never inferred from these minutes priors.
    """
    if n<16 or n>2048 or n%4 or duration not in (48.,5.) or step!=.5:raise ValueError('Bounded four-chain regulation/OT rotation experiment required')
    ids=sorted(priors);mu=np.array([priors[p]['mean']*duration/48 for p in ids]);sd=np.array([priors[p]['sd']*math.sqrt(duration/48) for p in ids]);cap=np.full(len(ids),int(duration/step));availability={}
    for i,p in enumerate(ids):
        fact=statuses.get(p,{});status=str(fact.get('status','unknown')).lower();availability[p]=status
        if status not in ('unknown','not_yet_submitted'):
            ts=fact.get('publishedAt') or (fact.get('retrievedAt') if fact.get('immutableReceipt') is True else None)
            if not str(fact.get('source','')).startswith('https://') or not fact.get('sourceVersion') or not ts or not priors[p].get('cutoff') or aware(ts)>=aware(priors[p]['cutoff']):raise ValueError('Availability facts require versioned strictly pre-cutoff evidence')
            if any(aware(fact[k])>=aware(priors[p]['cutoff']) for k in ('modifiedAt','availableAt') if fact.get(k)):raise ValueError('Availability edition is not pregame')
        if status in ('out','inactive','suspended'):active=False
        elif status in ('available','active'):active=True
        else:
            if p not in decisions or not isinstance(decisions[p],bool):raise ValueError('Explicit unweighted scenario required for '+p+' ('+status+')')
            active=decisions[p]
        if not active:cap[i]=0
        if status in ('restricted','limited'):
            if not fact.get('sourceVersion') or isinstance(fact.get('maxMinutes'),bool) or not isinstance(fact.get('maxMinutes'),(int,float)) or not math.isfinite(fact['maxMinutes']) or fact['maxMinutes']<0:raise ValueError('A restriction needs an exact sourced nonnegative finite minute cap')
            cap[i]=min(cap[i],int(float(fact['maxMinutes'])/step))
    if sum(cap>0)>15:raise ValueError('Conditional active list exceeds 15; declare the roster scenario explicitly')
    target=int(5*duration/step)
    if len(ids)<5 or cap.sum()<target or np.any(sd<=0) or not np.isfinite(mu).all() or not np.isfinite(sd).all():raise ValueError('Incomplete/unsupported rotation capacity')
    if hurdle:
        if any(not 0<=priors[p].get('zeroMinuteProbability',-1)<1 or priors[p].get('positiveSD',0)<=0 for p in ids):raise ValueError('Fitted nondegenerate zero/positive minute priors required')
        mu=np.array([priors[p]['positiveMean']*duration/48 for p in ids]);sd=np.array([priors[p]['positiveSD']*math.sqrt(duration/48) for p in ids])
    rng=np.random.default_rng(seed);x=np.zeros((4,len(ids)),int)
    for c in range(4):
        shifted=mu+rng.normal(0,sd);left,right=-1000.,1000.
        for _ in range(70):
            z=(left+right)/2;v=np.clip((shifted+z*sd**2)/step,0,cap)
            if v.sum()>target:right=z
            else:left=z
        v=np.clip((shifted+(left+right)/2*sd**2)/step,0,cap);x[c]=np.floor(v).astype(int);missing=target-int(x[c].sum())
        for i in np.argsort(v-x[c])[::-1]:
            if missing and x[c,i]<cap[i]:x[c,i]+=1;missing-=1
        if missing:raise ValueError('Feasible rotation initialization failed')
    samples=[];live=np.where(cap>0)[0];grid=np.arange(int(duration/step)+1)
    log_mass=np.empty((len(ids),len(grid)))
    for i,p in enumerate(ids):
        mass=-.5*((grid*step-mu[i])/sd[i])**2
        if hurdle and cap[i]>0:
            positive=mass[1:cap[i]+1];normalizer=np.max(positive)+np.log(np.exp(positive-np.max(positive)).sum());z=priors[p]['zeroMinuteProbability']
            mass[1:]=np.log1p(-z)+mass[1:]-normalizer;mass[0]=np.log(z) if z>0 else -np.inf
        log_mass[i]=mass
    for sweep in range(burn+(n//4)*thin):
        for _ in range(len(live)):
            i,j=rng.choice(live,2,replace=False);s=x[:,i]+x[:,j];k=grid[None,:];valid=(k<=cap[i])&(s[:,None]-k>=0)&(s[:,None]-k<=cap[j]);other=np.clip(s[:,None]-k,0,len(grid)-1);logp=log_mass[i][k]+log_mass[j][other];logp[~valid]=-np.inf;weights=np.exp(logp-np.max(logp,axis=1)[:,None]);cdf=np.cumsum(weights/weights.sum(axis=1)[:,None],axis=1);chosen=np.sum(cdf<rng.random((4,1)),axis=1);x[:,i]=chosen;x[:,j]=s-chosen
        if sweep>=burn and (sweep-burn)%thin==0:samples.append(x.copy()*step)
    chains=np.stack(samples,axis=1);draws=chains.reshape(n,len(ids));within=np.var(chains,axis=1,ddof=1).mean(axis=0);between=np.var(chains.mean(axis=1),axis=0,ddof=1)*(n//4);vhat=(1-4/n)*within+between/(n//4);rhat=np.sqrt(np.divide(vhat,within,out=np.ones_like(vhat),where=within>1e-12))
    if not np.all(draws.sum(axis=1)==5*duration) or np.any(draws<0) or np.any(draws>cap*step):raise AssertionError('Rotation budget/cap invariant failed')
    return {'version':VERSION,'players':ids,'draws':draws,'sourceAvailability':availability,'scenarioDecisions':decisions,'scenarioWeights':None,'duration':duration,'seed':seed,'chains':4,'maximumRhat':float(np.max(rhat)),'samplerConverged':bool(np.max(rhat)<1.1),'teamMinuteBudget':5*duration,'conditionalOnDeclaredParticipants':True,'hurdleHistoricalZeroMass':hurdle,'availabilityProbabilitiesInvented':False,'completedBasketballGames':0}


def lineup_tape(ids,minutes,*,seed=280028,step=.5,starters=None,substitution_steps=None):
    q=np.rint(np.asarray(minutes)/step).astype(int);slots=int(round(q.sum()/5));rng=np.random.default_rng(seed)
    if not np.allclose(q*step,minutes) or np.any(q<0) or np.any(q>slots) or q.sum()!=5*slots:raise ValueError('Feasible exact minute allocation required')
    if not substitution_steps or any(not isinstance(v,(int,np.integer)) or v<1 for v in substitution_steps):raise ValueError('Observed quantized positive substitution intervals required')
    tape=[];current=[];next_sub=0
    for t in range(slots):
        remaining=slots-t;required=np.where(q==remaining)[0].tolist()
        if len(required)>5:raise ValueError('Infeasible remaining minute budget')
        if t==0 and starters is not None:
            current=[ids.index(p) for p in starters]
            if len(set(current))!=5 or any(q[i]<=0 for i in current) or not set(required)<=set(current):raise ValueError('Starter scenario incompatible with minute draw')
        elif t>=next_sub or not set(required)<=set(current) or any(q[i]<=0 for i in current):
            pool=[i for i in range(len(ids)) if q[i]>0 and i not in required];chosen=required.copy()
            if len(chosen)<5:
                weights=np.array([q[i] for i in pool],float);chosen+=rng.choice(pool,5-len(chosen),replace=False,p=weights/weights.sum()).tolist()
            current=chosen
        if len(current)!=5 or len(set(current))!=5:raise AssertionError('Five distinct players required')
        if t>=next_sub:next_sub=t+int(rng.choice(substitution_steps))
        tape.append({'startMinute':t*step,'endMinute':(t+1)*step,'players':[ids[i] for i in current]});q[current]-=1
    if q.sum()!=0:raise AssertionError('Lineup tape failed to spend exact individual minutes')
    return tape
