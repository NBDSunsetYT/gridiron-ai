"""Cold-process verification of compact saved inputs and seeded outcomes."""
import gzip,json,sys,time,resource,hashlib,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18 import nba,football
from modeling.reproducibility import restore_draw_order
from modeling.iterative_learning import digest,unrealism_flags
OUT=ROOT/'artifacts/structural-v18'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
if os.environ.get('VERCEL') or os.environ.get('RENDER'):raise SystemExit('Offline verification only')
resource.setrlimit(resource.RLIMIT_CPU,(90,92));cpu=time.process_time();checks=[]
for sport,candidate in [('NBA','learned_minutes'),('NBA','rotation_bootstrap'),('NFL','allocation_only')]:
    path=next(iter(sorted((OUT/'full-games'/sport/candidate).glob('*.forecast.json.gz'))));saved=read(path);f=saved['forecast'];m=read(OUT/'full-models'/(f['inputDataVersion']+'.json.gz'))
    if digest({k:v for k,v in m.items() if k!='sha256'})!=m['sha256']:raise ValueError('Saved input artifact hash changed')
    if sport!='NBA':m=restore_draw_order(m,read(OUT/'full-models'/(m['sha256']+'.order.json.gz')))
    args=(m,f['home'],f['away'],f['eventStart'],10000,f['seed']);result=nba.simulate_nba(*args) if sport=='NBA' else football.simulate_football(*args,representative_games=0)
    for k in ['scoreDistributions','players','totalDistribution','marginDistribution','convergence']:
        if result[k]!=f[k]:raise ValueError('Cold seeded replay differs: '+sport+':'+candidate+':'+k)
    if unrealism_flags(result):raise ValueError('Replayed accounting quality failed')
    checks.append({'sport':sport,'candidate':candidate,'simulations':10000,'forecastSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'exactPlayerAndScoreHistograms':True});print(json.dumps(checks[-1]),flush=True)
report={'checks':checks,'cpuSeconds':time.process_time()-cpu,'hostingCpuSeconds':0,'newForecasts':0,'additionalVerificationGames':30000,'originalForecastsChanged':False};(OUT/'cold-replay.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');print(json.dumps(report),flush=True)
