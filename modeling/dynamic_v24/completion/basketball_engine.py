"""V24 accounting engine with specialized-head actor allocation.

Derived from the preserved V24 research source. Untagged reference inputs retain
the prior seeded draws. Specialized inputs allocate two-point attempts using
two-point rates, instead of incorrectly including three-point attempts.

Mode A empirical participant/rotation conditioning is final-evidence research.
It is not licensed to emit pregame probabilities or betting accuracy claims.
"""
from collections import Counter
import numpy as np
from ...fullgame_v23.accounting import BasketballLedger
from ...fullgame_v23.modes import Mode,label

def complete_games(game,ctx,games=16,seed=23002,clock_intervals=None,availability_changes=None,initial_state=None,policy=None):
    from ...reconstruction_v19.runtime import local_only
    local_only()
    if ctx['sport']!='NBA' or not 1<=games<=100000:raise ValueError('Matching bounded basketball engine required')
    if not clock_intervals or min(clock_intervals)<=0:raise ValueError('Observed positive clock intervals required')
    teams=list(game['teams']);players={str(int(p['athlete_id'])):p for p in game['players'] if float(p.get('minutes') or 0)>0};owners={p:str(r['team_id']) for p,r in players.items()};rng=np.random.default_rng(seed);results=[]
    roster={t:[p for p in players if owners[p]==t] for t in teams};starters={t:[p for p in roster[t] if players[p].get('starter')] for t in teams}
    from ...fullgame_v23.availability import validate,due
    availability=validate(availability_changes,owners)
    if any(len(v)!=5 for v in starters.values()):raise ValueError('Actual starting five required for Mode A conditioning')
    def weighted(ids,stat):
        values=np.array([float(players[p].get('field_goals_attempted') or 0)-float(players[p].get('three_point_field_goals_attempted') or 0) if stat=='two_point_field_goals_attempted' else float(players[p].get(stat) or 0) for p in ids]);return str(rng.choice(ids,p=values/values.sum() if values.sum()>0 else None))
    def probability(p,made,attempted,team):
        n=float(players[p].get(attempted) or 0)
        if n:return float(players[p].get(made) or 0)/n
        ids=roster[team];den=sum(float(players[p].get(attempted) or 0) for p in ids)
        if not den:raise ValueError('No supported shooting cohort')
        return sum(float(players[p].get(made) or 0) for p in ids)/den
    trips=game.get('freeThrowTrips',[]);trips=[v for vs in trips.values() for v in vs] if isinstance(trips,dict) else trips
    # A one-shot trip cannot silently become an ordinary possession-ending
    # shooting foul. And-ones/technical retained possession are replayed and
    # unit-tested separately; this generator conditions on ordinary 2/3 trips.
    trip_pool=[int(v) for v in trips if 2<=int(v)<=3];stints=[float(v) for v in game.get('stints',[]) if float(v)>0]
    if not trip_pool:raise ValueError('Observed free-throw trip counts required')
    events={};assist={};orb={}
    for t in teams:
        own=game['teams'][t];other=game['teams'][next(x for x in teams if x!=t)];a=np.array([own['turnovers'],own['field_goals_attempted']-own['three_point_field_goals_attempted'],own['three_point_field_goals_attempted'],own['free_throws_attempted']/np.mean(trip_pool)],float)
        if a.sum()<=0:raise ValueError('No observed event opportunity evidence')
        events[t]=a/a.sum();assist[t]=own['assists']/own['field_goals_made'] if own['field_goals_made'] else 0;den=own['offensive_rebounds']+other['defensive_rebounds'];orb[t]=own['offensive_rebounds']/den if den else 0
    for trial in range(games):
        applied=set();ledger=BasketballLedger(teams,owners);disqualified=set();exception_players=set();technical_exceptions=0;substitutions=0;poss=Counter();team_miss=Counter();reboundable=0;rebounded=0;timing=[];overtime=0;total_seconds=0;first=int(rng.integers(2));off=first;trace=[]
        for t in teams:ledger.set_lineup(t,starters[t])
        remaining=720.;period=1;until_sub={t:float(rng.choice(stints)) if stints else None for t in teams}
        if any(v is None or v<=0 for v in until_sub.values()):raise ValueError('Positive observed substitution intervals required')
        shot_clock=24.
        actual_elapsed=0.
        if initial_state is not None:
            from copy import deepcopy
            ledger=deepcopy(initial_state['ledger']);period=initial_state['period'];remaining=float(initial_state['remaining']);actual_elapsed=(period-1)*720+720-remaining
            if set(ledger.teams)!=set(teams) or ledger.owners!=owners:raise ValueError('NBA actual ledger identities mismatch')
            if not 1<=period<=4 or not 0<=remaining<=720:raise ValueError('Verified regulation checkpoint required')
            ledger.verify(actual_elapsed);total_seconds=actual_elapsed;off=teams.index(initial_state['offense']);first=teams.index(initial_state['firstPossessionTeam']);shot_clock=float(initial_state['shotClock']);timing=[720]*(period-1);until_sub={t:0. for t in teams};disqualified={p for p,s in ledger.players.items() if s['fouls']>=6};exception_players=set(initial_state.get('foulOutExceptionPlayers',[]))
            if not 0<shot_clock<=24 or any(p in disqualified and p not in exception_players for floor in ledger.lineups.values() for p in floor):raise ValueError('Unsupported shot clock or disqualified actual lineup')
        if policy is not None:policy.reset(initial_state)
        for step in range(4000):
            for i,r in enumerate(availability):
                if i in applied or not due(r,period,remaining):continue
                ledger.exclude(r['playerId']);applied.add(i);until_sub[r['teamId']]=0
            for t in teams:
                if until_sub[t]<=0:
                    allowed=[p for p in roster[t] if (p not in disqualified or p in exception_players) and p not in ledger.unavailable]
                    if len(allowed)<5:raise ValueError('Unsupported fewer-than-five injury/ejection scenario')
                    elapsed=total_seconds;budget=np.array([float(players[p]['minutes'])*60 for p in allowed]);deficit=budget*min(1,elapsed/2880)-np.array([ledger.seconds[p] for p in allowed])+budget/48;chosen=[allowed[i] for i in np.argsort(deficit)[-5:]];substitutions+=int(set(chosen)!=set(ledger.lineups[t]));ledger.set_lineup(t,chosen);until_sub[t]=float(rng.choice(stints))
            dt=min(float(rng.choice(clock_intervals)),shot_clock,remaining);ledger.tick(dt);remaining-=dt;total_seconds+=dt
            for t in teams:until_sub[t]-=dt
            t=teams[off];d=teams[1-off];court=list(ledger.lineups[t]);defense=list(ledger.lineups[d]);event=int(rng.choice(4,p=policy.probabilities(ledger,period,remaining,t,events[t]) if policy is not None and period<=4 else events[t]));at_buzzer=remaining<=1e-8;terminal=True
            if event==0:
                actor=weighted(court,'turnovers');steal=None;den=game['teams'][t]['turnovers'];psteal=min(1,game['teams'][d]['steals']/den) if den else 0
                if rng.random()<psteal:steal=weighted(defense,'steals')
                ledger.turnover(t,actor,steal)
            elif event in (1,2):
                value=2 if event==1 else 3;actor=weighted(court,('two_point_field_goals_attempted' if game.get('specializedHeadManifest') else 'field_goals_attempted') if value==2 else 'three_point_field_goals_attempted')
                if value==2:
                    n=float(players[actor]['field_goals_attempted']-players[actor]['three_point_field_goals_attempted']);p=(players[actor]['field_goals_made']-players[actor]['three_point_field_goals_made'])/n if n else sum(players[p]['field_goals_made']-players[p]['three_point_field_goals_made'] for p in roster[t])/max(1,sum(players[p]['field_goals_attempted']-players[p]['three_point_field_goals_attempted'] for p in roster[t]))
                else:p=probability(actor,'three_point_field_goals_made','three_point_field_goals_attempted',t)
                made=rng.random()<p;assister=weighted([p for p in court if p!=actor],'assists') if made and rng.random()<assist[t] else None;block=None
                misses=game['teams'][t]['field_goals_attempted']-game['teams'][t]['field_goals_made'];pblock=min(1,game['teams'][d]['blocks']/misses) if misses else 0
                if not made and rng.random()<pblock:block=weighted(defense,'blocks')
                ledger.shot(t,actor,value,made,assister,block,at_buzzer)
            else:
                actor=weighted(court,'free_throws_attempted');fouler=weighted(defense,'fouls');ledger.foul(d,fouler)
                if ledger.players[fouler]['fouls']>=6:
                    disqualified.add(fouler);available=[p for p in roster[d] if p not in disqualified and p not in ledger.unavailable]
                    if len(available)<5 or fouler in exception_players:
                        # NBA Rule 3: last five are retained, a technical is
                        # administered. Never silently field <5 or select a
                        # disqualified reserve as if ordinarily eligible.
                        exception_players.add(fouler);technical_exceptions+=1;tech=weighted(court,'free_throws_attempted');ledger.free_throw(t,tech,rng.random()<probability(tech,'free_throws_made','free_throws_attempted',t),True,technical=True)
                    else:
                        replacement=next((p for p in available if p not in defense),None)
                        if replacement is None:raise AssertionError('Foul-out replacement unavailable')
                        defense=[replacement if p==fouler else p for p in defense];ledger.set_lineup(d,defense);substitutions+=1
                attempts=int(rng.choice(trip_pool))
                for k in range(attempts):ledger.free_throw(t,actor,rng.random()<probability(actor,'free_throws_made','free_throws_attempted',t),k==attempts-1)
                if at_buzzer:ledger.live_rebound=None
            event_actor=actor # Rebound allocation must not overwrite the shot/TO actor.
            if ledger.live_rebound is not None:
                reboundable+=1;offensive=rng.random()<orb[t];owner=t if offensive else d;actor=weighted(list(ledger.lineups[owner]),'offensive_rebounds' if offensive else 'defensive_rebounds');ledger.rebound(owner,actor);rebounded+=1;terminal=not offensive
            if policy is not None and period<=4:policy.observe(ledger,period,remaining,t,['turnover','two','three','free_throws'][event],event_actor,terminal)
            if terminal:poss[t]+=1;off=1-off;shot_clock=24.
            else:shot_clock=14.
            if trial==0:trace.append({'period':period,'remaining':remaining,'seconds':dt,'team':t,'event':['turnover','two','three','free_throws'][event],'lineups':{t:list(v) for t,v in ledger.lineups.items()},'scores':{t:ledger.team[t]['points'] for t in teams}})
            if at_buzzer:
                timing.append(720 if period<=4 else 300)
                if period>=4 and ledger.team[teams[0]]['points']!=ledger.team[teams[1]]['points']:break
                period+=1
                if period>4:
                    overtime+=1
                    if overtime>12:raise ValueError('Bounded NBA overtime unresolved')
                    remaining=300.;off=int(rng.integers(2))
                else:remaining=720.;off=1-first if period in (2,3) else first
                until_sub={t:0. for t in teams};shot_clock=24.
        else:raise ValueError('Complete basketball game failed to terminate')
        if reboundable!=rebounded:raise AssertionError('Rebound opportunity ledger mismatch')
        if abs(total_seconds-(2880+300*overtime))>1e-7:raise AssertionError('NBA regulation/overtime time mismatch')
        ledger.verify(total_seconds);results.append({'scores':{t:ledger.team[t]['points'] for t in teams},'team':{t:dict(v) for t,v in ledger.team.items()},'players':{p:dict(v) for p,v in ledger.players.items()},'seconds':total_seconds,'actualSeconds':actual_elapsed,'simulatedRemainingSeconds':total_seconds-actual_elapsed,'periodSeconds':timing,'overtimePeriods':overtime,'possessions':dict(poss),'reboundableMisses':reboundable,'creditedRebounds':rebounded,'substitutions':substitutions,'foulOutExceptions':technical_exceptions,'trace':trace if trial==0 else None})
    return label({'engineVersion':'specialized-nba-event-core-24.1','games':games,'seed':seed,'results':results,'mechanicalInvariantsPassed':True,'forecastAccuracy':None,'ordinaryFreeThrowTripsObserved':len(trip_pool),'oneShotTripsNotMisclassifiedAsOrdinary':sum(int(v)==1 for v in trips),'reboundPolicy':'Observed empirical opportunity allocation only; rejected V22 court/proxy challengers are not used.','limitations':['Final-game roster/minutes conditioning is Mode A mechanics research, never pregame forecasting.','Observed event gaps are bounded by shot/period clocks; these are modeled latent event durations.','Conditional event kernel omits rare and-one/flagrant/retained-possession sequences; replay records them separately.']},ctx)
