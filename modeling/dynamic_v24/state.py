"""Forward-only observable workload and game-flow state, not physiology.

Snapshots are taken BEFORE observing an outcome. Updates never consume final
box totals, later substitutions, final scores, EP/WP model outputs or markets.
"""
from collections import Counter,defaultdict,deque
from copy import deepcopy
import math

class DynamicState:
    def __init__(self,sport,teams,prior=None):
        if sport not in ('NFL','CFB','NBA') or len(set(teams))!=2:raise ValueError('Explicit league and two teams required')
        self.sport=sport;self.teams=tuple(teams);self.score=Counter();self.players=defaultdict(Counter);self.team=defaultdict(Counter);self.recent={t:deque(maxlen=8) for t in teams};self.actor_recent=defaultdict(lambda:deque(maxlen=8));self.drives={t:deque(maxlen=3) for t in teams};self.prior=prior or {};self.period=1;self.remaining=720 if sport=='NBA' else 900;self.elapsed=0.;self.last_team=None;self.drive_snaps=0;self.possessions=Counter();self.lineups={};self.unavailable=set();self.seen=set();self.player_seconds=Counter();self.stints=Counter();self.last_exit={};self.version=0
    def set_lineup(self,team,players):
        players=tuple(players)
        if self.sport!='NBA' or team not in self.teams or len(set(players))!=5 or any(p in self.unavailable for p in players):raise ValueError('Five available on-court players required')
        before=set(self.lineups.get(team,()))
        for p in before-set(players):self.last_exit[p]=self.elapsed;self.stints[p]=0
        for p in set(players)-before:self.stints[p]=0
        self.lineups[team]=players;self.version+=1
    def tick(self,period,remaining):
        length=720 if self.sport=='NBA' and period<=4 else 300 if self.sport=='NBA' else 900
        if period<self.period or not 0<=remaining<=length:raise ValueError('Invalid event period/clock')
        elapsed=(period-1)*720+720-remaining if self.sport=='NBA' and period<=4 else 2880+(period-5)*300+300-remaining if self.sport=='NBA' else (period-1)*900+900-remaining
        if elapsed<self.elapsed-1e-6:raise ValueError('Clock revision needs a new rebuilt snapshot')
        dt=elapsed-self.elapsed
        if self.sport=='NBA':
            for court in self.lineups.values():
                for p in court:self.player_seconds[p]+=dt;self.stints[p]+=dt
        self.period=period;self.remaining=remaining;self.elapsed=elapsed
    def features(self,offense,*,down=1,distance=10,field=50,actor=None):
        if offense not in self.teams:raise ValueError('Team identity mismatch')
        defense=next(t for t in self.teams if t!=offense);remaining=max(0,(2880 if self.sport=='NBA' else 3600)-self.elapsed);r=list(self.recent[offense]);other=list(self.recent[defense]);p=self.players[actor] if actor is not None else Counter();lag=self.prior.get(offense,{})
        base={'score_diff':float(self.score[offense]-self.score[defense]),'remaining':remaining,'period':self.period,'down':down,'distance':distance,'field':field,'late_trailing':float(remaining<300 and self.score[offense]<self.score[defense]),'team_prior_efficiency':float(lag.get('efficiency',0)),'opponent_prior_efficiency':float(self.prior.get(defense,{}).get('efficiency',0)),'observed_possessions':self.possessions[offense],'lineup_known':float(offense in self.lineups) if self.sport=='NBA' else 0,'workload_drive_snaps':self.drive_snaps,'workload_actor_actions':p['actions'],'workload_defensive_actions':self.team[defense]['defending_actions'],'workload_actor_minutes':self.player_seconds[actor]/60 if actor else 0,'workload_consecutive_minutes':self.stints[actor]/60 if actor else 0,'workload_fouls':p['fouls'],'workload_rest_since_exit':max(0,self.elapsed-self.last_exit.get(actor,self.elapsed))/60 if actor else 0,'workload_missing_full_personnel':float(self.sport!='NBA')}
        dynamic={'recent_success':sum(v['success'] for v in r)/max(1,len(r)),'recent_explosives':sum(v['explosive'] for v in r),'recent_turnovers':sum(v['turnover'] for v in r),'recent_sacks':sum(v['sack'] for v in r),'recent_penalties':sum(v['penalty'] for v in r),'recent_efficiency':sum(v['gain'] for v in r)/max(1,len(r)),'recent_defensive_efficiency':sum(v['gain'] for v in other)/max(1,len(other)),'recent_scoring_drives':sum(self.drives[offense]),'recent_defensive_stops':sum(not x for x in self.drives[defense]),'recent_field_change':sum(v['fieldChange'] for v in r),'recent_actor_attempts':len(self.actor_recent[actor]) if actor else 0,'recent_actor_successes':sum(self.actor_recent[actor]) if actor else 0,'fatigue_drive_square':self.drive_snaps**2,'fatigue_stint_square':(self.stints[actor]/60)**2 if actor else 0,'fatigue_volume_interaction':p['actions']*self.drive_snaps}
        return base,dynamic
    def observe(self,event):
        required=('id','team','kind')
        if any(k not in event for k in required) or event['team'] not in self.teams:raise ValueError('Owned, identified event required')
        if event['id'] in self.seen:return False
        actor=event.get('actor');team=event['team'];other=next(t for t in self.teams if t!=team)
        if actor in self.unavailable:raise ValueError('Unavailable actor; rebuild lineup assumptions')
        if self.sport=='NBA' and actor and team in self.lineups and actor not in self.lineups[team]:raise ValueError('Off-court action')
        for k in ('points','gain'):
            if not math.isfinite(event.get(k,0)):raise ValueError('Non-finite outcome')
        self.seen.add(event['id']);self.version+=1
        if self.last_team!=team:self.drive_snaps=0
        self.last_team=team;self.drive_snaps+=1;self.team[team]['actions']+=1;self.team[other]['defending_actions']+=1
        if actor:
            p=self.players[actor];p['actions']+=1;p['fouls']+=int(event['kind']=='foul');self.actor_recent[actor].append(int(bool(event.get('success'))))
        self.score[team]+=event.get('points',0);gain=event.get('gain',0)
        self.recent[team].append({'success':int(bool(event.get('success'))),'explosive':int(abs(gain)>=20) if self.sport!='NBA' else 0,'turnover':int(bool(event.get('turnover'))),'sack':int(event['kind']=='sack'),'penalty':int(event['kind']=='penalty'),'gain':gain,'fieldChange':event.get('fieldChange',0)})
        if event.get('possessionEnd'):self.possessions[team]+=1;self.drives[team].append(int(event.get('driveScored',event.get('points',0)>0)));self.drive_snaps=0
        return True
    def snapshot(self):
        return deepcopy({'sport':self.sport,'teams':self.teams,'score':dict(self.score),'period':self.period,'remaining':self.remaining,'elapsed':self.elapsed,'version':self.version,'lineups':self.lineups,'unavailable':sorted(self.unavailable),'workloadInterpretation':'Observed actions/time proxies, not measured physiological fatigue','fullPersonnelKnown':self.sport=='NBA' and len(self.lineups)==2})
