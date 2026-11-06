"""Sequence-preserving CFB clock observations; scores never enter the model."""
from collections import defaultdict
import re
from .clock import seconds,regulation_clock
def kind(r):
    typ=str(r.get('type.text','')).lower();text=str(r.get('text','')).lower()
    if any(x in typ for x in ['kickoff','extra point','two point','timeout','end period','end of','start period']):return None
    if 'no play' in text and 'penalty' in text:return 'administrative'
    if 'kneel' in typ:return 'kneel'
    if r.get('sack'):return 'sack'
    if r.get('pass_attempt'):return 'pass'
    if r.get('rush'):return 'rush'
    if 'punt' in typ:return 'punt'
    if 'field goal' in typ:return 'field_goal'
    if 'penalty' in typ:return 'administrative'
    return None
def blocks_from_rows(rows,games):
    grouped=defaultdict(list);result=[];rejected=[]
    for r in rows:grouped[(str(int(r['game_id'])),str(r['drive.id']))].append(r)
    for (gid,drive),rs in grouped.items():
        event='cfb:espn:'+gid
        if event not in games:continue
        rs.sort(key=lambda r:int(r['sequenceNumber']));first=rs[0]
        try:
            q0=int(first['drive.start.period.number']);q1=int(first['drive.end.period.number']);start=seconds(first['drive.start.clock.displayValue']);end=seconds(first['drive.end.clock.displayValue']);elapsed=seconds(first['drive.timeElapsed.displayValue']);delta=regulation_clock(q0,start)-regulation_clock(q1,end)
            if elapsed!=delta or not 0<elapsed<=900:raise ValueError('Drive elapsed and boundary clocks conflict')
            plays=[];starts=[]
            for r in rs:
                k=kind(r)
                if not k:continue
                if k=='administrative':raise ValueError('Administrative no-play runoff not independently resolved')
                q=int(r['period.number']);c=seconds(r['clock.displayValue']);p={'kind':k,'complete':bool(r.get('completion')),'hurry':q in (2,4) and c<=120,'period':q,'clock':c,'id':str(int(r['id'])),'down':int(r['start.down']),'field':int(r['start.yardsToEndzone'])};plays.append(p);starts.append(regulation_clock(q,c))
            if not plays or len(plays)>60:raise ValueError('Supported bounded offensive sequence unavailable')
            team=str(int(first['start.team.id']))
            # Kickoff rows can belong to the incoming drive but to its opponent.
            owner=next(str(int(r['pos_team_id'])) for r in rs if kind(r) in ('rush','pass','sack','kneel'))
            if owner not in (games[event]['home'].split(':')[-1],games[event]['away'].split(':')[-1]):raise ValueError('Drive owner identity mismatch')
            # Reported clocks have mixed start/end conventions. Keep adjacent
            # positive inter-event observations as a prior, never label them
            # measured physical snap lengths. Drive totals provide constraints.
            gaps=[a-b for a,b in zip([regulation_clock(q0,start)]+starts[:-1],starts)]
            coherent=all(1<=d<=90 for d in gaps) and sum(gaps)==elapsed
            result.append({'id':event+':drive:'+drive,'eventId':event,'eventEnd':games[event]['lastObservedAt'],'teamId':'cfb:espn:'+owner,'teamAbbreviation':first['homeTeamAbbrev'] if owner==games[event]['home'].split(':')[-1] else first['awayTeamAbbrev'],'period':q0,'endPeriod':q1,'startClock':start,'endClock':end,'elapsedSeconds':elapsed,'plays':plays,'exactIntervals':None,'observedInterEventIntervals':gaps,'providerRecordedIntervals':gaps,'sequenceVerified':False,'anchorVerified':False,'sources':[],'measurementStatus':'positive_source_sequence' if coherent else 'coarsened_interval_censored'})
        except (ValueError,TypeError,KeyError,StopIteration) as e:rejected.append({'eventId':event,'driveId':drive,'reason':str(e)})
    return result,rejected
def name_key(value):
    return re.sub('[^a-z0-9]','',value.lower())
def official_team_codes(layout_text,team_names):
    """Only explicit adjacent team headings establish printed code identity."""
    result={};current=None
    for line in layout_text.splitlines():
        if 'Drive Chart' in line:current=None
        key=name_key(line)
        if key in team_names:current=team_names[key]
        m=re.match(r'^\s*([A-Za-z][A-Za-z0-9]{1,6})\s+(?:1st|2nd|3rd|4th)\s+[A-Za-z]+\d+\s+\d{1,2}:\d{2}',line)
        if m and current:
            code=m[1]
            if code in result and result[code]!=current:raise ValueError('Conflicting printed team identity')
            result[code]=current
    return result
def official_drive_rows(layout_text,team_names=None):
    rows=[];last={};current=None;codes=official_team_codes(layout_text,team_names or {});pattern=re.compile(r'^\s*([A-Z][A-Z0-9]{1,6})\s+(?:(1st|2nd|3rd|4th)\s+)?[A-Z]+\d+\s+(\d{1,2}:\d{2})\s+.*?[A-Z]+\d+\s+(\d{1,2}:\d{2})\s+.*?\s+(\d+)\s*-\s*(-?\d+)\s+(\d{1,2}:\d{2})\s*$',re.I)
    for line in layout_text.splitlines():
        if 'Drive Chart' in line:current=None
        if name_key(line) in (team_names or {}):current=team_names[name_key(line)]
        m=pattern.match(line)
        if m:
            team,q,start,end,plays,yards,total=m.groups();team=codes.get(team,team)
            # A second unlabeled summary page can interleave both teams and
            # omit quarter labels. It cannot inherit the previous team section.
            if team_names and (current is None or current!=team):continue
        else:
            m=re.match(r'^\s*(1st|2nd|3rd|4th)\s+[A-Za-z]+\d+\s+(\d{1,2}:\d{2})\s+\S+\s+[A-Za-z]+\d+\s+(\d{1,2}:\d{2})\s+\S+\s+(\d+)-(-?\d+)\s+(\d{1,2}:\d{2})\s*$',line)
            if not m or not current:continue
            q,start,end,plays,yards,total=m.groups();team=current
        if q:last[team]=int(q[0])
        if team not in last:continue
        rows.append({'team':team,'period':last[team],'start':seconds(start),'end':seconds(end),'elapsed':seconds(total),'printedPlayCount':int(plays),'line':line.strip()})
    unique={tuple(r[k] for k in ['team','period','start','end','elapsed','printedPlayCount']):r for r in rows}
    return list(unique.values())
def official_sequences(pages,team_names,team_codes=None):
    """Read printed down/field/action order, independently of ESPN IDs/clocks."""
    drives=[];current=None;period=None;codes=team_codes or {};in_pbp=False
    for text in pages:
        if re.search(r'Play\s*By\s*Play(?: report)?',text,re.I):in_pbp=True
        if not in_pbp:continue
        for line in text.splitlines():
            q=re.search(r'^\s*(1st|2nd|3rd|4th)\s+Quarter\s*$',line,re.I)
            if not q:q=re.search(r'Start of (1st|2nd|3rd|4th) quarter',line,re.I)
            if q:period=int(q[1][0])
            start=re.search(r'^\s*(.+?) drive starts at (\d{1,2}:\d{2})',line,re.I)
            if not start:
                start=re.match(r'^\s*(.+?) at (\d{1,2}:\d{2})\s*$',line)
            if start:
                name=re.sub('[^a-z0-9]','',start[1].lower());team=team_names.get(name);current={'team':team,'period':period,'start':seconds(start[2]),'plays':[]};drives.append(current)
            m=re.match(r'^\s*([1-4])(?:-(?:\d+|G)|(?:st|nd|rd|th) and (?:\d+|Goal) at)\s+([A-Za-z]+)(\d+)\s+(.+)',line)
            if not m or current is None:continue
            down,field_team,yard,action=m.groups();a=action.lower();k='sack' if 'sacked' in a else 'kneel' if 'kneel' in a else 'pass' if 'pass ' in a else 'rush' if 'rush ' in a else 'punt' if 'punt ' in a else 'field_goal' if 'field goal' in a else 'administrative' if 'penalty' in a else 'unresolved'
            if 'drive start' in a or 'kickoff' in a or 'kick attempt' in a:continue
            field_team=codes.get(field_team,field_team)
            field=100-int(yard) if field_team==current['team'] else int(yard);current['plays'].append({'down':int(down),'field':field,'kind':k})
    return drives
def verify_book(blocks,book_rows,source,sequences=None):
    accepted=[];unmatched=[]
    for b in blocks:
        candidates=[r for r in book_rows if (r['team'],r['period'],r['start'],r['end'],r['elapsed'])==(b['teamAbbreviation'],b['period'],b['startClock'],b['endClock'],b['elapsedSeconds'])]
        if len(candidates)!=1:unmatched.append({'blockId':b['id'],'reason':'Independent gamebook clock anchor not uniquely matched'});continue
        row=candidates[0];sequence=[s for s in sequences or [] if (s['team'],s['period'],s['start'])==(b['teamAbbreviation'],b['period'],b['startClock'])];tokens=[{k:p[k] for k in ['down','field','kind']} for p in b['plays']];verified=len(sequence)==1 and sequence[0]['plays']==tokens
        accepted.append({**b,'sequenceVerified':verified,'anchorVerified':True,'sources':[source],'printedPlayCount':row['printedPlayCount'],'playCountDiscrepancy':len(b['plays'])-row['printedPlayCount'],'exactIndividualTimesClaimed':False,'sequenceReason':None if verified else 'Printed independent down/field/action sequence is missing or does not reconcile'})
    return accepted,unmatched

def clock_accounting(pages,drive_rows,team_codes=None):
    """Independent elapsed-clock conservation; never fits scores or invents plays."""
    by=defaultdict(lambda:defaultdict(int));spans=[];problems=[];codes=team_codes or {}
    for r in drive_rows:
        start=(4-r['period'])*900+r['start'];end=start-r['elapsed']
        if end<0 or end>start:problems.append('Invalid regulation drive boundary');continue
        for q in range(1,5):by[r['team']][q]+=max(0,min(start,(5-q)*900)-max(end,(4-q)*900))
        spans.append((end,start,r['team']))
    overlaps=[{'teams':[a[2],b[2]],'seconds':min(a[1],b[1])-max(a[0],b[0])} for i,a in enumerate(spans) for b in spans[i+1:] if min(a[1],b[1])>max(a[0],b[0])]
    full={};printed_quarters=defaultdict(dict)
    for text in pages:
        lines=text.splitlines();header=next((re.match(r'^\s*(?:FULL GAME|Team Statistics)\s+([A-Za-z0-9]+)\s+([A-Za-z0-9]+)\s*$',l) for l in lines if re.match(r'^\s*(?:FULL GAME|Team Statistics)\s+([A-Za-z0-9]+)\s+([A-Za-z0-9]+)\s*$',l)),None)
        if header:
            teams=[codes.get(header[i],header[i]) for i in (1,2)]
            for line in lines:
                m=re.match(r'^\s*(?:Total offense plays|Plays)\s+(\d+)\s+(\d+)\s*$',line,re.I)
                if m:
                    for t,n in zip(teams,m.groups()):full.setdefault(t,{})['offensivePlays']=int(n)
                m=re.match(r'^\s*Possession Time\s+(\d+:\d+)\s+(\d+:\d+)\s*$',line)
                if m:
                    for t,v in zip(teams,m.groups()):full.setdefault(t,{})['timeOfPossession']=seconds(v)
                m=re.match(r'^\s*(1st|2nd|3rd|4th) Quarter\s+(\d+:\d+)\s+(\d+:\d+)\s*$',line)
                if m:
                    for t,v in zip(teams,m.groups()[1:]):printed_quarters[t][int(m[1][0])]=seconds(v)
        quarter=next((re.match(r'^\s*(FIRST|SECOND|THIRD|FOURTH) QUARTER\s+([A-Za-z0-9]+)\s+([A-Za-z0-9]+)\s*$',l) for l in lines if re.match(r'^\s*(FIRST|SECOND|THIRD|FOURTH) QUARTER\s+([A-Za-z0-9]+)\s+([A-Za-z0-9]+)\s*$',l)),None)
        if quarter:
            q=['FIRST','SECOND','THIRD','FOURTH'].index(quarter[1])+1
            for line in lines:
                m=re.match(r'^\s*Possession Time\s+(\d+:\d+)\s+(\d+:\d+)\s*$',line)
                if m:
                    for t,v in zip([codes.get(quarter[i],quarter[i]) for i in (2,3)],m.groups()):printed_quarters[t][q]=seconds(v)
    quarters=[{'period':q,'driveChargedSeconds':sum(d.get(q,0) for d in by.values()),'unassignedRegulationSeconds':900-sum(d.get(q,0) for d in by.values()),'printedPossessionSeconds':sum(d.get(q,0) for d in printed_quarters.values()) if any(q in d for d in printed_quarters.values()) else None} for q in range(1,5)]
    return {'independentDriveCount':len(drive_rows),'driveElapsedSeconds':sum(r['elapsed'] for r in drive_rows),'regulationSeconds':3600,'quarters':quarters,'overlappingDriveIntervals':overlaps,'printedTeamTotals':full,'printedQuarterTOP':dict(printed_quarters),'teamDriveChargedSeconds':{t:sum(qs.values()) for t,qs in by.items()},'boundaryProblems':problems,'meaning':'Drive intervals partition regulation game clock. Unassigned time may include kickoffs; it is reported rather than silently allocated. Offensive play totals exclude punts/field goals.'}
