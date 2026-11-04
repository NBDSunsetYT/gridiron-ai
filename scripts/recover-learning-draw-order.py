"""Add checked legacy draw-order sidecars, without modifying frozen artifacts."""
import argparse,gzip,json,pickle,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json,digest
from modeling.reproducibility import derive_draw_order,restore_draw_order


def recover(folder):
    cache={};records=[]
    for path in sorted((folder/'models').glob('*.json.gz')):
        model=json.loads(gzip.decompress(path.read_bytes()))
        if model['sport']=='NBA':continue
        sport=model['sport'];reference=model['version'].endswith('15.1.0');key=(sport,reference)
        if key not in cache:
            source=ROOT/'artifacts/engine-v15'/(sport+'-snap-start-clock-and-personnel-v15.1.cache') if reference else folder/'datasets'/(sport+'-repaired.pickle')
            cache[key]=pickle.load(source.open('rb')) # owned local source caches, never uploaded pickle
        order=derive_draw_order(model,cache[key]['rows']);restore_draw_order(model,order)
        target=folder/'draw-order-v2'/(model['sha256']+'.json.gz');freeze_json(target,order)
        records.append({'sport':sport,'modelSha256':model['sha256'],'drawOrderSha256':order['sha256'],'path':str(target.relative_to(folder))})
    result={'status':'passed','models':len(records),'records':records,'originalModelsModified':0,'originalForecastsModified':0,
            'method':'Recover first-observed participant ordering from the exact pinned training rows; verify every retained participation count, category identity and unchanged fitted-parameter hash.',
            'limitation':'Sidecars are required for exact replay of legacy sorted-JSON football artifacts; they are not an accuracy improvement.'}
    freeze_json(folder/'draw-order-recovery'/(digest(records)+'.json'),result);(ROOT/'docs/reports/v16-draw-order-recovery.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,default=ROOT/'artifacts/learning-v16');a=p.parse_args();r=recover(a.folder);print(json.dumps({k:v for k,v in r.items() if k!='records'}))
