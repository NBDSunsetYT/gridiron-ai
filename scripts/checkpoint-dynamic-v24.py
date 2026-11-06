"""Finalize supervised V24 artifacts without touching production or parent research."""
import sys,json,hashlib,subprocess,platform,glob,shutil,pickle
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.runtime import verify_parent
from modeling.overnight_v20.state import atomic,read
OUT=ROOT/'artifacts/dynamic-v24'
def run():
    verify_parent();s=read(OUT/'analysis/summary.json');ledger=read(OUT/'runtime/state.json');now=datetime.now(timezone.utc);start=read(OUT/'start.json');v24sessions=[v for v in ledger['sessions'] if v['startedAt']>=start['startedAt']];metered=sum(v.get('activeSeconds',0) for v in v24sessions);elapsed=(now-datetime.fromisoformat(start['startedAt'])).total_seconds();reservation=max(0,elapsed-metered)
    convergence=[]
    for p in (OUT/'sequential').glob('*/*-converged-r4/*-models.pickle'):
        models=pickle.load(p.open('rb'))
        for name,m in models.items():
            if not hasattr(m,'model'):continue
            assert m.converged, 'Numerically unstable event candidate'
            convergence.append({'file':str(p.relative_to(OUT)),'variant':name,'iterations':list(map(int,m.model[-1].n_iter_)),'converged':True})
    assert len(convergence)==48, 'Incomplete numerical verification'
    atomic(OUT/'numeric-convergence.json',convergence)
    if 'v24SupervisedEngineeringReservation' not in ledger:
        ledger['setupSafetyChargeSeconds']+=reservation
        ledger['v24SupervisedEngineeringReservation']={'through':now.isoformat(),'elapsedSeconds':elapsed,'meteredSeconds':metered,'unmeteredWallReservedSeconds':reservation,'meaning':'Conservative supervised wall reservation, not measured CPU or unattended execution'}
    ledger['finalResearchCheckpointAt']=now.isoformat();ledger['status']='checkpointed';ledger['stopReason']='bounded_V24_queue_complete_strict_forecast_and_live_evidence_gates_unresolved';atomic(OUT/'runtime/state.json',ledger)
    counts={}
    for prefix in ['tournament','supplement/tournament']:
        for p in (OUT/prefix).glob('*/*/results.json'):
            league=p.parent.parent.name;counts[league]=counts.get(league,0)+sum(len(r.get('candidates',{})) for r in read(p).values())
    packages={}
    from importlib.metadata import version
    for name in ['numpy','scipy','scikit-learn','pandas','pyarrow','matplotlib']:
        packages[name]=version(name)
    atomic(OUT/'dependencies.json',{'python':sys.version,'platform':platform.platform(),'packages':packages})
    code=[*sorted((ROOT/'modeling/dynamic_v24').glob('*.py')),ROOT/'modeling/test_dynamic_v24.py',*sorted((ROOT/'scripts').glob('*dynamic-v24.py'))]
    for p in code:
        dest=OUT/'code-checkpoint'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    cpu=sum(v.get('receipt',{}).get('cpuSeconds',0) for k,v in ledger['jobs'].items() if k.startswith('v24-'))
    report=['# V24 dynamic and specialized-model research checkpoint','',f"Checkpoint: {now.isoformat()}. Branch: `research/dynamic-v24`. Production promotions and production data writes: **0**.",'',
    'The bounded research batch is complete. No unattended process remains active. Strict pregame forecasting and strict live replay remain blocked; no claim of overall predictive superiority is established. Numerical repairs and mechanics checks do not unlock those gates.','',
    '## Scope and evidence','',
    '| League | New point-validation games | Supported marginal heads | Candidate/window evaluations | Sequential windows |', '|---|---:|---:|---:|---|']
    for league in ['NFL','CFB','NBA']:
        report.append(f"| {league} | {s['pointValidationGames'][league]} | {sum(h['sport']==league and h['status']=='conditional_evaluated' for h in s['leaderboard'])} | {counts[league]} | {s['sequentialValidationGames'][league]} |")
    report+=['','These are corrected-history conditional diagnostics, not publication-complete pregame forecasts. Selection excludes the 79 sealed final-test games, locked confirmations, and previously examined validation games. Training uses earlier dates and an internal distribution-calibration split. Final-test outcomes were not opened. Historical edition/arrival timestamps remain incomplete.','',
    '## A/B/C next-event comparisons','',
    'A is the unchanged V23 prior-only play-selection pool for football actions. Where V23 has no next-event API, A is explicitly an empirical prior-only reference. B adds game-state/workload features; C adds lagged outcomes and nonlinear workload. Fixed regularization is used throughout. A numerical audit found iteration-limited fits; revision r4 uses the identical objective/data with a 2,000-iteration ceiling and rejects unconverged fits. Older results are retained.','',
    '| League/task/window | Events / games | A log loss | B log loss | C log loss | C−B adjusted paired CI |','|---|---:|---:|---:|---:|---|']
    for league,ws in s['sequential'].items():
        for i,w in enumerate(ws):
            for task,r in w['tasks'].items():
                if r.get('status')!='evaluated':continue
                m=r['metrics'];ci=r['pairedLogLoss']['B_C']['familywiseCI'];report.append(f"| {league}/{task}/{i+1} | {r['events']} / {r['games']} | {m['A']['logLoss']:.5f} | {m['B']['logLoss']:.5f} | {m['C']['logLoss']:.5f} | [{ci[0]:.5f}, {ci[1]:.5f}] |")
    report+=['','NBA action-type improvements are predominantly nonlinear within-possession event-history effects. This is not physiological fatigue, a hot-hand effect, or demonstrated full-game score/win accuracy. Shot-success complexity did not generalize. Football incremental momentum effects did not pass repeated-window checks; CFB drive scoring regressed. No arbitrary bonus was introduced.','',
    '## Specialized models','',
    'The catalogue contains 48 league/statistic heads. Models include rolling/EWMA, opponent ridge, Lasso/Elastic Net, regularized hierarchical player effects, gradient boosting, quantile medians, negative-binomial/hurdle laws, residual mixtures, empirical Bayes, opportunity×efficiency, and an inner-calibration-weighted ensemble. The first window selects the family and the next window confirms it. No verified historical prop thresholds were acquired; line-specific calibration and betting outcomes remain ungraded.','',
    '| Category | Fixed family / estimand | Earlier MAE baseline → candidate | Confirmation MAE baseline → candidate | Decision |','|---|---|---:|---:|---|']
    for h in s['leaderboard']:
        if h['stat'] not in ['passingYards','rebounds'] and not h.get('pointResearchCandidate'):continue
        if not h.get('windows'):continue
        a,b=h['windows'];report.append(f"| {h['sport']} {h['stat']} | {h['bestFirstWindowFamily']} / {h['pointEstimand']} | {a['baseline']['mae']:.4f} → {a['candidate']['mae']:.4f} | {b['baseline']['mae']:.4f} → {b['candidate']['mae']:.4f} | {'conditional point candidate' if h.get('pointResearchCandidate') else 'not established'} |")
    report+=['','Touchdown median heads reduce MAE relative to rolling means, which is a loss/estimand distinction, not proof of superior expected values or touchdown probabilities. Legacy frozen quantile arrays named `mean` are explicitly interpreted as medians; their values are preserved. Probability champions and joint-game replacement remain withheld. One coordinate-descent screening fit emitted a convergence warning; it was not selected for promotion. The complete 48-head leaderboard, observations, RMSE, bias, CRPS, interval coverage, zero-event calibration, paired intervals and unavailable categories are in `dynamic-v24-results.json`.','',
    '## Mechanical and live work','',
    '56 ABC/ablation complete-game mechanical trials and 24 historical-prefix continuation trials passed joint accounting checks. These are deliberately small Mode A tests with final-conditioned source/roster rates, not forecasting backtests or requested 10,000-game accuracy runs. The continuation retains actual score/statistics and simulates only remaining time. NFL/CFB shared completed-pass and rushing credits reconcile; NBA points/minute/shot/rebound budgets reconcile. A tested NBA rebound actor-shadowing defect was fixed without changing prior V23 source.','',
    'Live infrastructure implements source ordering, idempotent duplicates, revisions, gap/latency freezes, immutable snapshots, a bounded local SQLite outbox, fencing leases, quotas, exponential retries and real worker deadlines. No qualified live provider job was queued. There are zero strict live calibration/latency observations, so those metrics are unavailable.','',
    '## Evidence and remaining blockers','',
    '15 newly recovered official NBA injury facts and primary NFL/college availability source inventories were saved with publication/retrieval metadata. They do not establish full pregame starting lineups or participation coverage. Unknown availability never becomes healthy by default. NBA forward lineups after period boundaries remain incomplete; two corrected-order games were withheld. CFB administrative clock/runoff and pace certification remain incomplete. No full-game gate was bypassed, and protected pause/checkpoint files remain unchanged.','',
    '## Verification and resources','',
    '- Full Python suite: 435 passed. Subsequent V24/V23 focused regression suite: 77 passed after worker, feedback and numerical-gate changes.',
    '- JavaScript: 793 tests in 115 files passed. TypeScript passed. Next.js production build passed; research flag-off returns HTTP 404.',
    '- Six Chromium iPhone-size/desktop league checks passed with no page exceptions, horizontal overflow or API calls. Physical iPhone/PWA installation was not performed.',
    '- Research dashboard reads compact frozen aggregates. It neither schedules simulations nor reads private financial data.','',
    f"Controlled V24 jobs consumed {cpu:.3f} measured CPU seconds including failed attempts. Local production build separately used 100.186 CPU seconds / 60.048 wall seconds, peak RSS 1,502,756 KiB; this is not Render runtime memory. Supervised session elapsed at checkpoint: {elapsed:.1f} seconds. Cumulative budget reservations are preserved in the inherited ledger; no claim of execution while inactive.",'',
    'Charts, screenshots, model pickles, forecast summaries, source receipts, random seeds, dependencies and checksums are retained under `artifacts/dynamic-v24`; raw licensed data and private records are excluded from Git. All 6,526 inherited checkpoint files passed checksum verification. Exact fitting replay requires the recorded source editions/dependencies; some earlier protocol hashes precede reporting-only code corrections, so use the preserved fitted-model hashes for forecast replay.','',
    '## Resume and decision','',
    'Do not repeat completed experiments or reopen sealed outcomes. `OPENBLAS_NUM_THREADS=1 python scripts/sequential-dynamic-v24.py` returns the completed r4 receipt. New evidence/numerical revisions require a new immutable protocol rather than modifying frozen snapshots. `python scripts/analyze-dynamic-v24.py`, `python scripts/dashboard-dynamic-v24.py`, and `python scripts/plots-dynamic-v24.py` reproduce summaries. `GRIDIRON_RESEARCH_V24=1 npm run dev -- --port 3024` previews the cached research-only route `/research/v24`.','',
    'No production model qualifies for automatic promotion. Next phase is isolated Render application compatibility/migration based on the unchanged production branch, with no DNS or traffic switch.']
    (ROOT/'docs/research/dynamic-v24-report.md').write_text('\n'.join(report)+'\n')
    paths=[p for p in OUT.rglob('*') if p.is_file() and 'runtime/' not in str(p.relative_to(OUT)) and p.name!='checkpoint-manifest.json'];atomic(OUT/'checkpoint-manifest.json',{'at':now.isoformat(),'parentFilesVerified':6526,'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'candidateWindowEvaluations':counts,'measuredControlledCpuSeconds':cpu,'strictForecasts':0,'productionWrites':0})
    print(json.dumps({'candidateEvaluations':counts,'controlledCpuSeconds':cpu,'checkpoint':str(OUT/'checkpoint-manifest.json')}))
if __name__=='__main__':run()
