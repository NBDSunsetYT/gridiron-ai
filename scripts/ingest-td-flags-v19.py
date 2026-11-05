"""Actual source touchdown flags, ingested separately for NFL AND CFB.
A source flag with unresolved scoring identity makes that game/stat unsupported.
No final game outcome tunes a prediction, and no old cache is overwritten.
"""
import sys,json,gzip,hashlib,time,math
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18.data import archives
from modeling.iterative_learning import freeze_json
from modeling.reconstruction_v19.stat_support import TD_STATS,freeze_invalid_head_notice
import pyarrow.parquet as pq
OUT=ROOT/'artifacts/parallel-v19'
def flag(v):return v is True or (isinstance(v,(int,float)) and math.isfinite(v) and v==1) or (isinstance(v,str) and v.lower() in ('true','1'))
def pid(v,sport):
    if v is None:return None
    if sport=='NFL':return str(v) if str(v).startswith('00-') else None
    try:
        n=float(v)
        if not math.isfinite(n) or n%1:return None
        return 'cfb:espn:'+str(int(n))
    except (ValueError,TypeError):return None

def main():
    start=time.process_time();report={};protocol=json.load((OUT/'protocol.json').open());hashes=[]
    for sport in ['NFL','CFB']:
        data=archives(sport);outcomes={};unresolved=defaultdict(Counter);sources=[];seen=set();duplicates=0
        for year in [2024,2025]:
            path=Path('/tmp')/('gridiron-nfl-pbp-' if sport=='NFL' else 'gridiron-cfb-public-pbp-');path=Path(str(path)+str(year)+'.parquet');f=pq.ParquetFile(path);cols=['game_id','passer_player_id','receiver_player_id','rusher_player_id', 'pass_touchdown' if sport=='NFL' else 'pass_td','rush_touchdown' if sport=='NFL' else 'rush_td','no_play' if sport=='NFL' else 'penalty_no_play','play_id' if sport=='NFL' else 'id'];cols+=[c for c in ['td_player_id'] if c in f.schema.names];sources.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            for batch in f.iter_batches(columns=cols,batch_size=16384):
                for r in batch.to_pylist():
                    gid=('cfb:espn:' if sport=='CFB' else '')+str(r['game_id']);key=(gid,str(r['play_id' if sport=='NFL' else 'id']))
                    if key in seen:duplicates+=1;continue
                    seen.add(key)
                    if gid not in data['games'] or flag(r.get('no_play' if sport=='NFL' else 'penalty_no_play')):continue
                    g=outcomes.setdefault(gid,{'players':{},'supported':{s:True for s in TD_STATS},'scoringEvents':Counter()})
                    def credit(who,stat):
                        if not who:unresolved[gid][stat]+=1;g['supported'][stat]=False;return
                        g['players'].setdefault(who,Counter())[stat]+=1;g['scoringEvents'][stat]+=1
                    if flag(r.get('pass_touchdown' if sport=='NFL' else 'pass_td')):
                        credit(pid(r['passer_player_id'],sport),'passingTouchdowns');credit(pid(r.get('td_player_id') if sport=='NFL' and r.get('td_player_id') else r['receiver_player_id'],sport),'receivingTouchdowns')
                    if flag(r.get('rush_touchdown' if sport=='NFL' else 'rush_td')):credit(pid(r.get('td_player_id') if sport=='NFL' and r.get('td_player_id') else r['rusher_player_id'],sport),'rushingTouchdowns')
        # Counter dictionaries are serialized explicitly, never missing -> zero
        # unless the entire source scoring-identity category is supported.
        for g in outcomes.values():g['players']={pid:dict(v) for pid,v in g['players'].items()};g['scoringEvents']=dict(g['scoringEvents'])
        comparisons=[]
        for path in (OUT/'outcomes').glob('*.official.json.gz'):
            box=json.loads(gzip.decompress(path.read_bytes()))['box']
            if box['sport']!=sport or box['eventId'] not in outcomes:continue
            observed=outcomes[box['eventId']]
            for player,row in box['players'].items():
                for stat in TD_STATS:
                    if stat not in row['stats'] or not observed['supported'][stat]:continue
                    actual=row['stats'][stat];derived=observed['players'].get(player,{}).get(stat,0);comparisons.append({'gameId':box['eventId'],'playerId':player,'stat':stat,'sourceFlagCount':derived,'official':actual,'equal':derived==actual})
        freeze_json(OUT/'repaired-labels'/(sport+'-td-flags.json.gz'),{'sport':sport,'version':'explicit-source-td-flags-19.0.0','sources':sources,'games':outcomes,'originalCachesModified':False,'publicationAvailabilityVerified':False})
        report[sport]={'games':len(outcomes),'scoringPlayerRecords':sum(len(g['players']) for g in outcomes.values()),'scoringEvents':{s:sum(g['scoringEvents'].get(s,0) for g in outcomes.values()) for s in TD_STATS},'unsupportedGameStatistics':sum(not value for g in outcomes.values() for value in g['supported'].values()),'duplicatesSkipped':duplicates,'officialComparisons':len(comparisons),'officialMismatches':[v for v in comparisons if not v['equal']],'sources':sources};print(json.dumps({'sport':sport,'games':len(outcomes),'scoringEvents':report[sport]['scoringEvents'],'officialMismatches':len(report[sport]['officialMismatches'])}),flush=True)
    report['cpuSeconds']=time.process_time()-start;freeze_json(ROOT/'docs/reports/parallel-v19-td-source-audit.json',report)
    affected=[i['sha256'] for i in protocol['sourceFiles'] if 'NFL-repaired' in i['path'] or 'CFB-repaired' in i['path']];freeze_json(ROOT/'docs/reports/parallel-v19-data-quality-notice.json',freeze_invalid_head_notice(affected))
if __name__=='__main__':main()
