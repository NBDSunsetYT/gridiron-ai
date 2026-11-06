"""Append verified missing grades; never rewrite original partial evaluations."""
import sys,json,gzip,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.sources import fetch,protocol
from modeling.overnight_v20.cohort import point_grade
from modeling.overnight_v20.state import atomic
from modeling.accuracy_v20.outcomes import normalize_nba_final,VERSION
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/overnight-v20';receipt=json.loads((OUT/'point-only/receipt.json').read_text());saved=[];failures=[]
for pending in receipt['pendingOutcomes']:
    g=next(g for g in protocol()['selection']['NBA'] if g['id']==pending['eventId']);url='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+g['id'].split(':')[-1];raw,source=fetch(url)
    try:
        if raw is None:raise ValueError('Official NBA final source HTTP '+str(source.get('httpStatus')))
        box=normalize_nba_final(json.loads(raw),g['id'],g['home'],g['away']);p=OUT/'point-only/cohorts'/('NBA-'+str(g['cohort']))/'forecasts.json.gz';rows=json.loads(gzip.decompress(p.read_bytes()))['rows'];rows=[r for r in rows if r['gameId']==g['id']];grades=point_grade(rows,{g['id']:box},'NBA');body={'game':g,'box':box,'source':source,'rows':grades,'originalForecastSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'noRefitting':True,'adapterVersion':VERSION,'originalPartialGradesPreserved':True};path=OUT/'point-only/completed-outcomes'/(g['id'].replace(':','_')+'-'+VERSION+'.json.gz');freeze_json(path,body);saved.append({'eventId':g['id'],'grades':len(grades),'artifact':str(path.relative_to(ROOT)),'sourceSha256':source['sha256'],'categoriesSupported':box['supportedStatisticsByTeam'],'missingMinutes':len(box['missingMinutes']),'unmappedRows':len(box['unmapped'])})
    except (ValueError,KeyError,TypeError) as e:failures.append({'eventId':g['id'],'reason':str(e)})
result={'completed':saved,'failures':failures,'simulations':0,'productionWrites':0,'finalTestGraded':False};atomic(OUT/'point-only/outcome-completion-receipt.json',result);print(json.dumps(result,indent=2))
