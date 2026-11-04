"""Bounded same-seed replay and independent-seed diagnostics on VALIDATION only.

No parameter fitting, final-test tuning, or model promotion. Counts from these
quality checks are reported separately from graded historical forecast versions.
"""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse,gzip,json,math,sys,time
import pickle
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json
from modeling.reproducibility import derive_draw_order,restore_draw_order


def read(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())


def variance(dist):
    bins=dist['histogram'];n=sum(b['count'] for b in bins);mean=sum(b['value']*b['count'] for b in bins)/n
    return sum((b['value']-mean)**2*b['count'] for b in bins)/max(1,n-1)


def check(folder):
    protocol=read(folder/'protocol.json');selection=read(folder/'final-selection-lock.json');completed=read(folder/'completed-report.json')
    if completed['budget']['cpuSeconds']+300>protocol['limits']['cpuSeconds']:return {'status':'not_run','reason':'Insufficient remaining worker CPU budget for predeclared checks'}
    output=folder/'convergence';output.mkdir(exist_ok=True);reports=[];cpu_start=time.process_time()
    models={}
    for path in (folder/'models').glob('*.json.gz'):
        m=read(path);models[m['sha256']]=m
    for sport in ('NFL','CFB','NBA'):
        finalist=selection['diagnosticFinalists'][sport]
        game=next(g for g in protocol['selection'] if g['sport']==sport and g['phase']=='validation')
        original=read(folder/'runs'/finalist/sport/(game['id'].replace(':','_')+'.forecast.json.gz'))['forecast'];model=models[original['inputDataVersion']]
        order_reference=None
        if sport!='NBA':
            source=ROOT/'artifacts/engine-v15'/(sport+'-snap-start-clock-and-personnel-v15.1.cache') if finalist=='reference-v15' else folder/'datasets'/(sport+'-repaired.pickle')
            order_path=folder/'draw-order-v2'/(model['sha256']+'.json.gz')
            if order_path.exists():ordering=read(order_path)
            else:
                data=pickle.load(source.open('rb')) # owned, checksum-pinned local cache
                ordering=derive_draw_order(model,data['rows']);freeze_json(order_path,ordering)
            model=restore_draw_order(model,ordering);order_reference={'sha256':ordering['sha256'],'path':order_path.name,'fittedParametersUnchanged':True}
        if sport=='NBA':
            if finalist=='reference-v15':from modeling.nba_v15 import simulate_nba as simulate
            else:from modeling.nba_v16 import simulate_nba as simulate
        else:
            if finalist=='reference-v15':from modeling.football_v15 import simulate_football as simulate
            else:from modeling.football_v16 import simulate_football as simulate
        runs=[]
        for seed in (protocol['seed'],protocol['seed']+1):
            path=output/(sport+'-'+str(seed)+'.json.gz')
            if path.exists():result=read(path)
            else:
                result=simulate(model,game['home'],game['away'],game['at'],10000,seed,batch_size=2000,**({} if sport=='NBA' else {'representative_games':0}));freeze_json(path,result)
            runs.append(result)
        repeat,independent=runs
        exact=all(repeat[key]==original[key] for key in ('players','scoreDistributions','marginDistribution','totalDistribution','homeWinProbability','convergence'))
        measures=[]
        for side in ('home','away'):
            a,b=original['scoreDistributions'][game[side]],independent['scoreDistributions'][game[side]];se=math.sqrt(variance(a)/10000+variance(b)/10000);difference=abs(a['mean']-b['mean'])
            measures.append({'metric':side+'ScoreMean','difference':difference,'combinedMonteCarloSE':se,'withinFourSamplingSE':difference<=4*se})
        a,b=original['homeWinProbability'],independent['homeWinProbability'];se=math.sqrt((a*(1-a)+b*(1-b))/10000)
        measures.append({'metric':'homeWinProbability','difference':abs(a-b),'combinedMonteCarloSE':se,'withinFourSamplingSE':abs(a-b)<=4*se})
        reports.append({'sport':sport,'gameId':game['id'],'phase':'validation','candidate':finalist,'drawOrderReference':order_reference,'sameSeedExactNumericReplay':exact,'independentSeedChecks':measures,'simulationsPerReplica':10000,'replicas':2,'passed':exact and all(m['withinFourSamplingSE'] for m in measures)})
    result={'status':'passed' if all(r['passed'] for r in reports) else 'diagnostic_failed','reports':reports,'additionalCompleteGames':60000,'newHistoricalGames':0,
            'cpuSeconds':time.process_time()-cpu_start,'interpretation':'Sampling stability and replay checks only. These do not measure model accuracy or reduce structural, parameter or availability uncertainty. No test-period outcomes were used.'}
    freeze_json(folder/'convergence-report.json',result);(ROOT/'docs/reports/v16-convergence.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,default=ROOT/'artifacts/learning-v16');a=p.parse_args();print(json.dumps(check(a.folder)))
