"""Isolated memory comparison on the same real CFB file; no forecasts or writes."""
import hashlib,importlib.util,json,resource,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
if sys.argv[1]=='before':
 spec=importlib.util.spec_from_file_location('modeling._memory_original',root/'tests/fixtures/performance-originals/cfb_public_research.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
else:
 from modeling import cfb_public_research as m
start=time.process_time();result=m.normalize_public_cfb(Path(sys.argv[2]),'2006','195','2026-11-03T00:00:00+00:00')
print(json.dumps({'phase':sys.argv[1],'cpuSeconds':time.process_time()-start,'peakRssBytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'outputSha256':hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()}))
