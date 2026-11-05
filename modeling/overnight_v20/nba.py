"""Separate NBA game engine using empirically pooled recent usage and pace.
The shared rotation, five-player court and scoring logic comes from v18.
"""
from collections import Counter
from datetime import datetime,timezone
import math
import numpy as np
from scipy.special import expit,logit
from ..nba_v15 import STATS,utc
from ..structural_v18.nba import _rotation,rotation_budgets
VERSION='nba-missed-opportunity-rebound-candidate-20.0.0'
STATS=(*STATS,'fieldGoalAttempts','threePointAttempts','freeThrowAttempts')
def simulate_nba(model,home,away,event_start,simulations=10000,seed=15002,lineups=None,batch_size=1000):
    if model.get('version')!=VERSION or home==away or any(t not in model['teams'] for t in (home,away)):
        raise ValueError('A separate fitted NBA artifact and exact NBA team IDs are required')
    if utc(event_start)<utc(model['cutoff']):raise ValueError('NBA event cannot precede training cutoff')
    if isinstance(simulations,bool) or simulations not in (1000,10000,50000,100000):raise ValueError('Choose 1,000 test or 10,000–100,000 complete NBA games')
    if not isinstance(seed,int) or isinstance(seed,bool) or not 0<=seed<2**53:raise ValueError('A nonnegative reproducible seed is required')
    from ..reconstruction_v19.runtime import local_only
    local_only()
    teams=[home,away];rot=[_rotation(model,t,(lineups or {}).get(t),event_start) for t in teams];ids=sorted(set(p for r in rot for p in r['minutes']));
    if set(rot[0]['minutes'])&set(rot[1]['minutes']):raise ValueError('Ambiguous player identity belongs to both historical team rotations')
    pi={p:i for i,p in enumerate(ids)};si={s:i for i,s in enumerate(STATS)};rng=np.random.default_rng(seed)
    score_hist=[Counter(),Counter()];total_hist=Counter();margin_hist=Counter();player_hist={p:{s:Counter() for s in STATS} for p in ids};convergence=[];wins=0;poss_sum=np.zeros(2);ot_games=0
    params=[]
    for side,t in enumerate(teams):
        recent=sorted(model['teams'][t],key=lambda g:g['at'])[-20:];op=sorted(model['teams'][teams[1-side]],key=lambda g:g['at'])[-20:];tot=Counter();opp=Counter()
        for g in recent:tot.update(g['stats'])
        for g in op:
            if g.get('opponentStats'):opp.update(g['opponentStats'])
            else:
                for h in model['teams'].get(g['opponent'],[]):
                    if h['game']==g['game']:opp.update(h['stats'])
        if not opp:opp=Counter(model['league'])
        l=model['league'];pr=np.array([tot['turnovers'],tot['field_goals_attempted']-tot['three_point_field_goals_attempted'],tot['three_point_field_goals_attempted'],sum(len(g.get('roster',[]))*0 for g in recent)])
        # FT trips per possession estimated from earlier observed trip lengths.
        mean_trip=float(np.mean(model['freeThrowTrips']));pr[3]=tot['free_throws_attempted']/mean_trip;pr/=pr.sum()
        rates={};aids=list(rot[side]['minutes'])
        for p in aids:
            z=model['players'][p];a,b=model['priors']['two'];two=(z['field_goals_made']-z['three_point_field_goals_made']+a)/(z['field_goals_attempted']-z['three_point_field_goals_attempted']+a+b);a,b=model['priors']['three'];three=(z['three_point_field_goals_made']+a)/(z['three_point_field_goals_attempted']+a+b);a,b=model['priors']['free'];ft=(z['free_throws_made']+a)/(z['free_throws_attempted']+a+b)
            rates[p]={'two':two,'three':three,'free':ft,'two_point_field_goals_attempted':(z['field_goals_attempted']-z['three_point_field_goals_attempted'])/max(1,z['minutes']),**{k:float(z[k])/max(1,z['minutes']) for k in ['field_goals_attempted','three_point_field_goals_attempted','free_throws_attempted','offensive_rebounds','defensive_rebounds','assists','steals','blocks','turnovers','fouls']}}
        for p in aids:
            rates[p].update(model['rateOverrides'][p])
            if model.get('reboundVariant') in ('share','share_buzzer'):
                rates[p]['offensive_rebounds']=model['reboundShares'][p]['offensive_rebounds']
                rates[p]['defensive_rebounds']=model['reboundShares'][p]['defensive_rebounds']
        params.append({'events':pr,'rates':rates,'pace':[g['stats']['possessions']+g['stats']['offensive_rebounds'] for g in recent],'paceWeight':np.exp2(-np.array([(utc(event_start)-utc(g['at'])).total_seconds()/86400 for g in recent])/model['recencyHalfLifeDays']),
            'assist':min(1.,tot['assists']/max(1,tot['field_goals_made'])),
            'offRebound':tot['offensive_rebounds']/max(1,tot['offensive_rebounds']+opp['defensive_rebounds']),
            'steal':min(1.,opp['steals']/max(1,tot['turnovers'])),
            'block':min(1.,opp['blocks']/max(1,tot['field_goals_attempted']-tot['field_goals_made'])),
            'defTwo':logit(np.clip((opp['field_goals_made']-opp['three_point_field_goals_made'])/max(1,opp['field_goals_attempted']-opp['three_point_field_goals_attempted']),1e-5,1-1e-5))-logit(np.clip((l['field_goals_made']-l['three_point_field_goals_made'])/(l['field_goals_attempted']-l['three_point_field_goals_attempted']),1e-5,1-1e-5)),
            'defThree':logit(np.clip(opp['three_point_field_goals_made']/max(1,opp['three_point_field_goals_attempted']),1e-5,1-1e-5))-logit(np.clip(l['three_point_field_goals_made']/l['three_point_field_goals_attempted'],1e-5,1-1e-5))})
    ft_trips=np.asarray(model['freeThrowTrips']);stint_seconds=np.asarray(model['rotationStints'])
    for offset in range(0,simulations,batch_size):
        n=min(batch_size,simulations-offset);ps=np.zeros((n,len(ids),len(STATS)));scores=np.zeros((n,2),int);poss=np.zeros((n,2),int);clock=np.full(n,2880.);period_end=np.zeros(n);ot=np.zeros(n,int);off=rng.integers(0,2,n);first_off=off.copy();active=np.ones(n,bool);played=np.zeros((n,len(ids)));court=np.zeros((n,2,len(ids)),bool);until_sub=np.zeros((n,2));row=np.arange(n)
        game_targets=[rotation_budgets(model,t,rot[i],n,rng)*60 for i,t in enumerate(teams)]
        pace=(rng.choice(params[0]['pace'],n,p=params[0]['paceWeight']/params[0]['paceWeight'].sum())+rng.choice(params[1]['pace'],n,p=params[1]['paceWeight']/params[1]['paceWeight'].sum()))/2
        duration=2880/(2*pace)
        for step in range(1500):
            if not active.any():break
            for side in (0,1):
                candidates=np.asarray([pi[p] for p in rot[side]['minutes']]);target=game_targets[side]
                until_sub[np.any(court[:,side]&(ps[:,:,si['fouls']]>=6),axis=1),side]=0
                change=active&(until_sub[:,side]<=0)
                changed=np.flatnonzero(change)
                if len(changed):
                    if step==0:
                        selected=candidates[np.argsort(target[changed],axis=1)[:,-5:]] if model['variant']=='rotation_bootstrap' else np.broadcast_to([pi[p] for p in rot[side]['starters']],(len(changed),5))
                    else:
                        elapsed_game=np.where(ot[changed]==0,2880-clock[changed],2880+300*ot[changed]-clock[changed])
                        deficit=target[changed]*(elapsed_game[:,None]/2880)-played[np.ix_(changed,candidates)]+target[changed]/48
                        fouls=ps[changed[:,None],candidates[None,:],si['fouls']]
                        deficit=np.where(fouls>=6,-1e12,deficit)
                        selected=candidates[np.argsort(deficit,axis=1)[:,-5:]]
                    court[changed,side]=False;court[changed[:,None],side,selected]=True;until_sub[changed,side]=rng.choice(stint_seconds,len(changed))
            def choose(side,weight,exclude=None):
                candidates=list(rot[side]['minutes']);weights=np.asarray([params[side]['rates'][p][weight] for p in candidates]);matrix=court[:,side,[pi[p] for p in candidates]]*weights
                if exclude is not None:
                    for j,p in enumerate(candidates):matrix[:,j]*=exclude!=pi[p]
                total=matrix.sum(axis=1);fallback=court[:,side,[pi[p] for p in candidates]].astype(float)
                if exclude is not None:
                    for j,p in enumerate(candidates):fallback[:,j]*=exclude!=pi[p]
                matrix=np.where((total>0)[:,None],matrix,fallback);matrix/=matrix.sum(axis=1)[:,None]
                pick=(rng.random(n)[:,None]>np.cumsum(matrix,axis=1)).sum(axis=1).clip(max=len(candidates)-1)
                return np.asarray([pi[p] for p in candidates])[pick]
            def credit(mask,who,stat,value=1):
                ix=np.flatnonzero(mask);np.add.at(ps,(ix,who[ix],np.full(len(ix),si[stat])),np.broadcast_to(value,(n,))[ix])
            before_clock=clock.copy();quarter_remaining=np.where(np.mod(clock,720)==0,720,np.mod(clock,720));remaining=np.where(ot==0,quarter_remaining,clock)
            elapsed=np.minimum(remaining,np.maximum(.1,duration));played+=((court[:,0]|court[:,1])&active[:,None])*elapsed[:,None];until_sub-=elapsed[:,None];clock[active]-=elapsed[active]
            original_off=off.copy()
            for side in (0,1):
                m=active&(original_off==side);defense=1-side
                event=(rng.random(n)[:,None]>np.cumsum(params[side]['events'])).sum(axis=1).clip(max=3)
                turnover=m&(event==0);two=m&(event==1);three=m&(event==2);free=m&(event==3)
                shooter=choose(side,'two_point_field_goals_attempted');three_shooter=choose(side,'three_point_field_goals_attempted');shooter=np.where(three,three_shooter,shooter)
                who=choose(side,'turnovers');credit(turnover,who,'turnovers');credit(turnover&(rng.random(n)<params[side]['steal']),choose(defense,'steals'),'steals')
                p2=np.asarray([params[side]['rates'][ids[p]]['two'] for p in shooter]);p3=np.asarray([params[side]['rates'][ids[p]]['three'] for p in shooter]);success=expit(np.where(three,logit(p3)+params[side]['defThree'],logit(p2)+params[side]['defTwo']));made=(two|three)&(rng.random(n)<success);points=np.where(three,3,2)
                credit(two|three,shooter,'fieldGoalAttempts');credit(three,shooter,'threePointAttempts');scores[made,side]+=points[made];credit(made,shooter,'points',points);credit(made,shooter,'fieldGoalsMade');credit(made&two,shooter,'twoPointersMade');credit(made&three,shooter,'threePointersMade');credit(made&(rng.random(n)<params[side]['assist']),choose(side,'assists',shooter),'assists')
                miss=(two|three)&~made;credit(miss&(rng.random(n)<params[side]['block']),choose(defense,'blocks'),'blocks')
                ft_shooter=choose(side,'free_throws_attempted');trip=rng.choice(ft_trips,n);ft_prob=np.asarray([params[side]['rates'][ids[p]]['free'] for p in ft_shooter]);last_ft=rng.random(n)<ft_prob;ft_made=rng.binomial(trip-1,ft_prob)+last_ft;scores[free,side]+=ft_made[free];credit(free,ft_shooter,'points',ft_made);credit(free,ft_shooter,'freeThrowsMade',ft_made);credit(free,ft_shooter,'freeThrowAttempts',trip);credit(free,choose(defense,'fouls'),'fouls')
                # Only the final missed FT is reboundable. Earlier misses do
                # not create phantom rebounds/extra possessions.
                ft_last_miss=free&~last_ft
                period_ended=(elapsed>=remaining-1e-8)
                rebound=(miss|ft_last_miss)&(~period_ended if model.get('reboundVariant') in ('buzzer','share_buzzer') else True);orb=rebound&(rng.random(n)<params[side]['offRebound']);drb=rebound&~orb
                credit(orb,choose(side,'offensive_rebounds'),'offensiveRebounds');credit(drb,choose(defense,'defensive_rebounds'),'defensiveRebounds')
                terminal=m&~orb;poss[terminal,side]+=1;off[terminal]=defense
            # NBA possession entitlement: opening-tip winner starts quarters
            # one/four; the opponent starts two/three. No quarter spans a
            # sampled possession clock. Jump-ball skill is not independently fit.
            boundary=active&(ot==0)&(clock>1e-9)&(np.ceil(before_clock/720)>np.ceil(clock/720))
            off[boundary]=np.where(clock[boundary]>720,1-first_off[boundary],first_off[boundary]);until_sub[boundary]=0
            end=active&(clock<=1e-9);tied=end&(scores[:,0]==scores[:,1]);ot[tied]+=1
            if np.any(ot>10):raise ValueError('NBA overtime failed to resolve within ten periods')
            off[tied]=rng.integers(0,2,int(tied.sum()));clock[tied]=300;until_sub[tied]=0;active[end&~tied]=False
        else:raise ValueError('NBA possession/clock bound failed')
        ps[:,:,si['rebounds']]=ps[:,:,si['offensiveRebounds']]+ps[:,:,si['defensiveRebounds']]
        ps[:,:,si['minutes']]=played/60
        for name,parts in [('pointsReboundsAssists',['points','rebounds','assists']),('pointsRebounds',['points','rebounds']),('pointsAssists',['points','assists']),('reboundsAssists',['rebounds','assists'])]:ps[:,:,si[name]]=sum(ps[:,:,si[p]] for p in parts)
        categories=sum(ps[:,:,si[p]]>=10 for p in ['points','rebounds','assists','steals','blocks']);ps[:,:,si['doubleDouble']]=categories>=2;ps[:,:,si['tripleDouble']]=categories>=3
        for side in (0,1):
            indices=[pi[p] for p in rot[side]['minutes']]
            if not np.array_equal(ps[:,indices,si['points']].sum(axis=1),scores[:,side]):raise AssertionError('NBA player points do not equal team score')
            if not np.allclose(ps[:,indices,si['minutes']].sum(axis=1),240+25*ot,atol=1e-7):raise AssertionError('NBA minutes do not reconcile to five on court')
        if not np.array_equal(ps[:,:,si['points']],2*ps[:,:,si['twoPointersMade']]+3*ps[:,:,si['threePointersMade']]+ps[:,:,si['freeThrowsMade']]):raise AssertionError('NBA scoring accounting failed')
        def count(values):
            v,c=np.unique(values,return_counts=True);return Counter({int(x):int(y) for x,y in zip(v,c)})
        for side in (0,1):score_hist[side].update(count(scores[:,side]))
        total_hist.update(count(scores.sum(axis=1)));margin_hist.update(count(scores[:,0]-scores[:,1]))
        for player_id,i in pi.items():
            for stat,j in si.items():player_hist[player_id][stat].update(count(np.rint(ps[:,i,j]).astype(int)))
        wins+=int((scores[:,0]>scores[:,1]).sum());poss_sum+=poss.sum(axis=0);ot_games+=int((ot>0).sum());count_games=offset+n;p=wins/count_games;convergence.append({'simulations':count_games,'homeWinProbability':p,'monteCarloSE':math.sqrt(p*(1-p)/count_games)})
    p=wins/simulations
    from ..simulator import wilson,histogram_summary
    return {'modelVersion':VERSION,'sport':'NBA','modelStatus':'experimental_unpromoted','inputDataVersion':model['sha256'],'opportunityVariant':model['variant'],'reboundVariant':model.get('reboundVariant'),'reboundsAfterPeriodEndAllowed':model.get('reboundVariant') not in ('buzzer','share_buzzer'),'evidenceCutoff':model['cutoff'],'eventStart':event_start,'home':home,'away':away,'simulations':simulations,'seed':seed,'homeWinProbability':p,'awayWinProbability':1-p,'calibratedProbability':None,'monteCarloInterval95':wilson(wins,simulations),'monteCarloSE':math.sqrt(p*(1-p)/simulations),
        'scoreDistributions':{home:histogram_summary(score_hist[0],simulations),away:histogram_summary(score_hist[1],simulations)},'totalDistribution':histogram_summary(total_hist,simulations),'marginDistribution':histogram_summary(margin_hist,simulations),
        'players':{'nba:espn:'+p:{s:histogram_summary(player_hist[p][s],simulations) for s in STATS} for p in ids},'playerNames':{'nba:espn:'+p:model['playerNames'][p] for p in ids},'rotationAssumptions':dict(zip(teams,rot)),
        'gameEnvironment':{'homePossessions':float(poss_sum[0]/simulations),'awayPossessions':float(poss_sum[1]/simulations),'overtimeProbability':ot_games/simulations},'convergence':convergence,
        'quality':{'productionEligible':False,'lineupsVerified':all(r['verified'] for r in rot),'injuriesComplete':all(r['injuriesComplete'] for r in rot),'playerTeamPointsReconciled':True,'minutesReconciled':True,'combinedStatsShareOutcomes':True,'regulationQuarters':4,'quarterSeconds':720,'overtimeSeconds':300},
        'uncertainty':{'modelInterval':None,'sampling':'Wilson 95% numerical interval; not model/lineup uncertainty.'},
        'limitations':['Separate experimental NBA model; current starter/rotation/injury validation and probability calibration are not established.','Five-player rotations follow recent minute budgets and observed substitution intervals; causal blowout, rest/back-to-back and coaching adjustments are not independently validated.','Empirical-Bayes shooting and descriptive opponent log-odds effects require chronological full-game validation.','Free-throw trips and rebound/assist events are approximate; and-ones, technical/bonus administration and team rebounds are incomplete.','Reported minute histograms round to whole minutes, while internal five-player accounting uses exact seconds.','Source corrections may postdate the replay cutoff; no historical market lines or original publication timestamps are invented.'],
        'createdAt':datetime.now(timezone.utc).isoformat()}
