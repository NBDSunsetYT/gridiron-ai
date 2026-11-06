"""V26 bounded public evidence capture for six real upcoming matchups.

No registry, paid feed, service deployment or statistical winner is created.
Raw publisher responses stay in private artifacts; immutable hashes identify
the editions actually available before the future event. Never fetch a selected
target's final box as historical model input.
"""
import sys,json,gzip,hashlib,time,threading,csv
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import digest
from modeling.iterative_learning import freeze_json
from modeling.accuracy_v20.quality import aware
from modeling.integration_v22.datasets import protected

OUT=ROOT/'artifacts/accuracy-v26/source-probes'
LEAGUES={'NFL':'football/nfl','CFB':'football/college-football','NBA':'basketball/nba'}
TARGETS=[('NBA','401909288'),('NBA','401909294'),('NFL','401873045'),('NFL','401873050'),('CFB','401856740'),('CFB','401856743')]
LOCK=threading.Lock();LAST=[0.];REQUESTS=[0]


def now():return datetime.now(timezone.utc).isoformat()


def get(url):
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if path.exists():
        receipt=json.loads(path.read_text())
        if receipt.get('object'):
            body=gzip.decompress((ROOT/receipt['object']).read_bytes())
            if hashlib.sha256(body).hexdigest()!=receipt['sourceVersion']:raise ValueError('Captured body checksum mismatch')
            return body,receipt
        return None,receipt
    if not url.startswith('https://'):raise ValueError('HTTPS required')
    with LOCK:
        if REQUESTS[0]>=180:raise RuntimeError('180-request capture budget exhausted')
        delay=max(0,.25-(time.monotonic()-LAST[0]))
        if delay:time.sleep(delay)
        LAST[0]=time.monotonic();REQUESTS[0]+=1
    receipt={'url':url,'requestStartedAt':now()};body=None
    try:
        with urlopen(Request(url,headers={'User-Agent':'GRIDIRON-AI-Public-Research/26'}),timeout=18) as response:
            body=response.read(4000001)
            if len(body)>4000000:raise ValueError('4MB response cap exceeded')
            sha=hashlib.sha256(body).hexdigest();obj=OUT/(sha+'.gz')
            if not obj.exists():obj.write_bytes(gzip.compress(body,mtime=0))
            receipt.update(httpStatus=response.status,sourceVersion=sha,object=str(obj.relative_to(ROOT)),
                           serverDate=response.headers.get('Date'),lastModified=response.headers.get('Last-Modified'),
                           contentType=response.headers.get('Content-Type'),finalUrl=response.url,bytes=len(body))
    except HTTPError as e:receipt.update(httpStatus=e.code,error='HTTPError')
    except (OSError,ValueError) as e:receipt.update(error=type(e).__name__,message=str(e)[:150])
    receipt['retrievedAt']=now();freeze_json(path,receipt)
    return body,receipt


def payload(url):
    body,receipt=get(url)
    if body is None:raise ValueError('Source unavailable: '+url+' '+str(receipt.get('httpStatus',receipt.get('error'))))
    return json.loads(body),receipt


def summary(sport,event):
    return payload('https://site.api.espn.com/apis/site/v2/sports/'+LEAGUES[sport]+'/summary?event='+event)


def hidden_ids():
    hidden=protected();provider={x.split(':')[-1] for x in hidden}
    schedule=ROOT/'artifacts/parallel-v19/sources/nfl-games.csv'
    if schedule.exists():
        with schedule.open() as file:
            for row in csv.DictReader(file):
                if row['game_id'] in hidden and row.get('espn'):provider.add(str(row['espn']))
    return hidden|provider


def collect():
    banned=hidden_ids();targets=[];histories=set();rosters=set()
    for sport,event in TARGETS:
        if event in banned:raise ValueError('Protected event cannot become a new forecast target')
        data,receipt=summary(sport,event);header=data['header'];comp=header['competitions'][0]
        if str(header['id'])!=event or comp['status']['type']['state']!='pre' or aware(receipt['retrievedAt'])>=aware(comp['date']):
            raise ValueError('Target is not a verified upcoming event: '+event)
        teams=[{'teamId':str(t['team']['id']),'name':t['team']['displayName'],'abbreviation':t['team']['abbreviation'],'side':t['homeAway']} for t in comp['competitors']]
        selection={};season=int(header['season']['year'])
        for team in teams:
            past=next((g['events'] for g in data.get('lastFiveGames',[]) if str(g['team']['id'])==team['teamId']),[])
            eligible=[g for g in past if str(g['id']) not in banned and aware(g['gameDate'])<aware(receipt['retrievedAt'])]
            chosen=sorted(eligible,key=lambda g:aware(g['gameDate']))[-5:]
            selection[team['teamId']]=[str(g['id']) for g in chosen]
            histories.update((sport,str(g['id'])) for g in chosen)
            rosters.add((sport,team['teamId'],season))
        targets.append({'sport':sport,'eventId':event,'eventAt':comp['date'],'teams':teams,
                        'summarySource':receipt['url'],'summarySourceVersion':receipt['sourceVersion'],
                        'capturedAt':receipt['retrievedAt'],'historyIds':selection,'season':season,
                        'confirmedStarterBoxAvailable':bool(data.get('boxscore',{}).get('players')),
                        'venue':data.get('gameInfo',{}).get('venue'),'weather':data.get('gameInfo',{}).get('weather'),
                        'scoresReadAsTargetInputs':False})
    tasks=[('history',s,e,None) for s,e in sorted(histories)]+[('roster',s,t,year) for s,t,year in sorted(rosters)]
    def retrieve(task):
        kind,sport,identity,year=task
        try:
            if kind=='history':
                d,r=summary(sport,identity);c=d['header']['competitions'][0]
                if str(d['header']['id'])!=identity or c['status']['type']['completed'] is not True or aware(c['date'])>=aware(r['retrievedAt']):
                    raise ValueError('Historical source is not verified final before capture')
                return {'kind':kind,'sport':sport,'eventId':identity,'eventAt':c['date'],'status':'final','receipt':r}
            url='https://site.api.espn.com/apis/site/v2/sports/'+LEAGUES[sport]+'/teams/'+identity+'/roster?season='+str(year)
            d,r=payload(url);return {'kind':kind,'sport':sport,'teamId':identity,'season':year,'receipt':r}
        except (ValueError,KeyError) as e:return {'kind':kind,'sport':sport,'identity':identity,'error':str(e)}
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(retrieve,tasks))
    manifest={'captureStartedAt':min(t['capturedAt'] for t in targets),'captureCompletedAt':now(),
              'targets':targets,'sources':results,'newRequests':REQUESTS[0],
              'protectedIdsExcluded':True,'targetFinalOutcomesFetched':False,'modelFits':0,
              'rawResponsesPubliclyCommitted':False,'productionWrites':0}
    freeze_json(ROOT/'artifacts/accuracy-v26/prospective-inputs-r1.json',manifest)
    print(json.dumps({'targets':len(targets),'historicalSources':sum(r['kind']=='history' and 'error' not in r for r in results),
                      'rosterSources':sum(r['kind']=='roster' and 'error' not in r for r in results),
                      'failures':[r for r in results if 'error' in r],'requests':REQUESTS[0]}),flush=True)


if __name__=='__main__':collect()
