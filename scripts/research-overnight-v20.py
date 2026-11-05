"""Resumable ten-hour, local-cloud research controller with real heartbeats.
Does not install a paid scheduler or promise to survive environment shutdown.
"""
import sys,os,json,time,signal,subprocess,resource,argparse,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import Campaign,atomic,read,process_identity
from modeling.reconstruction_v19.runtime import local_only
from modeling.overnight_v20.sources import protocol
OUT=ROOT/'artifacts/overnight-v20'
p=argparse.ArgumentParser();p.add_argument('--slice-seconds',type=int,default=1800);p.add_argument('--status',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--revision',default='r1');args=p.parse_args();campaign=Campaign(OUT/'runtime')
if args.status:print(json.dumps(campaign.state(),indent=2));sys.exit(0)
if not 30<=args.slice_seconds<=36000:p.error('Slice must be 30..36000 seconds')
import re
if not re.fullmatch(r'r[1-9][0-9]*',args.revision):p.error('Revision must be r1, r2, ...')
local_only();spec=protocol();stop=False
for file in ['NFL','CFB','NBA']:
    if not (OUT/'evidence'/(file+'-aligned-v3.json.gz')).exists():raise RuntimeError('Run source reconstruction before the expensive queue')
model_files=list((ROOT/'modeling/overnight_v20').glob('*.py'));fingerprint={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in model_files};jobs=[]
for c in range(4):
    for sport in ['NFL','CFB','NBA']:
        if any(g['cohort']==c for g in spec['selection'][sport]):jobs.append((sport,c))
# Initial implementation/spec is immutable before grading. A resume with changed
# math must become a separately named experiment rather than overwrite work.
registry=OUT/('execution-spec-'+args.revision+'.json');body={'jobs':jobs,'revision':args.revision,'modelFiles':fingerprint,'protocolSha256':hashlib.sha256((OUT/'protocol-effective.json').read_bytes()).hexdigest(),'maxWorkers':2,'sourceEvidence':{s:hashlib.sha256((OUT/'evidence'/(s+'-aligned-v3.json.gz')).read_bytes()).hexdigest() for s in ['NFL','CFB','NBA']},'primaryMetrics':spec['primaryMetrics'],'productionPromotion':False,'modelTrainingMaximumGames':500}
if registry.exists():
    original=read(registry)
    if original!=body:
        # Resume-only orchestration fixes may not change numerical code, inputs
        # or job identity. Preserve the original CAS fingerprint and record both
        # implementations; mathematical changes still require a new revision.
        def numerical(v):
            v=dict(v);v['modelFiles']={k:h for k,h in v['modelFiles'].items() if not k.endswith(('/state.py','/__init__.py'))};return v
        if numerical(original)!=numerical(body):raise RuntimeError('Numerical code/input fingerprint changed. Preserve outputs and register a new experiment revision.')
        audit=OUT/'runtime'/('orchestration-compatibility-'+hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()+'.json')
        if not audit.exists():atomic(audit,{'original':original,'observed':body,'numericalInputsUnchanged':True})
        body=original
else:atomic(registry,body)
def nonimproving_candidates(state):
    # A candidate evaluated in four windows is one model, not four candidates.
    # Only fully evaluated configurations enter the consecutive-failure limit.
    completed=[]
    for sport in ['NFL','CFB','NBA']:
        expected=[args.revision+'-'+s+'-'+str(c) for s,c in jobs if s==sport]
        entries=[state['jobs'].get(k,{}) for k in expected]
        if not entries or not all(e.get('status')=='completed' for e in entries):continue
        outcomes={}
        for e in entries:
            for o in e.get('receipt',{}).get('experimentOutcomes',[]):outcomes.setdefault(o['variant'],[]).append(o)
        for variant,windows in outcomes.items():
            completed.append((max(e['finishedAt'] for e in entries),sport,variant,all(o['meaningfulConditionalImprovement'] for o in windows)))
    n=0
    for _,sport,variant,better in sorted(completed):n=0 if better else n+1
    return n
def handle(signum,frame):
    global stop
    stop=True
signal.signal(signal.SIGTERM,handle);signal.signal(signal.SIGINT,handle)
with campaign.lease():
    campaign.begin();start=time.monotonic();running={};reason='predefined_experiment_queue_completed';idle=False
    try:
        while True:
            state=campaign.heartbeat()
            for key,(proc,sport,c,receipt) in list(running.items()):
                rss=0
                try:
                    fields=Path('/proc/'+str(proc.pid)+'/status').read_text().splitlines();rss=int(next(x.split()[1] for x in fields if x.startswith('VmRSS:')))*1024
                except (FileNotFoundError,StopIteration):pass
                if rss>spec['workerMaxRssBytes']:proc.terminate();reason='worker_memory_limit'
                if proc.poll() is not None:
                    r=read(receipt,{'status':'failed','error':'Subprocess exited before writing its receipt','cpuSeconds':1800,'exitCode':proc.returncode});campaign.finish(key,r)
                    del running[key];print(json.dumps({'completed':key,'status':r['status'],'simulatedGames':r.get('completeGamesSimulated',0),'cpuSeconds':r['cpuSeconds']}),flush=True)
            if stop or time.monotonic()-start>=args.slice_seconds-10:reason='requested_stop' if stop else 'execution_slice_checkpoint';idle=True
            if state['measuredActiveSeconds']+state['unobservedActiveUpperBoundSeconds']+state.get('setupSafetyChargeSeconds',0)>=36000-10:reason='maximum_ten_hour_active_runtime';break
            if shutil.disk_usage(ROOT).free<spec['minimumFreeBytes']:reason='disk_space_guard';break
            if sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())>spec['maximumCampaignBytes']:reason='campaign_storage_guard';break
            if not idle:
                for sport,c in jobs:
                    key=args.revision+'-'+sport+'-'+str(c);entry=campaign.state()['jobs'].get(key)
                    if key in running or entry and entry['status'] in ('completed','failed'):continue
                    if len(running)>=2:break
                    if nonimproving_candidates(campaign.state())>=20:reason='twenty_consecutive_nonimproving_candidates';idle=True;break
                    allowed,why=campaign.may_start(1800)
                    if not allowed:reason=why;idle=True;break
                    log=OUT/'logs'/(key+'.log');log.parent.mkdir(exist_ok=True);receipt=OUT/'receipts'/(key+'.json');env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONHASHSEED='0',GRIDIRON_RESEARCH_REVISION=args.revision)
                    with log.open('ab') as output:proc=subprocess.Popen([sys.executable,str(ROOT/'scripts/overnight-v20-worker.py'),sport,str(c),str(receipt)],stdin=subprocess.DEVNULL,stdout=output,stderr=output,env=env,start_new_session=True)
                    campaign.claim(key,process_identity(proc.pid),1800,body);running[key]=(proc,sport,c,receipt);print(json.dumps({'started':key,'pid':proc.pid}),flush=True)
            if not running:
                if idle or all(campaign.state()['jobs'].get(args.revision+'-'+s+'-'+str(c),{}).get('status') in ('completed','failed') for s,c in jobs):break
            # Wall timeouts are enforced even if a job waits on a provider.
            for key,(proc,sport,c,receipt) in running.items():
                began=campaign.state()['jobs'][key]['startedAt'];from datetime import datetime,timezone
                if (datetime.now(timezone.utc)-datetime.fromisoformat(began)).total_seconds()>1800:proc.terminate();reason='worker_wall_timeout'
            time.sleep(5)
    finally:
        for key,(proc,sport,c,receipt) in list(running.items()):
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            campaign.finish(key,read(receipt,{'status':'interrupted','error':'Controller stopped; completed artifacts remain; reserved CPU charged until reconciliation','cpuSeconds':1800}))
        campaign.end(reason)
    print(json.dumps({'state':'checkpointed','reason':reason,'activeSeconds':campaign.state()['measuredActiveSeconds'],'cpuSeconds':campaign.state()['completedCpuSeconds'],'resume':'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python scripts/research-overnight-v20.py --resume --slice-seconds 1800'}),flush=True)
