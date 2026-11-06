"""Two new historical QB validation windows; fixed structural families.

Earlier r4 NFL QB windows lacked enough three-block chronological training
observations. Acquire a genuinely new season instead of reducing that guard.
"""
import sys,json,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.completion.additional_data import packets,raw_rows,FOLDER
from modeling.dynamic_v24.completion.data import features_only
from modeling.integration_v22.datasets import protected,nfl_packets
from modeling.integration_v22.control import replay
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,digest
spec=importlib.util.spec_from_file_location('completion_runner',ROOT/'scripts/complete-models-v24.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
runner.REV='completion-nfl-extension-r2';runner.DEST=OUT/runner.REV;runner.WINDOWS={'NFL':[('2020-11-01','2020-12-01'),('2021-10-01','2021-11-15')]};runner.packets=lambda sport:[g for g in packets(sport) if g['at']<'2022-01-01'];runner.FAMILY_LIST=('rolling5','ewma','opponent_ridge','hierarchical','boosted','hurdle','opportunity_pooling','v20_hurdle_refit');runner.catalogue=lambda:{'NFL':{'passingAttempts':{},'passingYards':{},'passingCompletions':{}}};runner.EXTRA_FOOT=()

def code():
    paths=[Path(__file__),ROOT/'scripts/complete-models-v24.py',*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py'))]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def reference(sport,stat,rows,folder):
    if stat!='passingYards':return None
    old=nfl_packets()[1];extra=raw_rows();previous=[]
    import pyarrow.parquet as pq
    previous=pq.read_table(ROOT/'artifacts/fullgame-v23/sources/stats_player_week_2024.parquet',filters=[('game_id','not in',list(protected()))]).to_pylist();raw=old+previous+extra;cache={};values=[]
    for r in features_only(rows):
        key=(int(r['season']),int(r['gameId'].split('_')[1]))
        if key not in cache:cache[key]=replay(raw,*key,r['at'])[0]
        values.append(cache[key].get(r['player'],{}).get('mean'))
    freeze_json(folder/stat/'production-source-reference.json',{'pointEstimate':values,'gameIds':[r['gameId'] for r in rows],'playerIds':[r['player'] for r in rows],'scope':'Unchanged production source algorithm on prior 2024/2025 QB appearances; conditional, not a verified pregame snapshot','futureInformationUsed':False});return values
runner.production_source_reference=reference

def register():
    original=read(OUT/'completion-r4/protocol.json');rng=np.random.default_rng(240241);excluded=runner.old_evaluations();excluded.update(g for ws in original['selection'].values() for w in ws for g in w['games']);gs=runner.packets('NFL');selection=[]
    for start,end in runner.WINDOWS['NFL']:
        available=[g['id'] for g in gs if start<=g['at']<end and g['id'] not in excluded];rng.shuffle(available);selection.append({'start':start,'end':end,'games':sorted(available[:40]),'pool':len(available)})
    sources=dict(original['sourceVersions'])
    for p in FOLDER.glob('*.parquet'):sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    protocol={**original,'revision':runner.REV,'numericCode':code(),'selection':{'NFL':selection},'sourceVersions':sources,'excludedValidationIds':sorted(excluded),'families':runner.FAMILY_LIST,'heads':['passingAttempts','passingYards','passingCompletions'],'reason':'2025 was already exposed in sequential research. Use unexposed 2020/2021 games with 2019 training; retain observation gates','priorCohortResultsUsedToTuneParameters':False};freeze_json(runner.DEST/'protocol.json',protocol);freeze_json(OUT/'specs/extension-nfl-r2.json',{'numericCode':code(),'inputHashes':sources,'protocol':digest(protocol)});print(json.dumps({'games':[len(w['games']) for w in selection],'priorGames':len(gs),'validationSeasons':[2020,2021]}))

if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:print(json.dumps(job('extension-nfl-r2',lambda:runner.run('NFL'),cpu=600,wall=900),indent=2))
