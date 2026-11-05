"""One bounded V21 job at a time, inheriting rather than resetting V20 costs."""
from pathlib import Path
import os,time,threading,signal,resource,hashlib,shutil
from .io import ROOT,OUT
from ..overnight_v20.state import Campaign,read,atomic,process_identity,digest
from ..reconstruction_v19.runtime import local_only
def protocol():return read(OUT/'protocol-effective.json',read(OUT/'protocol.json'))
def verify_parent():
    for path,sha in protocol()['sealedAndLockedFiles'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise RuntimeError('Protected V20 checkpoint changed: '+path)
    for item in protocol().get('sourceFiles',[])+protocol().get('rawSourceFiles',[]):
        path=Path(item['path']);path=path if path.is_absolute() else ROOT/path
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Research source checksum changed: '+str(path))
def job(name,callback,cpu=1200,wall=1800,revision='r1'):
    local_only();verify_parent();campaign=Campaign(OUT/'runtime');definition=read(OUT/('execution-'+revision+'.json'));key='v21-'+revision+'-'+name;old=campaign.state()['jobs'].get(key)
    if old and old['status']=='completed':return old['receipt']
    if not definition:raise RuntimeError('Register immutable V21 code/protocol before executing experiments')
    for path,sha in definition['numericCode'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise RuntimeError('Registered numerical code changed; preserve r1 and register a new revision')
    with campaign.lease():
        campaign.begin();allowed,why=campaign.may_start(cpu)
        if not allowed:campaign.end(why);raise RuntimeError(why)
        campaign.claim(key,process_identity(os.getpid()),cpu,definition);start=time.monotonic();before=time.process_time();child_before=resource.getrusage(resource.RUSAGE_CHILDREN);stop=threading.Event()
        def beat():
            while not stop.wait(5):
                campaign.heartbeat()
                rss=int(next((line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmRSS:')),'0'))*1024
                if rss>3*1024**3 or shutil.disk_usage(ROOT).free<268435456:os.kill(os.getpid(),signal.SIGTERM)
        def timeout(sig,frame):raise TimeoutError('Bounded V21 wall/signal stop')
        signal.signal(signal.SIGTERM,timeout);signal.signal(signal.SIGALRM,timeout);signal.alarm(wall);resource.setrlimit(resource.RLIMIT_CPU,(int(time.process_time())+cpu,int(time.process_time())+cpu+5));resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));thread=threading.Thread(target=beat,daemon=True);thread.start();receipt={'status':'failed','productionWrites':0,'productionPromotions':0,'newCompleteGameSimulations':0}
        try:
            from threadpoolctl import threadpool_limits
            with threadpool_limits(limits=1):
                receipt.update(callback());receipt['status']='completed'
        except Exception as e:receipt.update(error=type(e).__name__,reason=str(e));raise
        finally:
            stop.set();thread.join(timeout=10);signal.alarm(0);child_after=resource.getrusage(resource.RUSAGE_CHILDREN);child_cpu=child_after.ru_utime+child_after.ru_stime-child_before.ru_utime-child_before.ru_stime;receipt.update(cpuSeconds=time.process_time()-before+child_cpu,childCpuSeconds=child_cpu,activeSeconds=time.monotonic()-start,peakRssKiB=max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,child_after.ru_maxrss));atomic(OUT/'receipts'/(key+'.json'),receipt);campaign.finish(key,receipt);campaign.end(name+'_checkpoint');verify_parent()
    return receipt
