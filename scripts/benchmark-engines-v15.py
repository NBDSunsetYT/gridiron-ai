"""Local real-history scale/reproducibility check; no paid hosting CPU used."""
from pathlib import Path
import gzip,json,hashlib,sys,time,resource
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modeling.football_v15 import simulate_football,VERSION as FOOTBALL_VERSION
from modeling.nba_v15 import simulate_nba,VERSION as NBA_VERSION
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/engine-v15'
prior=ROOT/'docs/reports/v15-scale-benchmark.json'
report=json.loads(prior.read_text()) if prior.exists() else {'status':'running','scope':'local real historical inputs; mechanical/convergence check, not accuracy validation','runs':[],'retainedIndividualGames':0}
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def digest(r):return hashlib.sha256(json.dumps({k:r[k] for k in ['scoreDistributions','players','convergence']},sort_keys=True).encode()).hexdigest()
for sport in ['NFL','CFB','NBA']:
 if len([r for r in report['runs'] if r['sport']==sport])==5:continue
 folder=OUT/'candidate-hurdle/models' if sport!='NBA' else OUT/'nba/models-15.1.1'
 files=sorted(folder.glob((sport+'-*' if sport!='NBA' else '*')+'.json.gz'))
 model=load(files[0]);event='2026-01-01T00:00:00+00:00' if sport!='NBA' else '2025-06-01T00:00:00+00:00'
 if sport=='NBA':home,away='2','18';fn=simulate_nba;args={'batch_size':2000}
 else:home,away=[t for t in model['teams'] if len(model['histories'].get(t,{}))>=3][:2];fn=simulate_football;args={'batch_size':2000,'representative_games':0}
 previous=None
 for n,seed in [(10000,15023),(10000,15023),(10000,15024),(50000,15023),(100000,15023)]:
  start=time.process_time();wall=time.perf_counter();r=fn(model,home,away,event,n,seed,**args);raw=json.dumps(r,separators=(',',':')).encode();sha=digest(r)
  row={'sport':sport,'modelVersion':r['modelVersion'],'inputVersion':model['sha256'],'games':n,'seed':seed,'cpuSeconds':time.process_time()-start,'wallSeconds':time.perf_counter()-wall,'rssHighWaterBytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'compressedSummaryBytes':len(gzip.compress(raw,mtime=0)),'homeWinProbability':r['homeWinProbability'],'monteCarloSE':r['monteCarloSE'],'monteCarloInterval95':r['monteCarloInterval95'],'accounting':r['quality'],'distributionChecksum':sha}
  if previous and previous['games']==n and previous['seed']==seed:assert sha==previous['distributionChecksum'];row['exactSeedReplayPassed']=True
  for d in r['scoreDistributions'].values():assert sum(v['count'] for v in d['histogram'])==n
  report['runs'].append(row);previous=row;print(json.dumps(row),flush=True)
  (ROOT/'docs/reports/v15-scale-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
report['status']='passed';report['limitations']=['Independent-seed differences measure numerical sampling variation, not underlying model validity.','Same-seed exact replay requires identical model, code, dependency versions and batch configuration.']
(ROOT/'docs/reports/v15-scale-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
