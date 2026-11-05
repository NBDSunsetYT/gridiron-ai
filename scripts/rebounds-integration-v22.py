"""Complete the preregistered rebound comparison after an archive-key repair.

Frozen minute models/forecasts and exposure fits are reused unchanged. Outcome
archive dictionary keys are not event IDs; join exact game['id'] instead.
"""
import sys,json,gzip,pickle,hashlib
from pathlib import Path
from collections import defaultdict
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.integration_v22.io import OUT
from modeling.integration_v22.runtime import job
from modeling.integration_v22.datasets import protected
from modeling.integration_v22.metrics import paired
from modeling.overnight_v20 import data
from modeling.overnight_v20.state import read,atomic,digest
from modeling.accuracy_v20.quality import aware
from modeling.iterative_learning import freeze_json
def unpack(p):return json.loads(gzip.decompress(p.read_bytes()))
def run():
    packets=[g for g in data.packets('NBA') if g['id'] not in protected()];history=defaultdict(list);raw={g['id']:g for g in data.archives('NBA').values()};results=[];aggregate=[]
    for g in packets:
        for t in [g['home'],g['away']]:history[t].append(g)
    protocol=read(OUT/'protocol.json')
    for wi,games in enumerate(protocol['selection']['NBA']):
        prior=OUT/'components/NBA'/str(wi);snapshot=unpack(prior/'forecasts.json.gz');models=pickle.load((prior/'models.pickle').open('rb'));folder=OUT/'rebounds-r2'/str(wi);folder.mkdir(parents=True,exist_ok=True);path=folder/'forecasts.json.gz'
        if path.exists():pred=unpack(path)['rows']
        else:
            pred=[];details=[]
            for g in games:
                for team in [g['home'],g['away']]:
                    minutes={r['player']:r['predictions']['starter_state'] for r in snapshot['rows'] if r['gameId']==g['id'] and r['team']==team and r['stat']=='minutes' and 'starter_state' in r['predictions']};own=[];other=[]
                    if len(minutes)<5:raise ValueError('Insufficient frozen minute roster')
                    for tid,seq in [(team,own),(g['away'] if team==g['home'] else g['home'],other)]:
                        for prev in [p for p in history[tid] if aware(p['end'])+timedelta(hours=6)<aware(g['at'])][-5:]:
                            actual=raw[prev['id']];t=actual['teams'][tid];seq.append((t,actual['teams'][str(t['opponent_team_id'])]))
                    extra={}
                    for family,m in models['court'].items():
                        values,detail=m.predict_team(minutes,own,other);extra[family]=values;details.append({'eventId':g['id'],'team':team,'family':family,'trainingExposureGames':len(m.games),'fitCutoff':snapshot['fitCutoff'],'budgets':detail})
                    for r in snapshot['rows']:
                        if r['gameId']==g['id'] and r['team']==team and r['stat']=='rebounds':pred.append(r|{'predictions':{**r['predictions'],**{f:float(v[r['player']]) for f,v in extra.items()}}})
            freeze_json(path,{'rows':pred,'details':details,'sourceForecastHash':hashlib.sha256((prior/'forecasts.json.gz').read_bytes()).hexdigest(),'forecastsFrozenBeforeGrading':True,'newFit':False,'originalForecastsChanged':False,'conditionalOnly':True})
        actuals={(r['gameId'],r['team'],r['player']):r['actual'] for r in unpack(prior/'grades.json.gz') if r['stat']=='rebounds'};grades=[r|{'actual':actuals[(r['gameId'],r['team'],r['player'])]} for r in pred];freeze_json(folder/'grades.json.gz',grades);r={'window':wi,'games':len({r['gameId'] for r in grades}),'comparisons':{f:paired(grades,f,'hurdle') for f in ['identified_court','minutes_proxy']},'decision':'Conditional comparison only; no promotion'};atomic(folder/'results.json',r);results.append(r);aggregate.extend(grades)
    result={'windows':results,'games':len({r['gameId'] for r in aggregate}),'observations':len(aggregate),'comparisons':{f:paired(aggregate,f,'hurdle') for f in ['identified_court','minutes_proxy']},'additionalDistinctGamesBeyondComponents':0,'fixedFailure':'Normalized dictionary keys differed from canonical game id; exact g[id] index now used','modelParametersChanged':False,'promotionAllowed':False};atomic(OUT/'rebounds-r2/results.json',result);return result
if __name__=='__main__':
    path=OUT/'specs/rebounds-r2.json'
    if '--register' in sys.argv:
        if path.exists():raise ValueError('Rebound revision already registered')
        atomic(path,{'numericCode':{'scripts/rebounds-integration-v22.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'reason':'Exact canonical identity join repair; no parameter changes or selection changes; reuse original frozen minutes/exposure fits','baseProtocolHash':digest(read(OUT/'protocol.json'))});print('Registered rebound join repair')
    else:print(json.dumps(job('rebounds-r2',run,cpu=180,wall=600),indent=2))
