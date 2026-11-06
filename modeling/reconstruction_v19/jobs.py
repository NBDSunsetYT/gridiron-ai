"""Local, single-flight research tasks with persistent CPU accounting.
Not a Vercel/Render request path. Completed immutable outputs are reused. A
crashed task requires budget reconciliation, never automatic costly retries.
Callers enumerate every input dataset and result-affecting model configuration;
changed inputs select a new task identity, never an outdated cached forecast.
"""
import fcntl,hashlib,json,os,resource,subprocess,sys
from pathlib import Path
from .runtime import local_only
from .evidence import canonical
class LocalCampaign:
    def __init__(self,folder,cpu_budget=1800):
        if not 1<=cpu_budget<=1800:raise ValueError('Research CPU budget must be 1..1800 seconds')
        self.path=Path(folder);self.path.mkdir(parents=True,exist_ok=True);self.budget=cpu_budget
    def run(self,task,script,outputs,*,inputs,configuration,cpu_limit=60,wall_limit=120):
        local_only()
        if not 1<=cpu_limit<=self.budget or not 1<=wall_limit<=3600:raise ValueError('Invalid bounded task limits')
        if not isinstance(configuration,dict) or not configuration:raise ValueError('Explicit model/seed/trial/cutoff configuration is required')
        input_hashes={str(Path(p).resolve()):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in inputs}
        script=Path(script).resolve();outputs=[Path(p).resolve() for p in outputs];identity=hashlib.sha256(canonical({'task':task,'script':str(script),'sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'outputs':list(map(str,outputs)),'inputs':input_hashes,'configuration':configuration})).hexdigest();receipt=self.path/(identity+'.json')
        with (self.path/'campaign.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Research already running; no duplicate work was started')
            logs=[json.loads(p.read_text()) for p in self.path.glob('*.json')]
            if any(l['status']=='running' for l in logs):raise RuntimeError('Prior interrupted task needs explicit CPU budget reconciliation')
            if receipt.exists():
                r=json.loads(receipt.read_text())
                if r['status']!='completed':raise RuntimeError('Failed task is not automatically repeated')
                if any(not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in r['outputHashes'].items()):raise ValueError('Completed output changed; use a new campaign')
                return r|{'cacheHit':True}
            if any(p.exists() for p in outputs):raise ValueError('Unreceipted outputs exist; preserve and audit before resuming')
            spent=sum(l.get('cpuSeconds',0) for l in logs)
            if spent+cpu_limit>self.budget:raise RuntimeError('Campaign CPU budget exhausted before starting another task')
            r={'task':task,'identity':identity,'status':'running','reservedCpuSeconds':cpu_limit,'cpuSeconds':None};receipt.write_bytes(canonical(r));before=resource.getrusage(resource.RUSAGE_CHILDREN);env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            # setrlimit is applied in the child. No shell, tokens, credentials,
            # model payload or private record is added to the command/log.
            def bounds():resource.setrlimit(resource.RLIMIT_CPU,(cpu_limit,cpu_limit+1))
            try:
                with (self.path/(identity+'.log')).open('wb') as log:result=subprocess.run([sys.executable,str(script)],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=wall_limit,preexec_fn=bounds)
                if result.returncode:raise RuntimeError('Research subprocess failed; inspect its local log')
                if any(not p.is_file() for p in outputs):raise RuntimeError('Research did not produce all expected outputs')
                r.update(status='completed',outputHashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs})
            except (RuntimeError,subprocess.TimeoutExpired) as e:r.update(status='failed',reason=str(e));raise
            finally:
                after=resource.getrusage(resource.RUSAGE_CHILDREN);r['cpuSeconds']=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime;receipt.write_bytes(canonical(r))
            return r|{'cacheHit':False}
