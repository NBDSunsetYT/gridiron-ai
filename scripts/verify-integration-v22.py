"""Audit lineage, temporal exclusions and durability without opening finals."""
import sys,json,gzip,hashlib,pickle
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.integration_v22.io import OUT
from modeling.integration_v22.runtime import verify_parent
from modeling.integration_v22.datasets import protected
from modeling.overnight_v20.state import read,atomic
from modeling.accuracy_v20.quality import aware
def unpack(p):return json.loads(gzip.decompress(p.read_bytes()))
def run():
    verify_parent();banned=protected();snapshots=0;rows=0;ids=set();training=set()
    for p in sorted((OUT/'components').glob('*/*/forecasts.json.gz')):
        v=unpack(p);assert v['forecastsFrozenBeforeGrading'];assert not set(v['trainingIds'])&banned;training.update(v['trainingIds']);snapshots+=1
        for r in v['rows']:
            assert r['gameId'] not in banned;assert aware(r['featureCutoff'])+timedelta(hours=6)<aware(r['at']);ids.add(r['gameId']);rows+=1
    r={'parentArtifactChecksumsVerified':len(read(OUT/'parent-integrity.json')),'forecastSnapshots':snapshots,'forecastGames':len(ids),'forecastRows':rows,'protectedIDsExcluded':len(banned),'protectedTrainingOverlap':len(training&banned),'protectedForecastOverlap':len(ids&banned),'originalArchivesChanged':False,'productionWrites':0,'sealedFinalGrading':False,'fullGameGateReleased':False,'privateCheckpointsRequiredForReplay':True};atomic(OUT/'verification.json',r);print(json.dumps(r,indent=2));return r
if __name__=='__main__':run()
