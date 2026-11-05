"""Bounded, source-verified historical transaction backfill for eight ambiguities.
No final-game box is consulted. Published AND modified article times must be
before each event cutoff. Facts are curated from official receive/exchange
sections and matched to unique prior-known IDs, never a final roster.
"""
import sys,json,gzip,re,unicodedata
from pathlib import Path
from datetime import timedelta
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.sources import fetch,protocol
from modeling.overnight_v20.data import archives
from modeling.accuracy_v20.quality import aware
from modeling.iterative_learning import freeze_json,digest
OUT=ROOT/'artifacts/overnight-v20';urls={'eubanks':'https://www.nba.com/jazz/news/utah-jazz-complete-trade-with-la-clippers-2','bucks':'https://www.nba.com/bucks/news/milwaukee-bucks-acquire-kevin-porter-jr','2025':'https://www.nba.com/news/2024-25-nba-trade-tracker','2026':'https://www.nba.com/news/2025-26-nba-trade-tracker'}
rows=[('3914285','Drew Eubanks','12','eubanks',['nba:espn:401705317']),('4397140','Kevin Porter Jr.','15','bucks',['nba:espn:401705359']),('4432179','MarJon Beauchamp','12','bucks',['nba:espn:401705359']),('4278053','Davion Mitchell','14','2025',['nba:espn:401705366']),('3032979','Dennis Schroder','5','2026',['nba:espn:401810611']),('4065732',"De'Andre Hunter",'23','2026',['nba:espn:401810611']),('4702177','Keon Ellis','5','2026',['nba:espn:401810611']),('4066372','Kevin Huerter','8','2026',['nba:espn:401810669'])]
def norm(s):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,t,a):
        if t in ('script','style'):self.skip+=1
    def handle_endtag(self,t):
        if t in ('script','style'):self.skip=max(0,self.skip-1)
    def handle_data(self,s):
        if not self.skip:self.parts.append(s)
sources={};failures=[]
for key,url in urls.items():
    raw,receipt=fetch(url)
    if raw is None:failures.append({'source':url,'httpStatus':receipt.get('httpStatus')});continue
    html=raw.decode(errors='strict');dates={name:sorted(set(re.findall(r'"'+name+r'"\s*:\s*"([^"]+)"',html))) for name in ['datePublished','dateModified']}
    if any(len(v)!=1 for v in dates.values()):failures.append({'source':url,'reason':'Article publication/modified timestamp ambiguous'});continue
    t=Text();t.feed(html);sources[key]={'source':url,'receipt':receipt,'publishedAt':dates['datePublished'][0],'modifiedAt':dates['dateModified'][0],'availableAt':max(aware(v[0]) for v in dates.values()).isoformat(),'text':norm(' '.join(t.parts))}
data=archives('NBA');games={g['id']:g for g in protocol()['selection']['NBA']};facts=[]
for pid,name,team,key,events in rows:
    try:
        source=sources[key]
        if norm(name) not in source['text']:raise ValueError('Exact article player mention missing')
        for event in events:
            g=games[event];cut=aware(g['at'])-timedelta(minutes=30)
            if aware(source['availableAt'])>=cut:raise ValueError('Article modification/publication occurs after prediction cutoff')
            prior={str(p['athlete_id']) for old in data.values() if aware(old['at'])+timedelta(hours=6)<cut for p in old['players'] if norm(p['athlete_display_name'])==norm(name)}
            if prior!={pid}:raise ValueError('Prior player identity is not uniquely verified')
            if team not in [g['home'],g['away']]:raise ValueError('Published receiving team is not in this event')
        facts.append({'sport':'NBA','playerId':'nba:espn:'+pid,'name':name,'teamId':team,'eventIds':events,'source':source['source'],'sourceVersion':source['receipt']['sha256'],'publishedAt':source['publishedAt'],'articleModifiedAt':source['modifiedAt'],'availableAt':source['availableAt'],'retrievedAt':source['receipt']['retrievedAt'],'sourceVerified':True,'factType':'official_transaction_membership','curation':'Receiving/exchange direction independently checked in the linked official article; script verifies exact prior-known ID, mention, event team and pre-cutoff article timestamps.','availability':'unknown','confirmedStarter':False,'finalBoxUsed':False})
    except (ValueError,KeyError) as e:failures.append({'playerId':pid,'sourceKey':key,'reason':str(e)})
body={'facts':facts,'failures':failures,'scope':'Eight known historical identity ambiguities only; not complete NBA injury/lineup coverage','productionWrites':0,'newSimulations':0};path=OUT/'accuracy-first'/('membership-'+digest(body)+'.json');freeze_json(path,body);freeze_json(ROOT/'docs/reports/overnight-v20-membership.json',body);print(json.dumps({'verifiedFacts':len(facts),'failures':failures,'artifact':str(path.relative_to(ROOT))},indent=2))
