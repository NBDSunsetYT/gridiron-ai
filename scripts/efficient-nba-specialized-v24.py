"""Resume the same NBA protocol after feature-preparation memory admission failed.
No outer NBA forecast/metric existed in the failed parent job. All selected input
vectors must equal the unoptimized algorithm; models/parameters stay unchanged.
"""
import sys,json,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,digest
spec=importlib.util.spec_from_file_location('completion_runner',ROOT/'scripts/complete-models-v24.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
runner.REV='completion-nba-efficient-r1';runner.DEST=OUT/runner.REV;original=read(OUT/'completion-r4/protocol.json');runner.WINDOWS={'NBA':original['selection']['NBA']}
selection=original['selection']['NBA'];selected=set()
all_packets=runner.packets
def packets(sport):return [g for g in all_packets(sport) if g['at']<max(w['end'] for w in selection)]
runner.packets=packets
def rows(games,sport):
    chosen=set(g for w in selection for g in w['games'])
    for w in selection:chosen.update(g['id'] for g in [g for g in games if g['at']<w['start']][-500:])
    return records(games,sport,chosen)
runner.records=rows

def code():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'scripts/complete-models-v24.py',*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py'))]}
if __name__=='__main__':
    if '--register' in sys.argv:
        protocol={**original,'revision':runner.REV,'selection':{'NBA':selection},'numericCode':code(),'reason':'Same NBA cohort and methods; skip unrequested feature rows and cache pure historical aggregates after 3 GiB watchdog stopped parent before any forecasts','sameSelectedFeatureVectorsRequired':True};freeze_json(runner.DEST/'protocol.json',protocol);freeze_json(OUT/'specs/efficient-nba-r1.json',{'numericCode':code(),'inputHashes':protocol['sourceVersions'],'protocol':digest(protocol)});print('Registered same NBA cohort; no new model assumptions.')
    else:print(json.dumps(job('efficient-nba-r1',lambda:runner.run('NBA'),cpu=900,wall=1200),indent=2))
