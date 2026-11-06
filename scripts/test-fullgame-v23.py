"""Single-threaded bounded local regression suite with measured resources."""
import sys,subprocess,os,hashlib,json,time,resource
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.fullgame_v23.io import OUT
from modeling.fullgame_v23.runtime import job
from modeling.iterative_learning import freeze_json
def run():
    before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic()
    with (OUT/'python-suite.log').open('w') as f:r=subprocess.run([sys.executable,'-m','unittest','discover','-s','modeling','-t','.','-p','test_*.py'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'},timeout=600)
    after=resource.getrusage(resource.RUSAGE_CHILDREN);result={'exitCode':r.returncode,'wallSeconds':time.monotonic()-start,'cpuSeconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'peakRssKiB':after.ru_maxrss,'command':'python -m unittest discover -s modeling -t . -p test_*.py'}
    if r.returncode:raise RuntimeError('Regression suite failed; inspect python-suite.log')
    return result
if __name__=='__main__':
    if '--register' in sys.argv:freeze_json(OUT/'specs/tests-r1.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/fullgame_v23').glob('*.py')),ROOT/'modeling/test_fullgame_v23.py']},'heavyWorkloadTarget':'local supervised environment only','testTimeoutSeconds':600})
    else:print(json.dumps(job('tests-r1',run,cpu=500,wall=650),indent=2))
