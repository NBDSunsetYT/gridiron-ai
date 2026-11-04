"""Real public NFL outcome audit. Never reads or changes personal records."""
import argparse,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modeling.public_research import fetch_dataset
from modeling.prop_history import finite,NFL_FIELDS
from modeling.history_regularization import audit_regularization
from collections import Counter

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--test-season',type=int,default=2026);parser.add_argument('--out',type=Path,default=Path('docs/reports/history-regularization-audit.json'));args=parser.parse_args()
sources=[];records=[]
for season in (args.test_season-1,args.test_season):
    source=fetch_dataset('player_stats',season,ttl=86400);sources.append(source.metadata)
    for r in source.rows():
        if r.get('season_type')!='REG' or r.get('position') not in ('QB','RB','WR','TE') or sum(finite(r.get(k)) or 0 for k in ('attempts','carries','targets','receptions'))<=0:continue
        for stat,key in NFL_FIELDS.items():
            if stat in ('passingYards','passingTouchdowns','passingAttempts','completions','interceptions') and r['position']!='QB':continue
            value=finite(r.get(key))
            if value is not None:records.append({'player':r['player_id'],'position':r['position'],'season':season,'week':int(r['week']),'game':r['game_id'],'stat':stat,'value':value})
results={};start=time.process_time()
for stat,position in sorted({(r['stat'],r['position']) for r in records}):
    a=audit_regularization(records,stat,position,args.test_season);results[stat+':'+position]=a
    v=a.get('validation',{});print(json.dumps({'stat':stat,'position':position,'approved':a['approved'],'n':v.get('testPredictions'),'brier':v.get('brierScore'),'raw':v.get('benchmarkBrier'),'adjustedP':v.get('familywiseAdjustedPValue')}),flush=True)
report={'protocol':'predeclared-jeffreys24-v1','sport':'NFL','testSeason':args.test_season,'testThroughWeek':max(r['week'] for r in records if r['season']==args.test_season),'createdAt':datetime.now(timezone.utc).isoformat(),'sources':sources,'cohorts':results,'cpuSeconds':time.process_time()-start,'historicalFirstPublicationVerified':False,'prospectiveAccuracyClaimed':False,'personalRecordsChanged':False}
args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
