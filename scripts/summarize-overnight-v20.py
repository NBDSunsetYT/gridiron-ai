"""Read-only analysis of frozen V20 validation; never opens the sealed test set.

Counts unique configurations separately from chronological replications. Paired
uncertainty is clustered by game, not by correlated players within a game.
"""
import sys,json,gzip,math,hashlib
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import atomic,read
from modeling.overnight_v20.evaluation import summarize,compare
from modeling.structural_v18.models import error_metrics
from modeling.calibration_research import paired_interval
OUT=ROOT/'artifacts/overnight-v20'
def unpack(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def point_metrics(rows):
    return {f:error_metrics([r['actual'] for r in rows if f in r['predictions']],[r['predictions'][f] for r in rows if f in r['predictions']]) for f in sorted({k for r in rows for k in r['predictions']})}
def point_comparisons(rows):
    families=sorted({k for r in rows for k in r['predictions']});out={}
    for f in families:
        if f=='rolling5':continue
        bygame=defaultdict(list)
        for r in rows:
            if f in r['predictions'] and 'rolling5' in r['predictions']:bygame[r['gameId']].append((abs(r['predictions']['rolling5']-r['actual']),abs(r['predictions'][f]-r['actual'])))
        a=[np.mean([x[0] for x in rs]) for rs in bygame.values()];b=[np.mean([x[1] for x in rs]) for rs in bygame.values()]
        out[f]={'pairedGames':len(a),'pairedGameMAEDifference':paired_interval(a,b,20020) if a else None,'productionPromotion':False}
    return out
def build():
    result={'scope':'Conditional retrospective corrected-history validation; no qualified production promotion','reservedFinalOpened':False,'productionWrites':0,'leagues':{},'revisionResults':{}}
    for revision in sorted((OUT/'experiments').glob('r*')):
        rev={};result['revisionResults'][revision.name]=rev
        for sport in ['NFL','CFB','NBA']:
            folders=sorted((revision/'cohorts').glob(sport+'-*'));points=[];grades=defaultdict(list);windows=[];failures=[];attempts=[]
            for folder in folders:
                if (folder/'point-grades.json.gz').exists():points.extend(unpack(folder/'point-grades.json.gz'))
                for v in (folder/'grades').glob('*'):
                    for p in v.glob('*.json.gz'):grades[v.name].append(unpack(p))
                if (folder/'metrics.json').exists():windows.append({'cohort':folder.name,'metrics':read(folder/'metrics.json')})
                if (folder/'result.json').exists():
                    r=read(folder/'result.json');failures.extend(r['failures']);attempts.extend(r['runs'])
            primary='rebounds' if sport=='NBA' else 'passingYards';ps=[r for r in points if r['player']!='__team__'];cats={s:[r for r in ps if r['stat']==s] for s in sorted({r['stat'] for r in ps})};reference={g['gameId']:g for g in grades['v19_reference']}
            stats={v:summarize(gs) for v,gs in grades.items()};comparison={v:compare(reference,{g['gameId']:g for g in gs},sport) for v,gs in grades.items() if v!='v19_reference'}
            bycategory={s:{'observations':len(rs),'games':len({r['gameId'] for r in rs}),'players':len({r['player'] for r in rs}),'metrics':point_metrics(rs),'pairedComparisons':point_comparisons(rs)} for s,rs in cats.items()}
            groups={}
            for key in ['season','role','injuryEvidence','knownOutAtCutoff']:
                buckets=defaultdict(list)
                for r in ps:
                    if r['stat']==primary:buckets[str(r[key])].append(r)
                groups[key]={v:{'observations':len(rs),'games':len({r['gameId'] for r in rs}),'metrics':point_metrics(rs)} for v,rs in buckets.items()}
            # Include withheld completed batches without representing them as
            # accepted predictions. Other pre-simulation failures remain unknown.
            withheld=sum(f.get('error')=='Full-game accounting validation failed' for f in failures)
            rev[sport]={'projectionGamesEvaluated':len({r['gameId'] for r in points}),'playerObservations':len(ps),'playerIdentities':len({r['player'] for r in ps}),'fullGameMatchupsEvaluated':len(set(g['gameId'] for gs in grades.values() for g in gs)),'acceptedCompletedBatches':len(attempts),'acceptedSimulatedGames':sum(r['simulations'] for r in attempts),'completedButWithheldBatches':withheld,'completedButWithheldSimulatedGames':withheld*10000,'failures':failures,'fullGameSummaries':stats,'fullGameComparisons':comparison,'pointCategories':bycategory,'primaryPointBreakdowns':groups,'windows':windows,'uniquePointChallengers':4 if points else 0,'uniqueFullGameChallengers':len([v for v in grades if v!='v19_reference']),'pointInTimeCoverageComplete':False,'productionPromotion':False}
    result['runtime']=read(OUT/'runtime/state.json');result['evidence']=read(OUT/'source-effective-results.json')
    result['uniqueModelConfigurationMeaning']='Four point-projection alternatives plus two full-game engine alternatives per league. Windows, stat heads and seeds are replications, not distinct architectures.'
    return result
if __name__=='__main__':
    result=build();atomic(OUT/'summary.json',result)
    print(json.dumps({'runtimeActiveSeconds':result['runtime']['measuredActiveSeconds'],'status':result['runtime']['status'],'revisions':{revision:{sport:{k:v[k] for k in ['projectionGamesEvaluated','fullGameMatchupsEvaluated','acceptedSimulatedGames','completedButWithheldSimulatedGames']} for sport,v in leagues.items()} for revision,leagues in result['revisionResults'].items()}},indent=2))
