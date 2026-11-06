"""Predeclared structural candidates; all fitting uses earlier complete games."""
from collections import defaultdict,Counter
import copy,math
import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln,logit
from ..reconstruction_v19.evidence import aware
from ..iterative_learning import digest
from ..nba_v15 import beta_prior

def fit_qb_continuity(model):
    counts={};novel=0;transitions=0
    for team,hist in model['histories'].items():
        games=sorted(hist.values(),key=lambda h:h['at']);success=total=0;known=set()
        for previous,current in zip(games,games[1:]):
            if not previous['qb'] or not current['qb']:continue
            a=max(previous['qb'],key=previous['qb'].get);b=max(current['qb'],key=current['qb'].get);success+=int(a==b);total+=1;novel+=int(b not in known and a!=b);transitions+=1;known.update(previous['qb'])
        if total:counts[team]=(success,total)
    if len(counts)<5:raise ValueError('Earlier quarterback transitions lack five supported teams')
    a,b=beta_prior([s for s,n in counts.values()],[n for s,n in counts.values()])
    return {'alpha':a,'beta':b,'byTeam':{t:{'retained':s,'transitions':n,'probabilityRetained':(s+a)/(n+a+b)} for t,(s,n) in counts.items()},'transitions':transitions,'novelLeaderTransitions':novel,'interpretation':'Empirical-Bayes starter continuity among earlier observed leaders; not an injury-availability probability. Unknown future debutants remain unsupported.'}

def qb_plans(model,teams,lineups):
    plans={};prior=model['qbContinuity']
    for team in teams:
        h=sorted([v for gid,v in model['histories'][team].items() if model.get('gameSeasons',{}).get(gid)==model.get('forecastSeason')],key=lambda h:h['at'])[-5:];excluded=set((lineups or {}).get(team,{}).get('inactive',[]));eligible=Counter();leaders=[]
        for g in h:
            if g['qb']:leaders.append(max(g['qb'],key=g['qb'].get))
            for p,n in g['qb'].items():
                if n>=5 or p in leaders:eligible[p]+=n
        choices=sorted(p for p in eligible if p not in excluded and not p.split(':')[-1].startswith('-'))
        if not choices:raise ValueError('No supported quarterback remains after verified exclusions')
        incumbent=next((p for p in reversed(leaders) if p in choices),max(choices,key=eligible.get));retain=prior['byTeam'].get(team,{}).get('probabilityRetained',prior['alpha']/(prior['alpha']+prior['beta']));weights={p:(retain if p==incumbent else (1-retain)*eligible[p]/sum(eligible[q] for q in choices if q!=incumbent)) for p in choices} if len(choices)>1 else {choices[0]:1.}
        plans[team]={'ids':choices,'probabilities':[weights[p] for p in choices],'incumbent':incumbent,'conditionedOnKnownPriorQuarterbacks':True,'availabilityProbabilities':None,'publicationComplete':False,'unknownDebutantsNotInvented':True}
    return plans

def enrich_rebounds(model,data,cutoff):
    grouped={k:defaultdict(lambda:np.zeros(2)) for k in ['offensive_rebounds','defensive_rebounds']};valid=0
    for g in data.values():
        if (aware(cutoff)-aware(g['at'])).total_seconds()<=6*3600:continue
        for tid,t in g['teams'].items():
            other=g['teams'].get(str(t['opponent_team_id']))
            if not other:continue
            ps=[p for p in g['players'] if str(p['team_id'])==str(tid) and float(p.get('minutes') or 0)>0];minutes=sum(float(p['minutes']) for p in ps)
            if not 235<=minutes<=400 or sum(p['points'] for p in ps)!=t['team_score']:continue
            valid+=1
            opportunities={'offensive_rebounds':float(t['offensive_rebounds']+other['defensive_rebounds']),'defensive_rebounds':float(t['defensive_rebounds']+other['offensive_rebounds'])}
            for p in ps:
                pid=str(p['athlete_id'])
                for stat,opp in opportunities.items():grouped[stat][pid]+=np.array([float(p.get(stat) or 0),opp*float(p['minutes'])/(minutes/5)])
    shares=defaultdict(dict);evidence={}
    for stat,values in grouped.items():
        rs=np.array(list(values.values()));k,n=rs[:,0],rs[:,1];ok=n>0;k,n=k[ok],n[ok]
        if len(n)<30:raise ValueError('Thirty earlier player rebound opportunity histories required')
        def loss(logab):
            a,b=np.exp(logab);return -float(np.sum(gammaln(a+k)-gammaln(a)+a*np.log(b)-(a+k)*np.log(b+n)))
        f=minimize(loss,np.log([1.,20.]),method='L-BFGS-B',bounds=[(-7,15),(-7,15)])
        if not f.success:raise ValueError('Rebound opportunity hierarchy did not converge')
        a,b=np.exp(f.x);evidence[stat]={'alpha':float(a),'beta':float(b),'players':len(n),'observedPlayerRebounds':int(k.sum()),'onCourtOpportunityExposure':float(n.sum())}
        for pid,(count,exposure) in values.items():shares[pid][stat]=float((count+a)/(exposure+b))
    model['reboundShares']=dict(shares);model['reboundEvidence']={'priors':evidence,'validEarlierTeamBoxes':valid,'exposure':'Observed team credited offensive/defensive rebound opportunities times player minutes divided by team on-court duration. Not an invented player minute count.','fittedBefore':cutoff};return model

def volume_shift(model,projections,teams):
    result={}
    for t in teams:
        rows=projections[t]['__team__'];passes=max(.1,rows['dropbacks']);plays=max(passes+.1,rows['plays']);desired=np.clip(passes/plays,.02,.98);h=sorted(model['histories'][t].values(),key=lambda h:h['at'])[-5:];p=sum(sum(x['qb'].values()) for x in h);r=sum(sum(x['runner'].values()) for x in h)
        if min(p,r)<=0:raise ValueError('Earlier pass/rush opportunity budget unavailable')
        result[t]=float(logit(desired)-logit(p/(p+r)))
    return result

def refresh_context(model,data,g):
    """Refresh observed earlier roles while keeping fitted coefficients frozen.
    No current-game player/score dictionary is visited. New unsupported NBA
    rates are withheld, rather than silently dropping an observed rotation.
    """
    cutoff=aware(g['at'])-__import__('datetime').timedelta(minutes=30);teams=[g['home'],g['away']]
    if g['sport']!='NBA':
        eligible={gid for gid,h in data['games'].items() if aware(h['lastObservedAt'])+__import__('datetime').timedelta(hours=6)<cutoff};hist={t:{} for t in teams}
        for row in data['rows']:
            t=row['o']
            if t not in hist or row['game'] not in eligible or row['kind'] not in ['pass','sack','rush','kneel','punt','field_goal','penalty']:continue
            h=hist[t].setdefault(row['game'],{'at':row['at'],'qb':Counter(),'receiver':Counter(),'runner':Counter()});h['at']=max(h['at'],row['at'])
            for role,yes in [('qb',row['kind'] in ['pass','sack']),('receiver',row['kind']=='pass'),('runner',row['kind'] in ['rush','kneel'])]:
                if yes and row.get(role):h[role][row[role]]+=1
        for t in teams:model['histories'][t]={gid:{k:dict(v) if isinstance(v,Counter) else v for k,v in h.items()} for gid,h in hist[t].items()}
        model['gameSeasons']={gid:h['season'] for gid,h in data['games'].items() if gid in eligible}
    else:
        histories={t:[] for t in teams}
        for h in data.values():
            if aware(h['at'])+__import__('datetime').timedelta(hours=6)>=cutoff:continue
            for t in teams:
                if t not in h['teams']:continue
                ps=[p for p in h['players'] if str(p['team_id'])==t and float(p.get('minutes') or 0)>0];minutes=sum(float(p['minutes']) for p in ps)
                if not 235<=minutes<=400 or sum(p['points'] for p in ps)!=h['teams'][t]['team_score']:continue
                histories[t].append({'at':h['at'],'game':h['id'],'roster':[{k:p[k] for k in ['athlete_id','minutes','starter']} for p in ps]})
        for t in teams:
            hs=sorted(histories[t],key=lambda h:h['at'])[-20:]
            if any(str(p['athlete_id']) not in model['players'] for h in hs[-2:] for p in h['roster']):raise ValueError('New NBA rotation participant lacks fitted earlier usage; no player was silently dropped')
            model['rotationTeams'][t]=hs
    model['contextCutoff']=cutoff.isoformat();model['contextRefreshUsesFinalCurrentGame']=False;return model
