"""Two bounded local league processes, sharing the unchanged frozen r5 protocol.

Only selection views and receipt destinations differ. The fitting algorithm,
source cutoffs, game seeds, 10,000 trials, and forecast schema are unchanged.
"""
import sys,os,time,json,importlib.util,signal,shutil,fcntl
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
def runner():
    spec=importlib.util.spec_from_file_location('market_audit',ROOT/'scripts/market-v18-audit.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def worker(sport):
    os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');m=runner();original_read=m.read;original_atomic=m.atomic;token=str(os.getpid());lease=(OUT/(sport+'.lock')).open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def scoped_read(path,*args):
        data=original_read(path,*args)
        if Path(path)==OUT/'audit-protocol.json':return selection_for_sport(data,sport)
        return data
    def scoped_atomic(path,data):
        if Path(path)==OUT/'audit-receipt.json':path=OUT/'receipts'/(sport+'-'+token+'.json')
        return original_atomic(path,data)
    m.read=scoped_read;m.atomic=scoped_atomic
    try:return m.run()
    finally:fcntl.flock(lease,fcntl.LOCK_UN);lease.close()
def main():
    protocol=read(OUT/'audit-protocol.json')
    if not protocol:raise ValueError('Register the original audit first')
    # Quarantine only incomplete files created by this task. Never remove a
    # source archive, historical forecast, or any private/financial record.
    for p in [*(OUT/'models').glob('*.gz'),*(OUT/'runs').glob('*.gz')]:
        try:runner().load(p)
        except (ValueError,OSError,EOFError):p.rename(p.with_name(p.name+'.interrupted-'+str(time.time_ns())))
    started=time.monotonic();stop=False
    def timeout(sig,frame):raise TimeoutError('Bounded local research coordinator stopped')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(3100)
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures={sport:pool.submit(worker,sport) for sport in ['NFL','CFB']}
        while not all(f.done() for f in futures.values()):
            if shutil.disk_usage(ROOT).free<256*1024**2:
                for process in pool._processes.values():os.kill(process.pid,signal.SIGTERM)
                raise RuntimeError('Disk safety threshold reached; completed forecasts remain checkpointed')
            time.sleep(5)
        failures={}
        for sport,future in futures.items():
            try:future.result()
            except Exception as e:failures[sport]=type(e).__name__+': '+str(e)
    signal.alarm(0);result=runner().summarize();atomic(OUT/'worker-controller.json',{'wallSeconds':time.monotonic()-started,'maximumParallelProcesses':2,'failures':failures,'gamesCompleted':result['gamesCompleted'],'productionWrites':0});print(json.dumps({'gamesCompleted':result['gamesCompleted'],'failures':failures}))
if __name__=='__main__':main()
