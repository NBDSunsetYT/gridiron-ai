"""Join V21 reconciled CFB counts and censored clocks into the state engine."""
from collections import defaultdict
from datetime import timedelta
import copy
import numpy as np
from ..accuracy_v20.quality import aware
from ..evidence_v21.football_boxes import completion_evidence,earlier_packets
from ..evidence_v21.protection import assert_unexposed
from ..football_v15 import Predictor,numeric
from ..overnight_v20.state import digest
from .clock import serialize_clock
from .football import VERSION

def anonymous_play_credits(rows,eligible_ids):
    """Unidentified snap credits, distinct from reconciled official box totals.

    A game-level QB box total does not identify an anonymous individual snap.
    These counters are provenance, never added to box totals a second time.
    """
    credits=defaultdict(lambda:defaultdict(lambda:defaultdict(float)))
    for r in rows:
        if r['game'] not in eligible_ids or r['kind']!='pass':continue
        raw=str(r.get('qb') or '').split(':')[-1]
        if raw.isdigit() and int(raw)>0:continue
        c=credits[r['o']][r['game']];c['passingAttempts']+=1;c['completions']+=int(bool(r['complete']));c['passingYards']+=float(r['yards']) if r['complete'] else 0.
    return {team:{gid:dict(v) for gid,v in games.items()} for team,games in credits.items()}

def completion_offset(probabilities,target):
    """Binomial intercept bridge on complete-vs-incomplete outcomes only.

    Sack/interception probabilities and all state/identity slopes remain
    unchanged. Target is earlier official C/(ATT-INT), never a game outcome.
    """
    p=np.asarray(probabilities,float)
    if len(p)<20 or not np.all(np.isfinite(p)) or np.any((p<=0)|(p>=1)) or not 0<target<1:raise ValueError('Supported earlier conditional completion cohort required')
    from scipy.special import expit,logit
    z=logit(p);lo,hi=-30.,30.
    for _ in range(80):
        mid=(lo+hi)/2
        if np.mean(expit(z+mid))<target:lo=mid
        else:hi=mid
    offset=(lo+hi)/2
    if abs(np.mean(expit(z+offset))-target)>1e-7:raise ValueError('Official completion target cannot be reconciled')
    return offset

class CorrectedDropback:
    def __init__(self,wrapped,offsets,teams):self.wrapped=wrapped;self.offsets=offsets;self.teams=teams
    def adjust(self,p,teams):
        from scipy.special import expit,logit
        p=np.array(p,copy=True);classes=self.wrapped.a['classes'];ci=classes.index(3);ii=classes.index(2);total=p[:,ci]+p[:,ii]
        for team in set(teams):
            use=np.array(teams)==team
            if team not in self.offsets:raise ValueError('Official completion offset unavailable for '+str(team))
            if np.any(total[use]<=0):raise ValueError('Completion bridge has no conditional pass mass')
            q=p[use,ci]/total[use];adjusted=expit(logit(np.clip(q,1e-12,1-1e-12))+self.offsets[team]);p[use,ci]=total[use]*adjusted;p[use,ii]=total[use]*(1-adjusted)
        return p
    def fast(self,x,off,participant=None,probabilities=False):return self.adjust(self.wrapped.fast(x,off,participant,probabilities),[self.teams[int(i)] for i in off])
    def probabilities(self,x,offense,defense,participant=None):return self.adjust(self.wrapped.probabilities(x,offense,defense,participant),list(offense))

def integrate(base,packets,clock,cutoff,protected,play_rows=None,interceptions=None):
    if base['sport']!='CFB':raise ValueError('CFB accounting cannot be transferred into NFL or NBA')
    assert_unexposed(base.get('trainingGameIds',[]),protected)
    if aware(base['asOf'])>=aware(cutoff):raise ValueError('State model must precede integration cutoff')
    eligible=[g for g in earlier_packets(packets,cutoff) if g['id'] not in protected and g.get('boxRepair',{}).get('verifiedCountingStatistics')];ids={g['id'] for g in eligible};assert_unexposed(ids,protected)
    if len(eligible)<12:raise ValueError('At least twelve reconciled historical games required')
    m=copy.deepcopy(base);m['version']=VERSION;m['asOf']=cutoff;m['fittingCutoff']=cutoff;m['histories']={};totals=defaultdict(lambda:defaultdict(float));credits=defaultdict(dict);m['gameSeasons']={g['id']:g['season'] for g in eligible};offsets={};failure=[]
    for g in eligible:
        for team,t in g['teams'].items():
            if team not in m['teams']:continue
            h={'at':g['end'],'qb':{},'receiver':{},'runner':{}}
            for pid,p in t['players'].items():
                if int(pid.split(':')[-1])<=0:raise ValueError('Anonymous TEAM identity in individual opportunity pool')
                for role,stat in [('qb','passingAttempts'),('receiver','targets'),('runner','carries')]:
                    if p['stats'].get(stat,0)>0:h[role][pid]=p['stats'][stat]
                totals[team]['completions']+=p['stats'].get('completions',0)
            m['histories'].setdefault(team,{})[g['id']]=h;credits[team][g['id']]=dict(t['unassignedTeamCredits'])
            for stat in ['passingAttempts','passingYards','carries','rushingYards','plays']:totals[team][stat]+=t['totals'][stat]
            totals[team]['completions']+=t['unassignedTeamCredits'].get('completions',0)
    # No anonymous attempts enter an individual QB history. Separate team
    # credits remain inspectable even when their count is nonzero.
    m['historicalUnassignedTeamCredits']=dict(credits);m['historicalUnassignedPlayCredits']=anonymous_play_credits(play_rows or [],ids);m['reconciledTeamCounts']={t:dict(v) for t,v in totals.items()};m['censoredClock']=serialize_clock(clock)
    rows=[r for r in (play_rows or []) if r['game'] in ids and r['kind'] in ('pass','sack') and aware(r['at'])<aware(cutoff)]
    if rows and interceptions:
        pred=Predictor(m['dropback']);classes=m['dropback']['classes'];by=defaultdict(list)
        for r in rows:by[r['o']].append(r)
        for team,rs in by.items():
            if team not in totals or len(rs)<20:continue
            x=numeric(*[np.array([r[k] for r in rs]) for k in ('down','distance','field','clock','script','home')]);pr=pred.probabilities(x,np.array([r['o'] for r in rs]),np.array([r['d'] for r in rs]),np.array([r['qb'] for r in rs]));c=totals[team]['completions'];n=totals[team]['passingAttempts'];ints=interceptions.get(team)
            if ints is None:failure.append(team+':interception_count_missing');continue
            # Jeffreys finite-logit continuity correction, declared before fit.
            target=(c+.5)/(n-ints+1.)
            if c>n-ints:failure.append(team+':inconsistent_completion_interception_totals');continue
            try:offsets[team]=completion_offset(pr[:,classes.index(3)]/(pr[:,classes.index(3)]+pr[:,classes.index(2)]),target)
            except ValueError as e:failure.append(team+':'+str(e))
    m['completionOffsets']=offsets;m['integrationAudit']={'reconciledGames':len(eligible),'historicalCountsSource':'Separate ESPN-derived final player/team boxes','anonymousAttemptsAssignedToQB':False,'teamCreditsPreserved':True,'clockSource':clock.metadata,'fullClockGateResolved':False,'completionOffsetTeams':len(offsets),'completionOffsetFailures':failure,'unresolved':['Administrative runoff distribution','NCAA live-ball versus between-play timing / two-minute-warning state','Targets and sack/dropback coverage','Overtime possession/stat distribution validation','Pregame publication, availability, lineup and model-uncertainty evidence'],'productionEligible':False};m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});return m
