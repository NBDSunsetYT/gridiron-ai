"""Read-only derived leaderboard, never a model selector or new registry."""
import sys,json,hashlib
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import read,digest
from modeling.iterative_learning import freeze_json


def build(heads,registry,shadow):
    if shadow.get('traceCount')!=320 or shadow.get('sameEventSetChecksPassed')!=320 or shadow.get('forecastingGatePassed') is not False:
        raise ValueError('Completed frozen conditional shadow verification required')
    records=registry['versions'];rows=[]
    for h in heads:
        candidates=[r for r in records if r['sport']==h['sport'] and r['stat']==h['stat']]
        conditional=[r for r in candidates if r['decision']['conditionalImprovementEstablished']]
        numerical=[r for r in conditional if r['purpose']=='expected_value']
        probability=[r for r in conditional if r['purpose']=='distribution']
        observations=[r for r in shadow['traces'] if r['sport']==h['sport'] and r['stat']==h['stat']]
        rows.append({'sport':h['sport'],'stat':h['stat'],
            'approvedNumericalModel':None,'approvedProbabilityModel':None,'marketEdgeResearchModel':None,
            'existingReference':'rolling5 exposed research baseline; production reference unavailable unless separately recorded',
            'originalFixedCandidateFamily':h.get('fixedCandidateFamily'),'originalReferenceMAE':h.get('referenceMAE',[]),
            'originalCandidateMAE':h.get('candidateMAE',[]),'originalReferenceRMSE':h.get('referenceRMSE',[]),
            'originalCandidateRMSE':h.get('candidateRMSE',[]),'originalWindowGames':h.get('independentGames',[]),
            'originalWindowObservations':h.get('observations',[]),'originalPairedValidationUncertainty':h.get('pairedUncertainty',[]),
            'conditionalNumericalCandidates':[{'family':r['family'],'registryRecordId':r['id'],'metrics':r['metrics'],'uncertainty':r['uncertainty']} for r in numerical],
            'conditionalProbabilityCandidates':[{'family':r['family'],'registryRecordId':r['id'],'metrics':r['metrics'],'uncertainty':r['uncertainty']} for r in probability],
            'shadowScores':observations,'calibrationStatus':'No approved probability calibrator; training-quantile CDF diagnostics only',
            'jointCompatibility':False,'automaticRoutes':{'A_probability':'withheld','B_numerical':'withheld','C_market_research':'marketless'},
            'retainedChampion':'Existing production configuration remains unchanged outside this research router',
            'rejectedAlternatives':[{'family':r['family'],'purpose':r['purpose'],'reasons':r['decision']['reasons']} for r in candidates if not r['decision']['conditionalImprovementEstablished']],
            'blockers':['publication_complete_pregame_availability_and_source_editions_missing','model_bound_joint_validation_missing','no_verified_historical_market_cohort'],
            'newIndependentGames':0,'newStrictPregameGames':0,'promotionEligible':False})
    if len(rows)!=53 or len({(r['sport'],r['stat']) for r in rows})!=53:raise ValueError('Existing 53-category catalogue changed')
    return {'version':'objective-leaderboard-25.2','rows':rows,'originalRegistryUnmodified':True,
            'researchOnly':True,'isModelRegistry':False,'newModelSelection':False,'productionPromotions':0,
            'sameEventsAcrossModes':True,'newIndependentAccuracyImprovementEstablished':False}


def main():
    out=ROOT/'artifacts/accuracy-v25/objectives-r1';r=read(out/'results.json');receipt=read(out/'receipt.json')
    if not receipt.get('passed'):raise ValueError('Actual shadow run receipt required')
    original=read(ROOT/'docs/research/specialized-v24-results.json');registry=read(ROOT/'docs/research/specialized-v24-registry.json')
    report=build(original['heads'],registry,r)
    unique=defaultdict(set)
    for p in (out/'snapshots').rglob('*-replay.json'):
        value=read(p)
        if value['sha256']!=digest({k:v for k,v in value.items() if k!='sha256'}):raise ValueError('Shadow snapshot hash changed')
        for row in value['identities']:unique[row['sport']].add(row['gameId'])
    report['existingUniqueReplayGamesByLeague']={s:len(ids) for s,ids in unique.items()}
    report['resources']={k:receipt[k] for k in ('cpuSeconds','wallSeconds','peakRssKiB')}
    report['sourceRegistrySHA256']=hashlib.sha256((ROOT/'docs/research/specialized-v24-registry.json').read_bytes()).hexdigest()
    freeze_json(ROOT/'docs/research/V25_ROUTING_LEADERBOARD.json.gz',report)
    lines=['# V25 objective-routing leaderboard','',
           'This is a read-only view of the existing registry, not a replacement registry or a new model selection. All 53 categories remain present. No strict route, joint forecasting certificate, approved calibrator or market-edge model is invented.',
           '', 'A/B/C shadow scoring reused 320 original traces across 52 categories. CFB targets remains unsupported. Modes share each exact frozen event set. These are exposed conditional diagnostics, not unseen games. Newly eligible strict games: **0**; model promotions: **0**.',
           '', 'Existing unique replay games (not new independent evidence): '+', '.join(s+' '+str(n) for s,n in sorted(report['existingUniqueReplayGamesByLeague'].items()))+'.',
           '', '| League/statistic | Conditional numerical candidate | Conditional distribution candidate | Reference MAE → fixed candidate MAE (chronological windows) | Games / observations per window | Automatic route |',
           '|---|---|---|---|---|---|']
    def nums(values):return '/'.join('null' if x is None else f'{x:.3f}' for x in values)
    for row in report['rows']:
        numerical=', '.join(sorted({r['family'] for r in row['conditionalNumericalCandidates']})) or 'retain reference'
        probability=', '.join(sorted({r['family'] for r in row['conditionalProbabilityCandidates']})) or 'retain reference'
        lines.append('| '+row['sport']+' '+row['stat']+' | '+numerical+' | '+probability+' | '+nums(row['originalReferenceMAE'])+' → '+nums(row['originalCandidateMAE'])+' | '+str(row['originalWindowGames'])+' / '+str(row['originalWindowObservations'])+' | A/B withheld; C marketless |')
    lines.extend(['','The MAE column reports the original fixed expected-value challenger, not whichever distribution candidate has the lowest retrospective score. RMSE, bias, Brier/log loss, ECE, interval coverage, Winkler/quantile scores, paired game-level intervals and every rejected alternative are available in [the compressed machine-readable table](V25_ROUTING_LEADERBOARD.json.gz). None of the conditional candidates is a production-approved winner.',
                  '', 'All categories have joint compatibility **unqualified**, not a claim of a proven mechanical defect. Current blockers are missing publication-complete participant evidence, model-bound joint validation, and authentic historical market observations. The original production champion is retained outside this research-only router.',
                  '', f"Measured shadow verification: {receipt['cpuSeconds']:.3f} CPU seconds, {receipt['wallSeconds']:.3f} wall seconds, peak RSS {receipt['peakRssKiB']} KiB. Zero new model fits and zero full-game simulations. No protected final outcomes were opened."])
    (ROOT/'docs/research/V25_ROUTING_LEADERBOARD.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'rows':len(report['rows']),'traces':r['traceCount'],'existingReplayGames':report['existingUniqueReplayGamesByLeague'],'newStrictGames':0,'promotions':0}))


if __name__=='__main__':main()
