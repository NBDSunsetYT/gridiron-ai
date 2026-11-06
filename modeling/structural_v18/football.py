"""Offline opportunity-budget football challenger; never used in web handlers.
Possession, clock, scoring and shared player outcomes derive from repository v15.
Only pregame opportunity allocation and a learned dropback intercept differ.
"""
from collections import Counter
from datetime import datetime,timezone
import math
import numpy as np
from scipy.special import logit
from .. import football_v15 as base
from ..football_v15 import utc,Predictor,numeric,KINDS,STATS,_sample,_hist
from ..simulator import histogram_summary,wilson
VERSION='football-opportunity-budget-candidate-18.0.0'

def participant_roles(model,team,lineup,event_start):
    roles=base.participant_roles(model,team,lineup,event_start)
    p=model['projectedOpportunities'].get(team)
    if not p:raise ValueError('Pregame projected opportunity snapshot required')
    if model.get('variant')!='allocation_only' and not (lineup or {}).get('quarterback'):
        hs=sorted(model['histories'][team].values(),key=lambda h:h['at'])[-3:];qbs={pid for h in hs for pid in h['qb']}-set(roles['inactive'])
        eligible=[q for q in sorted(qbs) if p.get(q,{}).get('passingAttempts',0)>0]
        if not eligible:raise ValueError('Supported quarterback opportunity forecast missing')
        roles['quarterback']=max(eligible,key=lambda q:p[q]['passingAttempts'])
        for q in qbs:
            if q!=roles['quarterback']:roles['runners'].pop(q,None)
    for role,stat in [('receivers','targets'),('runners','carries')]:
        weights={pid:max(0.,p.get(pid,{}).get(stat,0.)) for pid in roles[role]}
        if sum(weights.values())<=0:raise ValueError('Supported '+stat+' opportunity forecast missing')
        roles[role]=weights
    roles['assumption']='Regularized zero-inclusive pregame opportunity forecasts; shared play allocation, inferred starter and unknown injury availability.'
    return roles

def _shift_play(probs,classes,side,teams,model):
    # A trained pregame dropback share adjusts the intercept; down/distance,
    # score, clock and opponent effects remain in the state model.
    shifts=np.array([model['dropbackLogitShift'][t] for t in teams])[side]
    for col,kind in enumerate(classes):
        if KINDS[kind]=='pass':probs[:,col]*=np.exp(shifts)
    probs/=probs.sum(axis=1)[:,None];return probs

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
            probs=_shift_play(probs,classes,oi,teams,model)
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
                    pr=_shift_play(pr[None,:],model['play']['classes'],np.array([turn]),teams,model)[0]
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
