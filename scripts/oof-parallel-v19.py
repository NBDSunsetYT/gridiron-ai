"""Second balanced football structural iteration; zero validation metrics tuned.
Reuses frozen core parameters, changes only training-heldout heterogeneity and
NCAA statistical credit. NFL/CFB estimation and forecast schedule stay balanced.
"""
import sys,json,gzip,copy,time,resource,importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.reconstruction_v19.oof_variance import estimate
from modeling.reconstruction_v19 import football_rules
from modeling.reconstruction_v19.runtime import local_only
from modeling.structural_v18.data import archives,packets
from modeling.reproducibility import restore_draw_order
from modeling.iterative_learning import digest,freeze_json,unrealism_flags
OUT=ROOT/'artifacts/parallel-v19';local_only();spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/run-parallel-v19.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
resource.setrlimit(resource.RLIMIT_CPU,(350,352));cpu=time.process_time();start=time.monotonic();p=runner.read(OUT/'protocol.json');plan={'hypothesis':'In-sample residual fitting can absorb game heterogeneity. Withhold 28 earlier training days before estimating a shared completion-game effect. Do not force a nonzero estimate.','leagues':['NFL','CFB'],'maximumRuns':18,'trials':10000,'cpuBudgetSeconds':350,'usesOwnValidationOutcomesForFitting':False,'validationMetricsInspectedBeforeChoosingThisEstimator':False,'alsoApplies':'NCAA statistical team credit for known simulated kneels; no invented spike subtype','noPromotion':True};freeze_json(OUT/'oof-plan.json',plan);data={s:archives(s) for s in ['NFL','CFB']};actual={s:{g['id']:g for g in packets(s)} for s in data};reports=[];count=0;cache_hits=0;failures=[];stop='predeclared_balanced_candidates_completed'
for cohort in range(3):
    if time.process_time()-cpu>280:stop='compute_budget_before_next_balanced_cohort';break
    estimates={};models={}
    def build(sport):
        index=runner.read(OUT/'fit-index'/(sport+'-'+str(cohort)+'.json'));m=runner.read(ROOT/index['models']['team_eb_frailty']);m=restore_draw_order(m,runner.read((ROOT/index['models']['team_eb_frailty']).with_name(Path(index['models']['team_eb_frailty']).name.replace('.json.gz','.order.json.gz'))));rows=[r for r in data[sport]['rows'] if r['game'] in set(m['trainingGameIds'])];ev=estimate(rows,data[sport]['games'],m['fittingCutoff']);m.update(version=football_rules.VERSION,completionFrailtySD=ev['sd'],completionFrailtyEvidence=ev,statRuleVersion='NCAA-team-kneel-19.1',candidateRecipe='chronological-training-holdout-game-effect-19.1');m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});return m,ev
    with ThreadPoolExecutor(max_workers=2) as pool:
        fs={s:pool.submit(build,s) for s in ['NFL','CFB']}
        for sport,f in fs.items():models[sport],ev=f.result();estimates[sport]=ev;reports.append({'sport':sport,'cohort':cohort,**ev});runner.save_model(models[sport]);print(json.dumps({'stage':'variance','sport':sport,'cohort':cohort,'sd':ev['sd'],'status':ev['status'],'cpuSeconds':time.process_time()-cpu}),flush=True)
    for ordinal in range(3):
        if time.process_time()-cpu>320:stop='compute_budget_before_next_balanced_pair';break
        for sport in ['NFL','CFB']:
            g=[g for g in p['selection'][sport] if g['cohort']==cohort][ordinal];original_path=OUT/'runs'/sport/'team_eb_frailty'/(g['id'].replace(':','_')+'.forecast.json.gz');original=runner.read(original_path);m=models[sport];fp=OUT/'runs'/sport/'oof_game_effect'/(g['id'].replace(':','_')+'.forecast.json.gz');ep=fp.with_name(fp.name.replace('.forecast.json.gz','.evaluation.json.gz'))
            try:
                begin=time.process_time();f=football_rules.simulate_football(m,g['home'],g['away'],g['at'],10000,original['forecast']['seed'],lineups=original['snapshot']['lineups'],representative_games=0)
                if unrealism_flags(f):raise ValueError('Full-game accounting failed')
                # Bookkeeping does not change NFL physical/player outcomes. A
                # zero estimated effect must not be claimed as new information.
                if estimates[sport]['sd']==0:
                    if f['scoreDistributions']!=original['forecast']['scoreDistributions']:raise ValueError('Zero-effect game distribution changed unexpectedly')
                    if sport=='NFL' and f['players']!=original['forecast']['players']:raise ValueError('NFL zero-effect player statistics changed')
                    cache_hits+=1
                freeze_json(fp,{'game':g,'candidate':'oof_game_effect','forecast':f,'snapshot':original['snapshot']|{'model':m['sha256']},'modelInput':m['sha256'],'parameterEvidence':estimates[sport],'parentForecastSha256':runner.sha(original_path),'cpuSeconds':time.process_time()-begin,'retrospective':True,'originalPublicationComplete':False});e=runner.grader.evaluate(f,actual[sport][g['id']]);e['candidate']='oof_game_effect';freeze_json(ep,e);count+=1;print(json.dumps({'stage':'complete','sport':sport,'gameId':g['id'],'cpuSeconds':time.process_time()-cpu}),flush=True)
            except (ValueError,AssertionError) as e:failures.append({'sport':sport,'gameId':g['id'],'error':str(e)});print(json.dumps(failures[-1]),flush=True)
    if stop!='predeclared_balanced_candidates_completed':break
freeze_json(OUT/'oof-results.json',{'newRuns':count,'completeGamesSimulated':count*10000,'estimates':reports,'zeroNewGameEffectCases':cache_hits,'failures':failures,'stop':stop,'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'hostedSimulationRequests':0,'financialDatabaseOperations':0});print(json.dumps({'newRuns':count,'cpuSeconds':time.process_time()-cpu,'stop':stop,'failures':failures}),flush=True)
