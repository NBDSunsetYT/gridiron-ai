"""Bounded official evidence collection. No private endpoints or invented dates."""
import json,gzip,hashlib,re,io,time,unicodedata
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from collections import defaultdict
import pdfplumber
from pypdf import PdfReader
from ..structural_v18.data import archives
from ..iterative_learning import freeze_json
from ..reconstruction_v19.evidence import aware
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'artifacts/overnight-v20'
def norm(s):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower())
def fetch(url):
    key=hashlib.sha256(url.encode()).hexdigest();receipt=OUT/'sources/receipts'/(key+'.json')
    if receipt.exists():
        r=json.loads(receipt.read_text());return (gzip.decompress((ROOT/r['object']).read_bytes()) if r.get('object') else None),r
    r={'url':url,'retrievedAt':datetime.now(timezone.utc).isoformat()}
    try:
        with urlopen(Request(url,headers={'User-Agent':'GRIDIRON-AI-Public-Research/20'}),timeout=20) as response:
            b=response.read(8000001)
            if len(b)>8000000:raise ValueError('Public source exceeds 8 MB cap')
            sha=hashlib.sha256(b).hexdigest();p=OUT/'sources/objects'/(sha+'.gz');p.parent.mkdir(parents=True,exist_ok=True)
            if not p.exists():p.write_bytes(gzip.compress(b,compresslevel=3,mtime=0))
            r.update(httpStatus=response.status,finalUrl=response.url,sha256=sha,object=str(p.relative_to(ROOT)),bytes=len(b),lastModified=response.headers.get('Last-Modified'),etag=response.headers.get('ETag'))
    except HTTPError as e:b=None;r.update(httpStatus=e.code)
    except Exception as e:b=None;r.update(error=type(e).__name__)
    freeze_json(receipt,r);time.sleep(.12);return b,r

def protocol():return json.load((OUT/('protocol-effective.json' if (OUT/'protocol-effective.json').exists() else 'protocol.json')).open())
_IDENTITIES={}
def earlier_names(sport,g):
    if sport not in _IDENTITIES:
        data=archives(sport);index=defaultdict(dict)
        for row in (data.values() if sport=='NBA' else data['games'].values()):
            at=aware(row['at'] if sport=='NBA' else row['lastObservedAt'])+timedelta(hours=6)
            for p in (row['players'] if sport=='NBA' else row['players'].values()):
                pid=str(int(p['athlete_id'])) if sport=='NBA' else None
                if sport!='NBA':continue
                key=norm(p['athlete_display_name']);index[key][pid]=min(at,index[key].get(pid,at))
            if sport!='NBA':
                for pid,p in row['players'].items():
                    key=(p['team'],norm(p.get('name','')));index[key][pid]=min(at,index[key].get(pid,at))
        _IDENTITIES[sport]=dict(index)
    names=defaultdict(set);cutoff=aware(g['at'])
    for key,ids in _IDENTITIES[sport].items():
        if sport!='NBA' and key[0] not in (g['home'],g['away']):continue
        label=key if sport=='NBA' else key[1]
        names[label].update(pid for pid,at in ids.items() if at<cutoff)
    return names

def nfl_evidence():
    import pyarrow.parquet as pq
    p=ROOT/'artifacts/parallel-v19/sources/injuries_2024.parquet';rows=pq.read_table(p).to_pylist();source=json.load((ROOT/'artifacts/parallel-v19/sources/injuries_2024.receipt.json').open());facts=[];coverage={}
    for g in protocol()['selection']['NFL']:
        cutoff=aware(g['at'])-timedelta(minutes=30);week=int(g['id'].split('_')[1]);accepted=[]
        for r in rows:
            if int(r['season'])!=g['season'] or int(r['week'])!=week or r['team'] not in (g['home'],g['away']) or not r['date_modified']:continue
            published=aware(r['date_modified'])
            if published>=cutoff:continue
            fact={'sport':'NFL','eventId':g['id'],'teamId':r['team'],'playerId':r['gsis_id'],'name':r['full_name'],'position':r['position'],'status':r['report_status'] or 'unspecified','practice':r['practice_status'],'source':source['url'],'publishedAt':published.isoformat(),'retrievedAt':source['retrievedAt'],'sourceVersion':source['sha256'],'confidence':'provider_timestamped_report','originalOfficialDocumentArchived':False,'cutoff':cutoff.isoformat()};accepted.append(fact);facts.append(fact)
        coverage[g['id']]={'reportedPlayers':len(accepted),'explicitOut':sum(f['status']=='Out' for f in accepted),'confirmedCompleteLineup':False,'missingIsHealthy':False}
    return {'facts':facts,'coverage':coverage,'unavailable2025':'Provider injury records have no original per-record publication time. Current file retrieval never supplies one.'}

def nba_rows(data):
    records=[];state={'date':None,'matchup':None,'team':None};report_time=None
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text=page.extract_text() or '';m=re.search(r'Injury\s*Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{1,2}:\d{2}\s*[AP]M)',text)
            if m:report_time=datetime.strptime(m[1]+' '+re.sub(r'\s+',' ',m[2]),'%m/%d/%y %I:%M %p').replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat()
            words=page.extract_words();labels=['GameDate','GameTime','Matchup','Team','PlayerName','CurrentStatus','Reason'];headers={w['text']:w for w in words if w['text'] in labels}
            if len(headers)!=7:continue
            starts=[headers[k]['x0']-1 for k in labels];top=max(w['bottom'] for w in headers.values());lines=defaultdict(list)
            for w in words:
                if w['top']>top+1:lines[round(w['top']/2)*2].append(w)
            for y,ws in sorted(lines.items()):
                cells=['']*7
                for w in sorted(ws,key=lambda w:w['x0']):
                    col=max((i for i,x in enumerate(starts) if w['x0']>=x),default=0);cells[col]+=(' ' if cells[col] else '')+w['text']
                date,clock,match,team,name,status,reason=cells
                if re.fullmatch(r'\d{2}/\d{2}/\d{4}',date):state['date']=datetime.strptime(date,'%m/%d/%Y').date().isoformat()
                if re.fullmatch(r'[A-Z]{2,4}@[A-Z]{2,4}',match):state['matchup']=match;state['team']=None
                if team and not re.search(r'Page\s*\d',team):state['team']=team
                if ',' in name and status in ['Out','Doubtful','Questionable','Probable','Available'] and state['team'] and state['date']:
                    last,first=name.split(',',1);records.append({**state,'name':first+' '+last,'status':status,'reason':reason})
                elif 'NOTYETSUBMITTED' in norm(name+status+reason).upper():records.append({**state,'status':'not_yet_submitted'})
    return records,report_time

def nba_evidence():
    games=protocol()['selection']['NBA'];bydate=defaultdict(list)
    for g in games:bydate[aware(g['at']).astimezone(ZoneInfo('America/New_York')).date().isoformat()].append(g)
    b,r=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams');teams={};abbr={}
    if b:
        for item in json.loads(b)['sports'][0]['leagues'][0]['teams']:
            t=item['team'];tid=str(t['id']);abbr[t['abbreviation']]=tid
            for name in [t['displayName'],t['shortDisplayName'],t.get('location','')+' '+t.get('name','')]:teams[norm(name)]=tid
        teams.update({norm('Los Angeles Clippers'):teams.get(norm('LA Clippers'),'12')})
        for code,name in {'GSW':'Golden State Warriors','NYK':'New York Knicks','NOP':'New Orleans Pelicans','SAS':'San Antonio Spurs','UTA':'Utah Jazz','PHX':'Phoenix Suns','BKN':'Brooklyn Nets','BRK':'Brooklyn Nets'}.items():
            if norm(name) in teams:abbr[code]=teams[norm(name)]
    facts=[];coverage={g['id']:{'reportedPlayers':0,'explicitOut':0,'teamReports':[],'confirmedCompleteLineup':False,'missingIsHealthy':False} for g in games};unmapped=[];reports=[]
    for date,gs in sorted(bydate.items()):
        for hour in [12,17]:
            stamp=f'{hour%12 or 12:02d}';ampm='PM';data=None
            for suffix in [stamp+ampm,stamp+'_00'+ampm]:
                url=f'https://ak-static.cms.nba.com/referee/injury/Injury-Report_{date}_{suffix}.pdf';data,receipt=fetch(url)
                if data and data.startswith(b'%PDF'):break
                data=None
            if data is None:continue
            try:rows,issued=nba_rows(data)
            except Exception as e:reports.append({'url':url,'status':'parse_failed','error':type(e).__name__});continue
            modified=receipt.get('lastModified');published=max(aware(issued),parsedate_to_datetime(modified).astimezone(timezone.utc)) if issued and modified else None;reports.append({'url':url,'rows':len(rows),'issuedAt':issued,'publishedAt':published.isoformat() if published else None,'httpStatus':receipt['httpStatus']})
            for g in gs:
                cutoff=aware(g['at'])-timedelta(minutes=30)
                if published is None or published>=cutoff:continue
                names=earlier_names('NBA',g)
                for row in rows:
                    parts=(row.get('matchup') or '').split('@');pair={abbr.get(x) for x in parts}
                    if row['date']!=date or pair!={g['home'],g['away']}:continue
                    team=teams.get(norm(row.get('team')))
                    if team not in pair:unmapped.append({'eventId':g['id'],'reason':'team_identity','team':row.get('team')});continue
                    if team not in coverage[g['id']]['teamReports']:coverage[g['id']]['teamReports'].append(team)
                    if row['status']=='not_yet_submitted':continue
                    ids=names.get(norm(row['name']),set());pid=next(iter(ids)) if len(ids)==1 else None
                    if not pid:unmapped.append({'eventId':g['id'],'reason':'player_identity','name':row['name']})
                    facts.append({'sport':'NBA','eventId':g['id'],'teamId':team,'playerId':pid,'name':row['name'],'status':row['status'],'source':url,'sourceVersion':receipt['sha256'],'publishedAt':published.isoformat(),'reportedAt':issued,'retrievedAt':receipt['retrievedAt'],'confidence':'official_timestamped_report' if pid else 'unresolved_identity','cutoff':cutoff.isoformat()})
        print(json.dumps({'stage':'nba_source','date':date,'facts':len(facts)}),flush=True)
    # Latest report wins for this prediction cutoff, never a later game outcome.
    latest={}
    for f in facts:
        key=(f['eventId'],f['teamId'],f['playerId'] or norm(f['name']))
        if key not in latest or f['publishedAt']>latest[key]['publishedAt']:latest[key]=f
    facts=list(latest.values())
    for g in games:
        rs=[f for f in facts if f['eventId']==g['id']];coverage[g['id']].update(reportedPlayers=len(rs),explicitOut=sum(f['status']=='Out' and f['playerId'] is not None for f in rs))
    return {'facts':facts,'coverage':coverage,'unmapped':unmapped,'reports':reports,'formatFinding':'2024 and November 2025 use _05PM; later 2026 reports use _05_00PM. Wrong historical URL format can return 403 even when the correct public document is accessible. No login or access bypass was used.'}

MAC_URLS=['https://getsomemaction.com/documents/2024/11/12/FB_AVAILABILITY_REPORT_11_12.pdf','https://getsomemaction.com/documents/2025/11/4/FB_Availability_Report_11_4.pdf','https://getsomemaction.com/documents/2025/11/8/2025_FB_Availability_Report_11_8.pdf','https://getsomemaction.com/documents/2025/11/12/FB_Availability_Report_Week_12_11_12.pdf','https://getsomemaction.com/documents/2025/11/15/FB_Availability_Report_Week_12_11_15.pdf','https://getsomemaction.com/documents/2025/11/28/FB_Availability_Report_Week_14_11_28.pdf','https://getsomemaction.com/documents/2025/8/30/2025_FB_Availability_Report_Week_One_Saturday_3.pdf']
def cfb_evidence():
    games=protocol()['selection']['CFB'];data=archives('CFB');team_names={}
    for g in data['games'].values():
        for side in ['home','away']:
            full=g[side+'Name'];team_names[norm(full)]=g[side]
    aliases={'ballstate':'cfb:espn:2050','easternmichigan':'cfb:espn:2199','bowlinggreen':'cfb:espn:189','kentstate':'cfb:espn:2309','ohio':'cfb:espn:195','miamiohio':'cfb:espn:193','miamioh':'cfb:espn:193','miami':'cfb:espn:193','toledo':'cfb:espn:2649','northernillinois':'cfb:espn:2459','westernmichigan':'cfb:espn:2711','centralmichigan':'cfb:espn:2117','akron':'cfb:espn:2006','buffalo':'cfb:espn:2084','massachusetts':'cfb:espn:113','umass':'cfb:espn:113'}
    facts=[];documents=[];unmapped=[];coverage={g['id']:{'reportedPlayers':0,'explicitOut':0,'confirmedCompleteLineup':False,'missingIsHealthy':False} for g in games}
    for url in MAC_URLS:
        b,r=fetch(url)
        if b and not b.startswith(b'%PDF'):
            links=re.findall(r'https://s3\.amazonaws\.com/sidearm\.sites/mac-sports/documents/[^\s\"<>]+\.pdf',b.decode(errors='ignore'))
            if links:b,r=fetch(links[0])
        if not b or not b.startswith(b'%PDF'):continue
        published=parsedate_to_datetime(r['lastModified']).astimezone(timezone.utc) if r.get('lastModified') else None
        with pdfplumber.open(io.BytesIO(b)) as pdf:
            for page in pdf.pages:
                text=page.extract_text() or '';match=re.search(r'([^\n]+?)\s+(?:vs\.?|at)\s+([^\n]+)',text,re.I);date=re.search(r'\b(\d{1,2})\.(\d{1,2})\.(\d{2})\b',text)
                if not match or not date:continue
                owner=norm(match[1]);team=aliases.get(owner) or next((tid for name,tid in team_names.items() if name.startswith(owner) and len(owner)>3),None);event_date=f'20{date[3]}-{int(date[1]):02d}-{int(date[2]):02d}'
                for g in games:
                    if team not in (g['home'],g['away']) or aware(g['at']).astimezone(ZoneInfo('America/New_York')).date().isoformat()!=event_date or published is None or published>=aware(g['at'])-timedelta(minutes=30):continue
                    names=earlier_names('CFB',g)
                    for side,status in [(0,'Out'),(1,'Questionable')]:
                        crop=page.crop((page.width*side/2,260,page.width*(side+1)/2,page.height-30));content=crop.extract_text() or ''
                        for line in content.splitlines():
                            row=re.match(r'^\s*(\d{1,2})\s+(.+?)\s*$',line)
                            if not row:continue
                            name=row[2];ids=names.get(norm(name),set());pid=next(iter(ids)) if len(ids)==1 else None
                            if not pid:unmapped.append({'eventId':g['id'],'name':name,'team':team})
                            facts.append({'sport':'CFB','eventId':g['id'],'teamId':team,'playerId':pid,'name':name,'jersey':int(row[1]),'status':status,'source':url,'sourceVersion':r['sha256'],'publishedAt':published.isoformat(),'retrievedAt':r['retrievedAt'],'confidence':'official_timestamped_report' if pid else 'unresolved_identity','cutoff':(aware(g['at'])-timedelta(minutes=30)).isoformat()})
        documents.append({'url':url,'publishedAt':published.isoformat() if published else None,'sha256':r['sha256']})
    for gid,c in coverage.items():
        rows=[f for f in facts if f['eventId']==gid];c.update(reportedPlayers=len(rows),explicitOut=sum(f['status']=='Out' and f['playerId'] is not None for f in rows))
    return {'facts':facts,'coverage':coverage,'documents':documents,'unmapped':unmapped,'limitation':'Sources for some conferences are incomplete. Calendar-placeholder CFB starts can reject valid game-day reports until schedule metadata is independently aligned. Unknown is never healthy.'}

def collect(sport):
    file=OUT/'evidence'/(sport+'-aligned-v3.json.gz')
    if file.exists():return json.loads(gzip.decompress(file.read_bytes()))
    result={'NFL':nfl_evidence,'CFB':cfb_evidence,'NBA':nba_evidence}[sport]();result.update(sport=sport,strictCompletePregameInputs=False,productionWrites=0);freeze_json(file,result);return result
