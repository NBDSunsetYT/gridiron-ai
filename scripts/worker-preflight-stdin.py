"""Private operator stdin configuration. No files, job claims or model imports."""
import json,os,runpy,sys
from pathlib import Path
print('Worker preflight receiver ready.',flush=True)
try:
    config=json.loads(sys.stdin.readline())
    names=('SUPABASE_URL','SUPABASE_PUBLISHABLE_KEY','GRIDIRON_PUBLIC_INGEST_TOKEN','SIMULATION_SERVICE_TOKEN')
    if set(config)!=set(names) or any(not isinstance(config[k],str) for k in names):raise ValueError('Invalid worker configuration')
    os.environ.update(config)
    os.environ['GRIDIRON_COMPUTE_ROLE']='worker';os.environ['GRIDIRON_WORKER_REQUEST_LIFETIME']='0'
    sys.argv=['compute-worker.py','--preflight']
    runpy.run_path(str(Path(__file__).with_name('compute-worker.py')),run_name='__main__')
except (ValueError,KeyError):
    print('Worker preflight configuration invalid. No job was claimed.',file=sys.stderr);sys.exit(1)
