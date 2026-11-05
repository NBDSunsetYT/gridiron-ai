"""Outcome-only lineup constraint reconstruction for historical exposures.

No inferred lineup is a pregame starter announcement. A quarter's substitutions
and participating player IDs constrain possible five-player lineups. Only board
exposures identical across all surviving paths are called identified.
"""
from itertools import combinations
from collections import defaultdict
import re,math
import numpy as np
VERSION='identified-on-court-rebound-exposure-21.0.0'
def player_id(v):return str(int(v)) if v is not None and not (isinstance(v,float) and math.isnan(v)) else None
def game_exposures(game,events):
    teams=list(game['teams']);rosters={t:sorted(player_id(p['athlete_id']) for p in game['players'] if str(p['team_id'])==t and float(p.get('minutes') or 0)>0) for t in teams};owner={p:t for t,ids in rosters.items() for p in ids}
    if len(owner)!=sum(map(len,rosters.values())):raise ValueError('Ambiguous outcome player ownership')
    if any(not 5<=len(ids)<=18 for ids in rosters.values()):raise ValueError('Bounded, complete historical roster required')
    def clock_value(r):
        m,s=str(r['clock_display_value']).split(':');return float(m)*60+float(s)
    # Corrected plays can retain an older numeric sequence ID. Period/clock is
    # the primary temporal order; sequence breaks ties at a stopped clock.
    events=sorted(events,key=lambda r:(int(r['period_number']),-clock_value(r),int(r['sequence_number'])));quarters=sorted({int(r['period_number']) for r in events})
    if quarters[:4]!=[1,2,3,4]:raise ValueError('Complete regulation play sequencing required')
    board_rows=[];minute_bounds=defaultdict(lambda:np.zeros(2));unidentified=0;actual=defaultdict(lambda:defaultdict(int));maximum_paths=0
    for period in quarters:
      period_events=[r for r in events if int(r['period_number'])==period];duration=720 if period<=4 else 300
      for team in teams:
        ids=rosters[team];bit={p:1<<i for i,p in enumerate(ids)};starters=[player_id(p['athlete_id']) for p in game['players'] if str(p['team_id'])==team and p.get('starter') and float(p.get('minutes') or 0)>0]
        if period==1 and len(starters)!=5:raise ValueError('Five actual first-quarter starters required for exposure grading')
        masks=np.asarray([sum(bit[p] for p in starters)] if period==1 else [sum(bit[p] for p in group) for group in combinations(ids,5)],dtype=np.uint64);maximum_paths=max(maximum_paths,len(masks));origins=np.arange(len(masks));integrals=np.zeros((len(masks),len(ids)));snapshots=[];previous=duration
        for r in period_events:
            clock=str(r['clock_display_value']);parts=clock.split(':');remaining=float(parts[0])*60+float(parts[1])
            if not 0<=remaining<=previous:raise ValueError('Nonmonotonic/out-of-period clock sequence')
            elapsed=previous-remaining
            for j in range(len(ids)):integrals[origins,j]+=elapsed*((masks&(1<<j))!=0)
            previous=remaining;text=r['text'] or '';typ=(r.get('type_text') or '').lower();a=player_id(r.get('athlete_id_1'));b=player_id(r.get('athlete_id_2'))
            if 'substitution' in typ or 'enters the game for' in text:
                if 'enters the game for' not in text:raise ValueError('Unrecognized substitution semantics')
                # ESPN athlete 1 enters for athlete 2; verify both against team.
                if a not in owner or b not in owner:raise ValueError('Unmapped substitution identity')
                if owner[a]!=owner[b]:raise ValueError('Substitution crosses team identity')
                if owner[a]==team:
                    valid=((masks&bit[b])!=0)&((masks&bit[a])==0);masks=masks[valid];origins=origins[valid];masks=(masks^bit[b])|bit[a]
            else:
                required=[] if 'technical' in typ or 'eject' in typ else [player_id(r.get('athlete_id_'+str(i))) for i in (1,2,3)];required=[p for p in required if p in owner and owner[p]==team]
                if required:
                    want=sum({bit[p] for p in required});valid=(masks&want)==want;masks=masks[valid];origins=origins[valid]
            if not len(masks):raise ValueError('No lineup satisfies participation/substitution sequence: '+str((team,period,r['id'],text)))
            isboard=('offensive rebound' in text.lower() or 'defensive rebound' in text.lower()) and a in owner
            if isboard:
                values=np.zeros(integrals.shape[0],dtype=np.uint64);values[origins]=masks;offensive='offensive rebound' in text.lower();shooting=owner[a] if offensive else next(t for t in teams if t!=owner[a]);snapshots.append((str(r['id']),values,'offensive_rebounds' if team==shooting else 'defensive_rebounds',a,offensive))
                if owner[a]==team:actual[a]['offensive_rebounds' if offensive else 'defensive_rebounds']+=1
        if previous>0:raise ValueError('Quarter-end clock evidence missing')
        for j,p in enumerate(ids):
            values=integrals[origins,j]/60
            minute_bounds[p]+=np.asarray([values.min(),values.max()])
        for eid,values,kind,actor,offensive in snapshots:
            candidates=np.unique(values[origins]);identified=len(candidates)==1
            if not identified:unidentified+=1;continue
            board_rows.append({'eventId':eid,'team':team,'kind':kind,'players':[p for p in ids if int(candidates[0])&bit[p]],'rebounder':actor,'offensive':offensive,'period':period})
    counts=defaultdict(lambda:defaultdict(int))
    for r in board_rows:
        for p in r['players']:counts[p][r['kind']]+=1
    for p in game['players']:
        pid=player_id(p['athlete_id'])
        if float(p.get('minutes') or 0)<=0:continue
        for stat in ['offensive_rebounds','defensive_rebounds']:
            if actual[pid][stat]!=int(p.get(stat) or 0):raise ValueError('Play-by-play rebounds do not reconcile with verified player box')
    return {'version':VERSION,'gameId':game['id'],'outcomeOnly':True,'identifiedBoardTeamEvents':len(board_rows),'unidentifiedBoardTeamEvents':unidentified,'complete':unidentified==0,'maximumQuarterLineupPaths':maximum_paths,'players':{p:{'exposure':dict(counts[p]),'actualRebounds':dict(actual[p]),'identifiedMinutes':float(minute_bounds[p][0]) if np.ptp(minute_bounds[p])<1e-8 else None,'minuteBounds':minute_bounds[p].tolist()} for p in owner},'boardEvents':board_rows,'lineupInterpretation':'Actual historical on-court outcome constraints, never a pregame starting-lineup claim.'}
