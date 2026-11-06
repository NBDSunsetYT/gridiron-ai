"""Bounded local worker. Never starts itself from a web request or cron.

python scripts/compute-worker.py --max-jobs 2 --cpu-seconds 300 --wall-seconds 600
Secrets come only from the operator environment. No new cloud resource required.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def validate_worker_config():
    for name in ['SUPABASE_URL','SUPABASE_PUBLISHABLE_KEY','GRIDIRON_PUBLIC_INGEST_TOKEN','SIMULATION_SERVICE_TOKEN']:
        if not os.environ.get(name):raise ValueError('Required worker setting missing: '+name)
    url=urlsplit(os.environ['SUPABASE_URL'])
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('Use the verified HTTPS Supabase project origin')
    for name in ['GRIDIRON_PUBLIC_INGEST_TOKEN','SIMULATION_SERVICE_TOKEN']:
        if len(os.environ[name])<32:raise ValueError('Worker capability is too short')

def rpc(payload):
    base=os.environ['SUPABASE_URL'].rstrip('/')
    req=urllib.request.Request(base+'/rest/v1/rpc/gridiron_compute_jobs',
        data=json.dumps({'token':os.environ['GRIDIRON_PUBLIC_INGEST_TOKEN'],'payload':payload}).encode(),
        headers={'apikey':os.environ['SUPABASE_PUBLISHABLE_KEY'],'Content-Type':'application/json'},method='POST')
    # HTTP_PROXY/HTTPS_PROXY and CA trust remain inherited from the runtime.
    with urllib.request.build_opener(NoRedirect).open(req,timeout=20) as response:return json.load(response)

def group_cpu(pgid):
    """Linux process-group CPU, including Python child and Node task; not billed CPU."""
    total=0.0
    for item in Path('/proc').iterdir():
        if not item.name.isdigit():continue
        try:
            fields=(item/'stat').read_text().rsplit(')',1)[1].split()
            if int(fields[2])==pgid:total+=sum(int(fields[i]) for i in (11,12,13,14))/os.sysconf('SC_CLK_TCK')
        except (OSError,ValueError,IndexError):pass
    return total

def stop_group(pgid):
    try:os.killpg(pgid,signal.SIGTERM)
    except ProcessLookupError:return
    time.sleep(.15)
    try:os.killpg(pgid,signal.SIGKILL)
    except ProcessLookupError:pass

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--max-jobs',type=int,default=2);p.add_argument('--cpu-seconds',type=float,default=300);p.add_argument('--wall-seconds',type=float,default=600);p.add_argument('--dry-run',action='store_true');p.add_argument('--refresh',action='store_true');p.add_argument('--preflight',action='store_true',help='Verify the durable queue without claiming or running a job');a=p.parse_args(argv)
    if os.environ.get('VERCEL') or os.environ.get('GRIDIRON_WORKER_REQUEST_LIFETIME')=='1':p.error('This worker cannot run on Vercel')
    if not 1<=a.max_jobs<=6 or not 1<=a.cpu_seconds<=1800 or not 1<=a.wall_seconds<=1800:p.error('Bounded worker budgets required')
    if a.dry_run:print(json.dumps({'execution':'disabled','maxJobs':a.max_jobs,'cpuSeconds':a.cpu_seconds,'wallSeconds':a.wall_seconds,'concurrency':1}));return
    if os.environ.get('GRIDIRON_COMPUTE_ROLE')!='worker' or os.environ.get('RENDER_SERVICE_TYPE')=='web' or os.environ.get('RENDER_SERVICE_ID') in ('srv-dblsg9gn74is73cjc8lg','srv-dbj680s9v7es7397nv2g'):
        p.error('An explicitly selected local/background worker is required; frontend and data-gateway execution are forbidden')
    validate_worker_config()
    if a.preflight:
        if a.refresh:p.error('Preflight is read-only and cannot request refresh work')
        status=rpc({'action':'status'})
        if not isinstance(status,dict) or status.get('role')!='cache_and_queue_only' or status.get('concurrency')!=1:
            raise ValueError('Unexpected queue policy; no work was claimed')
        print(json.dumps({'queueConnectivity':'verified','execution':'preflight_only','jobsClaimed':0,'simulationsStarted':0,'connection':'Supabase durable queue; Python model service binds loopback per controlled claim','queuePolicy':status,'continuousWorkerActive':False}));return
    if a.refresh:
        import hashlib
        task={'kind':'maintenance'};identity=hashlib.sha256(json.dumps(['bounded-compute-1',task],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        rpc({'action':'enqueue','id':identity,'task':task,'version':'bounded-compute-1'})
    began=time.monotonic();used=0.;completed=0
    for _ in range(a.max_jobs):
        remaining=min(300,a.wall_seconds-(time.monotonic()-began),a.cpu_seconds-used)
        if remaining<30:break
        job=rpc({'action':'claim','timeoutSeconds':int(remaining)})
        if not job:break
        # Every admitted task gets its own isolated process group and Python
        # endpoint. OS CPU limits and supervisor kill include cold model loading.
        import socket
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        env={**os.environ,'GRIDIRON_COMPUTE_ROLE':'worker','GRIDIRON_CLOUD_ONLY':'1','GRIDIRON_DEFER_AUTO_PROPS':'0','SIMULATION_SERVICE_URL':f'http://127.0.0.1:{port}', 'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','GRIDIRON_WORKER_REQUEST_LIFETIME':'0'}
        script='''import subprocess,sys,os,time,resource
resource.setrlimit(resource.RLIMIT_CPU,(int(sys.argv[2]),int(sys.argv[2])+1))
server=subprocess.Popen([sys.executable,'-m','uvicorn','modeling.service:app','--host','127.0.0.1','--port',sys.argv[1],'--workers','1','--no-access-log'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 import socket
 for _ in range(200):
  try:
   with socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=.2):break
  except OSError:time.sleep(.1)
 else:raise RuntimeError('Worker startup failed')
 task=subprocess.run(['node','--import','tsx','scripts/compute-task.ts'],stdin=sys.stdin,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 sys.exit(task.returncode)
finally:server.terminate()
'''
        child=subprocess.Popen([sys.executable,'-c',script,str(port),str(int(remaining))],cwd=ROOT,env=env,stdin=subprocess.PIPE,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        child.stdin.write(json.dumps(job).encode());child.stdin.close();start=time.monotonic();cpu=0.
        try:
            while child.poll() is None:
                cpu=max(cpu,group_cpu(child.pid))
                if cpu>a.cpu_seconds-used or time.monotonic()-start>remaining:stop_group(child.pid);break
                time.sleep(.1)
            child.wait(timeout=3)
        finally:stop_group(child.pid)
        used+=cpu;success=child.returncode==0;completed+=int(success)
        rpc({'action':'finish','id':job['id'],'generation':job['generation'],'success':success,'cpuMs':round(cpu*1000)})
        print(json.dumps({'kind':job['task']['kind'],'completed':success,'cpuSeconds':round(cpu,3),'wallSeconds':round(time.monotonic()-start,3)}),flush=True)
    print(json.dumps({'jobsCompleted':completed,'measuredProcessGroupCpuSeconds':round(used,3),'wallSeconds':round(time.monotonic()-began,3),'stop':'bounded_invocation_or_no_admitted_work'}))

if __name__=='__main__':
    try:main()
    except (KeyError,urllib.error.URLError,ValueError):print('Worker configuration or queue unavailable. No web computation was started.',file=sys.stderr);sys.exit(1)
