"""Preregister a metadata-only amendment before any V20 forecast evaluation."""
import sys,json,random,copy
from pathlib import Path
from datetime import datetime,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.sources import fetch
from modeling.structural_v18.data import archives
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/overnight-v20';target=OUT/'protocol-effective.json'
if target.exists():print('Effective protocol already frozen');sys.exit(0)
p=json.load((OUT/'protocol.json').open());p=copy.deepcopy(p);dates=sorted({g['at'][:10] for g in p['selection']['CFB']});events={};receipts=[]
for date in dates:
    url='https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates='+date.replace('-','')+'&groups=80&limit=1000';b,r=fetch(url);receipts.append(r)
    if b:
        for e in json.loads(b).get('events',[]):
            cs=e['competitions'][0]['competitors'];sides={c['homeAway']:'cfb:espn:'+str(c['team']['id']) for c in cs};events['cfb:espn:'+e['id']]={'at':e['date'],'home':sides['home'],'away':sides['away'],'sourceSha256':r['sha256']}
    print(json.dumps({'scheduleDate':date,'resolvedEvents':len(events)}),flush=True)
resolved=0
for g in p['selection']['CFB']:
    found=events.get(g['id'])
    if found:
        if (found['home'],found['away'])!=(g['home'],g['away']):raise ValueError('CFB schedule team identity mismatch')
        g.update(originalCalendarOrFirstPlayTime=g['at'],at=found['at'],scheduleSourceSha256=found['sourceSha256'],originalSchedulePublicationVerified=False);resolved+=1
# The originally selected November 2025 NFL window has no unexamined games.
# Add a new December 2024 window, not another look at the old graded sample.
d=archives('NFL');excluded=set(p['excludedEvaluationIds'])|{g['id'] for g in p['selection']['NFL']}|{g['id'] for g in p['sealedFinal']['NFL']};eligible=[]
for g in d['games'].values():
    if '2024-12-01'<=g['firstObservedAt'][:10]<'2024-12-15' and g['id'] not in excluded and g['plays']>=70:eligible.append(g)
rng=random.Random(20021);rng.shuffle(eligible)
for i,g in enumerate(eligible[:75]):p['selection']['NFL'].append({k:g[k] for k in ['id','sport','home','away','season']}|{'at':g['firstObservedAt'],'end':g['lastObservedAt'],'cohort':3,'fullGame':i<12})
p['amendment']={'number':1,'frozenBeforeV20ModelEvaluation':True,'reason':'Resolve CFB calendar placeholders; add a genuinely new NFL metadata window because the originally selected fourth window was empty.','cfbSchedulesResolved':resolved,'cfbSchedulesUnresolved':len(p['selection']['CFB'])-resolved,'newNflGames':len(eligible[:75]),'scheduleMetadataOnly':True,'noFinalStatisticsUsedForSelection':True}
freeze_json(target,p);freeze_json(ROOT/'docs/reports/overnight-v20-effective-protocol.json',p);print(json.dumps(p['amendment']))
