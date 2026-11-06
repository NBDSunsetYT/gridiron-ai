import sys,json,time,resource
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.sources import collect
from modeling.overnight_v20.state import atomic
start=time.monotonic();cpu=time.process_time()
with ThreadPoolExecutor(max_workers=3) as pool:
    tasks={s:pool.submit(collect,s) for s in ['NFL','CFB','NBA']}
    result={}
    for s,future in tasks.items():
        data=future.result();result[s]={'facts':len(data['facts']),'gamesWithReports':sum(c['reportedPlayers']>0 for c in data['coverage'].values()),'gamesWithMappedOuts':sum(c['explicitOut']>0 for c in data['coverage'].values())};atomic(ROOT/'artifacts/overnight-v20/source-progress.json',{'completed':result,'activeSeconds':time.monotonic()-start});print(json.dumps({'sport':s,**result[s]}),flush=True)
atomic(ROOT/'artifacts/overnight-v20/source-results.json',{'leagues':result,'activeSeconds':time.monotonic()-start,'cpuSeconds':time.process_time()-cpu,'hostedComputeRequests':0})
