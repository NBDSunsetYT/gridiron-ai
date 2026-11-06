import sys,time,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.sources import collect
from modeling.overnight_v20.state import atomic
start=time.monotonic();cpu=time.process_time()
with ThreadPoolExecutor(max_workers=3) as pool:
    fs={s:pool.submit(collect,s) for s in ['NFL','CFB','NBA']};results={}
    for s,f in fs.items():
        d=f.result();results[s]={'facts':len(d['facts']),'gamesWithReports':sum(c['reportedPlayers']>0 for c in d['coverage'].values()),'gamesWithMappedOuts':sum(c['explicitOut']>0 for c in d['coverage'].values())};print(json.dumps({'sport':s,**results[s]}),flush=True)
atomic(ROOT/'artifacts/overnight-v20/source-effective-results.json',{'leagues':results,'activeSeconds':time.monotonic()-start,'cpuSeconds':time.process_time()-cpu})
