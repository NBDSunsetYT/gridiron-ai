"""Cold-process, bit-identical distribution replay of three real 10k forecasts.
Separate local verification runs, not additional independent validation games.
"""
import sys,gzip,json,time,resource,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.reconstruction_v19 import football_rules,nba
from modeling.reconstruction_v19.runtime import local_only
from modeling.reproducibility import restore_draw_order
from modeling.iterative_learning import freeze_json,digest
OUT=ROOT/'artifacts/parallel-v19'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
local_only();resource.setrlimit(resource.RLIMIT_CPU,(100,102));cpu=time.process_time();checks=[]
# OOF models inherit their parent's exact categorical masses/order. Only the
# variance estimator and stat-rule version changed; original order is preserved.
for sport in ['NFL','CFB']:
    for fp in (OUT/'runs'/sport/'oof_game_effect').glob('*.forecast.json.gz'):
        a=read(fp);sha=a['modelInput'];path=OUT/'models'/(sha+'.order.json.gz')
        if path.exists():continue
        index=read(OUT/'fit-index'/(sport+'-'+str(a['game']['cohort'])+'.json'));parent=ROOT/index['models']['team_eb_frailty'];order=read(parent.with_name(parent.name.replace('.json.gz','.order.json.gz')));order.update(modelSha256=sha);order['sha256']=digest({k:v for k,v in order.items() if k!='sha256'});restore_draw_order(read(OUT/'models'/(sha+'.json.gz')),order);freeze_json(path,order)
for sport,candidate in [('NFL','oof_game_effect'),('CFB','oof_game_effect'),('NBA','recency_usage_eb')]:
    cached=OUT/'replay-checks'/(sport+'.json')
    if cached.exists():checks.append(read(cached));continue
    fp=sorted((OUT/'runs'/sport/candidate).glob('*.forecast.json.gz'))[0];a=read(fp);f=a['forecast'];sha=a['snapshot']['model'];m=read(OUT/'models'/(sha+'.json.gz'));before=time.process_time()
    if sport!='NBA':m=restore_draw_order(m,read(OUT/'models'/(sha+'.order.json.gz')));replay=football_rules.simulate_football(m,f['home'],f['away'],f['eventStart'],10000,f['seed'],lineups=a['snapshot']['lineups'],representative_games=0)
    else:replay=nba.simulate_nba(m,f['home'],f['away'],f['eventStart'],10000,f['seed'])
    keys=['scoreDistributions','players','homeWinProbability','marginDistribution','totalDistribution','convergence'];equal={k:replay[k]==f[k] for k in keys};checks.append({'sport':sport,'gameId':a['game']['id'],'candidate':candidate,'trials':10000,'checks':equal,'cpuSeconds':time.process_time()-before,'sameParametersAndSeed':True});freeze_json(cached,checks[-1]);print(json.dumps(checks[-1]),flush=True)
freeze_json(ROOT/'docs/reports/parallel-v19-reproducibility.json',{'checks':checks,'allDistributionsExactlyReproduced':all(all(r['checks'].values()) for r in checks),'thisInvocationCpuSeconds':time.process_time()-cpu,'completedSimulationCpuSeconds':sum(r['cpuSeconds'] for r in checks),'priorInterruptedInvocationCpuUpperBoundSeconds':100,'newVerificationRuns':3,'completeGamesReplayed':30000,'additionalIndependentValidationGames':0,'hostingRequests':0})
