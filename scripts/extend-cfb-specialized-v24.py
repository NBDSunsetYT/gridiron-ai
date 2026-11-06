"""Larger independent CFB confirmation windows; no parameter or gate relaxation."""
import sys,json,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,digest
spec=importlib.util.spec_from_file_location('completion_runner',ROOT/'scripts/complete-models-v24.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
runner.REV='completion-cfb-extension-r1';runner.DEST=OUT/runner.REV;runner.WINDOWS={'CFB':[('2026-09-15','2026-10-01'),('2026-10-01','2026-11-01')]};original=read(OUT/'completion-r4/protocol.json');original_packets=runner.packets
def packets(sport):return [g for g in original_packets(sport) if g['at']<'2026-11-01']
runner.packets=packets
def rows(games,sport):
    selection=read(runner.DEST/'protocol.json')['selection']['CFB'];chosen=set(g for w in selection for g in w['games'])
    for w in selection:chosen.update(g['id'] for g in [g for g in games if g['at']<w['start']][-500:])
    return records(games,sport,chosen)
runner.records=rows
def code():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'scripts/complete-models-v24.py',*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py'))]}
if __name__=='__main__':
    if '--register' in sys.argv:
        excluded=runner.old_evaluations();excluded.update(g for ws in original['selection'].values() for w in ws for g in w['games']);games=packets('CFB');rng=np.random.default_rng(240242);selection=[]
        for start,end in runner.WINDOWS['CFB']:
            available=[g['id'] for g in games if start<=g['at']<end and g['id'] not in excluded];rng.shuffle(available);selection.append({'start':start,'end':end,'games':sorted(available[:60]),'pool':len(available)})
        protocol={**original,'revision':runner.REV,'selection':{'CFB':selection},'excludedValidationIds':sorted(excluded),'numericCode':code(),'reason':'The earlier first window had fewer than 30 graded QB matchups. Expand to new games instead of weakening sample requirements. Same fixed families and hyperparameters.','newWindowFamilySelection':'Inner data only, fixed before second-window truth','rawMarketLinesAvailable':False};freeze_json(runner.DEST/'protocol.json',protocol);freeze_json(OUT/'specs/extension-cfb-r1.json',{'numericCode':code(),'inputHashes':protocol['sourceVersions'],'protocol':digest(protocol)});print(json.dumps({'newGames':[len(w['games']) for w in selection],'eligiblePools':[w['pool'] for w in selection]}))
    else:print(json.dumps(job('extension-cfb-r1',lambda:runner.run('CFB'),cpu=600,wall=900),indent=2))
