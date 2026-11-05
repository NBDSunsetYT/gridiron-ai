"""Algebraic opportunity/efficiency error attribution, not causal injury claims."""
import sys,json,gzip
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/parallel-v19'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def variance(d):return sum(h['count']*(h['value']-d['mean'])**2 for h in d['histogram'])/sum(h['count'] for h in d['histogram'])
report={}
for sport in ['NFL','CFB','NBA']:
    report[sport]={}
    for folder in sorted((OUT/'runs'/sport).iterdir()):
        pieces=defaultdict(list);margin=[];no_volume=[]
        for path in sorted(folder.glob('*.official-evaluation-v2.json.gz')):
            g=read(path);a=read(path.with_name(path.name.replace('.official-evaluation-v2','.forecast')));f=a['forecast'];by=defaultdict(dict)
            for r in g['ownPregameSupportPlayers']:by[r['id']][r['stat']]=r
            pairs={'points':'minutes','rebounds':'minutes','assists':'minutes'} if sport=='NBA' else {'passingYards':'passingAttempts','receivingYards':'receptions','rushingYards':'carries'}
            for pid,stats in by.items():
                for stat,op in pairs.items():
                    if stat not in stats or op not in stats:continue
                    y,vol=stats[stat],stats[op]
                    if min(y['mean'],vol['mean'])<0 or vol['mean']==0:continue
                    if vol['actual']==0:no_volume.append({'gameId':g['gameId'],'player':pid,'stat':stat,'projectedVolume':vol['mean'],'projectedStatistic':y['mean'],'note':'Zero final recorded volume does not establish pregame injury or inactive status.'});continue
                    rate=y['mean']/vol['mean'];observed=y['actual']/vol['actual'];op_error=(vol['mean']-vol['actual'])*rate;eff_error=vol['actual']*(rate-observed)
                    if abs(op_error+eff_error-y['error'])>1e-6:raise ValueError('Error decomposition did not reconcile')
                    pieces[stat].append({'gameId':g['gameId'],'player':pid,'cohort':g['cohort'],'opportunityError':op_error,'efficiencyError':eff_error,'signedError':y['error'],'projectedVolume':vol['mean'],'actualVolume':vol['actual']})
            actual=g['margin']['actual'];d=f['marginDistribution'];cov=(variance(f['totalDistribution'])-sum(variance(v) for v in f['scoreDistributions'].values()))/2
            margin.append({'gameId':g['gameId'],'cohort':g['cohort'],'predictedMargin':d['mean'],'actualMargin':actual,'predictedSD':float(np.sqrt(variance(d))),'standardizedError':(d['mean']-actual)/np.sqrt(variance(d)),'marginInterval90Covered':g['margin']['coverage']['0.9']['covered'],'teamScoreCovariance':cov,'latentCompletionSD':f.get('completionFrailtySD'),'informationCutoff':a['snapshot']['informationCutoff']})
        summaries={}
        for stat,rs in pieces.items():
            summaries[stat]={'observations':len(rs),'games':len({r['gameId'] for r in rs}),'meanAbsoluteOpportunityComponent':float(np.mean([abs(r['opportunityError']) for r in rs])),'meanAbsoluteEfficiencyComponent':float(np.mean([abs(r['efficiencyError']) for r in rs])),'signedOpportunityBias':float(np.mean([r['opportunityError'] for r in rs])),'signedEfficiencyBias':float(np.mean([r['efficiencyError'] for r in rs])),'byWindow':{str(c):{'observations':sum(r['cohort']==c for r in rs),'absoluteOpportunity':float(np.mean([abs(r['opportunityError']) for r in rs if r['cohort']==c])),'absoluteEfficiency':float(np.mean([abs(r['efficiencyError']) for r in rs if r['cohort']==c]))} for c in sorted({r['cohort'] for r in rs})}}
        report[sport][folder.name]={'opportunityDecomposition':summaries,'marginAndCovariance':margin,'zeroObservedVolumeCases':no_volume,'interpretation':'Additive decomposition using predicted opportunity rate. Associations are not proof of injury, lineup, coaching or weather causation. Absolute components can offset; they do not add to MAE.'}
freeze_json(ROOT/'docs/reports/parallel-v19-diagnostics.json',report)
print(json.dumps({s:{c:v['opportunityDecomposition'] for c,v in cs.items() if c in ['frozen_reference','oof_game_effect','recency_usage_eb']} for s,cs in report.items()}))
