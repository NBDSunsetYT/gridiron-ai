"""Reproducible CPU/equivalence benchmark. Fixtures never enter production.
Run from project root: python scripts/performance-benchmark.py --cfb-parquet /path/to/2026.parquet
"""
import argparse,copy,hashlib,importlib.util,json,os,resource,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.test_performance import original
from modeling.test_simulator import fixture_csv
from modeling.fit import fit_csv
from modeling import simulator,hierarchical_props,cfb_public_research,football_prop_feeds
from modeling.test_hierarchical_props import HierarchicalTests
from modeling.test_cfb_simulator import cfb_fixture_csv
from modeling.cfb_simulator import fit_cfb_csv,simulate_cfb

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def measured(fn):
 t=time.perf_counter();c=time.process_time();v=fn();return v,{'cpuSeconds':time.process_time()-c,'wallSeconds':time.perf_counter()-t}
def paired(name,before,after,project=lambda x:x):
 a,old=measured(before);b,new=measured(after)
 if project(a)!=project(b):raise AssertionError(name+' numerical mismatch')
 return {'workload':name,'before':old,'after':new,'cpuReductionPercent':100*(1-new['cpuSeconds']/old['cpuSeconds']),'exactOutputHash':digest(project(b))}

p=argparse.ArgumentParser();p.add_argument('--cfb-parquet');p.add_argument('--output',default='docs/reports/performance-benchmark.json');p.add_argument('--counts',default='10000,50000,100000');args=p.parse_args()
report={'version':'12.1.1','fixtureUse':'Synthetic NFL/CFB mechanical fixtures only. Public CFB normalization uses real published source when supplied. These benchmarks do not validate prediction accuracy or measure total hosting bills.','measure':'time.process_time CPU; perf_counter wall. Before and after run sequentially with identical inputs/seeds.','results':[]}
oldsim=original('simulator');oldhier=original('hierarchical_props');oldcfb=original('cfb_public_research');oldfeed=original('football_prop_feeds')
records=HierarchicalTests().records();report['results'].append(paired('chronological CDF fit and validation',lambda:oldhier._pool_candidate(records,'receptions','WR',2026),lambda:hierarchical_props._pool_candidate(records,'receptions','WR',2026)))
model=fit_csv(fixture_csv(),'SYNTHETIC PERFORMANCE MECHANICS','2024-02-01T00:00:00Z',100,{'recencyHalfLifeDays':90,'conditionalShrinkage':True})['model']
fields=['homeWinProbability','awayWinProbability','tieProbability','scoreDistributions','players','totalDistribution','marginDistribution','contracts','jointOutcomes','convergence','correlations','gameEnvironment']
project=lambda r:{k:r.get(k) for k in fields}
for n in [int(v) for v in args.counts.split(',') if v]:
 report['results'].append(paired('NFL '+str(n)+' complete games',lambda:oldsim.simulate(model,'SYNTH-A','SYNTH-B',n,1211,'2024-03-01T00:00:00Z'),lambda:simulator.simulate(model,'SYNTH-A','SYNTH-B',n,1211,'2024-03-01T00:00:00Z'),project));print('NFL',n,flush=True)
# Load the unchanged NCAA transition code against the original pooling class.
current=sys.modules['modeling.simulator'];sys.modules['modeling.simulator']=oldsim
spec=importlib.util.spec_from_file_location('modeling._old_cfb_simulator',ROOT/'modeling/cfb_simulator.py');oldncaa=importlib.util.module_from_spec(spec);spec.loader.exec_module(oldncaa);sys.modules['modeling.simulator']=current
cm=fit_cfb_csv(cfb_fixture_csv(),'SYNTHETIC PERFORMANCE MECHANICS','2024-02-01T00:00:00Z',100,{'recencyHalfLifeDays':90,'conditionalShrinkage':True})['model']
for n in [int(v) for v in args.counts.split(',') if v]:
 report['results'].append(paired('CFB '+str(n)+' complete games',lambda:oldncaa.simulate_cfb(cm,'cfb:SYNTH-A','cfb:SYNTH-B',n,1211,'2024-03-01T00:00:00Z'),lambda:simulate_cfb(cm,'cfb:SYNTH-A','cfb:SYNTH-B',n,1211,'2024-03-01T00:00:00Z'),project));print('CFB',n,flush=True)
if args.cfb_parquet:
 path=Path(args.cfb_parquet);report['publicCfbSourceSha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 report['results'].append(paired('real CFB parquet normalization, Akron/Ohio, unchanged row order',lambda:oldcfb.normalize_public_cfb(path,'2006','195','2026-11-03T00:00:00+00:00'),lambda:cfb_public_research.normalize_public_cfb(path,'2006','195','2026-11-03T00:00:00+00:00')))
# Identical already-validated cached board; provider requests deliberately zero.
os.environ.update(RENDER='true',RENDER_SERVICE_ID='SYNTHETIC',PROPLINE_API_KEY='SYNTHETIC-BENCHMARK-NOT-A-CREDENTIAL')
now=time.time();at=__import__('datetime').datetime.fromtimestamp(now,__import__('datetime').timezone.utc).isoformat();row={'provider':'PropLine','sport':'NFL','sourceUpdatedAt':at,'book':{'key':'draftkings'},'market':'player_pass_yds','player':{'id':'espn:1','name':'SYNTHETIC'},'kickoff':'2099-01-01','americanOdds':-110,'threshold':'250.5'}
board={'provider':'PropLine','sport':'NFL','items':[{**row,'id':str(i)} for i in range(10000)],'injuries':[],'status':'available'}
a=oldfeed.PropLineClient(clock=lambda:now);b=football_prop_feeds.PropLineClient(clock=lambda:now);a.cache['NFL']=(now,copy.deepcopy(board));b.cache['NFL']=(now,copy.deepcopy(board))
def oldpages():
 results=[]
 for i in range(10):
  value=a.read('NFL');rows=value['items'];results.append({**value,'items':rows[500:1000],'totalResults':len(rows),'nextCursor':1000})
 return results
def newpages():return [b.read_page('NFL',500,500) for _ in range(10)]
report['results'].append(paired('Render 10 warm 500-row pages from 10000-row board',oldpages,newpages))
report['rssHighWaterBytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
out=ROOT/args.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':'passed','report':str(out),'workloads':len(report['results'])}),flush=True)
