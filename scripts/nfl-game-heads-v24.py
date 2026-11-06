"""Independent old-season NFL game heads, separate from the QB cohorts."""
import sys,json,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.dynamic_v24.stat_models import FAMILIES
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,digest
spec=importlib.util.spec_from_file_location('nfl_extension',ROOT/'scripts/extend-nfl-specialized-v24.py');ext=importlib.util.module_from_spec(spec);spec.loader.exec_module(ext);runner=ext.runner
runner.REV='completion-nfl-games-r1';runner.DEST=OUT/runner.REV;runner.WINDOWS={'NFL':[('2020-10-01','2020-11-01'),('2021-11-15','2021-12-31')]};runner.FAMILY_LIST=FAMILIES;runner.catalogue=lambda:{'NFL':{s:{} for s in ['teamPoints','moneyline','spread','total']}};runner.EXTRA_FOOT=()
def rows(games,sport):
    ws=read(runner.DEST/'protocol.json')['selection']['NFL'];chosen={g for w in ws for g in w['games']}
    for w in ws:chosen.update(g['id'] for g in [g for g in games if g['at']<w['start']][-500:])
    return records(games,sport,chosen)
runner.records=rows
def code():return {**ext.code(),str(Path(__file__).relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
if __name__=='__main__':
    if '--register' in sys.argv:
        original=read(OUT/'completion-nfl-extension-r2/protocol.json');excluded=set(original['excludedValidationIds']);excluded.update(g for ws in original['selection'].values() for w in ws for g in w['games']);games=runner.packets('NFL');selection=[];rng=np.random.default_rng(240243)
        for start,end in runner.WINDOWS['NFL']:
            available=[g['id'] for g in games if start<=g['at']<end and g['id'] not in excluded];rng.shuffle(available);selection.append({'start':start,'end':end,'games':sorted(available[:40]),'pool':len(available)})
        protocol={**original,'revision':runner.REV,'selection':{'NFL':selection},'numericCode':code(),'excludedValidationIds':sorted(excluded),'heads':['teamPoints','moneyline','spread','total'],'families':FAMILIES,'reason':'New games for separately selected game-outcome heads; margin/total projections are not fabricated market thresholds','verifiedHistoricalLines':0};freeze_json(runner.DEST/'protocol.json',protocol);freeze_json(OUT/'specs/nfl-game-heads-r1.json',{'numericCode':code(),'inputHashes':protocol['sourceVersions'],'protocol':digest(protocol)});print(json.dumps({'newGames':[len(w['games']) for w in selection]}))
    else:print(json.dumps(job('nfl-game-heads-r1',lambda:runner.run('NFL'),cpu=600,wall=900),indent=2))
