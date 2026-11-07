"""Mode A final-evidence replay; no pregame probability or accuracy outputs."""
from collections import Counter,defaultdict
import re,math
from .accounting import FootballLedger,FootballPlay,team_actor
from .modes import Mode,label

def finite(v,default=0):
    try:return float(v) if math.isfinite(float(v)) else default
    except (TypeError,ValueError):return default
def pid(v,sport):
    if v is None or v=='':return None
    if sport=='NFL':return str(v)
    try:return 'cfb:espn:'+str(int(v)) if int(v)>0 else None
    except (ValueError,TypeError):return None
def name_key(v):return re.sub('[^a-z0-9]','',str(v).lower())
def clock_seconds(v):
    m,s=str(v).split(':');return int(m)*60+float(s)

def ordered_rows(rows,sport):
    """Keep provider order. Insert primary-only events at explicit clock anchors.

    No sequence IDs or exact unknown physical durations are synthesized.
    Equal-clock original events retain their source order.
    """
    key='play_id' if sport=='NFL' else 'sequenceNumber'
    base=sorted([r for r in rows if not r.get('adapterOrderIsNotProviderSequence')],key=lambda r:finite(r.get(key)))
    for r in [r for r in rows if r.get('adapterOrderIsNotProviderSequence')]:
        q=int(r['period']);c=clock_seconds(r['clock.displayValue']);at=len(base)
        for i,other in enumerate(base):
            oq=int(other.get('period') or 0)
            if oq>q or oq==q and clock_seconds(other['clock.displayValue'])<c:at=i;break
        base.insert(at,r)
    return base

def clock_audit(rows,sport):
    periods=defaultdict(list);order='play_id' if sport=='NFL' else 'sequenceNumber';zero=0;backward=0;unknown=[]
    for r in ordered_rows(rows,sport):
        q=int(r.get('qtr' if sport=='NFL' else 'period',0) or 0)
        if not 1<=q<=4:continue
        try:c=float(r['quarter_seconds_remaining']) if sport=='NFL' else clock_seconds(r['clock.displayValue'])
        except (KeyError,ValueError,TypeError):unknown.append(str(r.get('id',r.get('play_id'))));continue
        if not 0<=c<=900:raise ValueError('Invalid source quarter clock')
        periods[q].append(c)
    for q,seq in periods.items():
        deltas=[a-b for a,b in zip(seq,seq[1:])];zero+=sum(x==0 for x in deltas);backward+=sum(x<0 for x in deltas)
    anchors={q:{'first':seq[0],'last':seq[-1],'span':seq[0]-seq[-1]} for q,seq in periods.items()};span=sum(v['span'] for v in anchors.values());complete=set(periods)=={1,2,3,4} and all(v['first']==900 and v['last']==0 for v in anchors.values()) and not backward and not unknown
    return {'regulationPeriodsObserved':sorted(periods),'sourceQuarterAnchors':anchors,'observedAnchoredSeconds':span,'ruleBoundaryBudgetSeconds':3600,'boundaryConservation':complete,'coarsenedOrStoppedIntervals':zero,'backwardSourceIntervals':backward,'missingClockRows':unknown,'individualPhysicalDurationsIdentified':False,'administrativeZeroAssumed':False,'interpretation':'Actual source boundary anchors only. Presence of four quarters alone is not conservation proof. Equal/coarsened labels do not prove zero physical duration or identify administrative runoff.'}

def football_replay(raw,game,box,ctx):
    if ctx['mode']!=Mode.MECHANICS:raise ValueError('Final boxes cannot enter a pregame path')
    sport=ctx['sport'];teams=(game['away'],game['home']);owners={p:t for t,v in box['teams'].items() for p in v['players']};names=defaultdict(set)
    for t,v in box['teams'].items():
        for p,rec in v['players'].items():
            if rec.get('name'):
                names[(t,name_key(rec['name']))].add(p);parts=rec['name'].split()
                if len(parts)>1:names[(t,name_key(''.join(parts[1:])+parts[0]))].add(p)
    ledger=FootballLedger(sport,teams,owners);unknown=Counter();resolutions=[];seen=set();accepted=[];rejected=[];scoring=[];drives=set();duplicate=0;last_period={};order='play_id' if sport=='NFL' else 'sequenceNumber'
    def actor(r,key,team):
        value=pid(r.get(key+'_player_id'),sport)
        if value and owners.get(value)==team:return value
        # Exact full-name prefix only, verified against this game's box roster.
        # This is OUTCOME replay identity resolution, never pregame evidence.
        text=r.get('text','');verb='pass' if key=='passer' else 'run' if key=='rusher' else None
        text=re.sub(r'^(?:\([^)]*\)\s*)?(?:(?:No Huddle-)?Shotgun\s+|No Huddle\s+|Pistol\s+|Under Center\s+)*','',text,flags=re.I)
        match=re.match(r'^(.+?)\s+'+verb+r'\b',text,re.I) if verb else None
        vals=names.get((team,name_key(match[1])),set()) if match else set()
        if len(vals)==1:
            found=next(iter(vals));resolutions.append({'sourcePlay':str(r.get('id',r.get('play_id'))),'player':found,'method':'exact full-name text prefix + official final box identity; Mode A only'});return found
        unknown[(team,key)]+=1;return None
    for r in ordered_rows(raw,sport):
        uid=str(r.get('play_id' if sport=='NFL' else 'id'));signature=str(r)
        if r.get('_duplicateOf'):duplicate+=1;continue
        if uid in seen:duplicate+=1;continue
        seen.add(uid);team=r.get('posteam') if sport=='NFL' else pid(r.get('pos_team_id'),'CFB');defense=next((t for t in teams if t!=team),None);typ=str(r.get('play_type' if sport=='NFL' else 'type.text','')).lower();period=int(finite(r.get('qtr' if sport=='NFL' else 'period')));drive=r.get('fixed_drive' if sport=='NFL' else 'drive.id')
        if team in teams and drive is not None:drives.add((str(drive),team))
        if team not in teams:continue
        # The derived college `penalty_negated_play` incorrectly marks some
        # completed, credited plays followed by enforcement. Do not nullify
        # them unless the explicit no-play field/text establishes it.
        no_play=bool(r.get('no_play')) if sport=='NFL' else bool(r.get('penalty_no_play')) or bool(re.search(r'\bNO PLAY\b',r.get('text',''),re.I))
        primary=r.get('_primaryAccounting')
        if primary is not None:no_play=primary['noPlay']
        if no_play:
            accepted.append(uid);continue
        is_try=bool(r.get('two_point_attempt') or r.get('extra_point_attempt')) if sport=='NFL' else ('two point' in typ or 'two-point' in typ or 'extra point' in typ or period>=7)
        if is_try:
            if sport=='NFL':points=1 if r.get('extra_point_result')=='good' else 2 if r.get('two_point_conv_result')=='success' else 0
            else:points=int(finite(r.get('pointAfterAttempt.value'))) if r.get('scoringPlay') else 0;points=2 if ('two' in typ or period>=7) and r.get('scoringPlay') else points
            ledger.apply(FootballPlay('administrative',team,is_try=True,conversion_points=points));continue
        sack=bool(r.get('sack'));spike=bool(r.get('qb_spike')) if sport=='NFL' else bool(r.get('spike'));kneel=bool(r.get('qb_kneel' if sport=='NFL' else 'kneel_down'));pas=bool(r.get('pass_attempt')) or sport=='CFB' and typ=='passing touchdown';rush=bool(r.get('rush_attempt' if sport=='NFL' else 'rush')) or sport=='CFB' and typ=='rushing touchdown';fg=bool(r.get('field_goal_attempt' if sport=='NFL' else 'fg_attempt'));punt=bool(r.get('punt_attempt' if sport=='NFL' else 'punt'));kind='sack' if sack else 'spike' if spike else 'kneel' if kneel else 'pass' if pas else 'rush' if rush else 'field_goal' if fg else 'punt' if punt else 'administrative'
        if sport=='CFB' and r.get('yds_sacked') is not None:kind='sack'
        if sport=='CFB' and re.search(r'\bspike\b',r.get('text',''),re.I):kind='spike'
        if sport=='CFB' and 'field goal' in typ:kind='field_goal'
        if primary is not None:kind=primary['kind']
        comp=bool(r.get('complete_pass' if sport=='NFL' else 'completion')) or sport=='CFB' and typ=='passing touchdown';interception=bool(r.get('interception' if sport=='NFL' else 'int'));td=bool(r.get('touchdown'));off_td=td and (kind in ('pass','rush') and (sport=='CFB' and r.get('offense_score_play') or sport=='NFL' and r.get('td_team')==team));points_before={t:ledger.team[t]['points'] for t in teams}
        if sport=='NFL':
            yards=finite(r.get('passing_yards')) if kind=='pass' and comp else finite(r.get('rushing_yards')) if kind in ('rush','kneel') else finite(r.get('yards_gained')) if sack else 0
            if kind=='spike':yards=0
        else:yards=finite(r.get('yds_receiving')) if kind=='pass' else finite(r.get('yds_sacked')) if sack else finite(r.get('yds_rushed'))
        if primary is not None:
            comp=primary['complete']
            if primary['yards'] is not None:yards=primary['yards']
        qb=actor(r,'passer',team) if kind in ('pass','spike','sack') else None;receiver=actor(r,'receiver',team) if comp else None;runner=actor(r,'rusher',team) if kind in ('rush','kneel') else None
        if primary and primary.get('actorId'):
            if kind in ('pass','sack'):qb=primary['actorId']
            elif kind=='rush':runner=primary['actorId']
        split=()
        if sport=='NFL' and r.get('lateral_reception'):
            lateral=pid(r.get('lateral_receiver_player_id'),sport);ly=finite(r.get('lateral_receiving_yards'));initial=finite(r.get('receiving_yards'))
            if lateral not in owners:rejected.append({'id':uid,'reason':'unmapped_lateral_receiver'});continue
            split=((receiver,initial),(lateral,ly));yards=initial+ly
        try:
            made=primary['made'] if primary is not None else r.get('field_goal_result')=='made' if sport=='NFL' else bool(r.get('fg_made')) or typ=='field goal good'
            ledger.apply(FootballPlay(kind,team,int(yards),qb,receiver,runner,comp,interception,bool(r.get('fumble_lost' if sport=='NFL' else 'pos_fumble_lost')),off_td,bool(r.get('safety') if sport=='NFL' else r.get('penalty_safety')),made=made,receiving_credits=split))
            if td and not off_td:
                score_team=r.get('td_team') if sport=='NFL' else team if r.get('offense_score_play') else defense
                if score_team not in teams:raise ValueError('Unmapped return touchdown team')
                ledger.team[score_team]['points']+=6;ledger.team[score_team]['returnTouchdowns']+=1
            if sport=='CFB' and td:
                xp=int(finite(r.get('pointAfterAttempt.value')))
                if xp not in (0,1,2):raise ValueError('Unrecognized combined try')
                score_team=team if r.get('offense_score_play') else defense;ledger.apply(FootballPlay('administrative',score_team,is_try=True,conversion_points=xp))
            accepted.append(uid)
        except (ValueError,AssertionError) as e:rejected.append({'id':uid,'reason':str(e)})
        if any(ledger.team[t]['points']!=points_before[t] for t in teams):scoring.append({'id':uid,'period':period,'points':{t:ledger.team[t]['points']-points_before[t] for t in teams},'kind':typ})
    ledger.verify();comparisons=[];player_comparisons=[]
    for t,v in box['teams'].items():
        for stat in ['passingAttempts','passingYards','completions','carries','rushingYards','receptions','receivingYards']:
            truth=v['totals'].get(stat)
            if truth is None:continue
            observed=ledger.team[t][stat];comparisons.append({'team':t,'stat':stat,'replayed':observed,'reference':truth,'equal':observed==truth})
        for p,rec in v['players'].items():
            for stat in ['passingAttempts','passingYards','completions','carries','rushingYards','receptions','receivingYards']:
                if stat in rec['stats'] and (rec['stats'][stat]!=0 or ledger.players[p][stat]!=0):player_comparisons.append({'team':t,'player':p,'stat':stat,'replayed':ledger.players[p][stat],'reference':rec['stats'][stat],'equal':ledger.players[p][stat]==rec['stats'][stat]})
    scores={t:ledger.team[t]['points'] for t in teams};expected={t:box['teams'][t]['totals']['score'] for t in teams}
    return label({'gameId':game['id'],'scores':scores,'referenceScores':expected,'scoreReconciled':scores==expected,'teamComparisons':comparisons,'playerComparisons':player_comparisons,'teamAccountingReconciled':all(r['equal'] for r in comparisons),'playerAccountingReconciled':all(r['equal'] for r in player_comparisons),'unassignedIdentityCounts':[{'team':t,'role':k,'count':n} for (t,k),n in unknown.items()],'exactTextIdentityResolutions':resolutions,'rejectedPlays':rejected,'duplicateEventIds':duplicate,'driveIdentityPairs':len(drives),'clock':clock_audit(raw,sport),'scoringEvents':scoring,'team':{t:dict(v) for t,v in ledger.team.items()},'players':{p:dict(v) for p,v in ledger.players.items()},'completeAccountingReplay':scores==expected and all(r['equal'] for r in comparisons+player_comparisons) and not rejected,'participationInterpretation':'Actual final-game participants, not a pregame lineup claim'},ctx)

def football_book_totals(text,sport,teams):
    """Parse the final team-stat page, not a first-half summary or a final score prior."""
    rows={};patterns={'rushingYards':r'NET YARDS RUSHING\s+(-?\d+)\s+(-?\d+)','passingYards':r'Gross yards passing\s+(-?\d+)\s+(-?\d+)' if sport=='NFL' else r'NET YARDS PASSING\s+(-?\d+)\s+(-?\d+)','offensivePlays':r'Total Offensive Plays[^\n]*?\s+(\d+)\s+(\d+)\s*$' if sport=='NFL' else r'Total offense plays\s+(\d+)\s+(\d+)'}
    for stat,pattern in patterns.items():
        m=re.search(pattern,text,re.I|re.M)
        if m:rows[stat]={t:int(v) for t,v in zip(teams,m.groups())}
    pattern=r'PASS ATTEMPTS-COMPLETIONS-HAD INTERCEPTED\s+(\d+)-(\d+)-(\d+)\s+(\d+)-(\d+)-(\d+)' if sport=='NFL' else r'Completions-Attempts-Int\s+(\d+)-(\d+)-(\d+)\s+(\d+)-(\d+)-(\d+)'
    m=re.search(pattern,text,re.I)
    if m:
        vals=list(map(int,m.groups()))
        for i,t in enumerate(teams):
            first,second,ints=vals[i*3:i*3+3]
            for stat,value in [('passingAttempts',first if sport=='NFL' else second),('completions',second if sport=='NFL' else first),('interceptions',ints)]:rows.setdefault(stat,{})[t]=value
    return rows

def nba_book_players(text,away,home):
    # PDF extractors preserve different whitespace between the report title
    # and the quarter heading. Quarter-only rows must never overwrite FINAL
    # BOX rows when constructing the official player/minute reference.
    first=re.split(r"OFFICIAL SCORER'S REPORT\s*1st\s+QUARTER",text,maxsplit=1,flags=re.I)[0];team=None;out=[];columns=['fieldGoalsMade','fieldGoalAttempts','threePointersMade','threePointAttempts','freeThrowsMade','freeThrowAttempts','offensiveRebounds','defensiveRebounds','rebounds','assists','fouls','steals','turnovers','blocks','plusMinus','points']
    for line in first.splitlines():
        if line.startswith('VISITOR:'):team=away
        if line.startswith('HOME:'):team=home
        m=re.match(r'^\s*\d+\s+(.+?)\s+(?:[FCG-]+\s+)?(\d+:\d\d)\s+((?:-?\d+\s+){15}-?\d+)\s*$',line)
        if m and team:
            out.append({'team':team,'name':m[1].strip(),'seconds':clock_seconds(m[2]),'stats':dict(zip(columns,map(int,m[3].split())))})
    if len(out)<10:raise ValueError('Incomplete official NBA final player table')
    if len({(p['team'],name_key(p['name'])) for p in out})!=len(out):raise ValueError('Repeated official NBA player rows; full-game and period tables cannot be combined')
    return out
