"""Two bounded local league processes, sharing the unchanged frozen r5 protocol.

Only selection views and receipt destinations differ. The fitting algorithm,
source cutoffs, game seeds, 10,000 trials, and forecast schema are unchanged.
"""
import sys,os,time,json,importlib.util,signal,shutil,fcntl,hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import read,atomic
OUT=ROOT/'artifacts/market-v18/r5'
def selection_for_sport(protocol,sport):
    if sport not in ('NFL','CFB'):raise ValueError('Only frozen football audit partitions are allowed')
    selected=[r for r in protocol['selection'] if r['sport']==sport]
    if len({r['gameId'] for r in selected})!=len(selected):raise ValueError('Duplicate game in audit partition')
    return {**protocol,'selection':selected}
def pending_partitions(protocol,completed,workers=2,prepared=()):
    if workers not in (1,2):raise ValueError('At most two local workers')
    groups={};all_ids=[r['gameId'] for r in protocol['selection']]
    if len(set(all_ids))!=len(all_ids):raise ValueError('Duplicate frozen game identity')
    if set(completed)-set(all_ids):raise ValueError('Unexpected completed game outside frozen cohort')
    for row in protocol['selection']:
        if row['gameId'] not in completed:
            key=(row['sport'],row['fitCutoff']);key=(*key,row['gameId']) if key in prepared else (*key,'')
            groups.setdefault(key,[]).append(row['gameId'])
    assigned=[set() for _ in range(workers)]
    for key,ids in sorted(groups.items(),key=lambda v:(-len(v[1]),v[0])):
        target=min(range(workers),key=lambda i:(len(assigned[i]),i));assigned[target].update(ids)
    return [sorted(ids) for ids in assigned if ids]
def runner():
    spec=importlib.util.spec_from_file_location('market_audit',ROOT/'scripts/market-v18-audit.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def worker(name,selected):
    os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');m=runner();original_read=m.read;original_atomic=m.atomic;token=str(os.getpid());lease=(OUT/(name+'.lock')).open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);wanted=set(selected)
    def scoped_read(path,*args):
        data=original_read(path,*args)
        if Path(path)==OUT/'audit-protocol.json':return {**data,'selection':[r for r in data['selection'] if r['gameId'] in wanted]}
        return data
    def scoped_atomic(path,data):
        if Path(path)==OUT/'audit-receipt.json':path=OUT/'receipts'/(name+'-'+token+'.json')
        return original_atomic(path,data)
    m.read=scoped_read;m.atomic=scoped_atomic
    try:return m.run()
    finally:fcntl.flock(lease,fcntl.LOCK_UN);lease.close()
def main():
    protocol=read(OUT/'audit-protocol.json')
    if not protocol:raise ValueError('Register the original audit first')
    # Hold both original league leases: an older coordinator cannot race this
    # partitioned coordinator. Each model/cutoff group has exactly one owner.
    leases=[]
    for sport in ('NFL','CFB'):
        lease=(OUT/(sport+'.lock')).open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);leases.append(lease)
    # Quarantine only incomplete files created by this task. Never remove a
    # source archive, historical forecast, or any private/financial record.
    for p in [*(OUT/'models').glob('*.gz'),*(OUT/'runs').glob('*.gz')]:
        try:runner().load(p)
        except (ValueError,OSError,EOFError):p.rename(p.with_name(p.name+'.interrupted-'+str(time.time_ns())))
    completed={read(p)['gameId'] for p in (OUT/'runs').glob('*.summary.json')};prepared=set();rows_by_group={}
    for row in protocol['selection']:rows_by_group.setdefault((row['sport'],row['fitCutoff']),[]).append(row)
    for (sport,cutoff),rows in rows_by_group.items():
        path=OUT/'models'/(sport+'-'+cutoff[:10]+'.json.gz')
        if path.exists():
            models=runner().load(path)
            if all(r['originalModelSHA256'] in models and models[r['originalModelSHA256']]['fittingCutoff']==cutoff for r in rows):prepared.add((sport,cutoff))
    partitions=pending_partitions(protocol,completed,prepared=prepared)
    receipt_name=str(time.time_ns())+'-'+str(os.getpid());atomic(OUT/'execution-plans'/(receipt_name+'.json'),{'workerSourceSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'partitions':partitions,'completedPreviously':len(completed),'readOnlyPreparedModelGroups':[list(k) for k in sorted(prepared)],'numericProtocolChanged':False,'simulationsPerGame':10000})
    started=time.monotonic();stop=False
    def timeout(sig,frame):raise TimeoutError('Bounded local research coordinator stopped')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(3100)
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures={'partition-'+str(i):pool.submit(worker,'partition-'+str(i),ids) for i,ids in enumerate(partitions)}
        while not all(f.done() for f in futures.values()):
            if shutil.disk_usage(ROOT).free<256*1024**2:
                for process in pool._processes.values():os.kill(process.pid,signal.SIGTERM)
                raise RuntimeError('Disk safety threshold reached; completed forecasts remain checkpointed')
            time.sleep(5)
        failures={}
        for sport,future in futures.items():
            try:future.result()
            except Exception as e:failures[sport]=type(e).__name__+': '+str(e)
    signal.alarm(0);result=runner().summarize();receipt={'wallSeconds':time.monotonic()-started,'maximumParallelProcesses':2,'failures':failures,'gamesCompleted':result['gamesCompleted'],'productionWrites':0};atomic(OUT/'controllers'/(receipt_name+'.json'),receipt);atomic(OUT/'worker-controller.json',receipt)
    for lease in leases:fcntl.flock(lease,fcntl.LOCK_UN);lease.close()
    print(json.dumps({'gamesCompleted':result['gamesCompleted'],'failures':failures}))
if __name__=='__main__':main()
