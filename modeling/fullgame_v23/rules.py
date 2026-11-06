"""Versioned football/basketball mechanics, separate from fitted probabilities."""
from dataclasses import dataclass,field
from ..evidence_v21.rules import first_down_clock
RULE_SOURCES={
 'NFL2024':'https://operations.nfl.com/media/24emxacq/2024-nfl-rulebook.pdf',
 'NFL2025':'https://operations.nfl.com/media/ntif5hxb/2025-nfl-rulebook-final.pdf',
 'CFB':'https://www.ncaapublications.com/productdownloads/FR24.pdf',
 'CFBstatistics':'https://fs.ncaa.org/Docs/stats/Stats_Manuals/Football.pdf',
 'NBA':'https://official.nba.com/rule-no-3-players-substitutes-and-coaches/',
 'NBAclock':'https://official.nba.com/rule-no-5-scoring-and-timing/' }

def dead_ball_enforcement(field,yards,defense=False):
    """Ordinary distance penalty, half-distance when prescribed; no DPI guess."""
    if not 0<field<100 or yards<=0:raise ValueError('Supported spot and distance penalty required')
    available=field if defense else 100-field;enforced=min(float(yards),available/2)
    return field-enforced if defense else field+enforced,enforced

def runoff_seconds(sport,reason,period,remaining,clock_running,timeout_used=False,opponent_accepts=True):
    if sport not in ('NFL','CFB') or reason not in ('injury','foul'):raise ValueError('Unsupported runoff scenario')
    limit=120 if sport=='NFL' and reason=='injury' else 60
    if period not in (2,4) or remaining>limit or not clock_running or timeout_used or not opponent_accepts:return 0
    return min(10,remaining)

def try_required(scores,side,clock=None,overtime=None):
    """No extra point after a game-ending TD when the try cannot affect it."""
    if overtime is not None:
        old_nfl=overtime.sport=='NFL' and not (overtime.season>=2025 or overtime.postseason and overtime.season>=2022)
        if old_nfl and overtime.turns==0:return False
        second_or_sudden=overtime.turns>=1 if overtime.sport=='NFL' else overtime.turns%2==1
        if second_or_sudden and scores[side]>scores[1-side]:return False
        return True
    if clock and clock.period==4 and clock.remaining==0 and abs(scores[0]-scores[1])>2:return False
    return True

@dataclass
class RegulationClock:
    sport:str
    season:int
    period:int=1
    remaining:float=None
    elapsed:float=0.
    period_charges:list=field(default_factory=list)
    warning_taken:bool=False
    pending_warning:bool=False
    running:bool=False
    def __post_init__(self):
        if self.sport not in ('NFL','CFB','NBA'):raise ValueError('Unknown ruleset')
        self.length=720 if self.sport=='NBA' else 900
        if self.remaining is None:self.remaining=float(self.length)
    def advance(self,seconds,*,kind='play',verified=False):
        if self.period>4 or not 0<=seconds<=self.remaining or kind not in ('play','running','administrative','runoff'):raise ValueError('Clock charge crosses period or is invalid')
        if kind=='running' and not self.running:raise ValueError('A stopped clock cannot burn between-play runoff')
        if kind in ('administrative','runoff') and not verified:raise ValueError('Administrative/runoff charge needs explicit evidence or an identified conditional scenario')
        if kind=='runoff' and seconds not in (0,min(10,self.remaining)):raise ValueError('Unsupported explicit runoff')
        old=self.remaining;self.remaining-=seconds;self.elapsed+=seconds
        if self.sport!='NBA' and self.period in (2,4) and (self.sport=='NFL' or self.season>=2024) and not self.warning_taken and old>=120 and self.remaining<=120:self.pending_warning=True
    def take_warning(self):
        if not self.pending_warning:raise ValueError('No two-minute warning is due')
        self.warning_taken=True;self.pending_warning=False
    def runoff(self,reason,clock_running,timeout_used=False,opponent_accepts=True):
        amount=runoff_seconds(self.sport,reason,self.period,self.remaining,clock_running,timeout_used,opponent_accepts)
        if amount:self.advance(amount,kind='runoff',verified=True)
        return amount
    def first_down_rule(self):
        if self.sport=='NBA':raise ValueError('Football rule requested for basketball')
        return first_down_clock(self.sport,self.season,self.period,int(self.remaining),self.warning_taken if self.season>=2024 else None)
    def next_period(self):
        if self.remaining!=0 or self.period>4:raise ValueError('Cannot skip unaccounted regulation time')
        self.period_charges.append(self.length);self.period+=1
        self.running=False
        if self.period<=4:self.remaining=float(self.length)
        if self.period==3:self.warning_taken=False;self.pending_warning=False
    def verify_complete(self):
        if self.period!=5 or self.elapsed!=4*self.length or self.period_charges!=[self.length]*4:raise AssertionError('Incomplete regulation clock')

@dataclass
class FootballOvertime:
    sport:str
    season:int
    postseason:bool=False
    first:int=0
    period:int=1
    turns:int=0
    remaining:float=None
    score:list=field(default_factory=lambda:[0,0])
    finished:bool=False
    def __post_init__(self):
        if self.sport not in ('NFL','CFB') or self.first not in (0,1):raise ValueError('Unsupported overtime')
        self.remaining=None if self.sport=='CFB' else float(900 if self.postseason else 600)
    @property
    def shooter_period(self):return 3 if self.season>=2021 else 5 if self.season>=2019 else None
    @property
    def shootout(self):return self.sport=='CFB' and self.shooter_period is not None and self.period>=self.shooter_period
    @property
    def requires_two(self):return self.sport=='CFB' and self.period>=(2 if self.season>=2021 else 3)
    @property
    def offense(self):return self.first if self.turns%2==0 else 1-self.first
    def finish_possession(self,offense,points,elapsed=0,defense_points=0):
        if self.finished or offense!=self.offense or points<0 or defense_points<0:raise ValueError('Out-of-order or invalid overtime possession')
        if self.shootout and (points not in (0,2) or elapsed):raise ValueError('NCAA shootout is an untimed try, not an ordinary drive')
        if self.sport=='CFB' and elapsed:raise ValueError('NCAA overtime has no game clock')
        if self.sport=='NFL':
            if not 0<=elapsed<=self.remaining:raise ValueError('NFL overtime clock exhausted')
            self.remaining-=elapsed
        self.score[offense]+=points;self.score[1-offense]+=defense_points;self.turns+=1
        both=self.turns>=2;new_rule=self.season>=2025 or self.postseason and self.season>=2022
        if defense_points>0 or self.sport=='NFL' and self.turns==1 and not new_rule and points>=6:self.finished=True
        elif self.sport=='NFL' and both and self.score[0]!=self.score[1]:self.finished=True
        elif self.sport=='NFL' and self.remaining==0:
            if not self.postseason:self.finished=True
            else:self.remaining=900.
        elif self.sport=='CFB' and self.turns%2==0:
            if self.score[0]!=self.score[1]:self.finished=True
            else:self.period+=1;self.first=1-self.first
        return self.finished
