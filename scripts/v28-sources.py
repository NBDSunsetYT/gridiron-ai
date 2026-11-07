"""V28 bounded source capture; never overwrite V26/V27 or private datasets."""
import sys,json,runpy,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/forecast-certification-v28';base=runpy.run_path(str(ROOT/'scripts/v26-capture.py'));base['get'].__globals__['OUT']=OUT/'source-probes'
def fetch(url):
    cache=OUT/'source-probes';p=cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if not p.exists() and len(list(cache.glob('*.json')))>=100:raise RuntimeError('V28 source budget exhausted')
    return base['get'](url)
def run():
    rows=[]
    for kind,tag in [('player','espn_nba_player_boxscores'),('team','espn_nba_team_boxscores')]:
        url='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/'+tag+'/'+kind+'_box_2027.parquet';body,r=fetch(url);rows.append(r)
        if body and r.get('sourceVersion'):
            p=OUT/'fresh-nba'/('NBA-'+kind+'_box_2027.parquet');p.parent.mkdir(exist_ok=True);p.write_bytes(body)
    schedules=[]
    for date in ('20261104','20261105','20261106'):
        body,r=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+date)
        if body:
            for g in json.loads(body).get('events',[]):
                c=g['competitions'][0];schedules.append({'id':'nba:espn:'+str(g['id']),'at':g['date'],'sourceVersion':r['sourceVersion'],'final':g['status']['type']['completed'],'teams':[{'id':str(t['team']['id']),'name':t['team']['displayName'],'side':t['homeAway']} for t in c['competitors']]})
    freeze_json(OUT/'schedule-candidates.json',schedules)
    body,r=fetch('https://official.nba.com/nba-injury-report-2026-27-season/')
    links=sorted(set(re.findall(r'https://[^\s"<>]+\.pdf',body.decode(errors='replace')))) if body else []
    freeze_json(OUT/'injury-pdf-links.json',{'receipt':r,'links':links})
    freeze_json(OUT/'fresh-nba-manifest.json',{'sources':[{k:r.get(k) for k in ('url','sourceVersion','retrievedAt','lastModified','httpStatus','bytes')} for r in rows],'oldArtifactsModified':False})
    print(json.dumps({'freshSources':[(r.get('httpStatus'),r.get('bytes')) for r in rows],'scheduleCandidates':len(schedules),'injuryLinks':len(links)}))
if __name__=='__main__':run()
