"""Restore small public NFL source assets with exact checkpoint checksums."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.integration_v22.io import OUT,fetch
from modeling.overnight_v20.state import atomic,read
def run():
    protocol=read(OUT/'protocol.json',read(ROOT/'docs/reports/integration-v22-results.json',{}).get('protocol',{}));versions=protocol.get('sourceVersions',{})
    for kind in ['player','team']:
        for season in [2022,2023]:
            name=f'stats_{kind}_week_{season}.parquet';p=OUT/'external'/name;url=f'https://github.com/nflverse/nflverse-data/releases/download/stats_{kind}/'+name;expected=versions.get(str(p.relative_to(ROOT)))
            if not expected:raise ValueError('Restore the V22 protocol or aggregate source manifest first')
            if p.exists():body=p.read_bytes();receipt=None
            else:
                body,receipt=fetch(url)
                if body is None:raise ValueError('Public source unavailable; restore the checksum-addressed private checkpoint')
            if hashlib.sha256(body).hexdigest()!=expected:raise ValueError('Official dataset changed; use archived original bytes or register a new revision, never silently replay corrected inputs')
            if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
            if receipt:atomic(p.with_suffix('.source.json'),receipt)
            print(json.dumps({'source':url,'sha256':expected,'verified':True}),flush=True)
if __name__=='__main__':run()
