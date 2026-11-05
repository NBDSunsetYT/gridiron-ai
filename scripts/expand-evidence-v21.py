"""Expand source coverage and schedule identity before numerical registration."""
import sys,json,csv,types,copy,io,re
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.io import fetch,pdf_link,OUT
from modeling.evidence_v21.runtime import job
from modeling.overnight_v20 import sources
from modeling.overnight_v20.state import read,atomic
from modeling.iterative_learning import freeze_json
from modeling.accuracy_v20.quality import aware
from pypdf import PdfReader

def run():
 p=read(OUT/'protocol-components.json');updates=[];errors=[]
 def wrapped(url):
  b,r=fetch(url);return b,{**r,'sha256':r.get('sourceVersion')}
 collector=types.FunctionType(sources.nba_evidence.__code__,{**sources.nba_evidence.__globals__,'fetch':wrapped,'protocol':lambda:{'selection':p['componentSelection']}});nba=collector();freeze_json(OUT/'evidence/NBA-expanded.json.gz',nba)
 schedule={r['game_id']:r for r in csv.DictReader((ROOT/'artifacts/parallel-v19/sources/nfl-games.csv').open())}
 for sport in ['NFL','CFB']:
  for g in p['componentSelection'][sport]:
   provider=str(schedule[g['id']]['espn']) if sport=='NFL' else g['id'].split(':')[-1];league='nfl' if sport=='NFL' else 'college-football';url='https://site.api.espn.com/apis/site/v2/sports/football/'+league+'/summary?event='+provider;b,r=fetch(url)
   if b is None:errors.append({'eventId':g['id'],'reason':r});continue
   h=json.loads(b)['header'];c=h['competitions'][0]
   if str(h['id'])!=provider:raise ValueError('Event ID does not match schedule')
   if sport=='CFB' and {t['homeAway']:'cfb:espn:'+str(t['team']['id']) for t in c['competitors']}!={'home':g['home'],'away':g['away']}:raise ValueError('Team identity mismatch')
   updates.append({'eventId':g['id'],'old':g['at'],'scheduledKickoff':aware(c['date']).isoformat(),'source':url,'sourceVersion':r['sourceVersion'],'originalPublicationVerified':False});g['at']=aware(c['date']).isoformat()
  print(json.dumps({'stage':'component_schedule_aligned','sport':sport,'games':len(p['componentSelection'][sport])}),flush=True)
 books=[]
 for gid,u in [('cfb:espn:401635556','https://goheels.com/documents/2024/9/21/36664.PDF'),('cfb:espn:401643793','https://dxbhsrqyrr690.cloudfront.net/sidearm.nextgen.sites/bsu.sidearmsports.com/stats/football/2024/pdf/20250127012908-36665.pdf'),('cfb:espn:401628497','https://mgoblue.com/documents/2024/9/28/20240928-fbl-minneota.pdf')]:
  b,r=fetch(u)
  if b and not b.startswith(b'%PDF') and (linked:=pdf_link(b)):u=linked;b,r=fetch(u)
  if b and b.startswith(b'%PDF'):
   target=OUT/'gamebooks'/(gid.replace(':','_')+'.pdf');target.parent.mkdir(exist_ok=True);target.write_bytes(b);books.append({'eventId':gid,'path':str(target.relative_to(ROOT)),'source':u,'sourceVersion':r['sourceVersion'],'retrievedAt':r['retrievedAt'],'forOutcomesAndClockMeasurementOnly':True})
  else:errors.append({'eventId':gid,'stage':'gamebook','reason':r})
 freeze_json(OUT/'gamebooks/manifest.json',books);p['componentAlignment']={'updates':updates,'noScoresUsed':True};atomic(OUT/'protocol-final.json',p);public={**p,'sealedAndLockedFiles':{'manifestSha256':__import__('hashlib').sha256(json.dumps(p['sealedAndLockedFiles'],sort_keys=True).encode()).hexdigest(),'count':len(p['sealedAndLockedFiles']),'privateManifest':'artifacts/overnight-v21/protocol-final.json'}};atomic(ROOT/'docs/reports/overnight-v21-final-protocol.json',public);atomic(OUT/'expanded-source-receipt.json',{'nbaFacts':len(nba['facts']),'nbaMappedFacts':sum(f['playerId'] is not None for f in nba['facts']),'gamebooks':books,'errors':errors});return {'nbaFacts':len(nba['facts']),'alignedComponentGames':len(updates),'gamebooks':len(books),'sourceErrors':errors,'wholeGameForecastsStarted':0}
if __name__=='__main__':print(json.dumps(job('expanded-sources',run,cpu=1200,wall=2400,revision='collection-r2'),indent=2))
