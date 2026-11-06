"""Specialized expected-value heads feed shared events, never marginal tapes.

These adapters establish an executable connection to the V24 ledgers. Mechanical
success is not a forecasting certificate. Conditional diagnostics cannot call
the strict forecast entry points. Unsupported touchdown/game-probability heads
remain derived events, not independently sampled constraints.
"""
from copy import deepcopy
from collections import defaultdict
import hashlib,json
import numpy as np
from scipy.optimize import brentq
from scipy.special import expit,logit
from ..football import PlayKernel,mechanics_games
from .. import basketball
from ...fullgame_v23.modes import Mode
from ...overnight_v20.state import digest

def bounded_budget(values,total=240.,cap=48.):
    """Euclidean projection onto a capped team-minute simplex (KKT solution)."""
    x=np.asarray(values,float)
    if not np.all(np.isfinite(x)) or np.any(x<0) or len(x)*cap<total or total<=0:raise ValueError('Impossible minute budget')
    left=-float(np.max(x))-cap;right=total+cap
    for _ in range(100):
        middle=(left+right)/2
        if np.clip(x+middle,0,cap).sum()>total:right=middle
        else:left=middle
    result=np.clip(x+(left+right)/2,0,cap)
    if abs(result.sum()-total)>1e-7:raise AssertionError('Minute projection failed')
    return result

def validate_estimates(estimates):
    if not estimates:raise ValueError('Explicit specialized expected values required')
    for player,stats in estimates.items():
        if not isinstance(player,str) or not stats:raise ValueError('Stable player identity required')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or v<0 and not stat.endswith('Yards') for stat,v in stats.items()):raise ValueError('Finite expected values required; counts cannot be negative')

class HeadFootballKernel(PlayKernel):
    """Opportunity-weighted actors and conditional yards inside each real play.

    The least-squares shared passing budget is documented in `headDiagnostics`;
    it is accounting reconciliation, not statistical evidence of better accuracy.
    Actual completions credit the very same yards to QB and receiver. Anonymous
    source credits remain anonymous. No touchdown is independently sampled.
    """
    def __init__(self,*args,estimates,head_manifest,**kwargs):
        super().__init__(*args,**kwargs);validate_estimates(estimates)
        if not head_manifest.get('modelVersions') or head_manifest.get('estimand')!='conditional_mean':raise ValueError('Versioned expected-value heads required; medians are incompatible')
        if head_manifest.get('sport')!=self.sport:raise ValueError('Head league mismatch')
        self.estimates=deepcopy(estimates);self.head_manifest=deepcopy(head_manifest);self.headDiagnostics={};self.input_hash=digest({'kernel':self.input_hash,'heads':estimates,'manifest':head_manifest})
        for team in self.teams:
            members={p:v for p,v in estimates.items() if self.owners.get(p)==team};q=sum(v.get('passingYards',0) for v in members.values());r=sum(v.get('receivingYards',0) for v in members.values());c=sum(v.get('receptions',0) for v in members.values());a=sum(v.get('passingAttempts',0) for v in members.values())
            if min(q,r,c,a)<=0 or c>a+1e-6:raise ValueError('Supported coherent passing volume/receiving heads required')
            self.headDiagnostics[team]={'projectedPassingYards':q,'projectedReceivingYards':r,'sharedPassingYards':(q+r)/2,'reconciliationResidual':(r-q)/2,'projectedCompletions':c,'projectedAttempts':a,'objective':'Equal-unit squared-distance projection onto shared team passing yard budget; no independence or uncertainty claim'}
    def pick(self,rng,team,stat):
        members=[p for p,v in self.estimates.items() if self.owners.get(p)==team and v.get(stat,0)>0]
        if not members:raise ValueError('No supported '+stat+' actor')
        if any(p in self.unavailable for p in members):raise ValueError('Availability changed: rebuild a supported scenario plan; no implicit proportional redistribution')
        weights=np.array([self.estimates[p][stat] for p in members]);return str(rng.choice(members,p=weights/weights.sum()))
    def select(self,rng,offense,down,field,clock,diff,overtime=False,period=4,distance=10):
        row=super().select(rng,offense,down,field,clock,diff,overtime,period,distance)
        # Replace the reference's marginal pass/run odds with the forecast team
        # opportunity odds, preserving its contextual down/clock/script offset.
        # This is an explicit candidate strategy law, not a momentum bonus.
        if down<4 and row['kind'] in ('pass','sack','rush'):
            hurry=period in (2,4) and clock<=120;key=(offense,down,float(field),float(distance),hurry,int(np.sign(diff)),overtime,period in (2,4),tuple(sorted(self.unavailable)))
            pool=self.cache[key];pass_rows=[r for r in pool if r['kind'] in ('pass','sack')];rush_rows=[r for r in pool if r['kind']=='rush'];all_rows=[r for r in self.rows[offense] if r['kind'] in ('pass','sack','rush')]
            attempts=self.headDiagnostics[offense]['projectedAttempts'];carries=sum(v.get('carries',0) for p,v in self.estimates.items() if self.owners.get(p)==offense)
            sack_rate=sum(r['kind']=='sack' for r in all_rows)/max(1,sum(r['kind'] in ('pass','sack') for r in all_rows));dropbacks=attempts/max(1e-6,1-sack_rate)
            if pass_rows and rush_rows and carries>0:
                contextual=len(pass_rows)/(len(pass_rows)+len(rush_rows));reference=sum(r['kind'] in ('pass','sack') for r in all_rows)/len(all_rows);target=dropbacks/(dropbacks+carries)
                p=float(expit(logit(np.clip(contextual,1e-6,1-1e-6))+logit(np.clip(target,1e-6,1-1e-6))-logit(np.clip(reference,1e-6,1-1e-6))))
                subset=pass_rows if rng.random()<p else rush_rows;row=subset[int(rng.integers(len(subset)))].copy()
        if row['kind']=='pass':
            anonymous=not row.get('qb') or self.owners.get(row.get('qb'))!=offense
            if not anonymous:row['qb']=self.pick(rng,offense,'passingAttempts')
            if row.get('complete') and not row.get('int'):
                rec=self.pick(rng,offense,'receptions');row['receiver']=rec;v=self.estimates[rec];diag=self.headDiagnostics[offense]
                mean=v.get('receivingYards',0)/v['receptions']*diag['sharedPassingYards']/diag['projectedReceivingYards']
                pool=[float(r['yards']) for r in self.rows[offense] if r['kind']=='pass' and r.get('complete') and not r.get('int')]
                if not pool:raise ValueError('Conditional completed-pass yard distribution missing')
                row['yards']=float(rng.choice(pool))-float(np.mean(pool))+mean
        elif row['kind']=='rush':
            runner=self.pick(rng,offense,'carries');row['runner']=runner;v=self.estimates[runner]
            pool=[float(r['yards']) for r in self.rows[offense] if r['kind']=='rush']
            row['yards']=float(rng.choice(pool))-float(np.mean(pool))+v.get('rushingYards',0)/v['carries']
        return row

def football_mechanics(kernel,ctx,season,*,games=16,seed=240241,conversions=None):
    if ctx['mode']!=Mode.MECHANICS:raise ValueError('Uncertified head integration is mechanics only')
    result=mechanics_games(kernel,ctx,season,games,seed,conversions)
    return result|{'specializedHeadManifest':kernel.head_manifest,'headDiagnostics':kernel.headDiagnostics,'jointHeadAccuracyValidated':False,'unusedDirectHeads':['touchdowns','moneyline','spread','total'],'opportunityScope':'Team pass/run odds, participant shares and efficiency; pace/clock law still requires independent validation'}

def nba_rates(base,estimates,manifest,ctx):
    if ctx['mode']!=Mode.MECHANICS:raise ValueError('Uncertified NBA head integration is mechanics only')
    validate_estimates(estimates)
    if manifest.get('sport')!='NBA' or manifest.get('estimand')!='conditional_mean' or not manifest.get('modelVersions'):raise ValueError('Versioned NBA expected-value heads required')
    game=deepcopy(base);players={str(int(p['athlete_id'])):p for p in game['players'] if float(p.get('minutes') or 0)>0};diagnostics={}
    for team in game['teams']:
        ids=[p for p,r in players.items() if str(r['team_id'])==team]
        if any(p not in estimates for p in ids):raise ValueError('Missing participant head; do not treat unknown as active/healthy')
        minute_input=[estimates[p].get('minutes',float(players[p]['minutes'])) for p in ids];minutes=bounded_budget(minute_input);totals=defaultdict(float)
        for pid,minute in zip(ids,minutes):
            raw=players[pid];v=estimates[pid];old_min=float(raw['minutes']);raw['minutes']=float(minute)
            fga=v.get('fieldGoalAttempts',float(raw['field_goals_attempted']));three=v.get('threePointAttempts',float(raw['three_point_field_goals_attempted']));fta=v.get('freeThrowAttempts',float(raw['free_throws_attempted']))
            if three>fga+1e-8:raise ValueError('Three-point attempts exceed field-goal attempts')
            two=fga-three;old_two=float(raw['field_goals_attempted']-raw['three_point_field_goals_attempted']);p2=float(raw['field_goals_made']-raw['three_point_field_goals_made'])/old_two if old_two else .5;p3=float(raw['three_point_field_goals_made'])/max(1,float(raw['three_point_field_goals_attempted']));pft=float(raw['free_throws_made'])/max(1,float(raw['free_throws_attempted']))
            probs=np.clip([p2,p3,pft],1e-6,1-1e-6)
            if 'points' in v:
                target=v['points'];maximum=2*two+3*three+fta
                if not 0<=target<=maximum:raise ValueError('Points head incompatible with shared shot opportunities')
                if target==0:probs=np.zeros(3)
                elif target==maximum:probs=np.ones(3)
                else:
                    offset=brentq(lambda s:float(np.dot([2*two,3*three,fta],expit(logit(probs)+s)))-target,-60,60);probs=expit(logit(probs)+offset)
            p2,p3,pft=probs;counts={'field_goals_attempted':fga,'three_point_field_goals_attempted':three,'free_throws_attempted':fta,'field_goals_made':two*p2+three*p3,'three_point_field_goals_made':three*p3,'free_throws_made':fta*pft}
            for key in ['assists','steals','blocks','turnovers','fouls']:counts[key]=v.get(key,float(raw[key]))
            rebound=v.get('rebounds',float(raw['offensive_rebounds']+raw['defensive_rebounds']));orb=float(raw['offensive_rebounds'])/max(1,float(raw['offensive_rebounds']+raw['defensive_rebounds']));counts['offensive_rebounds']=rebound*orb;counts['defensive_rebounds']=rebound*(1-orb)
            if minute<=0 and any(x>0 for x in counts.values()):raise ValueError('Zero-minute player cannot carry positive opportunity')
            for key,value in counts.items():totals[key]+=value;raw[key]=value/max(minute,1e-12)
            # The on-court actor sampler receives per-minute rates. Team event
            # totals retain counts, avoiding a second implicit minutes weighting.
        if totals['assists']>totals['field_goals_made']:raise ValueError('Assist projection exceeds made-shot opportunities')
        for key,value in totals.items():game['teams'][team][key]=value
        diagnostics[team]={'projectedRegulationMinutes':float(sum(minutes)),'inputMinutes':float(sum(minute_input)),'perPlayerCap':48,'actorWeights':'per-minute rates; only eligible on-court players receive actual events'}
    game['specializedHeadManifest']=manifest;game['headDiagnostics']=diagnostics;return game

def nba_mechanics(game,ctx,*,games=16,seed=240241,clock_intervals=None):
    if ctx['mode']!=Mode.MECHANICS or isinstance(games,bool) or not 1<=games<=128:raise ValueError('Uncertified NBA head integration is bounded mechanics only')
    from .basketball_engine import complete_games
    result=complete_games(game,ctx,games,seed,clock_intervals)
    return result|{'specializedHeadManifest':game.get('specializedHeadManifest'),'headDiagnostics':game.get('headDiagnostics'),'jointHeadAccuracyValidated':False,'combinedProps':'Derived from shared player event outcomes; never separately sampled'}

def forecast_with_heads(registry,model,match,ctx,evidence,certificate,*,kernel=None,games=10000,seed=240241,conversions=None):
    """Research-only strict route. No caller can convert Mode A into Mode B."""
    heads=registry.joint_heads(model['sport'],model=model,match=match,ctx=ctx,evidence=evidence,certificate=certificate)
    if model['sport']=='NBA':
        rates=model.get('ratesInput',{})
        if rates.get('sourcePolicy')!='point_in_time' or set(rates.get('specializedHeadIds',[]))!=set(model['specializedHeadIds']):raise ValueError('NBA rate input is not bound to qualified specialized heads')
        if model.get('engineVersion')!='specialized-nba-event-core-24.1' or games!=10000 or digest({'rates':rates,'clockIntervals':model.get('clockIntervals')})!=model.get('kernelInputHash'):raise ValueError('Certified NBA specialized engine/rates do not match')
        from .basketball_engine import complete_games
        from ...fullgame_v23.forecast import compact
        return compact(complete_games(rates,ctx,games,seed,model['clockIntervals']))
    from ..football import forecast_games
    if not isinstance(kernel,HeadFootballKernel) or set(kernel.head_manifest.get('headIds',[]))!=set(model['specializedHeadIds']):raise ValueError('Football kernel is not bound to qualified specialized heads')
    return forecast_games(model,kernel,match,ctx,evidence,certificate,games,seed,conversions)
