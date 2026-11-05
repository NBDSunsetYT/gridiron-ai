"""Reuse cumulative budgets while protecting every inherited checkpoint."""
import hashlib,os,resource,signal,threading,time,shutil
from pathlib import Path
from .io import ROOT,OUT
from ..overnight_v20.state import Campaign,read,atomic,process_identity
from ..reconstruction_v19.runtime import local_only
def verify_parent():
    for path,sha in read(OUT/'parent-integrity.json').items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise RuntimeError('Inherited checkpoint changed: '+path)
def job(name,callback,cpu=900,wall=1800):
    local_only();verify_parent();c=Campaign(OUT/'runtime');key='v22-'+name;spec=read(OUT/'specs'/(name+'.json'))
    if c.state()['jobs'].get(key,{}).get('status')=='completed':return c.state()['jobs'][key]['receipt']
    if not spec:raise ValueError('Preregister immutable inputs and code before execution')
    for path,sha in spec['numericCode'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise ValueError('Registered code changed; create another revision')
    with c.lease():
        c.begin();ok,reason=c.may_start(cpu)
        if not ok:c.end(reason);raise RuntimeError(reason)
        c.claim(key,process_identity(os.getpid()),cpu,spec);start=time.monotonic();before=time.process_time();children=resource.getrusage(resource.RUSAGE_CHILDREN);stop=threading.Event();receipt={'status':'failed','productionWrites':0,'promotions':0}
        def timeout(sig,frame):raise TimeoutError('Bounded V22 job stopped')
        def heartbeat():
            while not stop.wait(5):
                c.heartbeat();rss=int(next(x.split()[1] for x in Path('/proc/self/status').read_text().splitlines() if x.startswith('VmRSS:')))*1024
                if rss>3*1024**3 or shutil.disk_usage(ROOT).free<256*1024**2:os.kill(os.getpid(),signal.SIGTERM)
        signal.signal(signal.SIGTERM,timeout);signal.signal(signal.SIGALRM,timeout);signal.alarm(wall);resource.setrlimit(resource.RLIMIT_CPU,(int(time.process_time())+cpu,int(time.process_time())+cpu+5));resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
        try:
            from threadpoolctl import threadpool_limits
            with threadpool_limits(limits=1):receipt.update(callback());receipt['status']='completed'
        except Exception as e:receipt.update(error=type(e).__name__,reason=str(e));raise
        finally:
            stop.set();thread.join(timeout=10);signal.alarm(0);child=resource.getrusage(resource.RUSAGE_CHILDREN);receipt.update(cpuSeconds=time.process_time()-before+child.ru_utime+child.ru_stime-children.ru_utime-children.ru_stime,wallSeconds=time.monotonic()-start,peakRssKiB=max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,child.ru_maxrss));atomic(OUT/'receipts'/(name+'.json'),receipt);c.finish(key,receipt);c.end(name+'_checkpoint');verify_parent()
    return receipt
