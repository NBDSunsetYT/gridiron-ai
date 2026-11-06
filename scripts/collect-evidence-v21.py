"""Bounded primary source recovery. No scores are extracted for model inputs."""
import sys,json,types,csv,copy,re,hashlib
from pathlib import Path
from datetime import timedelta
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.io import fetch,pdf_link,published_metadata,OUT
from modeling.evidence_v21.availability import injury_tables,depth_chart,article_timestamp
from modeling.evidence_v21.runtime import job,protocol
from modeling.overnight_v20 import sources
from modeling.overnight_v20.state import atomic,read
from modeling.iterative_learning import freeze_json
from modeling.accuracy_v20.quality import aware
import pyarrow.parquet as pq

def collect():
 p=protocol();names=defaultdict(set)
 for r in pq.read_table(ROOT/'artifacts/parallel-v19/sources/players.parquet',columns=['gsis_id','display_name']).to_pylist():
  if r['gsis_id'] and r['display_name']:
   name=sources.norm(r['display_name'])
   for team in {g[t] for g in p['selection']['NFL'] for t in ['home','away']}:names[(team,name)].add(r['gsis_id'])
 facts=[];documents=[];errors=[];games={g['id']:g for gs in p['selection'].values() for g in gs}
 for url,gid,teams,kind in [('https://www.bengals.com/news/week-4-injury-report-bengals-at-panthers','2024_04_CIN_CAR',['CIN','CAR'],'injury'),('https://www.giants.com/news/giants-release-unofficial-depth-chart-for-week-4-vs-cowboys','2024_04_DAL_NYG',['NYG'],'depth')]:
  b,r=fetch(url)
  try:fs=injury_tables(b,r,games[gid],teams,names) if kind=='injury' else depth_chart(b,r,games[gid],teams[0],names);facts.extend(fs);documents.append({'url':url,'facts':len(fs),'mapped':sum(f['playerId'] is not None for f in fs),'canonicalArticleTimestampSelected':True})
  except Exception as e:errors.append({'url':url,'reason':str(e)})
 def wrapped(url):
  b,r=fetch(url);return b,{**r,'sha256':r.get('sourceVersion')}
 collector=types.FunctionType(sources.nba_evidence.__code__,{**sources.nba_evidence.__globals__,'fetch':wrapped,'protocol':lambda:{'selection':p['selection']}})
 nba=collector();freeze_json(OUT/'evidence/NBA-pregame.json.gz',nba)
 # Public historical notes are distinct from current game-day confirmations.
 for url in ['https://goheels.com/documents/2024/9/16/04_JMU_v3.pdf','https://fightingirish.com/wp-content/uploads/2024/09/LouisivlleND.pdf','https://owlsports.com/documents/2024/9/24/Army_Game_Notes.pdf','https://static.iuhoosiers.com/custompages/pdf/fb/2024/24-09-21-Notes_Charlotte.pdf','https://www.secsports.com/fbreports-archive']:
  b,r=fetch(url);record={'url':url,'receipt':r,'factType':'document_inventory','pregameParticipationConfirmed':False}
  if b and not b.startswith(b'%PDF') and (u:=pdf_link(b)):
   b,r=fetch(u);record.update(pdfUrl=u,pdfReceipt=r)
  if b and b.startswith(b'%PDF'):
   from pypdf import PdfReader
   import io
   reader=PdfReader(io.BytesIO(b));record.update(pdfPages=len(reader.pages),pdfMetadata={str(k):str(v) for k,v in dict(reader.metadata or {}).items() if k in ('/CreationDate','/ModDate')},lastModified=r.get('lastModified'));record['depthChartPages']=[i for i,page in enumerate(reader.pages) if 'DEPTH CHART' in (page.extract_text() or '').upper()]
  documents.append(record)
 # Align identity and actual scheduled kickoff without using final boxes/scores.
 schedule={r['game_id']:r for r in csv.DictReader((ROOT/'artifacts/parallel-v19/sources/nfl-games.csv').open())};updates=[];aligned=copy.deepcopy(p)
 for group in ['selection','componentSelection']:
  for sport in ['NFL','CFB']:
   for g in aligned[group][sport]:
    provider=str(schedule[g['id']]['espn']) if sport=='NFL' else g['id'].split(':')[-1];league='nfl' if sport=='NFL' else 'college-football';url='https://site.api.espn.com/apis/site/v2/sports/football/'+league+'/summary?event='+provider;b,r=fetch(url)
    if b is None:errors.append({'eventId':g['id'],'stage':'schedule','reason':r});continue
    d=json.loads(b);h=d['header'];comp=h['competitions'][0]
    if str(h['id'])!=provider:raise ValueError('Event ID mismatch')
    if sport=='CFB':
     sides={t['homeAway']:'cfb:espn:'+str(t['team']['id']) for t in comp['competitors']}
     if sides.get('home')!=g['home'] or sides.get('away')!=g['away']:raise ValueError('CFB team mapping mismatch')
    new=aware(comp['date']).isoformat();updates.append({'eventId':g['id'],'old':g['at'],'scheduledKickoff':new,'source':url,'sourceVersion':r['sourceVersion'],'retrievedAt':r['retrievedAt'],'originalSchedulePublicationVerified':False});g['at']=new
    print(json.dumps({'stage':'scheduled_kickoff','eventId':g['id'],'at':new}),flush=True)
 aligned['scheduleAlignment']={'updates':updates,'noScoresUsed':True,'originalSchedulePublicationVerified':False};atomic(OUT/'protocol-aligned.json',aligned);freeze_json(OUT/'evidence/NFL-primary-facts.json.gz',facts);freeze_json(OUT/'evidence/source-inventory.json.gz',{'documents':documents,'errors':errors});atomic(OUT/'evidence/coverage.json',{'NFL':{'primaryFacts':len(facts),'mappedFacts':sum(f['playerId'] is not None for f in facts),'reportsAndDepthCharts':len(documents[:2])},'NBA':{'facts':len(nba['facts']),'mappedFacts':sum(f['playerId'] is not None for f in nba['facts']),'gamesWithReport':sum(v['reportedPlayers']>0 for v in nba['coverage'].values())},'CFB':{'documentInventoryOnly':True,'confirmedGameDayFacts':0},'strictCompleteInputGames':0,'errors':errors});return {'sourceDocuments':len(documents),'newNFLPrimaryFacts':len(facts),'newNBAPrimaryFacts':len(nba['facts']),'scheduleIdentitiesAligned':len(updates),'fullGameJobsQueued':0}
if __name__=='__main__':print(json.dumps(job('source-recovery',collect,cpu=1200,wall=2400,revision='collection-r1'),indent=2))
