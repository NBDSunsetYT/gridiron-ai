"""Resume only preregistered V21 work; never reset V20 costs or final sets.

An actual finite queue, not a claim of continuous execution during VM shutdown.
Each child obtains the inherited campaign lease and enforces its own budget.
"""
import sys,os,time,json,subprocess,fcntl,signal,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.io import OUT
from modeling.evidence_v21.runtime import verify_parent
from modeling.overnight_v20.state import Campaign,read,atomic
from modeling.reconstruction_v19.runtime import local_only
QUEUE=[('r1','statistical-components',['scripts/research-components-v21.py']),('independent-r2','independent-components',['scripts/research-independent-v21.py']),('season-r3','independent-components',['scripts/research-independent-v21.py','--campaign','season-confirmation']),('clock-accounting-r5','clock-components',['scripts/test-clock-evidence-v21.py','--revision','clock-accounting-r5']),('audit-r1','diagnostic-audit',['scripts/audit-results-v21.py']),('availability-r5','additional-availability',['scripts/recover-pregame-v21.py','--revision','availability-r5']),('source-repair-r1','source-repair-components',['scripts/research-source-repair-v21.py']),('schema-r2','forecast-report-schema',['scripts/repair-research-report-v21.py']),('clean-confirmation-r1','source-repair-components',['scripts/research-source-repair-v21.py','--campaign','clean-confirmation']),('verification-r2','regression-tests',['scripts/verify-v21.py','--revision','verification-r2','--python-only'])]
def main():
 local_only();verify_parent();c=Campaign(OUT/'runtime');status=[{'key':'v21-'+rev+'-'+name,'status':c.state()['jobs'].get('v21-'+rev+'-'+name,{}).get('status','pending')} for rev,name,args in QUEUE]
 if '--run' not in sys.argv:print(json.dumps({'queue':status,'productionWrites':False,'newFullGameSimulationsAllowed':False,'cumulativeBudgetState':{k:v for k,v in c.state().items() if k in ['measuredActiveSeconds','setupSafetyChargeSeconds','completedCpuSeconds','cpuBudgetSeconds','maximumSeconds']}} ,indent=2));return
 (OUT/'runtime').mkdir(exist_ok=True)
 with (OUT/'runtime/supervisor.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise SystemExit('A V21 supervisor is already active; no duplicate launched')
  for revision,name,args in QUEUE:
   key='v21-'+revision+'-'+name
   if c.state()['jobs'].get(key,{}).get('status')=='completed':continue
   if not (OUT/('execution-'+revision+'.json')).exists():raise SystemExit('Missing preregistration; refusing '+key)
   started=time.monotonic()
   while True:
    # Waiting consumes no research compute and cannot start a duplicate job.
    try:
     with c.lease():pass
     break
    except RuntimeError:
     if time.monotonic()-started>1200:raise SystemExit('Lease wait timeout; active work left unchanged')
     time.sleep(5)
   if shutil.disk_usage(ROOT).free<512*1024**2 or not c.may_start(1800)[0]:raise SystemExit('Resource/budget gate reached; checkpoints retained')
   log=OUT/'logs'/('resume-'+key+'.log');log.parent.mkdir(exist_ok=True)
   with log.open('a') as f:
    p=subprocess.Popen([sys.executable,*args],cwd=ROOT,stdout=f,stderr=f,start_new_session=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    atomic(OUT/'runtime/supervisor.json',{'status':'child_running','key':key,'pid':p.pid,'log':str(log),'startedAtMonotonic':time.monotonic()})
    try:code=p.wait(timeout=2700)
    finally:
     if p.poll() is None:
      os.killpg(p.pid,signal.SIGTERM)
      try:p.wait(timeout=10)
      except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   if code:raise SystemExit('Child failed with preserved checkpoint: '+key+'; '+str(log))
   verify_parent()
  result={'status':'checkpointed','stopReason':'registered_component_batches_complete_further_forecast_tuning_requires_new_verified_evidence','productionWrites':0,'promotions':0,'fullGameGateBypassed':False,'persistentExecutionGuaranteed':False};atomic(OUT/'runtime/supervisor.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
