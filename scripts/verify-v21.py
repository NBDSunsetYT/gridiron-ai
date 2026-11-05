"""Local regression suite with bounded child groups and accounted child CPU."""
import sys,os,signal,subprocess,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.runtime import job
from modeling.evidence_v21.io import OUT
from modeling.overnight_v20.state import atomic
def run():
 results=[];folder=OUT/'tests';folder.mkdir(exist_ok=True)
 suites=[('python',['python','-m','unittest','discover','-s','modeling','-t','.','-p','test_*.py'])]
 if not PYTHON_ONLY:suites.append(('javascript',['node','node_modules/vitest/vitest.mjs','run','--maxWorkers','2']))
 for name,command in suites:
  start=time.monotonic();env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
  log=folder/(name+'-'+REVISION+'.log')
  with log.open('x') as f:
   p=subprocess.Popen(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=env,start_new_session=True)
   try:code=p.wait(timeout=420)
   finally:
    if p.poll() is None:
     os.killpg(p.pid,signal.SIGTERM)
     try:p.wait(timeout=5)
     except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  results.append({'suite':name,'command':command,'exitCode':code,'wallSeconds':time.monotonic()-start,'log':str(log)})
  atomic(folder/('results-'+REVISION+'.json'),results);print(json.dumps(results[-1]),flush=True)
  if code:raise RuntimeError(name+' regression suite failed; see preserved log')
 return {'tests':results,'newCompleteGameSimulations':0,'note':'Unit test fixtures are not new historical forecasting evaluations.'}
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--revision',default='verification-r1');parser.add_argument('--python-only',action='store_true');args=parser.parse_args();REVISION=args.revision;PYTHON_ONLY=args.python_only;print(json.dumps(job('regression-tests',run,cpu=900,wall=1000,revision=REVISION),indent=2))
