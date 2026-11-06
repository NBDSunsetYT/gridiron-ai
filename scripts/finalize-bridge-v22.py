"""Append unassigned play identity provenance without refitting V21 models."""
import sys,json,gzip,hashlib
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.integration_v22.io import OUT
from modeling.integration_v22.inputs import anonymous_play_credits
from modeling.integration_v22.datasets import cfb_packets
from modeling.integration_v22.runtime import job
from modeling.integration_v22.gates import audit
from modeling.overnight_v20 import data
from modeling.overnight_v20.state import read,atomic,digest
from modeling.accuracy_v20.quality import aware
from modeling.iterative_learning import freeze_json
def run():
    old=OUT/'integration/simulation-model.json.gz';m=json.loads(gzip.decompress(old.read_bytes()));packets,_=cfb_packets();ids={g['id'] for g in packets if aware(g['end'])+timedelta(hours=6)<aware(m['asOf'])};m['historicalUnassignedPlayCredits']=anonymous_play_credits(data.archives('CFB')['rows'],ids);m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});folder=OUT/'integration-r2';folder.mkdir(exist_ok=True);freeze_json(folder/'simulation-model.json.gz',m)
    cert=read(OUT/'integration/consistency-certificate.json');cert['modelHash']=m['sha256'];cert['sha256']=digest({k:v for k,v in cert.items() if k!='sha256'});atomic(folder/'consistency-certificate.json',cert);g=read(OUT/'protocol.json')['selection']['CFB'][0][0];q=audit(m,g|{'cutoff':(aware(g['at'])-timedelta(minutes=30)).isoformat()},{},cert);atomic(folder/'gate-decision.json',q)
    result=read(OUT/'integration/results.json');result.update(modelHash=m['sha256'],withheldReasons=q['reasons'],unassignedPlayIdentityAttempts=sum(v['passingAttempts'] for gs in m['historicalUnassignedPlayCredits'].values() for v in gs.values()),unassignedPlayIdentityPolicy='Source provenance, not additional team stat totals; never assigned to arbitrary QB',numericalModelRefitted=False);atomic(folder/'results.json',result);return result
if __name__=='__main__':
    path=OUT/'specs/bridge-final.json'
    if '--register' in sys.argv:
        if path.exists():raise ValueError('Bridge revision already registered')
        files=[Path(__file__),ROOT/'modeling/integration_v22/inputs.py',ROOT/'modeling/integration_v22/gates.py'];atomic(path,{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'reason':'Retain anonymous snap IDs separately from box credits, enforce content checksum; no refit or forecast changes'});print('Registered provenance and checksum hardening')
    else:print(json.dumps(job('bridge-final',run,cpu=180,wall=600),indent=2))
