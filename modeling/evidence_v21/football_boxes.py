"""CFB historical accounting repair from separately published final box tables.

This does not assign anonymous PBP passes to a guessed starting quarterback.
It reconstructs completed historical appearances using exact event/team/player
IDs. Callers must embargo those completed appearances before making forecasts.
Original PBP archives and frozen predictions are never changed.
"""
from collections import defaultdict,Counter
from datetime import timedelta
import math
from ..accuracy_v20.quality import aware
from ..overnight_v20.data import FOOTBALL

def number(v):
    if v is None:raise ValueError('Missing actual box statistic')
    x=float(str(v).replace(',',''))
    if not math.isfinite(x):raise ValueError('Non-finite box statistic')
    return x
def pair(v):
    a=str(v).split('/')
    if len(a)!=2:raise ValueError('Exact completions/attempts required')
    c,n=map(number,a)
    if not 0<=c<=n:raise ValueError('Invalid completions/attempts')
    return c,n
def repaired_packet(original,players,teams):
    gid=original['id'];numeric=gid.split(':')[-1];out={k:v for k,v in original.items() if k!='teams'};out['teams']={};checks=[]
    tr={}
    for r in teams:
        if str(int(r['game_id']))!=numeric:raise ValueError('Cross-event team box')
        t='cfb:espn:'+str(int(r['team_id']))
        if t in tr:raise ValueError('Duplicate team box')
        tr[t]=r
    if set(tr)!={original['home'],original['away']}:raise ValueError('Team box identity mismatch')
    grouped=defaultdict(list)
    for r in players:
        if str(int(r['game_id']))!=numeric:raise ValueError('Cross-event player box')
        t='cfb:espn:'+str(int(r['team_id']))
        if t not in tr:raise ValueError('Player box team identity mismatch')
        if r['category'] in ('passing','rushing','receiving'):grouped[t].append(r)
    for team,t in tr.items():
        ps={};credited=defaultdict(float);seen=set()
        for r in grouped[team]:
            pid='cfb:espn:'+str(int(r['athlete_id'])) if r.get('athlete_id') is not None else None;name=str(r.get('athlete_name',''));category=r['category']
            if (pid,category) in seen:raise ValueError('Duplicate player/category box')
            seen.add((pid,category));stats={}
            if category=='passing':
                c,n=pair(r['completions/passingAttempts']);stats={'passingAttempts':n,'passingYards':number(r['passingYards']),'completions':c}
            elif category=='rushing':stats={'carries':number(r['rushingAttempts']),'rushingYards':number(r['rushingYards'])}
            elif category=='receiving':stats={'receptions':number(r['receptions']),'receivingYards':number(r['receivingYards'])}
            # TEAM IDs can repeat across opponents. They are not real players
            # and must never share a game-wide player bucket.
            if pid is None or int(pid.split(':')[-1])<=0 or name.strip().lower()=='team':
                for k,v in stats.items():credited[k]+=v
                continue
            p=ps.setdefault(pid,{'stats':{s:0. for s in FOOTBALL},'starter':None,'name':name})
            for k,v in stats.items():p['stats'][k]=v
            # Target counts are not supplied by this box dataset. Retain only
            # the explicitly labeled legacy reference, never mark it verified.
            p['stats']['targets']=original['teams'][team]['players'].get(pid,{}).get('stats',{}).get('targets',0.)
        c,n=pair(t['completionAttempts']);totals={'passingAttempts':n,'passingYards':number(t['netPassingYards']),'receptions':c,'receivingYards':number(t['netPassingYards']),'carries':number(t['rushingAttempts']),'rushingYards':number(t['rushingYards'])}
        for stat,target in totals.items():
            total=sum(v['stats'].get(stat,0.) for v in ps.values())+credited.get(stat,0.)
            if abs(total-target)>1e-7:raise ValueError('Official player/team box does not reconcile: '+team+' '+stat)
            checks.append({'team':team,'stat':stat,'sum':total,'teamBox':target})
        previous=original['teams'][team]['totals'];totals.update(targets=previous['targets'],score=previous['score'],plays=n+totals['carries'],dropbacks=previous['dropbacks'])
        out['teams'][team]={'players':ps,'totals':totals,'opponent':original['teams'][team]['opponent'],'unassignedTeamCredits':dict(credited)}
    out['boxRepair']={'checks':checks,'historicalCorrectionAvailability':'unverified_original_publication','verifiedCountingStatistics':True,'unknownPlayerPassesAssignedToStarter':False,'targetsAndDropbacksVerified':False,'startingLineupVerified':False,'sourceRole':'Published ESPN-derived final player/team box tables; historical outcomes only'};return out

def earlier_packets(packets,cutoff):
    """Current/future final stats cannot enter a pregame historical feature set."""
    return [g for g in packets if aware(g['end'])+timedelta(hours=6)<aware(cutoff)]

def completion_evidence(packets,cutoff):
    """Unbiased team C/ATT counts, including anonymous-PBP incompletions.

    Not a state-conditioned probability model or a calibrated win forecast.
    The downstream simulator must validate a fitted play model separately.
    """
    totals=defaultdict(lambda:[0.,0.]);used=[]
    for g in earlier_packets(packets,cutoff):
        if not g.get('boxRepair',{}).get('verifiedCountingStatistics'):continue
        used.append(g['id'])
        for t,row in g['teams'].items():
            k=sum(p['stats'].get('completions',0.) for p in row['players'].values())+row['unassignedTeamCredits'].get('completions',0.);n=row['totals']['passingAttempts']
            if not 0<=k<=n:raise ValueError('Team pass-completion counts invalid')
            totals[t][0]+=k;totals[t][1]+=n
    return {'cutoff':cutoff,'games':used,'teamCompletionCounts':dict(totals),'incompleteUnknownPassersDropped':False,'probabilitiesPublished':False}
