"""Recover missing NFL QB scoring labels from sourced weekly history.

Separate unexamined 2020/2021 windows, no reused confirmation matchups.
This repairs a research input-coverage gap, not production availability.
"""
import sys,json,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.completion.additional_data import packets,FOLDER
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,digest
spec=importlib.util.spec_from_file_location('completion_runner',ROOT/'scripts/complete-models-v24.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
runner.REV='completion-nfl-scoring-r1';runner.DEST=OUT/runner.REV;runner.WINDOWS={'NFL':[('2020-09-01','2020-10-01'),('2021-09-01','2021-10-01')]};runner.packets=lambda sport:[g for g in packets(sport) if g['at']<'2022-01-01'];runner.catalogue=lambda:{'NFL':{'passingTouchdowns':{},'interceptions':{}}};runner.EXTRA_FOOT=()
def code():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'scripts/complete-models-v24.py',*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py'))]}
def register():
    base=read(OUT/'completion-nfl-extension-r2/protocol.json');excluded=runner.old_evaluations()
    for path in OUT.glob('completion-*/protocol.json'):
        for windows in read(path).get('selection',{}).values():
            for w in windows:excluded.update(w['games'])
    gs=runner.packets('NFL');selection=[];rng=np.random.default_rng(240247)
    for start,end in runner.WINDOWS['NFL']:
        pool=[g['id'] for g in gs if start<=g['at']<end and g['id'] not in excluded];rng.shuffle(pool);selection.append({'start':start,'end':end,'games':sorted(pool[:40]),'pool':len(pool)})
    protocol={**base,'revision':runner.REV,'numericCode':code(),'selection':{'NFL':selection},'excludedValidationIds':sorted(excluded),'families':runner.FAMILY_LIST,'heads':['passingTouchdowns','interceptions'],'reason':'Original packet lacked QB scoring labels; use verified NFL weekly counting fields, separate earlier/next-season confirmation, unchanged statistical gates'}
    freeze_json(runner.DEST/'protocol.json',protocol);freeze_json(OUT/'specs/nfl-scoring-r1.json',{'numericCode':code(),'inputHashes':protocol['sourceVersions'],'protocol':digest(protocol)});print(json.dumps({'newGames':[len(w['games']) for w in selection]}))
if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:print(json.dumps(job('nfl-scoring-r1',lambda:runner.run('NFL'),cpu=180,wall=240),indent=2))
