"""Versioned research IO; V20/V21 receipts remain read-only."""
from pathlib import Path
import types,json,gzip,hashlib
from ..evidence_v21 import io as previous
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/integration-v22'
_fetch=types.FunctionType(previous.fetch.__code__,{**previous.fetch.__globals__,'OUT':OUT})
def fetch(url,maximum_bytes=8000000):
    key=hashlib.sha256((url if maximum_bytes==8000000 else url+'#bounded-bytes='+str(maximum_bytes)).encode()).hexdigest()
    for folder in ['overnight-v21','overnight-v20']:
        p=ROOT/'artifacts'/folder/'sources/receipts'/(key+'.json')
        if p.exists():
            r=json.loads(p.read_text())
            if r.get('object'):return gzip.decompress((ROOT/r['object']).read_bytes()),r
    return _fetch(url,maximum_bytes)
