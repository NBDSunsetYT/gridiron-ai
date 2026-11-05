"""Inspect clock precision in earlier TRAINING games, not held-out outcomes."""
import sys,json,gzip,hashlib
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.data import archives
from modeling.overnight_v20.state import atomic
from modeling.overnight_v20.sources import fetch
from modeling.reconstruction_v19.football_fit import CLOCK_KINDS
OUT=ROOT/'artifacts/overnight-v20';report={'scope':'Earlier training clocks only; original forecasts and source files unchanged','newSimulations':0,'leagues':{},'findings':[]}
for sport in ['NFL','CFB']:
    p=OUT/'experiments/r1/cohorts'/(sport+'-0')/'simulation-model.json.gz';model=json.loads(gzip.decompress(p.read_bytes()));ids=set(model['trainingGameIds']);rs=[r for r in archives(sport)['rows'] if r['game'] in ids and r['kind']=='rush' and r['yards']>0];zero=sum(r['elapsed']==0 for r in rs);report['leagues'][sport]={'trainingGames':len(ids),'fittedBefore':model['fittingCutoff'],'positiveYardRushes':len(rs),'zeroRecordedElapsedRushes':zero,'zeroFraction':zero/len(rs),'originalClockPublicationVerified':False}
    if sport=='CFB':
        cube=np.asarray(model['clockCDF']);t='cfb:espn:256';i=model['teams'].index(t);k=CLOCK_KINDS.index('rush');report['findings'].append({'kind':'coarsened_clock_treated_as_independent_physical_snap_duration','team':t,'context':'rush, not a completion, outside final two minutes, tied/one-score script','zeroDurationProbability':float(cube[i,k,0,0,1,0]),'expectedSeconds':float(np.sum(1-cube[i,k,0,0,1,:-1])),'modelSha256':model['sha256']})
        url='https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=401635556';raw,receipt=fetch(url)
        if raw:
            d=json.loads(raw);plays=[p for drive in d.get('drives',{}).get('previous',[]) for p in drive.get('plays',[])];observed=[{'playId':p['id'],'clock':p.get('clock',{}).get('displayValue'),'type':p.get('type',{}).get('text')} for p in plays if p.get('id') in ['401635556101849905','401635556101849906','401635556101849907']];report['findings'].append({'kind':'official_source_repeats_the_coarsened_clock','trainingEventId':'cfb:espn:401635556','eventEligibleForTraining':'cfb:espn:401635556' in ids,'source':url,'sourceSha256':receipt['sha256'],'retrievedAt':receipt['retrievedAt'],'originalPublicationVerified':False,'observed':observed,'interpretation':'The current official historical payload also assigns the same clock to successive distinct rush/pass plays. It does not establish exact individual snap runoff. Treating these zeros as independent timing samples can inflate simulated play volume. Do not replace them with invented observed times.'})
atomic(OUT/'accuracy-first/clock-diagnostic.json',report);atomic(ROOT/'docs/reports/overnight-v20-clock-diagnostic.json',report);print(json.dumps(report,indent=2))
