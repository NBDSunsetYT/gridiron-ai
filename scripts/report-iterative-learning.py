"""Read-only paired analysis and figures. Never fits or selects a model."""
import argparse
from collections import defaultdict
from datetime import datetime
import gzip
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json


def read(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())


def compare(reference,candidate):
    a={r['gameId']:r for r in reference};b={r['gameId']:r for r in candidate};common=sorted(a.keys()&b.keys())
    if not common:return {'games':0}
    blocks=defaultdict(list);players=defaultdict(list);events=defaultdict(list);missing=defaultdict(int)
    for gid in common:
        r,c=a[gid],b[gid];week=datetime.fromisoformat(r['eventStart']).strftime('%G-%V')
        blocks[week].append(float(np.mean([abs(p['error']) for p in c['score']])-np.mean([abs(p['error']) for p in r['score']])))
        old={(p['id'],p['stat']):p for p in r['player']};new={(p['id'],p['stat']):p for p in c['player']}
        for key in old.keys()&new.keys():players[key[1]].append((old[key],new[key]))
        old_events={(p['id'],p['stat'],p['threshold']):p for p in r['events']};new_events={(p['id'],p['stat'],p['threshold']):p for p in c['events']}
        for key in old_events.keys()&new_events.keys():
            assert old_events[key]['outcome']==new_events[key]['outcome'],'A paired outcome changed'
            events[key[1]].append((old_events[key],new_events[key]))
        missing['referenceOnlyPlayerStatPairs']+=len(old.keys()-new.keys());missing['candidateOnlyPlayerStatPairs']+=len(new.keys()-old.keys())
    groups=list(blocks.values());rng=np.random.default_rng(16002);boot=[]
    for _ in range(2000):boot.append(float(np.mean([x for i in rng.integers(0,len(groups),len(groups)) for x in groups[int(i)]])))
    def calibration(rows):
        bins=[]
        for i in range(10):
            part=[p for p in rows if min(9,int(p['rawProbability']*10))==i]
            if part:bins.append({'n':len(part),'predicted':float(np.mean([p['rawProbability'] for p in part])),'observed':float(np.mean([p['outcome'] for p in part]))})
        return {'brier':float(np.mean([p['brier'] for p in rows])),'logLoss':float(np.mean([p['logLoss'] for p in rows])),
                'ece':sum(b['n']*abs(b['predicted']-b['observed']) for b in bins)/len(rows),'bins':bins}
    return {'games':len(common),'weeks':len(groups),'candidateMinusReferenceScoreMAEInterval95':np.quantile(boot,[.025,.975]).tolist(),
            'meanScoreMAEDifference':float(np.mean([x for xs in groups for x in xs])),
            'method':'Paired calendar-week block bootstrap, 2000 replicates, seeded; descriptive final test, never a selection gate.',
            'pairedPlayerCategories':{s:{'observations':len(ps),'referenceMAE':float(np.mean([abs(a['error']) for a,b in ps])),
                                           'candidateMAE':float(np.mean([abs(b['error']) for a,b in ps])),
                                           'referenceRMSE':float(np.sqrt(np.mean([a['error']**2 for a,b in ps]))),
                                           'candidateRMSE':float(np.sqrt(np.mean([b['error']**2 for a,b in ps])))} for s,ps in players.items()},
            'pairedCategoryProbabilityReliability':{s:{'observations':len(ps),'reference':calibration([a for a,b in ps]),'candidate':calibration([b for a,b in ps])} for s,ps in events.items()},
            'probabilityScoringScope':'Fixed research thresholds only. Players/thresholds within a game are correlated; counts are not independent sample sizes or verified betting lines.',
            'identityCoverageDifferences':dict(missing)}


def report(folder):
    completed=read(folder/'completed-report.json');results=[]
    for sport,finalist in completed['diagnosticFinalists'].items():
        for phase in ('validation','test'):
            def rows(candidate):return [r for p in (folder/'runs'/candidate/sport).glob('*.evaluation.json.gz') if (r:=read(p))['phase']==phase]
            results.append({'sport':sport,'phase':phase,'diagnosticFinalist':finalist,**compare(rows('reference-v15'),rows(finalist))})
    previous=read(ROOT/'docs/reports/v15-validation.json');ids={r['gameId'] for r in previous['inventory']}
    newids={read(p)['gameId'] for p in (folder/'runs').glob('*/*/*.evaluation.json.gz')}
    output={'protocolSha256':completed['protocolSha256'],'pairedComparisons':results,'cumulativeDistinctGamesAcrossV15AndV16':len(ids|newids),
            'newDistinctGamesNotInPreviousAudit':len(newids-ids),'newExperimentDistinctGames':len(newids),
            'finalTestDidNotSelectModels':True,'productionPromotions':completed['productionPromotions']}
    freeze_json(folder/'paired-analysis.json',output);(ROOT/'docs/reports/v16-paired-analysis.json').write_text(json.dumps(output,indent=2)+'\n')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(14,4),constrained_layout=True)
    for axis,(sport,models) in zip(axes,completed['finalTest'].items()):
        axis.plot([0,1],[0,1],'--',color='#999999',label='Ideal reliability')
        for candidate,metrics in models.items():
            if not metrics.get('homeWin'):continue
            bs=metrics['homeWin']['bins'];axis.plot([b['meanPredicted'] for b in bs],[b['observed'] for b in bs],marker='o',label=candidate+' n='+str(metrics['games']))
        axis.set(title=sport+' locked final test',xlim=(0,1),ylim=(0,1),xlabel='Raw home-win probability',ylabel='Observed home-win frequency');axis.legend(fontsize=7)
    fig.suptitle('Retrospective raw probability reliability; small samples and incomplete historical availability; no promotion')
    fig.savefig(ROOT/'docs/reports/v16-final-calibration.png',dpi=180);plt.close(fig)
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,default=ROOT/'artifacts/learning-v16');a=p.parse_args();print(json.dumps(report(a.folder)))
