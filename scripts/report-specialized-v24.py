"""Compile measured results; never fit, simulate, query private data or promote."""
import sys,json,gzip,hashlib,csv
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.registry import catalogue
from modeling.dynamic_v24.completion.data import EXTRA_FOOT,EXTRA_NBA
from modeling.overnight_v20.state import read,atomic,digest

PRIMARY={'NFL':{'default':'completion-r4','passingAttempts':'completion-nfl-extension-r2','passingYards':'completion-nfl-extension-r2','passingCompletions':'completion-nfl-extension-r2','passingTouchdowns':'completion-nfl-scoring-r1','interceptions':'completion-nfl-scoring-r1',**{s:'completion-nfl-games-r1' for s in ['teamPoints','moneyline','spread','total']}},'CFB':{'default':'completion-cfb-extension-r1'},'NBA':{'default':'completion-nba-clean-r1'}}
PROTOCOLS=[('completion-r4','NFL'),('completion-r4','CFB'),('completion-nba-efficient-r1','NBA'),('completion-nfl-extension-r2','NFL'),('completion-cfb-extension-r1','CFB'),('completion-nfl-games-r1','NFL'),('completion-nba-clean-r1','NBA'),('completion-nfl-scoring-r1','NFL')]
DEST=OUT/'completion-final'
def payload(path):return json.loads(gzip.decompress(path.read_bytes()))
def fmt(values):return ' / '.join(f'{v:.3f}' for v in values) if values else 'Unavailable'

def compile_results():
    heads=[];all_decisions=[];bank=[];registrations=[];registry_records=[];evaluations=0;unique={s:set() for s in PRIMARY};counts={};attributions=[];production=[]
    for folder,sport in PROTOCOLS:
        p=OUT/folder;protocol=read(p/'protocol.json');selected={g for w in protocol['selection'][sport] for g in w['games']};unique[sport].update(selected)
        valid=read(p/'registry.json',{'versions':[]})['versions'];registry_records.extend(valid)
        for wi in (0,1):
            report=read(p/sport/str(wi)/'results.json',{})
            for stat,r in report.items():
                evaluations+=len(r.get('candidates',{}))
                for family,value in r.get('attribution',{}).items():attributions.append({'protocol':folder,'sport':sport,'window':wi,'stat':stat,'family':family,**value})
                if r.get('productionChampionComparison',{}).get('status')=='conditional_production_source_algorithm_replay':production.append({'protocol':folder,'window':wi,'stat':stat,**r['productionChampionComparison']})
        all_decisions.extend({'protocol':folder,**r} for r in read(p/sport/'leaderboard.json',[]))
        counts[folder+':'+sport]={'selectedGames':len(selected),'candidateWindowEvaluations':sum(len(r.get('candidates',{})) for wi in (0,1) for r in read(p/sport/str(wi)/'results.json',{}).values())}
    for sport,config in PRIMARY.items():
        for stat in list(catalogue()[sport])+list(EXTRA_NBA if sport=='NBA' else EXTRA_FOOT):
            folder=config.get(stat,config['default']);p=OUT/folder;rows=read(p/sport/'leaderboard.json',[]);purpose='distribution' if stat in ('moneyline','doubleDouble','tripleDouble') else 'expected_value';row=next((r for r in rows if r['stat']==stat and r['purpose']==purpose),{'sport':sport,'stat':stat,'purpose':purpose,'improvementEstablished':False,'reason':'Insufficient evidence'})
            heads.append({'protocol':folder,**row,'referenceDescription':'Rolling historical baseline; production champion remains unchanged','evidenceTier':'conditional_corrected_history','approvedCalibrator':None,'jointSimulationEligible':False,'productionChampionKept':True,'productionPromotionEligible':False})
            if purpose!='expected_value':continue
            record=next((r for r in read(p/'registry.json',{'versions':[]})['versions'] if r['sport']==sport and r['stat']==stat and r['purpose']=='expected_value'),None)
            families=['rolling5']+([row['fixedCandidateFamily']] if row.get('improvementEstablished') and row.get('fixedCandidateFamily')!='rolling5' else [])
            for family in families:
                for wi in (0,1):
                    report=read(p/sport/str(wi)/'results.json',{}).get(stat,{})
                    artifact=report.get('modelArtifacts',{}).get(family)
                    if not artifact:continue
                    f=p/sport/str(wi)/stat/(family+'-forecast.json.gz');pred=payload(f)
                    if family=='inner_mixture':
                        dates=[payload(f.parent/(c+'-forecast.json.gz')) for c in pred['components']];available=max(d['selectionThrough'] for d in dates);training=max(d['trainingThrough'] for d in dates)
                    else:available=pred['selectionThrough'];training=pred['trainingThrough']
                    candidate=family!='rolling5';validation_end=max(w['end'] for w in read(p/'protocol.json')['selection'][sport]) if candidate else None
                    if validation_end:available=max(available,validation_end+'T00:00:00+00:00')
                    bank.append({'sport':sport,'stat':stat,'family':family,'role':'conditional_research_candidate' if candidate else 'research_reference','modelVersion':pred.get('modelVersion',artifact['sha256']),'modelPath':artifact['path'],'modelSHA256':artifact['sha256'],'trainingThrough':training,'availableAfter':available,'validationAvailableAfter':validation_end,'dataSourceVersions':read(p/'protocol.json')['sourceVersions'],'registryRecordId':record['id'] if candidate and record else None,'jointValidated':False,'evidenceTier':'conditional_corrected_history'})
    manifest={'format':'specialized-research-head-bank-24.3','productionPromotion':False,'jointForecastsQualified':0,'heads':bank,'chronologyPolicy':'Research candidates become selectable only after confirmation ends; reference heads remain available before that date.'};manifest['sha256']=digest(manifest)
    if (DEST/'bank-v3.json').exists():
        if read(DEST/'bank-v3.json')!=manifest:raise ValueError('Research bank changed; preserve it and create a new report revision')
    else:atomic(DEST/'bank-v3.json',manifest)
    for key,ids in unique.items():counts[key]={'distinctSelectedGames':len(ids)}
    ledger=read(OUT/'runtime/state.json');started=read(OUT/'completion-r1/audit-start.json')['startedAt'];jobs={k:v['receipt'] for k,v in ledger['jobs'].items() if v.get('startedAt','')>=started and 'receipt' in v};mechanics=read(OUT/'specialized-joint-mechanics-r1/results.json',{})
    result={'version':'V24 specialized completion','asOf':datetime.now(timezone.utc).isoformat(),'branch':'research/dynamic-v24','startingRemoteCommit':'d4d5fd1c538b188939947942c8772f768f7a0fa5','primaryProtocolPolicy':'Newest preregistered independent confirmation, not best outer result. Original NBA families were fixed before new clean-source confirmation.','heads':heads,'allDecisions':all_decisions,'counts':counts,'candidateWindowEvaluations':evaluations,'registeredMatchups':sum(len(v) for v in unique.values()),'perStatObservationCountsOnly':'Games overlap across categories; do not add observation counts to obtain unique games. Selected games without supported history are not graded.','strictPregameForecasts':0,'completeGameAccuracyComparisons':0,'verifiedHistoricalMarketLines':0,'productionPromotions':0,'pointInTimeCoverage':{s:{'publicationCompleteGames':0,'missing':['injury','lineup','participation','original_statistics_editions']} for s in PRIMARY},'jointMechanics':mechanics,'resources':{'controlledJobs':jobs,'measuredCpuSecondsIncludingFailures':sum(r.get('cpuSeconds',0) for r in jobs.values()),'peakResearchRssKiB':max(r.get('peakRssKiB',0) for r in jobs.values())},'attributions':attributions,'productionSourceComparisons':production,'bankManifestSHA256':manifest['sha256'],'bankHeads':len(bank),'sourceQuality':{'nbaSourceGamesRejected':len(read(OUT/'completion-nba-clean-r1/protocol.json')['sourceRejectedGames']),'actualOnCourtReboundExposureVerified':False},'remainingBlockers':['Historical publication-complete injuries, lineups and player participation remain missing','CFB administrative timing and pace consistency certificate remains incomplete','No source-complete, independently probability-validated specialized joint model certificate','No matching historical production forecast snapshots for most categories; NFL source replay is conditional','No verified historical market thresholds or settlement rules; diagnostic CDF calibration is not market calibration','Conditional head gains do not prove joint-game or production improvement']}
    target=ROOT/'docs/research';atomic(target/'specialized-v24-results.json',result);atomic(target/'specialized-v24-bank.json',manifest);atomic(target/'specialized-v24-registry.json',{'versions':list({r['id']:r for r in registry_records}.values()),'productionPromotions':0,'selectionPolicy':'Retain existing production champions; research records remain objective- and protocol-scoped'})
    fields=['sport','stat','purpose','candidate','conditionalWinner','referenceMAE','candidateMAE','referenceRMSE','candidateRMSE','games','observations','referenceCDFBrier','candidateCDFBrier','candidateLogLoss','coverage90','paired95','pairedAdjusted','decisionReasons','jointEligible','improvementEstablished','protocol']
    csv_path=target/'specialized-v24-leaderboard.csv'
    with csv_path.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
        for r in heads:writer.writerow({'sport':r['sport'],'stat':r['stat'],'purpose':r['purpose'],'candidate':r.get('fixedCandidateFamily','Unavailable'),'conditionalWinner':r.get('winningFamily') or 'None established','referenceMAE':fmt(r.get('referenceMAE')),'candidateMAE':fmt(r.get('candidateMAE')),'referenceRMSE':fmt(r.get('referenceRMSE')),'candidateRMSE':fmt(r.get('candidateRMSE')),'games':str(r.get('independentGames',[])),'observations':str(r.get('observations',[])),'referenceCDFBrier':fmt(r.get('referenceCalibration')),'candidateCDFBrier':fmt(r.get('candidateCalibration')),'candidateLogLoss':fmt(r.get('candidateLogLoss')),'coverage90':fmt([c['0.9'] for c in r.get('intervalCoverage',[])]),'paired95':json.dumps([u['CI95'] for u in r.get('pairedUncertainty',[])]),'pairedAdjusted':json.dumps([u['adjustedCI'] for u in r.get('pairedUncertainty',[])]),'decisionReasons':json.dumps(r.get('decision',{}).get('reasons',[])),'jointEligible':False,'improvementEstablished':r['improvementEstablished'],'protocol':r['protocol']})
    lines=['# V24 per-statistic leaderboard','','All results below are conditional corrected-history diagnostics. No production or strict joint-game champion was replaced. Each pair is the earlier/later independent validation window. CDF Brier uses training-derived diagnostic thresholds, not invented betting lines. Moneyline Brier uses raw classifier probabilities. See the JSON for RMSE, observation counts, log loss, coverage and paired confidence intervals.','', '| League/statistic | Fixed candidate | Reference MAE | Candidate MAE | Independent games | CDF Brier reference → candidate | Adjusted paired intervals | Conditional criterion met | Joint eligible |','|---|---|---|---|---|---|---|---|---|']
    for r in heads:lines.append('| '+r['sport']+' '+r['stat']+' | '+str(r.get('fixedCandidateFamily','Unavailable'))+' | '+fmt(r.get('referenceMAE'))+' | '+fmt(r.get('candidateMAE'))+' | '+str(r.get('independentGames','Unavailable'))+' | '+fmt(r.get('referenceCalibration'))+' → '+fmt(r.get('candidateCalibration'))+' | '+str([u['adjustedCI'] for u in r.get('pairedUncertainty',[])])+' | '+str(r['improvementEstablished'])+' | No |')
    (target/'specialized-v24-leaderboard.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'heads':len(heads),'registeredMatchups':result['registeredMatchups'],'candidateWindowEvaluations':evaluations,'bankHeads':len(bank),'cpuSecondsIncludingFailures':result['resources']['measuredCpuSecondsIncludingFailures'],'strictForecasts':0,'productionPromotions':0}))
    return result
if __name__=='__main__':compile_results()
