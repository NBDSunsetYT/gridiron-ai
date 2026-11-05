"""Durable active-time accounting and one-writer research checkpoints.
A dead/inactive environment accrues no new measured runtime. Interrupted work
reserves its declared CPU budget until reconciled; retries cannot bypass caps.
"""
from pathlib import Path
import os,json,time,hashlib,fcntl,signal
from contextlib import contextmanager
from datetime import datetime,timezone

def now():return datetime.now(timezone.utc).isoformat()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.partial');raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def read(path,default=None):
    p=Path(path);return json.loads(p.read_text()) if p.exists() else default

def process_identity(pid):
    try:return {'pid':pid,'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'startTicks':Path('/proc/'+str(pid)+'/stat').read_text().split()[21]}
    except (FileNotFoundError,ProcessLookupError):return None

def alive(identity):return identity is not None and process_identity(identity['pid'])==identity

class Campaign:
    def __init__(self,folder,maximum_seconds=36000,cpu_budget=36000):
        self.path=Path(folder);self.path.mkdir(parents=True,exist_ok=True);self.maximum=maximum_seconds;self.cpu_budget=cpu_budget;self.session=None;self.tick=None
    @contextmanager
    def lease(self):
        with (self.path/'runner.lock').open('a') as f:
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('A V20 runner already holds the lease; no duplicate process started')
            try:yield
            finally:fcntl.flock(f,fcntl.LOCK_UN)
    def event(self,kind,**values):
        row={'at':now(),'kind':kind,**values};row['sha256']=digest(row)
        with (self.path/'events.jsonl').open('a') as f:f.write(json.dumps(row,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
    def state(self):return read(self.path/'state.json',{'version':20,'measuredActiveSeconds':0.,'unobservedActiveUpperBoundSeconds':0.,'completedCpuSeconds':0.,'interruptedCpuReservedSeconds':0.,'sessions':[],'jobs':{},'maximumSeconds':self.maximum,'cpuBudgetSeconds':self.cpu_budget})
    def begin(self):
        state=self.state()
        for previous in state['sessions']:
            if previous['status']=='active':
                if alive(previous['identity']):raise RuntimeError('Another live session exists')
                previous['status']='interrupted';state['unobservedActiveUpperBoundSeconds']+=10
        self.session=digest({'started':now(),'identity':process_identity(os.getpid())})[:20];self.tick=time.monotonic();state['sessions'].append({'id':self.session,'identity':process_identity(os.getpid()),'startedAt':now(),'status':'active','lastHeartbeatAt':now()});state['status']='running';atomic(self.path/'state.json',state);self.event('session_started',session=self.session)
    def heartbeat(self):
        t=time.monotonic();s=self.state();delta=t-self.tick;self.tick=t;s['measuredActiveSeconds']+=delta
        session=next(x for x in s['sessions'] if x['id']==self.session);session['lastHeartbeatAt']=now();session['activeSeconds']=session.get('activeSeconds',0.)+delta;atomic(self.path/'state.json',s);return s
    def may_start(self,cpu_reservation):
        s=self.state();used=s['measuredActiveSeconds']+s['unobservedActiveUpperBoundSeconds']+s.get('setupSafetyChargeSeconds',0);reserved=sum(j.get('cpuReservation',0) for j in s['jobs'].values() if j['status']=='running')
        if used+10>=self.maximum:return False,'maximum_cumulative_active_runtime'
        if s['completedCpuSeconds']+s['interruptedCpuReservedSeconds']+reserved+cpu_reservation>self.cpu_budget:return False,'cumulative_cpu_budget'
        return True,None
    def claim(self,job,identity,cpu_reservation,inputs):
        s=self.state();old=s['jobs'].get(job)
        if old and old['status']=='completed':return False
        if old and old['status']=='running':
            if alive(old['identity']):raise RuntimeError('Live task already claimed')
            old['status']='interrupted';s['interruptedCpuReservedSeconds']+=old['cpuReservation'];self.event('interrupted_job_reserved',job=job,cpuSeconds=old['cpuReservation'])
        if old and old.get('fingerprint')!=digest(inputs):raise ValueError('Job inputs changed; preserve it and register a new experiment ID')
        s['jobs'][job]={'status':'running','identity':identity,'startedAt':now(),'cpuReservation':cpu_reservation,'fingerprint':digest(inputs),'attempt':old.get('attempt',0)+1 if old else 1};atomic(self.path/'state.json',s);return True
    def finish(self,job,receipt):
        s=self.state();entry=s['jobs'][job];entry.update(status=receipt['status'],finishedAt=now(),receipt=receipt);s['completedCpuSeconds']+=receipt.get('cpuSeconds',entry['cpuReservation']);atomic(self.path/'state.json',s);self.event('job_finished',job=job,status=receipt['status'],cpuSeconds=receipt.get('cpuSeconds'))
    def end(self,reason):
        s=self.heartbeat();s['status']='checkpointed';s['stopReason']=reason;next(x for x in s['sessions'] if x['id']==self.session).update(status='stopped',finishedAt=now());atomic(self.path/'state.json',s);self.event('session_stopped',session=self.session,reason=reason)
