"""Train original GAFIE on verified historical events; simulate a held-out game.
The input must come from the operator historical audit; no fabricated data.
"""
import sys,json,time,hashlib,argparse
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modeling.gafie import fit_gafie,simulate_gafie
def run(source,out,count):
    f=json.loads(source.read_text());model=json.loads(source.with_suffix('.input.json').read_text());start=time.process_time();candidate=fit_gafie(model);fit_cpu=time.process_time()-start;model['gafie']=candidate
    start=time.process_time();result=simulate_gafie(model,f['game']['home']['id'],f['game']['away']['id'],count,14013,f['game']['startTime']);cpu=time.process_time()-start
    f.update(analysisId='gafie-retrospective-'+hashlib.sha256((f['game']['id']+candidate['artifactId']+str(count)).encode()).hexdigest(),modelVersion=result['modelVersion'],predictedAt=datetime.now(timezone.utc).isoformat(),result=result,retrospective=True);f['research']['gafieCandidate']=candidate
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(f,separators=(',',':')));out.with_suffix('.input.json').write_text(json.dumps(model,separators=(',',':')))
    report={'sport':f['game']['sport'],'gameId':f['game']['id'],'modelVersion':result['modelVersion'],'simulations':count,'fitCPUSeconds':fit_cpu,'simulationCPUSeconds':cpu,'trainingGames':len(candidate['trainingGames']),'holdoutGames':len(candidate['holdoutGames']),'playSelectionValidation':candidate['validation'],'predictedHome':result['scoreDistributions'][result['home']]['mean'],'predictedAway':result['scoreDistributions'][result['away']]['mean'],'modelPromoted':False,'mode':'retrospective','sourceInputVersion':model['sha256'],'candidateId':candidate['artifactId'],'allGamesRetained':False};out.with_suffix('.report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--simulations',type=int,choices=[10000,50000,100000],default=10000);a=p.parse_args();run(a.source,a.out,a.simulations)
