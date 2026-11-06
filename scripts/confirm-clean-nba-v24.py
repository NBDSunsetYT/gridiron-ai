"""New NBA confirmation after independent source-accounting rejection.

Families remain fixed from the original inner (pre-January-2025) selector. Both
new windows follow the previously inspected period; no outer family reselection.
"""
import sys,json,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.dynamic_v24.completion.nba_quality import audit
from modeling.overnight_v20.data import archives
from modeling.integration_v22.datasets import protected
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,digest
spec=importlib.util.spec_from_file_location('completion_runner',ROOT/'scripts/complete-models-v24.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
runner.REV='completion-nba-clean-r1';runner.DEST=OUT/runner.REV;runner.WINDOWS={'NBA':[('2026-03-01','2026-03-16'),('2026-03-16','2026-04-01')]};original=read(OUT/'completion-nba-efficient-r1/protocol.json');prior=read(OUT/'completion-nba-efficient-r1/NBA/0/results.json');original_packets=runner.packets
def packets(sport):
    audits=[audit(g) for g in archives('NBA').values() if g['id'] not in protected()];bad={r['gameId'] for r in audits if not r['usable']}
    return [g for g in original_packets(sport) if g['id'] not in bad and g['at']<'2026-04-01']
runner.packets=packets
def rows(games,sport):
    ws=read(runner.DEST/'protocol.json')['selection']['NBA'];chosen={g for w in ws for g in w['games']}
    for w in ws:chosen.update(g['id'] for g in [g for g in games if g['at']<w['start']][-500:])
    return records(games,sport,chosen)
runner.records=rows
current={};old_candidate=runner.candidate;old_choose=runner.choose
def candidate(family,stat,train,cal):current['stat']=stat;return old_candidate(family,stat,train,cal)
def choose(inner,estimands,purpose):
    family=prior.get(current['stat'],{}).get('selected',{}).get(purpose)
    if family not in inner:raise ValueError('Fixed confirmation family is unavailable; do not substitute the best outer model')
    return family
runner.candidate=candidate;runner.choose=choose
def code():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'scripts/complete-models-v24.py',*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py'))]}
if __name__=='__main__':
    if '--register' in sys.argv:
        audits=[audit(g) for g in archives('NBA').values() if g['id'] not in protected()];excluded=set(original['excludedValidationIds']);excluded.update(g for ws in original['selection'].values() for w in ws for g in w['games']);games=packets('NBA');selection=[];rng=np.random.default_rng(240245)
        for start,end in runner.WINDOWS['NBA']:
            pool=[g['id'] for g in games if start<=g['at']<end and g['id'] not in excluded];rng.shuffle(pool);selection.append({'start':start,'end':end,'games':sorted(pool[:60]),'pool':len(pool)})
        protocol={**original,'revision':runner.REV,'selection':{'NBA':selection},'numericCode':code(),'excludedValidationIds':sorted(excluded),'sourceRejectedGames':[a for a in audits if not a['usable']],'fixedFamilies':{s:v.get('selected',{}) for s,v in prior.items()},'reason':'Reject inconsistent shooting/points boxes before lags and fitting. Fresh post-inspection game windows, unchanged families/parameters.','originalArchivesModified':False};freeze_json(runner.DEST/'protocol.json',protocol);freeze_json(OUT/'specs/clean-nba-r1.json',{'numericCode':code(),'inputHashes':protocol['sourceVersions'],'protocol':digest(protocol)});print(json.dumps({'newGames':[len(w['games']) for w in selection],'sourceGamesRejected':sum(not a['usable'] for a in audits)}))
    else:print(json.dumps(job('clean-nba-r1',lambda:runner.run('NBA'),cpu=900,wall=1200),indent=2))
