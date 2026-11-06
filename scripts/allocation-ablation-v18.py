"""LOCAL development ablation: isolate receiver/rusher allocation from the
new dropback intercept and QB inference. Reuses frozen earlier fitted artifacts.
No new fitting or calibration, no final-test selection, no production changes.
"""
import gzip,json,copy,hashlib,importlib.util,resource,time,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18 import football
from modeling.structural_v18.data import packets
from modeling.iterative_learning import digest,unrealism_flags
from modeling.reproducibility import restore_draw_order
spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/backtest-structural-v18.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
OUT=runner.OUT
if os.environ.get('VERCEL') or os.environ.get('RENDER'):raise SystemExit('Local research only')
resource.setrlimit(resource.RLIMIT_CPU,(270,272));cpu=time.process_time();start=time.monotonic();protocol=runner.read(OUT/'protocol.json');runner.runner.verify_sources(protocol)
plan={'candidate':'allocation_only','hypothesis':'If player weights help but the dropback shift harms team reliability, preserve the original state probabilities and inferred QB while changing only receiver/rusher allocation.','developmentReuse':True,'untouchedTest':False,'maxCpuSeconds':270,'maxGames':18,'simulations':10000,'noPromotion':True}
runner.runner.save(OUT/'allocation-ablation-plan.json',plan);results=[];skipped=[];count=0
for sport in ['NFL','CFB']:
    games={g['id']:g for g in packets(sport)}
    for path in sorted((OUT/'full-games'/sport/'learned_allocation').glob('*.forecast.json.gz')):
        if time.process_time()-cpu>240:skipped.append({'path':str(path),'reason':'Insufficient remaining CPU budget for a complete run'});continue
        original=runner.read(path);g=original['game'];sha=original['forecast']['inputDataVersion'];m=runner.read(OUT/'full-models'/(sha+'.json.gz'));order=runner.read(OUT/'full-models'/(sha+'.order.json.gz'));m=restore_draw_order(m,order);m.update(variant='allocation_only',dropbackLogitShift={t:0. for t in m['dropbackLogitShift']});m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});order['modelSha256']=m['sha256'];order['sha256']=digest({k:v for k,v in order.items() if k!='sha256'})
        runner.runner.save(OUT/'full-models'/(m['sha256']+'.json.gz'),m);runner.runner.save(OUT/'full-models'/(m['sha256']+'.order.json.gz'),order)
        fp=OUT/'full-games'/sport/'allocation_only'/path.name;ep=fp.with_name(fp.name.replace('.forecast.json.gz','.evaluation.json.gz'))
        if fp.exists():f=runner.read(fp)['forecast']
        else:
            t=time.process_time();f=football.simulate_football(m,g['home'],g['away'],g['at'],10000,original['forecast']['seed'],representative_games=0)
            if unrealism_flags(f):raise ValueError('Internal accounting failure')
            runner.runner.save(fp,{'game':g,'candidate':'allocation_only','forecast':f,'cpuSeconds':time.process_time()-t,'parentForecastSha256':runner.runner.digest(path),'protocol':plan,'sourceSha256':hashlib.sha256((ROOT/'modeling/structural_v18/football.py').read_bytes()).hexdigest()});count+=1
        result=runner.evaluate(f,games[g['id']]);result['candidate']='allocation_only';runner.runner.save(ep,result);results.append(result);print(json.dumps({'sport':sport,'game':g['id'],'cpuSeconds':time.process_time()-cpu}),flush=True)
runner.runner.save(OUT/'allocation-ablation-resources.json',{'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'runs':count,'completeGamesSimulated':count*10000,'skipped':skipped,'hostingCpuSeconds':0,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss});print(json.dumps({'runs':count,'cpuSeconds':time.process_time()-cpu,'skipped':skipped}),flush=True)
