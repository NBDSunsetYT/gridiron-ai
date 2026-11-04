"""Independent read-only verification of compact learning artifacts after restart."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import digest,unrealism_flags
from modeling.reproducibility import restore_draw_order


def verify(folder):
    def read(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())
    protocol=read(folder/'protocol.json');check=dict(protocol);expected=check.pop('sha256')
    assert digest(check)==expected,'Protocol checksum mismatch'
    selected={g['id']:g for g in protocol['selection']};model_hashes=set()
    for path in (folder/'models').glob('*.json.gz'):
        model=read(path);sha=model['sha256']
        assert digest({k:v for k,v in model.items() if k!='sha256'})==sha,'Fitted model checksum mismatch'
        if model['sport'] in ('NFL','CFB'):
            order=folder/'draw-order-v2'/(sha+'.json.gz')
            assert order.exists(),'Missing legacy categorical draw-order metadata'
            restore_draw_order(model,read(order))
        model_hashes.add(sha)
    quarantined=set(protocol['quarantinedExposedFinalIds']);forecasts=0;complete=0;unique=set();counts=Counter();archive_bytes=0;missing=[]
    for path in sorted((folder/'runs').glob('*/*/*.forecast.json.gz')):
        archive=read(path);game=archive['game'];forecast=archive['forecast'];gid=game['id']
        assert archive['protocol']==expected and selected[gid]==game,'Forecast does not match frozen selection'
        assert forecast['inputDataVersion'] in model_hashes,'Missing fitted model artifact'
        assert forecast['evidenceCutoff']<game['cutoff']<=game['at'],'Future observation reached a forecast'
        assert forecast['simulations']==10000,'Requested complete-game count changed'
        assert not unrealism_flags(forecast),'Simulation failed internal quality checks'
        assert forecast.get('calibratedProbability') is None,'Unfitted probabilities labeled calibrated'
        assert not forecast.get('representativePlays'),'Bulk simulated plays were stored'
        if game['phase']=='test':assert gid not in quarantined,'Previously exposed final game was reused'
        evaluation=path.with_name(path.name.replace('.forecast.json.gz','.evaluation.json.gz'))
        if not evaluation.exists():missing.append(gid);continue
        result=read(evaluation)
        assert result['forecastSha256']==hashlib.sha256(path.read_bytes()).hexdigest(),'Forecast was changed after evaluation'
        forecasts+=1;complete+=forecast['simulations'];unique.add(gid);counts[game['sport']]+=1;archive_bytes+=path.stat().st_size
    report=read(folder/'completed-report.json')
    assert report['forecastVersions']==forecasts and report['uniqueGames']==len(unique),'Report inventory disagrees with persisted records'
    assert not missing,'Forecasts still need outcome evaluation'
    lock=read(folder/'final-selection-lock.json')
    assert report['researchSelectedModels']==lock['selected'],'Final results altered validation selection'
    assert report['diagnosticFinalists']==lock['diagnosticFinalists'],'Diagnostic finalist changed after final test'
    for path in (folder/'decisions').glob('*.json'):
        decision=read(path)
        assert decision['gate'].get('productionEligible') is not True,'Incomplete availability archives allowed a production promotion'
    return {'status':'passed','freshProcessRead':True,'protocolSha256':expected,'uniqueGames':len(unique),
            'forecastVersions':forecasts,'completeSimulatedGames':complete,'bySportForecastVersions':dict(counts),
            'compactForecastBytes':archive_bytes,'meanForecastBytes':archive_bytes//max(1,forecasts),
            'finalSelectionUnchanged':True,'privateDatabaseWrites':0,'bulkPlaysPermanentlyStored':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,default=ROOT/'artifacts/learning-v16');p.add_argument('--output',type=Path);a=p.parse_args();result=verify(a.folder)
    if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
