"""Grade archived minute forecasts against local verified-ID final box records.
Final minutes are outcomes ONLY, never historical pregame model inputs.
"""
import gzip,hashlib,json,time,sys
from pathlib import Path
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'artifacts/learning-v16';start=time.process_time()
manifest=json.loads((SOURCE/'protocol.json').read_text());games=[g for g in manifest['selection'] if g['sport']=='NBA' and g['phase']=='validation'];ids={g['id'].split(':')[-1] for g in games}
source=Path('/tmp/gridiron-nba-player_box_2026.parquet')
if not source.exists():raise SystemExit('Original box-score archive unavailable; no minutes were invented')
frame=pd.read_parquet(source,columns=['game_id','athlete_id','team_id','minutes','starter','points','field_goals_attempted'])
frame=frame[frame.game_id.astype(str).isin(ids)];actual={}
for row in frame.to_dict('records'):
    if pd.isna(row['athlete_id']) or pd.isna(row['minutes']):continue
    if float(row['athlete_id'])%1:raise RuntimeError('Non-integral player identity')
    gid='nba:espn:'+str(row['game_id']);pid='nba:espn:'+str(int(row['athlete_id']))
    if pd.isna(row['minutes']):continue
    if (gid,pid) in actual:raise RuntimeError('Duplicate player identity in box-score archive')
    actual[(gid,pid)]=row
def error(e):return None if not e else {'n':len(e),'mae':float(np.mean(np.abs(e))),'rmse':float(np.sqrt(np.mean(np.array(e)**2))),'bias':float(np.mean(e))}
report={'scope':'24 NBA development games only; final box minutes used solely for diagnostic grading','sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'candidates':{},'causalLimitations':['Minute error cannot on its own distinguish injuries, lineup changes, coaching, fouls and blowouts. Original pregame availability reports remain unverified.','Absent box rows are not assigned invented zero minutes.','Minute histograms are rounded by the existing engine; within-game accounting uses exact seconds.'],'modelsPromoted':[]}
for candidate in ['reference-v15','repair-conversions','conditional-clock','stronger-shrinkage']:
    errors=[];coverage=[];by_game=[];unmatched=0;unmodeled=0;fp={}
    for game in games:
        path=SOURCE/'runs'/candidate/'NBA'/(game['id'].replace(':','_')+'.forecast.json.gz')
        forecast=json.loads(gzip.decompress(path.read_bytes()))['forecast'];per=[];active=set()
        for pid,distributions in forecast['players'].items():
            d=distributions.get('minutes');row=actual.get((game['id'],pid))
            if not d:continue
            if row is None:unmatched+=1;continue
            active.add(pid);err=d['mean']-float(row['minutes']);errors.append(err);per.append(err);coverage.append(d['interval90'][0]<=row['minutes']<=d['interval90'][1])
        unmodeled+=sum(gid==game['id'] and row['minutes']>0 and pid not in active for (gid,pid),row in actual.items())
        by_game.append({'gameId':game['id'],'minutes':error(per)})
    report['candidates'][candidate]={'minuteError':error(errors),'coverage90':float(np.mean(coverage)) if coverage else None,'unmatchedForecastPlayers':unmatched,'unmodeledActualParticipants':unmodeled,'byGame':by_game}
if any(v['minuteError'] is None for v in report['candidates'].values()):raise RuntimeError('Verified minute identities could not be reconciled')
report['resources']={'cpuSeconds':time.process_time()-start,'newSimulations':0,'providerRequests':0}
(ROOT/'docs/reports/nba-minutes-v17.json').write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
print(json.dumps({k:v['minuteError'] for k,v in report['candidates'].items()}))
