"""Lock one additional forward confirmation sample without reading its outcomes."""
import sys,json,random,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.data import archives
from modeling.overnight_v20.sources import protocol
from modeling.iterative_learning import freeze_json,digest
OUT=ROOT/'artifacts/overnight-v20/confirmation';OUT.mkdir(exist_ok=True);path=OUT/'protocol.json'
if path.exists():print('Confirmation already registered');sys.exit(0)
p=protocol();seen=set(p['excludedEvaluationIds'])|{g['id'] for gs in p['selection'].values() for g in gs}|{g['id'] for gs in p['sealedFinal'].values() for g in gs};rng=random.Random(20021);selection={};counts={}
for sport in ['NFL','CFB','NBA']:
    data=archives(sport);rows=data.values() if sport=='NBA' else data['games'].values();start,end=('2026-03-01','2026-03-15') if sport=='NBA' else ('2025-12-01','2025-12-15');eligible=[]
    for g in rows:
        at=g['at'] if sport=='NBA' else g['firstObservedAt']
        if not start<=at[:10]<end or g['id'] in seen:continue
        if sport=='NBA':
            sides={t['team_home_away']:str(tid) for tid,t in g['teams'].items()}
            if set(sides)!={'home','away'}:continue
            item={'id':g['id'],'sport':sport,'at':at,'home':sides['home'],'away':sides['away'],'season':g['season'],'cohort':4,'fullGame':False}
        else:item={k:g[k] for k in ['id','sport','home','away','season']}|{'at':at,'cohort':4,'fullGame':False}
        eligible.append(item)
    rng.shuffle(eligible);selection[sport]=sorted(eligible[:75],key=lambda g:g['at']);counts[sport]={'eligible':len(eligible),'selected':len(selection[sport]),'window':[start,end],'reason':'No new eligible events before the sealed final boundary' if not eligible else 'Metadata-only reproducible selection; no outcome-based filter'}
body={'id':'accuracy-forward-confirmation-20.1','seed':20021,'selection':selection,'counts':counts,'primaryCandidate':'opportunity_hurdle','primaryReference':'rolling5','primaryStatistics':{'NFL':'passingYards','CFB':'passingYards','NBA':'rebounds'},'allFamiliesLocked':['rolling5','ridge','hierarchical','boosted','hybrid','opponent_adjusted_rolling','opportunity_hurdle'],'noFurtherTuning':True,'newSimulations':0,'maximumCpuSeconds':900,'maximumWallSeconds':1800,'promotionAllowed':False,'existingFinalSetUntouched':True,'originalProtocolSha256':digest(p),'numericCode':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'modeling/opportunity_hurdle_v20.py',ROOT/'modeling/accuracy_v20/projections.py',ROOT/'modeling/accuracy_v20/benchmarks.py',ROOT/'modeling/structural_v18/models.py',ROOT/'modeling/overnight_v20/data.py']}}
freeze_json(path,body);freeze_json(ROOT/'docs/reports/overnight-v20-confirmation-protocol.json',body);print(json.dumps(counts,indent=2))
