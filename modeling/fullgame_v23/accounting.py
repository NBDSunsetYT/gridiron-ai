"""Shared event accounting for replay and generated games. No final-score fitting."""
from collections import Counter,defaultdict
from dataclasses import dataclass
import math

def team_actor(team):return 'team-stat:'+str(team)
@dataclass(frozen=True)
class FootballPlay:
    kind:str
    offense:str
    yards:int=0
    quarterback:str|None=None
    receiver:str|None=None
    runner:str|None=None
    complete:bool=False
    interception:bool=False
    fumble_lost:bool=False
    touchdown:bool=False
    safety:bool=False
    defensive_touchdown:bool=False
    made:bool=False
    no_play:bool=False
    penalty_team:str|None=None
    penalty_yards:int=0
    accepted_penalty:bool=False
    is_try:bool=False
    conversion_points:int=0
    # Explicit split-yard lateral evidence; initial receiver gets the catch.
    receiving_credits:tuple=()

class FootballLedger:
    def __init__(self,sport,teams,owners):
        if sport not in ('NFL','CFB') or len(set(teams))!=2:raise ValueError('Two football teams required')
        self.sport=sport;self.teams=tuple(teams);self.owners=dict(owners);self.players=defaultdict(Counter);self.team={t:Counter() for t in teams};self.events=0;self.unavailable=set()
    def exclude(self,pid):
        if pid not in self.owners:raise ValueError('Unknown unavailable player')
        self.unavailable.add(pid)
    def credit(self,team,pid,stat,value=1):
        pid=pid or team_actor(team)
        if pid in self.unavailable:raise ValueError('Unavailable player credited after lineup change')
        if pid!=team_actor(team) and self.owners.get(pid)!=team:raise ValueError('Player/event team identity mismatch: '+str(pid))
        if not math.isfinite(value):raise ValueError('Nonfinite statistic')
        self.players[pid][stat]+=value;self.team[team][stat]+=value
    def apply(self,e):
        if e.offense not in self.team:raise ValueError('Unknown offense')
        if e.kind not in ('pass','spike','rush','kneel','sack','field_goal','punt','administrative','kickoff'):raise ValueError('Unsupported football event kind')
        if e.accepted_penalty and (e.penalty_team not in self.team or e.penalty_yards<0):raise ValueError('Explicit penalty ownership/enforcement required')
        if e.no_play and (e.touchdown or e.is_try):raise ValueError('Nullified play cannot score')
        if e.is_try and e.conversion_points not in (0,1,2):raise ValueError('Unsupported try score')
        if (e.complete or e.interception) and e.kind not in ('pass','spike'):raise ValueError('Passing outcome attached to a non-pass')
        if e.complete and e.interception or e.safety and e.touchdown:raise ValueError('Mutually exclusive football outcomes')
        if e.kind=='sack' and e.yards>0:raise ValueError('Positive sack yardage')
        if e.touchdown and not (e.kind=='rush' or e.kind=='pass' and e.complete):raise ValueError('Offensive touchdown has no valid scoring play')
        for p in [e.quarterback,e.receiver,e.runner,*[p for p,y in e.receiving_credits]]:
            if p is not None and p!=team_actor(e.offense) and (self.owners.get(p)!=e.offense or p in self.unavailable):raise ValueError('Invalid/unavailable football participant')
        if e.receiving_credits and sum(y for p,y in e.receiving_credits)!=e.yards:raise ValueError('Lateral yardage does not reconcile')
        t=e.offense;d=next(x for x in self.teams if x!=t);self.events+=1
        if e.accepted_penalty:
            if e.penalty_team not in self.team or e.penalty_yards<0:raise ValueError('Explicit penalty ownership/enforcement required')
            self.team[e.penalty_team]['penalties']+=1;self.team[e.penalty_team]['penaltyYards']+=e.penalty_yards
        if e.no_play:
            if e.touchdown or e.is_try:raise ValueError('Nullified play cannot score')
            return
        if e.is_try:
            if e.conversion_points not in (0,1,2):raise ValueError('Unsupported try score')
            self.team[t]['points']+=e.conversion_points;self.team[t]['tryPoints']+=e.conversion_points;self.team[t]['tryAttempts']+=1;return
        qb=e.quarterback;receiver=e.receiver;runner=e.runner
        if e.kind=='spike' and self.sport=='CFB':qb=team_actor(t)
        if e.kind=='kneel' and self.sport=='CFB':runner=team_actor(t)
        if e.kind in ('pass','spike'):
            self.credit(t,qb,'passingAttempts');self.team[t]['offensivePlays']+=1
            if e.receiver:self.credit(t,receiver,'targets')
            if e.complete:
                if e.interception:raise ValueError('Completion and interception cannot coincide')
                self.credit(t,qb,'completions');self.credit(t,qb,'passingYards',e.yards);self.credit(t,receiver,'receptions')
                splits=e.receiving_credits or ((receiver,e.yards),)
                if sum(y for p,y in splits)!=e.yards:raise ValueError('Lateral receiving credits do not equal passing gain')
                for p,y in splits:self.credit(t,p,'receivingYards',y)
                if e.touchdown:self.credit(t,qb,'passingTouchdowns');self.credit(t,receiver,'receivingTouchdowns')
            if e.interception:self.credit(t,qb,'interceptions')
        elif e.kind in ('rush','kneel'):
            self.credit(t,runner,'carries');self.credit(t,runner,'rushingYards',e.yards);self.team[t]['offensivePlays']+=1
            if e.touchdown:self.credit(t,runner,'rushingTouchdowns')
        elif e.kind=='sack':
            self.team[t]['sacksAllowed']+=1;self.team[t]['sackYardsLost']+=-e.yards;self.team[t]['offensivePlays']+=1
            if e.yards>0:raise ValueError('Positive sack yardage')
            if self.sport=='CFB':self.credit(t,qb,'carries');self.credit(t,qb,'rushingYards',e.yards)
        elif e.kind=='field_goal':self.team[t]['fieldGoalAttempts']+=1;self.team[t]['fieldGoalsMade']+=int(e.made);self.team[t]['points']+=3*int(e.made)
        elif e.kind=='punt':self.team[t]['punts']+=1
        elif e.kind not in ('administrative','kickoff'):raise ValueError('Unsupported football event kind '+e.kind)
        if e.fumble_lost:self.team[t]['fumblesLost']+=1
        if e.touchdown:self.team[t]['points']+=6;self.team[t]['touchdowns']+=1
        if e.safety:self.team[d]['points']+=2;self.team[d]['safeties']+=1
        if e.defensive_touchdown:self.team[d]['points']+=6;self.team[d]['defensiveTouchdowns']+=1
    def verify(self):
        for t,v in self.team.items():
            expected=6*(v['touchdowns']+v['defensiveTouchdowns']+v['returnTouchdowns'])+3*v['fieldGoalsMade']+v['tryPoints']+2*v['safeties']
            if v['points']!=expected:raise AssertionError('Football score component identity failed')
            if v['completions']!=v['receptions'] or v['passingYards']!=v['receivingYards'] or not 0<=v['completions']<=v['passingAttempts']:raise AssertionError('Passing/receiving team reconciliation failed')
            if v['offensivePlays']!=v['passingAttempts']+v['carries']+(v['sacksAllowed'] if self.sport=='NFL' else 0):raise AssertionError('Offensive play accounting failed')
            for stat in ('passingAttempts','completions','passingYards','carries','rushingYards','receptions','receivingYards'):
                actual=sum(p[stat] for pid,p in self.players.items() if self.owners.get(pid)==t or pid==team_actor(t))
                if actual!=v[stat]:raise AssertionError('Player/team partition failed')
            v['netPassingYards']=v['passingYards']-(v['sackYardsLost'] if self.sport=='NFL' else 0)
        return True

class BasketballLedger:
    def __init__(self,teams,owners):
        self.teams=tuple(teams);self.owners=dict(owners);self.players=defaultdict(Counter);self.team={t:Counter() for t in teams};self.lineups={};self.seconds=Counter();self.live_rebound=None;self.pending_assist=None;self.unavailable=set()
    def exclude(self,pid):
        if pid not in self.owners:raise ValueError('Unknown unavailable player')
        self.unavailable.add(pid)
    def set_lineup(self,team,players):
        if team not in self.team or len(set(players))!=5 or any(self.owners.get(p)!=team or p in self.unavailable for p in players):raise ValueError('Five distinct available owned players required')
        self.lineups[team]=tuple(players)
    def tick(self,seconds):
        if not 0<=seconds<=720 or set(self.lineups)!=set(self.teams):raise ValueError('Complete lineups and bounded interval required')
        for team,players in self.lineups.items():
            for p in players:self.seconds[p]+=seconds
    def credit(self,t,p,stat,n=1):
        if self.owners.get(p)!=t:raise ValueError('NBA player identity mismatch')
        if p in self.unavailable:raise ValueError('Unavailable NBA player credited')
        if self.lineups and p not in self.lineups.get(t,()):raise ValueError('Off-court player credited')
        self.players[p][stat]+=n;self.team[t][stat]+=n
    def shot(self,t,p,value,made,assist=None,block=None,at_buzzer=False):
        if value not in (2,3) or made and block is not None or assist==p:raise ValueError('Impossible shot/assist/block')
        if assist and not made:raise ValueError('Assist on a missed shot')
        for team,actor in [(t,p),(t,assist),(next(x for x in self.teams if x!=t),block)]:
            if actor and (self.owners.get(actor)!=team or actor in self.unavailable or self.lineups and actor not in self.lineups.get(team,())):raise ValueError('Invalid or off-court shot participant')
        self.credit(t,p,'fieldGoalAttempts');self.credit(t,p,'threePointAttempts',int(value==3));self.credit(t,p,'fieldGoalsMade',int(made));self.credit(t,p,'threePointersMade',int(made and value==3));self.credit(t,p,'points',value*int(made));self.live_rebound=None if made or at_buzzer else t
        if assist:
            if not made:raise ValueError('Assist on a missed shot')
            self.credit(t,assist,'assists')
        if block:self.credit(next(x for x in self.teams if x!=t),block,'blocks')
    def free_throw(self,t,p,made,last,technical=False):
        self.credit(t,p,'freeThrowAttempts');self.credit(t,p,'freeThrowsMade',int(made));self.credit(t,p,'points',int(made));self.live_rebound=t if last and not made and not technical else None
    def and_one(self,t,p,value,free_throw_made,assist=None):
        self.shot(t,p,value,True,assist=assist);self.free_throw(t,p,free_throw_made,True)
    def rebound(self,t,p,*,team_rebound=False):
        if self.live_rebound is None:raise ValueError('Rebound without a reboundable missed shot')
        stat='offensiveRebounds' if t==self.live_rebound else 'defensiveRebounds'
        if team_rebound:self.team[t]['team'+stat[0].upper()+stat[1:]]+=1
        else:self.credit(t,p,stat)
        self.live_rebound=None
    def turnover(self,t,p,steal=None):
        self.credit(t,p,'turnovers')
        if steal:self.credit(next(x for x in self.teams if x!=t),steal,'steals')
    def foul(self,t,p):self.credit(t,p,'fouls')
    def verify(self,seconds):
        for t,v in self.team.items():
            ids=[p for p,own in self.owners.items() if own==t]
            if abs(sum(self.seconds[p] for p in ids)-5*seconds)>1e-7:raise AssertionError('Five-player seconds budget failed')
            if v['points']!=2*v['fieldGoalsMade']+v['threePointersMade']+v['freeThrowsMade']:raise AssertionError('NBA scoring identity failed')
            if v['assists']>v['fieldGoalsMade'] or v['fieldGoalsMade']>v['fieldGoalAttempts'] or v['freeThrowsMade']>v['freeThrowAttempts']:raise AssertionError('Impossible NBA totals')
            for p in ids:
                s=self.players[p];s['rebounds']=s['offensiveRebounds']+s['defensiveRebounds'];s['minutes']=self.seconds[p]/60
                for stat,parts in [('pointsReboundsAssists',['points','rebounds','assists']),('pointsRebounds',['points','rebounds']),('pointsAssists',['points','assists']),('reboundsAssists',['rebounds','assists'])]:s[stat]=sum(s[k] for k in parts)
                n=sum(s[k]>=10 for k in ['points','rebounds','assists','steals','blocks']);s['doubleDouble']=int(n>=2);s['tripleDouble']=int(n>=3)
            if sum(self.players[p]['points'] for p in ids)!=v['points']:raise AssertionError('NBA player/team points mismatch')
        return True
