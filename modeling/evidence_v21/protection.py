"""Protect both untouched finals and previously locked confirmation cohorts."""
from pathlib import Path
from ..overnight_v20.state import read
ROOT=Path(__file__).resolve().parents[2]
def protected_ids(protocol):
    sealed={g['id'] for gs in protocol.get('sealedFinal',{}).values() for g in gs}|set(protocol.get('sealedIds',[]))
    confirmation=read(ROOT/'artifacts/overnight-v20/confirmation/protocol.json')
    locked={g['id'] for gs in confirmation['selection'].values() for g in gs}
    return sealed|locked
def assert_unexposed(ids,protected):
    overlap=set(ids)&set(protected)
    if overlap:raise ValueError('Protected historical evaluation IDs cannot train this research candidate: '+str(len(overlap)))
