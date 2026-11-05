"""One bounded research subprocess. Not an app server or public endpoint."""
import sys,json,time,resource,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.cohort import run
from modeling.overnight_v20.state import atomic
sport=sys.argv[1];cohort=int(sys.argv[2]);receipt=Path(sys.argv[3]);resource.setrlimit(resource.RLIMIT_CPU,(1800,1802));start=time.monotonic()
try:r=run(sport,cohort)
except Exception as e:r={'status':'failed','sport':sport,'cohort':cohort,'error':type(e).__name__+': '+str(e),'cpuSeconds':time.process_time(),'activeSeconds':time.monotonic()-start};traceback.print_exc()
r['peakRssKiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;atomic(receipt,r)
if r['status']!='completed':sys.exit(1)
