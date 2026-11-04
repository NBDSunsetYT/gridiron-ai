"""Read-only, game-clustered grading of immutable structural experiment outputs."""
import gzip,json,sys,hashlib,time,resource
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18.models import error_metrics,cluster_delta
from modeling.iterative_learning import probability
from modeling.calibration_research import metrics,paired_interval
OUT=ROOT/'artifacts/structural-v18'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def summarize(rows):
    return {**error_metrics([r['actual'] for r in rows],[r['mean'] for r in rows]),'games':len({r['gameId'] for r in rows}),'players':len({r['id'] for r in rows}),'interval90Coverage':float(np.mean([r['coverage']['0.9']['covered'] for r in rows]))}
def support(f,stat):
    if f['sport']=='NBA':return set(f['players'])
    roles=f['participantAssumptions'].values()
    if stat.startswith('passing') or stat in ('completions','interceptions'):return {r['quarterback'] for r in roles}
    if stat.startswith('receiving') or stat in ('targets','receptions'):return {p for r in roles for p in r['receivers']}
    if stat in ('carries','rushingYards','rushingTouchdowns'):return {p for r in roles for p in r['runners']}|({r['quarterback'] for r in roles} if f['sport']=='CFB' else set())
    return set(f['players'])
def full_report(sport):
    candidates={};hashes={};simulations=0
    for folder in sorted((OUT/'full-games'/sport).iterdir()):
        if not folder.is_dir():continue
        items={}
        for p in folder.glob('*.forecast.json.gz'):
            f=read(p)['forecast'];e=read(p.with_name(p.name.replace('.forecast.json.gz','.evaluation.json.gz')));items[e['gameId']]={'f':f,'e':e};hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest();simulations+=f['simulations']
            if f['simulations']!=10000 or f.get('calibratedProbability') is not None:raise ValueError('Simulation count/calibration label changed')
            for d in [*f['scoreDistributions'].values(),*[d for ss in f['players'].values() for d in ss.values()]]:
                if sum(b['count'] for b in d['histogram'])!=10000:raise ValueError('Distribution mass failed')
        if items:candidates[folder.name]=items
    reference=candidates['frozen_v15'];report={}
    selected_stats=['minutes','points','rebounds','assists'] if sport=='NBA' else ['passingAttempts','passingYards','targets','receivingYards','receptions','carries','rushingYards','passingTouchdowns','receivingTouchdowns','rushingTouchdowns']
    threshold={'points':20.5,'rebounds':7.5,'assists':5.5,'passingYards':249.5,'receivingYards':64.5,'receptions':4.5,'rushingYards':59.5,'passingTouchdowns':1.5,'receivingTouchdowns':.5,'rushingTouchdowns':.5}
    for candidate,items in candidates.items():
        pairs=[(reference[g],item) for g,item in items.items() if g in reference];es=[c['e'] for b,c in pairs];bs=[b['e'] for b,c in pairs]
        summary={'games':len(pairs),'teamScore':error_metrics([s['actual'] for e in es for s in e['score']],[s['mean'] for e in es for s in e['score']]),'moneyline':metrics([e['probability'] for e in es if not e['ties']],[e['truth'] for e in es if not e['ties']]),'byStat':{},'pairedScoreDelta':paired_interval([np.mean([abs(s['error']) for s in e['score']]) for e in bs],[np.mean([abs(s['error']) for s in e['score']]) for e in es]),'pairedBrierDelta':paired_interval([(e['probability']-e['truth'])**2 for e in bs],[(e['probability']-e['truth'])**2 for e in es]),'unmodeledActualParticipants':sum(e['unmodeledActualParticipants'] for e in es),'productionEligible':False}
        for stat in selected_stats:
            original=[];new=[];events=[];original_events=[]
            for b,c in pairs:
                f,cf=b['f'],c['f'];common=support(f,stat)&support(cf,stat);by_id={p['id']:p for p in b['e']['players'] if p['stat']==stat};cy={p['id']:p for p in c['e']['players'] if p['stat']==stat}
                for pid in sorted(common&set(by_id)&set(cy)):
                    x={**by_id[pid],'gameId':b['e']['gameId']};y={**cy[pid],'gameId':c['e']['gameId']};original.append(x);new.append(y)
                    if stat in threshold:
                        event=probability(cf['players'][pid][stat],threshold[stat]);base_event=probability(f['players'][pid][stat],threshold[stat]);events.append((event['rawProbability'],int(y['actual']>threshold[stat])));original_events.append((base_event['rawProbability'],int(y['actual']>threshold[stat])))
            if new:
                summary['byStat'][stat]={'commonSupportedReference':summarize(original),'commonSupportedCandidate':summarize(new),'pairedMAEDelta':cluster_delta([{'gameId':r['gameId'],'y':r['actual']} for r in new],[r['mean'] for r in original],[r['mean'] for r in new]),'denominator':'Common pregame-supported identities with verified actual records; NBA complete-box DNP=0, football missing identity excluded and coverage reported.'}
                if events:summary['byStat'][stat]['diagnosticProp']={'threshold':threshold[stat],'candidate':metrics([p for p,y in events],[y for p,y in events]),'reference':metrics([p for p,y in original_events],[y for p,y in original_events]),'historicalMarketLine':False,'calibrated':False}
        summary['verdict']={'status':'not_promoted','reasons':['Only nine full-game validation games, below the 200-game gate.','No verified originally published pregame lineup/injury archive.','Previously inspected development evidence; no untouched final test opened.']}
        if summary['teamScore']['mae']>error_metrics([s['actual'] for e in bs for s in e['score']],[s['mean'] for e in bs for s in e['score']])['mae']:summary['verdict']['reasons'].append('Team-score MAE regressed in the paired sample.')
        if summary['moneyline']['brier']>metrics([e['probability'] for e in bs],[e['truth'] for e in bs])['brier']:summary['verdict']['reasons'].append('Moneyline Brier score regressed in the paired sample.')
        report[candidate]=summary
    return {'games':len({g for items in candidates.values() for g in items}),'runs':sum(map(len,candidates.values())),'completeGamesSimulated':simulations,'candidates':report,'sourceChecksums':hashes}
def main():
    cpu=time.process_time();projection=read(OUT/'projection-report.json');protocol=read(OUT/'protocol.json');root=read(ROOT/'docs/reports/structural-v18-root-causes-v3.json');result={'version':'structural-v18','developmentAuditGames':root['developmentGames'],'newValidationGames':sum(v['games'] for v in projection['leagues'].values()),'projectionCandidatesPerLeague':5,'projectionPipelineConfigurations':15,'sourceProtocolSha256':hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest(),'leagues':{},'fullGames':{},'promoted':[],'final':protocol['prospectiveFinal'],'limitations':['Every confidence interval is exploratory and unadjusted for multiple model/category comparisons.','The 536 games are chronological validation, not an untouched final test. Standalone coefficients train before July 2025; lagged features update using earlier completed games. Full-game models refit before each cohort, so earlier validation games may enter later chronological training. No game uses its own future outcome. Later ablations reuse the nine-game development sample.','No verified historical executable player-prop lines were available; threshold diagnostics are not betting records.','No original publication archives for historical injuries/lineups/weather; no production promotion is authorized by these results.']}
    for sport,r in projection['leagues'].items():
        important=['minutes','points','rebounds','assists','fieldGoalAttempts','threePointAttempts','freeThrowAttempts','steals','blocks','turnovers'] if sport=='NBA' else ['passingAttempts','passingYards','targets','receivingYards','receptions','carries','rushingYards','passingTouchdowns','receivingTouchdowns','rushingTouchdowns'];summary={'games':r['games'],'players':r['players'],'trainingGames':r['trainingGames'],'playerMetrics':{s:r['groups']['player:'+s] for s in important},'teamScore':r['groups']['team:score'],'moneyline':r['teamWin'],'verdicts':{}}
        for family in ['ridge','hierarchical','boosted','hybrid']:
            reasons=[];retained=[]
            for stat in important:
                group=summary['playerMetrics'][stat];m=group[family];base=group['rolling5'];all_windows=all(m['windows'][w]['mae']<=base['windows'][w]['mae'] for w in m['windows']);credible=m['pairedVsRolling']['bootstrap95'][1]<0
                if credible and all_windows:retained.append(stat)
                elif m['mae']>base['mae']*1.03:reasons.append('More than 3% MAE regression: '+stat)
            win=summary['moneyline'].get(family,{}).get('moneyline',{});base=summary['moneyline']['rolling5']['moneyline']
            if win and (win['brier']>base['brier'] or win['logLoss']>base['logLoss']):reasons.append('Game-probability Brier/log-loss guard fails relative to rolling baseline.')
            if family=='hybrid':reasons.append('Opportunity/efficiency chained prediction intervals are not independently validated.')
            summary['verdicts'][family]={'researchComponentsWithNegativePaired95AndAllWindowMAEImprovement':retained,'structuralLimitations':reasons,'productionPromotion':False,'reason':'Components may be retained for research only; independent projections are not coherent full-game joint distributions and pregame source reliability gates remain unmet.'}
        result['leagues'][sport]=summary;result['fullGames'][sport]=full_report(sport)
    resources=[read(OUT/(s+'-full-game-report.json'))['resources'] for s in ['NFL','CFB','NBA']]+[projection['resources']]
    for p in ['rotation-bootstrap-resources.json','allocation-ablation-resources.json']:
        if (OUT/p).exists():resources.append(read(OUT/p))
    result['resources']={'instrumentedExperimentCpuSeconds':sum(r['cpuSeconds'] for r in resources),'fullGameRuns':sum(v['runs'] for v in result['fullGames'].values()),'completeGamesSimulated':sum(v['completeGamesSimulated'] for v in result['fullGames'].values()),'hostingCpuSeconds':0,'maxReportedFullGameProcessRssMiB':max(r.get('peakRssKiB',0) for r in resources)/1024,'budgetSeconds':1800,'accounting':'Research runner CPU only; small audits, test suites, interpreter startup and packaging are reported separately, not included in this total.'}
    result['resources']['coldReplay']=read(OUT/'cold-replay.json')
    result['resources']['totalInstrumentedExperimentAndReplayCpuSeconds']=result['resources']['instrumentedExperimentCpuSeconds']+result['resources']['coldReplay']['cpuSeconds']
    result['resources']['projectionMemory']='Whole-process peak was not recorded. One live RSS sample was 1850972 KiB; do not interpret the full-game-only maximum as the experiment maximum.'
    for p,sha in root['sourceChecksums'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha:raise ValueError('Original forecast/evaluation changed')
    result['originalDevelopmentFilesVerified']=len(root['sourceChecksums']);result['financialDatabaseOperations']=0;result['stop']='Predeclared validation cohorts and bounded structural hypotheses completed. Promotion blocked by reliability/coverage and source-availability gates; no further parameter sweeps scheduled.';result['reportCpuSeconds']=time.process_time()-cpu
    (ROOT/'docs/reports/structural-v18-results.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n');print(json.dumps({'games':result['newValidationGames'],'resources':result['resources'],'preserved':result['originalDevelopmentFilesVerified']}))
if __name__=='__main__':main()
