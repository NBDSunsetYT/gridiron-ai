"""Retrieve public official final boxes for BOTH football cohorts, grading only.
Balanced two-request concurrency; no source feeds into frozen pregame models.
"""
import sys,json,gzip,csv,io,hashlib,time,urllib.request,urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json
from modeling.reconstruction_v19.outcomes import normalize_box
from modeling.reconstruction_v19.runtime import local_only
import pyarrow.parquet as pq
OUT=ROOT/'artifacts/parallel-v19';ALL='--all' in sys.argv;local_only();p=json.load((OUT/'protocol.json').open());plan=json.load((OUT/'compute-plan.json').open());schedule={r['game_id']:r for r in csv.DictReader((OUT/'sources/nfl-games.csv').open())};depth=pq.read_table(OUT/'sources/depth_charts_2025.parquet',columns=['espn_id','gsis_id']).to_pylist();mapping={}
for r in depth:
    if r['espn_id'] and r['gsis_id']:
        if r['espn_id'] in mapping and mapping[r['espn_id']]!=r['gsis_id']:raise ValueError('Ambiguous NFL provider player identity')
        mapping[r['espn_id']]=r['gsis_id']
jobs=[]
for c in range(3):
    for ordinal in range(plan['fullGameSubsetPerWindow']):
        for sport in ['NFL','CFB']:
            g=[g for g in p['selection'][sport] if g['cohort']==c][ordinal];jobs.append(g)
def fetch(g):
    sport=g['sport'];provider_id=schedule[g['id']]['espn'] if sport=='NFL' else g['id'].split(':')[-1];league='nfl' if sport=='NFL' else 'college-football';url=f'https://site.api.espn.com/apis/site/v2/sports/football/{league}/summary?event={provider_id}';path=OUT/'outcomes'/(g['id'].replace(':','_')+'.official.json.gz')
    if path.exists():return json.loads(gzip.decompress(path.read_bytes()))['receipt']
    try:
        if ALL:time.sleep(.6)
        with urllib.request.urlopen(url,timeout=20) as response:
            raw=response.read(4000001)
            if len(raw)>4000000:raise ValueError('Official box exceeds request budget')
        parsed=json.loads(raw)
        if parsed['header']['id']!=provider_id:raise ValueError('Provider event identifier mismatch')
        box=normalize_box(parsed,sport,g['id'],g['home'],g['away'],mapping);receipt={'sport':sport,'eventId':g['id'],'source':url,'sourceSha256':hashlib.sha256(raw).hexdigest(),'retrievedAt':datetime.now(timezone.utc).isoformat(),'confidence':'official_final_box','publishedAt':None,'publicationNote':'Final outcomes retrieved for grading after predictions; original public publication minute not asserted.','httpStatus':200,'bytes':len(raw)}
        freeze_json(path,{'receipt':receipt,'box':box});freeze_json(OUT/'outcomes/raw'/(hashlib.sha256(raw).hexdigest()+'.json.gz'),parsed);return receipt|{'accountingFailures':sum(not c['equal'] for c in box['accountingChecks']),'unmappedPlayers':len(box['unmapped'])}
    except Exception as e:return {'sport':sport,'eventId':g['id'],'error':type(e).__name__+': '+str(e),'httpStatus':getattr(e,'code',None)}
if ALL:
    jobs=[]
    for c in range(3):
        leagues={s:[g for g in p['selection'][s] if g['cohort']==c] for s in ['NFL','CFB']}
        for ordinal in range(max(map(len,leagues.values()))):
            for sport in ['NFL','CFB']:
                if ordinal<len(leagues[sport]):jobs.append(leagues[sport][ordinal])
start=time.process_time()
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,jobs))
freeze_json(ROOT/('docs/reports/parallel-v19-official-outcomes'+('-all' if ALL else '')+'.json'),{'sources':results,'cpuSeconds':time.process_time()-start,'forGradingOnly':True,'originalForecastsAndGradesOverwritten':False});print(json.dumps({'successes':sum('error' not in r for r in results),'bySport':{s:sum(r['sport']==s and 'error' not in r for r in results) for s in ['NFL','CFB']},'failures':[r for r in results if 'error' in r],'cpuSeconds':time.process_time()-start}),flush=True)
