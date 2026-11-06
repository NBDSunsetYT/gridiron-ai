"""Second structural DEVELOPMENT iteration, not an untouched test or calibration.
Joint earlier team rotation plans replace fixed per-game minute targets.
Reuses original saved pregame models; no refit on the nine graded game outcomes.
"""
import gzip,json,copy,hashlib,importlib.util,resource,time,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18 import nba
from modeling.structural_v18.data import packets
from modeling.iterative_learning import digest,unrealism_flags
spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/backtest-structural-v18.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
OUT=runner.OUT
if os.environ.get('VERCEL') or os.environ.get('RENDER'):raise SystemExit('Local-only experimental candidate')
resource.setrlimit(resource.RLIMIT_CPU,(240,242));cpu=time.process_time();start=time.monotonic();protocol=runner.read(OUT/'protocol.json');runner.runner.verify_sources(protocol)
plan={'variant':'rotation_bootstrap','baseline':'original fixed-ridge learned_minutes','hypothesis':'Historical shared workload plans recover missing playing-time variance without treating DNP as a verified injury.','jointPlans':5,'recenter':'Scale observed minute vectors by learned expected minutes, reconcile 240-minute cap; no variance factor tuned to outcomes.','developmentReuse':True,'untouchedTest':False,'maximumCpuSeconds':240,'maximumGames':9,'simulations':10000,'noPromotion':True}
runner.runner.save(OUT/'rotation-bootstrap-plan.json',plan)
games={g['id']:g for g in packets('NBA')};results=[];skipped=[];count=0
for path in sorted((OUT/'full-games/NBA/learned_minutes').glob('*.forecast.json.gz')):
    if time.process_time()-cpu>210:skipped.append({'path':str(path),'reason':'Remaining CPU budget cannot support another complete run'});continue
    original=runner.read(path);g=original['game'];m=runner.read(OUT/'full-models'/(original['forecast']['inputDataVersion']+'.json.gz'));m['variant']='rotation_bootstrap';m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});runner.runner.save(OUT/'full-models'/(m['sha256']+'.json.gz'),m)
    fp=OUT/'full-games/NBA/rotation_bootstrap'/path.name;ep=fp.with_name(fp.name.replace('.forecast.json.gz','.evaluation.json.gz'))
    if fp.exists():f=runner.read(fp)['forecast']
    else:
        t=time.process_time();f=nba.simulate_nba(m,g['home'],g['away'],g['at'],10000,original['forecast']['seed'])
        if unrealism_flags(f):raise ValueError('Internal accounting failure')
        runner.runner.save(fp,{'game':g,'candidate':'rotation_bootstrap','forecast':f,'cpuSeconds':time.process_time()-t,'parentForecastSha256':runner.runner.digest(path),'protocol':plan,'sourceSha256':hashlib.sha256((ROOT/'modeling/structural_v18/nba.py').read_bytes()).hexdigest()});count+=1
    result=runner.evaluate(f,games[g['id']]);result['candidate']='rotation_bootstrap';runner.runner.save(ep,result);results.append(result);print(json.dumps({'game':g['id'],'cpuSeconds':time.process_time()-cpu}),flush=True)
runner.runner.save(OUT/'rotation-bootstrap-resources.json',{'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'runs':count,'completeGamesSimulated':count*10000,'skipped':skipped,'hostingCpuSeconds':0,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss});print(json.dumps({'runs':count,'cpuSeconds':time.process_time()-cpu,'skipped':skipped}),flush=True)
