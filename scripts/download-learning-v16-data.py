"""Recover the exact public data used in the frozen local experiment.

No credentials, user database, pricing API or browser uploads are used. Source
corrections are rejected rather than silently changing the historical audit.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
URLS={
    **{'gridiron-nfl-pbp-'+str(y)+'.parquet':'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_'+str(y)+'.parquet' for y in (2024,2025)},
    **{'gridiron-cfb-public-pbp-'+str(y)+'.parquet':'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_pbp/play_by_play_'+str(y)+'.parquet' for y in (2024,2025)},
    'gridiron-nba-pbp-2026.parquet':'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_pbp/play_by_play_2026.parquet',
    'gridiron-nba-player_box_2026.parquet':'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_player_boxscores/player_box_2026.parquet',
    'gridiron-nba-team_box_2026.parquet':'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_team_boxscores/team_box_2026.parquet',
}


def recover(protocol):
    for item in protocol['sources']:
        path=Path('/tmp')/item['name'];url=URLS[item['name']]
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('An existing source has changed and was preserved: '+path.name)
            print('Verified '+path.name);continue
        temporary=path.with_suffix('.learning-v16.partial')
        try:
            with urllib.request.urlopen(url,timeout=45) as response,temporary.open('xb') as output:
                size=0;sha=hashlib.sha256()
                while chunk:=response.read(1024*1024):
                    size+=len(chunk)
                    if size>item['bytes']:raise ValueError('Published source size changed; a new versioned experiment is required')
                    output.write(chunk);sha.update(chunk)
            if size!=item['bytes'] or sha.hexdigest()!=item['sha256']:raise ValueError('Published source checksum changed; no mismatched source accepted')
            temporary.rename(path);print('Recovered '+path.name)
        finally:temporary.unlink(missing_ok=True)
    # Build only owned normalization caches, never forecasts or a new test
    # selection. The scientific runner reuses these for its reference model.
    spec=importlib.util.spec_from_file_location('v15_reference',ROOT/'scripts/backtest-engine-v15.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for sport in ('NFL','CFB'):module.dataset(sport)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',type=Path,default=ROOT/'docs/reports/v16-protocol.json');a=p.parse_args();recover(json.loads(a.protocol.read_text()))
