"""Evidence-only CFB PBP reconciliation. Never patches data to match a score.

Corrections require a unique independent down/field/quarter/action fingerprint.
Ambiguities remain missing. Original secondary records are never overwritten.
"""
from collections import defaultdict
import re,copy
from .replay import name_key,finite
def primary_actions(text,team_names,codes):
    active=False;period=1;team=None;records=[];current=None
    def finish():
        nonlocal current
        if current:records.append(current);current=None
    for line in text.splitlines():
        if re.search(r'Play\s*By\s*Play',line,re.I):active=True
        if not active:continue
        if not line.strip():finish();continue
        if current and (re.search(r'kickoff|kick attempt|\b\d+ plays,\s*\d+ yards',line,re.I) or re.search(r'^\s*(?:Team Statistics|Individual Statistics|Participation|Scoring Summary)',line,re.I)):finish()
        q=re.search(r'(?:Start of (?:Quarter #|the )?([1-4])|Start of (1st|2nd|3rd|4th) quarter|^\s*(1st|2nd|3rd|4th) Quarter\s*$)',line,re.I)
        if q:
            value=next(g for g in q.groups() if g);period=int(value[0])
        start=re.match(r'^\s*(.+?) (?:drive starts at|at)\s+(\d{1,2}:\d{2})',line,re.I)
        if start and name_key(start[1]) in team_names:finish();team=team_names[name_key(start[1])]
        m=re.match(r'^\s*([1-4])(?:-(?:\d+|G)|(?:st|nd|rd|th) and (?:\d+|Goal) at)\s+([A-Za-z]+)(\d+)\s+(.+)',line)
        if m and team:
            finish();down,field_team,yard,action=m.groups();home=codes.get(field_team)
            if home is None:continue
            field=100-int(yard) if home==team else int(yard);current={'team':team,'period':period,'down':int(down),'field':field,'action':action,'sourceLine':line.strip()}
        elif current and (line.startswith(' ') and not re.search(r'(?:Totals:|FIRST|SECOND|THIRD|FOURTH|RUSHING|PASSING|RECEIVING|Scoring|Team Statistics)',line)):current['action']+=' '+line.strip()
    finish()
    out=[]
    for r in records:
        r['action']=re.split(r'\(Original Play:',r['action'],flags=re.I)[0]
        a=r['action'].lower();verbs=[(a.find(v),k) for v,k in [('sacked','sack'),('kneel','kneel'),('pass ','pass'),('rush ','rush'),('field goal','field_goal'),('punt ','punt')] if v in a];kind=min(verbs)[1] if verbs else None
        if kind is None:continue
        no_play=bool(re.search(r'\bNO PLAY\b',r['action'],re.I));yards=None
        if kind=='sack':
            m=re.search(r'sacked for loss of (\d+) yards',a)
            if m:yards=-int(m[1])
        elif kind in ('pass','rush','kneel'):
            m=re.search(r'for (\d+) yards?(?: (gain|loss))?',a)
            if m:yards=int(m[1])*(-1 if m[2]=='loss' else 1)
            credited=re.search(r'for \d+ yards? (?:gain|loss)\s*\((-?\d+)\)',a)
            if credited:yards=int(credited[1])
            elif 'no gain' in a or kind=='pass' and ('incomplete' in a or 'intercept' in a):yards=0
        r.update(kind=kind,noPlay=no_play,yards=yards,complete=kind=='pass' and 'pass complete' in a,made=kind=='field_goal' and bool(re.search(r'\bgood\b',a)) and not bool(re.search(r'\bno good\b',a)))
        out.append(r)
    return out
def raw_kind(r):
    typ=str(r.get('type.text','')).lower()
    if r.get('sack') or r.get('yds_sacked') is not None:return 'sack'
    if re.search(r'\bspike\b',str(r.get('text','')),re.I):return 'spike'
    if r.get('kneel_down') or 'kneel' in str(r.get('text','')).lower():return 'kneel'
    if r.get('pass_attempt') or 'passing touchdown' in typ:return 'pass'
    if r.get('rush') or 'rushing touchdown' in typ:return 'rush'
    if r.get('fg_attempt') or 'field goal' in typ:return 'field_goal'
    if r.get('punt'):return 'punt'
    return None
def reconcile(raw,primary,source,players=None):
    index=defaultdict(list)
    for r in primary:index[(r['team'],r['period'],r['down'],r['field'],r['kind'])].append(r)
    aliases=defaultdict(set)
    for team,people in (players or {}).items():
        for pid,p in people.items():
            parts=p.get('name','').split()
            if parts:
                for name in [''.join(parts),''.join(parts[1:])+parts[0],parts[0][0]+''.join(parts[1:])]:aliases[(team,name_key(name))].add(pid)
    copied=[];proof=[];unmatched=[];raw_keys=set();unique_uses=defaultdict(list)
    for original in raw:
        r=copy.deepcopy(original);kind=raw_kind(r);team='cfb:espn:'+str(int(r['pos_team_id'])) if r.get('pos_team_id') is not None else None
        try:key=(team,int(r['period']),int(r['down']),int(r['start.yardsToEndzone']),kind)
        except (TypeError,KeyError,ValueError):copied.append(r);continue
        raw_keys.add(key)
        candidates=index.get(key,[])
        if not candidates and kind is None and str(r.get('type.text','')).lower()=='penalty':
            possible=[p for k,ps in index.items() if k[:4]==key[:4] for p in ps if 'PENALTY' in p['action'] and not p['noPlay'] and p['yards'] is not None]
            if len(possible)==1:candidates=possible;kind=possible[0]['kind'];key=(*key[:4],kind)
        if len(candidates)>1 and r.get('end.yardsToEndzone') is not None:
            gain=finite(r['start.yardsToEndzone'])-finite(r['end.yardsToEndzone']);bounded=[p for p in candidates if p['yards']==gain]
            if len(bounded)==1:candidates=bounded
        # Repeated fingerprints are accepted only when their independently
        # printed accounting statements agree; no outcome selects the match.
        signatures={(p['noPlay'],p['yards'],p['complete']) for p in candidates}
        if candidates and len(signatures)==1:
            p=candidates[0];patch={'noPlay':p['noPlay'],'kind':kind,'complete':p['complete'],'yards':p['yards'],'made':p['made']}
            head=re.split(r'\b(?:pass|rush|sacked|kneel)\b',p['action'],maxsplit=1,flags=re.I)[0];head=re.sub(r'^(?:\([^)]*\)\s*)?(?:(?:No Huddle-)?Shotgun\s+|No Huddle\s+|Pistol\s+|Under Center\s+)*','',head,flags=re.I);head=re.sub(r'^#\d+\s*','',head).strip();identity=aliases.get((key[0],name_key(head)),set())
            if len(identity)==1:patch['actorId']=next(iter(identity));patch['actorIdentityProof']='Unique printed full-name/initial+surname, team, down/spot, official final roster ID; Mode A only'
            r['_primaryAccounting']=patch;r['_primarySource']=source;proof.append({'playId':str(r['id']),'fingerprint':list(key),'primaryStatement':p['sourceLine'],'matchingStatements':len(candidates),'correction':patch,'source':source})
            if len(candidates)==1:unique_uses[key].append(r)
        elif kind:unmatched.append({'playId':str(r['id']),'fingerprint':list(key),'candidateStatements':len(candidates)})
        copied.append(r)
    duplicates=[]
    for key,rs in unique_uses.items():
        if len(rs)<2 or len({r.get('clock.displayValue') for r in rs})!=1:continue
        preferred=max(rs,key=lambda r:(sum(r.get(k) is not None for k in ['passer_player_id','receiver_player_id','rusher_player_id']),len(r.get('text',''))))
        for r in rs:
            if r is preferred:continue
            r['_duplicateOf']=str(preferred['id']);duplicates.append({'discardedSecondaryEvent':str(r['id']),'canonicalSecondaryEvent':str(preferred['id']),'primaryStatement':index[key][0]['sourceLine'],'reason':'One primary action, two same-clock secondary IDs; richer identity record retained'})
    inserted=[]
    # Explicit NCAA spike missing from the secondary stream. Its printed
    # actor does not receive a personal attempt: NCAA credits TEAM instead.
    for p in primary:
        if p['kind']!='pass' or not re.search(r'\bspike\b',p['action'],re.I):continue
        team=p['team'];q=p['period'];m=re.search(r'^\((\d+:\d\d)\)',p['action'])
        if not m or any(re.search(r'\bspike\b',r.get('text',''),re.I) and int(r.get('period',0))==q and str(int(r.get('pos_team_id') or 0))==team.split(':')[-1] for r in raw):continue
        record={'game_id':int(raw[0]['game_id']),'id':'primary-spike:'+str(len(inserted)),'period':q,'pos_team_id':int(team.split(':')[-1]),'down':p['down'],'start.yardsToEndzone':p['field'],'clock.displayValue':m[1],'type.text':'Pass Incompletion','pass_attempt':True,'text':p['action'],'_primarySource':source,'adapterOrderIsNotProviderSequence':True};copied.append(record);inserted.append({'sourceLine':p['sourceLine'],'adapterEventId':record['id'],'reason':'Explicit printed NCAA TEAM spike missing from secondary stream','source':source})
    for key,statements in index.items():
        if key in raw_keys or any(k[0]==key[0] and k[1]==key[1] and k[-1]=='field_goal' for k in raw_keys) or key[-1]!='field_goal' or len({(p['made'],p['sourceLine']) for p in statements})!=1:continue
        p=statements[0];m=re.search(r'clock\s+(\d+:\d\d)',p['action'],re.I)
        if not m:continue
        # A real printed play missing from the secondary feed. Adapter order
        # is explicitly distinct from provider sequence IDs.
        team,q,down,field,kind=key;record={'game_id':int(raw[0]['game_id']),'id':'primary-book:'+str(len(inserted)), 'period':q,'pos_team_id':int(team.split(':')[-1]),'down':down,'start.yardsToEndzone':field,'clock.displayValue':m[1],'type.text':'Field Goal Good' if p['made'] else 'Field Goal Missed','fg_attempt':True,'fg_made':p['made'],'text':p['action'],'_primaryAccounting':{'noPlay':False,'kind':kind,'complete':False,'yards':0,'made':p['made']},'_primarySource':source,'providerSequenceInvented':False,'adapterOrderIsNotProviderSequence':True};copied.append(record);inserted.append({'sourceLine':p['sourceLine'],'adapterEventId':record['id'],'reason':'Printed primary event absent from secondary play stream','source':source})
    return copied,{'verifiedStatements':proof,'duplicateSecondaryEvents':duplicates,'insertedPrimaryEvents':inserted,'unmatchedOrAmbiguous':unmatched,'source':source,'scoreOrFinalTotalsUsedForMatching':False,'originalRecordsChanged':False}
