"""Research-only complete football games through the V23-derived accounting reducer.

An empirical contextual play kernel is a mechanics diagnostic, not an approved
forecast. Final-game participant conditioning is permitted ONLY in Mode A.
"""
from collections import defaultdict,Counter
import hashlib,json
import numpy as np
from ..fullgame_v23.accounting import FootballLedger,FootballPlay,team_actor
from ..fullgame_v23.rules import RegulationClock,FootballOvertime,dead_ball_enforcement,try_required
from ..fullgame_v23.modes import Mode,label

class PlayKernel:
    def __init__(self,sport,teams,rows,owners,clock_model=None,additional_clock_pools=None,phase_clock=None):
        self.sport=sport;self.teams=tuple(teams);self.owners=owners;self.rows={t:[r for r in rows if r['o']==t] for t in teams};self.clock_model=clock_model
        if any(len(rs)<30 for rs in self.rows.values()):raise ValueError('Thirty observed team actions required')
        self.positive={k:[int(r['elapsed']) for rs in self.rows.values() for r in rs if r['kind']==k and r.get('elapsed') is not None and 1<=r['elapsed']<=90] for k in ('pass','sack','rush','kneel','punt','field_goal')}
        self.additional_clock_pools=additional_clock_pools or {}
        self.phase_clock=phase_clock
        self.unavailable=set()
        for k,values in self.additional_clock_pools.items():
            if k not in self.positive or any(not 1<=v<=90 for v in values):raise ValueError('Positive same-league clock support required')
            self.positive[k].extend(values)
        self.admin=[int(r['elapsed']) for rs in self.rows.values() for r in rs if r['kind']=='penalty' and r.get('elapsed') is not None and 0<=r['elapsed']<=90]
        self.cache={};self.input_hash=hashlib.sha256(json.dumps({'inputBindingVersion':'27.0','sport':sport,'teams':self.teams,'owners':owners,'rows':rows,'clockArtifact':clock_model.artifact if clock_model else None,'additionalClockPools':self.additional_clock_pools,'phaseClockObservations':phase_clock.observations if phase_clock else None},sort_keys=True,default=str).encode()).hexdigest()
    def select(self,rng,offense,down,field,clock,diff,overtime=False,period=4,distance=10):
        # The distance calculation uses exact state, so memoize exact state.
        # Bucket-only keys would make future draws depend on which game first
        # warmed the cache, rather than on the frozen state and random seed.
        hurry=period in (2,4) and clock<=120;key=(offense,down,float(field),float(distance),hurry,int(np.sign(diff)),overtime,period in (2,4),tuple(sorted(self.unavailable)))
        if key not in self.cache:
            candidates=[r for r in self.rows[offense] if r['kind'] in ('pass','sack','rush','kneel','punt','field_goal','penalty') and (r['kind']!='penalty' or abs(r.get('yards',0)) in (5,10,15)) and (down==4 or r['kind'] not in ('punt','field_goal')) and (r['kind']!='field_goal' or field<=max([r0['field'] for r0 in self.rows[offense] if r0['kind']=='field_goal'] or [0])) and (r['kind']!='kneel' or period in (2,4) and clock<=120 and diff>=0 and not overtime)]
            if not candidates:raise ValueError('No supported legal play in this state')
            candidates=[r for r in candidates if not any(r.get(k) in self.unavailable for k in ['qb','receiver','runner'])]
            if not candidates:raise ValueError('Availability scenario has no supported remaining play participants')
            distances=np.array([abs(r['down']-down)*4+abs(r.get('distance',10)-distance)/5+abs(r['field']-field)/20+int((r.get('quarter',4) in (2,4) and r['clock']%1800<=120)!=hurry)*2+int(np.sign(r['script'])!=np.sign(diff)) for r in candidates]);nearest=np.quantile(distances,.25);pool=[r for r,d in zip(candidates,distances) if d<=nearest];self.cache[key]=pool
        pool=self.cache[key];return pool[int(rng.integers(len(pool)))].copy()
    def charge(self,rng,r,clock):
        if r['kind']=='penalty':
            if not self.admin:raise ValueError('Administrative interval evidence unavailable; no zero substitution')
            return min(int(rng.choice(self.admin)),int(clock.remaining)),True
        kind=r['kind'];hurry=clock.period in (2,4) and clock.remaining<=120
        if self.clock_model is not None and kind in self.clock_model.artifact['supported']:
            cdf=self.clock_model.cdf(kind,bool(r.get('complete')),hurry);value=int(np.searchsorted(cdf,rng.random()))
        else:
            pool=self.positive.get(kind) or []
            if not pool:raise ValueError('Positive clock interval evidence unavailable for '+kind)
            value=int(rng.choice(pool))
        if value<=0:raise ValueError('Timed play cannot silently consume zero physical/latent charge')
        return min(value,int(clock.remaining)),False
    def actor(self,r,name,team):
        p=r.get(name)
        return p if p and self.owners.get(p)==team else None

def _drive(kernel,rng,ledger,offense,field,down,distance,clock=None,ot=None,trace=None,max_plays=500,availability=None,applied=None):
    """Execute one possession or its remaining quarter segment."""
    team=kernel.teams[offense];defense=kernel.teams[1-offense];actions=0
    while actions<max_plays:
        if clock:
            from ..fullgame_v23.availability import due
            for i,r in enumerate(availability or []):
                if i in applied or not due(r,clock.period,clock.remaining):continue
                player=r['playerId'];ledger.exclude(player);kernel.unavailable.add(player);applied.add(i)
                qbs={row.get('qb') for row in kernel.rows[r['teamId']] if row.get('kind') in ('pass','sack') and row.get('qb') in kernel.owners}
                if player in qbs and not qbs-kernel.unavailable:raise ValueError('Availability scenario withheld: no observed replacement quarterback evidence')
        if clock is not None and clock.remaining<=0:return 'period',field,down,distance,actions

        if hasattr(kernel,'before_action') and ot is None:kernel.before_action(ledger,clock,team,down,distance,field)
        diff=ledger.team[team]['points']-ledger.team[defense]['points'];r=kernel.select(rng,team,down,field,clock.remaining if clock else 600,diff,ot is not None,period=clock.period if clock else 5,distance=distance);kind=r['kind'];gain=float(np.clip(r.get('yards',0),field-100,field));complete=kind=='pass' and bool(r.get('complete'));interception=kind=='pass' and bool(r.get('int'));lost=bool(r.get('fumble')) and (kind in ('rush','sack','kneel') or complete);qb=kernel.actor(r,'qb',team);receiver=kernel.actor(r,'receiver',team);runner=kernel.actor(r,'runner',team)
        if kind=='pass' and not complete:gain=0
        if kind in ('punt','field_goal','penalty'):gain=0
        touchdown=kind in ('rush','pass') and (kind=='rush' or complete) and gain>=field and not interception and not lost;safety=kind in ('rush','sack','kneel') and field-gain>=100
        charge=0
        if clock:
            charge,admin=kernel.charge(rng,r,clock)
            if kernel.phase_clock:
                prior=clock.remaining;terminal=touchdown or safety or interception or lost or kind in ('punt','field_goal');kernel.phase_clock.advance(rng,clock,kind,complete,charge,first_down=gain>=distance,out_of_bounds=bool(r.get('outOfBounds')),terminal=terminal);charge=prior-clock.remaining
            else:
                clock.advance(charge,kind='administrative' if admin else 'play',verified=admin)
                if clock.pending_warning:clock.take_warning()
        if kind=='penalty':
            # Only a standalone no-play penalty is currently in this kernel.
            # Enforcement uses the observed offense-relative yardage; owner is
            # explicit from its sign. Declined/live-ball penalties are replayed
            # separately rather than guessed by the stochastic kernel.
            py=int(r.get('yards',0));pteam=team if py<0 else defense;field,enforced=dead_ball_enforcement(field,abs(py),defense=py>0);distance=max(.5,distance-enforced if py>0 else distance+enforced)
            if r.get('firstDownPenalty') or py>0 and distance<=.5:down=1;distance=min(10,field)
            ledger.apply(FootballPlay('administrative',team,no_play=True,accepted_penalty=True,penalty_team=pteam,penalty_yards=enforced))
        else:
            stat_gain=int(np.sign(gain)*np.floor(abs(gain)+.5));e=FootballPlay(kind,team,stat_gain,qb,receiver,runner,complete,interception,lost,touchdown,safety,made=bool(r.get('made')));ledger.apply(e)
        if hasattr(kernel,'after_action') and ot is None:kernel.after_action(ledger,clock,team,kind,gain,complete,touchdown or safety or interception or lost or kind in ('punt','field_goal') or down==4 and gain<distance,qb if kind in ('pass','sack') else runner)
        actions+=1
        if trace is not None:trace.append({'offense':team,'kind':kind,'down':down,'distance':distance,'fieldBefore':field,'gain':gain,'clockCharge':charge,'period':clock.period if clock else 'OT','remaining':clock.remaining if clock else None,'quarterback':qb,'receiver':receiver,'runner':runner,'anonymousCredit':qb is None and kind=='pass'})
        if touchdown:return 'touchdown',0,1,10,actions
        if safety:return 'safety',100,1,10,actions
        if kind=='field_goal':return 'field_goal_made' if r.get('made') else 'field_goal_missed',field,1,10,actions
        if kind=='punt':return 'punt',field,1,10,actions
        if interception or lost:return 'turnover',int(np.clip(field-gain,1,99)),1,10,actions
        if kind!='penalty':
            field-=gain
            if gain>=distance:down=1;distance=min(10,field)
            else:down+=1;distance=max(1,distance-gain)
            if down>4:return 'downs',field,1,10,actions
    raise ValueError('Bounded possession failed to terminate; no fabricated completion')

def restart_field(kernel,rng,offense,ending,field,season):
    """Possession transition in offense-relative coordinates.

    Kicks are explicitly conditioned on a legal touchback, not claimed to be
    a complete return model. Punts use observed net distances. No drive reset
    is allowed to erase a turnover's field position.
    """
    if ending in ('touchdown','safety','field_goal_made'):
        return touchback_field(kernel.sport,season)
    if ending=='punt':
        pool=[r['puntNet'] for r in kernel.rows[kernel.teams[offense]] if r['kind']=='punt' and r.get('puntNet',0)>0]
        if not pool:raise ValueError('Punt-net evidence unavailable')
        landing=100-field+float(rng.choice(pool))
        return 80 if landing>=100 else max(1,landing)
    if ending=='field_goal_missed':return float(np.clip(100-field-(7 if kernel.sport=='NFL' else 0),1,80))
    if ending in ('turnover','downs'):return float(np.clip(100-field,1,99))
    raise ValueError('Unsupported possession transition '+ending)

def touchback_field(sport,season):
    return (65 if season>=2025 else 70 if season>=2024 else 75) if sport=='NFL' else 75

def _complete_games(kernel,ctx,season,games=16,seed=23001,conversions=None,postseason=False,availability_changes=None,initial_state=None,policy=None):
    from ..reconstruction_v19.runtime import local_only
    local_only()
    if ctx['sport']!=kernel.sport or not 1<=games<=100000:raise ValueError('Bounded matching football engine required')
    if not conversions or not conversions.get('extra_point') or not conversions.get('two_point'):raise ValueError('Observed conversion outcomes required')
    from ..fullgame_v23.availability import validate
    availability=validate(availability_changes,kernel.owners)
    rng=np.random.default_rng(seed);results=[];teams=kernel.teams
    for trial in range(games):
        kernel.unavailable=set();applied=set();ledger=FootballLedger(kernel.sport,teams,kernel.owners);clock=RegulationClock(kernel.sport,season);first=int(rng.integers(2));off=first;field=touchback_field(kernel.sport,season);down=1;distance=10;drives=1;trace=[];steps=0
        actual_elapsed=0
        if initial_state is not None:
            from copy import deepcopy
            ledger=deepcopy(initial_state['ledger']);ledger.verify();period=initial_state['period'];remaining=initial_state['remaining']
            if ledger.sport!=kernel.sport or set(ledger.teams)!=set(teams) or ledger.owners!=kernel.owners:raise ValueError('Actual ledger identity/accounting rules mismatch')
            if initial_state['down'] not in (1,2,3,4) or not 0<initial_state['field']<100 or not 0<initial_state['distance']<=100:raise ValueError('Invalid observed down/field/distance')
            if not 1<=period<=4 or not 0<=remaining<=900:raise ValueError('Verified regulation checkpoint required')
            actual_elapsed=(period-1)*900+900-remaining;clock=RegulationClock(kernel.sport,season,period=period,remaining=remaining,elapsed=actual_elapsed,period_charges=[900]*(period-1),warning_taken=initial_state.get('warningTaken',False),running=initial_state.get('running',False));first=teams.index(initial_state['firstReceivingTeam']);off=teams.index(initial_state['offense']);field=initial_state['field'];down=initial_state['down'];distance=initial_state['distance'];kernel.unavailable=set(ledger.unavailable)
        if hasattr(kernel,'reset_policy'):kernel.reset_policy(initial_state)
        while clock.period<=4:
            before=clock.remaining;ending,field,down,distance,n=_drive(kernel,rng,ledger,off,field,down,distance,clock,trace=trace if trial==0 else None,availability=availability,applied=applied);steps+=n
            if steps>1000:raise ValueError('Regulation play budget exceeded')
            if ending=='touchdown' and try_required([ledger.team[t]['points'] for t in teams],off,clock=clock):
                p=int(rng.choice(conversions['extra_point']));ledger.apply(FootballPlay('administrative',teams[off],is_try=True,conversion_points=p))
            if ending!='period':
                old=off;off=1-off;drives+=int(clock.remaining>0)
                field=restart_field(kernel,rng,old,ending,field,season)
                down=1;distance=min(10,field)
            if clock.remaining==0:
                if clock.period==2:off=1-first;field=touchback_field(kernel.sport,season);down=1;distance=10;drives+=1
                clock.next_period()
        clock.verify_complete();ot_periods=0
        if ledger.team[teams[0]]['points']==ledger.team[teams[1]]['points']:
            overtime=FootballOvertime(kernel.sport,season,postseason,int(rng.integers(2)));guard=0;ot_field=25 if kernel.sport=='CFB' else touchback_field(kernel.sport,season)
            while not overtime.finished:
                guard+=1
                if guard>80:raise ValueError('Overtime budget exhausted')
                side=overtime.offense;before=ledger.team[teams[side]]['points'];op_before=ledger.team[teams[1-side]]['points']
                if overtime.shootout:
                    p=int(rng.choice(conversions['two_point']));ledger.apply(FootballPlay('administrative',teams[side],is_try=True,conversion_points=2*p));elapsed=0
                else:
                    ot_clock=None
                    if kernel.sport=='NFL':
                        # A local 10/15-minute period clock; no regulation
                        # quarter transition or NCAA clock is reused.
                        ot_clock=RegulationClock('NFL',season,period=4,remaining=overtime.remaining,warning_taken=overtime.remaining<120)
                    ending,f,dd,dist,n=_drive(kernel,rng,ledger,side,ot_field,1,10,ot_clock,ot=overtime,trace=trace if trial==0 else None);elapsed=ot_clock.elapsed if ot_clock else 0;steps+=n
                    if ending=='period' and postseason:
                        raise ValueError('Postseason unfinished drive across an overtime boundary requires continuation evidence; withheld')
                    if ending=='touchdown' and try_required([ledger.team[t]['points'] for t in teams],side,overtime=overtime):
                        two=overtime.requires_two;made=int(rng.choice(conversions['two_point' if two else 'extra_point']));ledger.apply(FootballPlay('administrative',teams[side],is_try=True,conversion_points=made*(2 if two else 1)))
                    if ending!='period':ot_field=25 if kernel.sport=='CFB' else restart_field(kernel,rng,side,ending,f,season)
                overtime.finish_possession(side,ledger.team[teams[side]]['points']-before,elapsed,ledger.team[teams[1-side]]['points']-op_before);ot_periods=overtime.period
        ledger.verify();results.append({'scores':{t:ledger.team[t]['points'] for t in teams},'team':{t:dict(v) for t,v in ledger.team.items()},'players':{p:dict(v) for p,v in ledger.players.items()},'regulationSeconds':clock.elapsed,'actualRegulationSeconds':actual_elapsed,'simulatedRemainingRegulationSeconds':clock.elapsed-actual_elapsed,'periodCharges':clock.period_charges,'regulationDriveStarts':drives,'overtimePeriods':ot_periods,'actions':steps,'representativePlays':trace if trial==0 else None})
    return label({'engineVersion':'event-accounting-game-core-24.0-research','seed':seed,'games':games,'inputHash':kernel.input_hash,'results':results,'mechanicalInvariantsPassed':True,'forecastAccuracy':None,'phaseClockDiagnostics':kernel.phase_clock.diagnostics() if kernel.phase_clock else None,'additionalObservedClockSupport':{k:len(v) for k,v in kernel.additional_clock_pools.items()},'clockInterpretation':'Latent effective charge sampled from observed/censored timing evidence, not a claim of exact physical snap duration. Administrative timing law remains conditional.','limitations':['Empirical mechanics kernel is not a validated predictive model.','Standalone no-play enforcement only in generated trials; rare live-ball penalties/returns require replay coverage.','Unavailable/injured players require explicit scenario constraints; observed participant conditioning is not pregame availability.']},ctx)

def mechanics_games(kernel,ctx,season,games=16,seed=23001,conversions=None,postseason=False,availability_changes=None):
    if ctx['mode']!=Mode.MECHANICS or isinstance(games,bool) or not 1<=games<=128:raise ValueError('Mode A only; at most 128 conditional mechanics games')
    return _complete_games(kernel,ctx,season,games,seed,conversions,postseason,availability_changes)

def forecast_games(model,kernel,match,ctx,evidence,certificate,games=10000,seed=23001,conversions=None):
    from ..fullgame_v23.forecast import require,compact
    require(model,match,ctx,evidence,certificate)
    if games!=10000:raise ValueError('The registered initial forecast comparison uses 10,000 games')
    if kernel.input_hash!=model.get('kernelInputHash'):raise ValueError('Forecast kernel differs from frozen point-in-time inputs')
    return compact(_complete_games(kernel,ctx,model['season'],games,seed,conversions))


def remaining_games(kernel,ctx,season,initial_state,games=16,seed=24024,conversions=None):
    if ctx['mode']!=Mode.MECHANICS or not 1<=games<=128:raise ValueError('Unqualified remainder experiments are Mode A mechanics only')
    return _complete_games(kernel,ctx,season,games,seed,conversions,initial_state=initial_state)
