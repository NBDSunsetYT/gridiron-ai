"""Recover additional primary editions, without guessing complete availability."""
import sys,json,runpy,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.io import canonical_article,published_metadata
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/forecast-certification-v28'
SOURCES=[
 ('NFL','2026_01_NE_SEA','NE','https://www.patriots.com/news/week-1-inactives-patriots-at-seahawks'),
 ('NFL','2026_01_NE_SEA','SEA','https://www.seahawks.com/news/nick-emmanwori-tory-horton-inactive-for-seahawks-opener-vs-patriots'),
 ('NFL','2026_01_ATL_PIT','ATL','https://www.atlantafalcons.com/news/atlanta-falcons-inactives-week-1-pittsburgh-steelers'),
 ('NFL','2026_01_ATL_PIT','PIT','https://www.steelers.com/news/week-1-injury-report-falcons-x3059'),
 ('CFB','cfb:espn:401628497','MIN','https://gophersports.com/documents/download/2024/9/25/09.28.24_Michigan_Notes.pdf'),
 ('CFB',None,'conference-policy','https://bigten.org/news/2026/8/28/big-ten-announces-changes-to-football-availability-reporting-process.aspx')]

def run():
    cpu=time.process_time();fetch=runpy.run_path(str(ROOT/'scripts/v28-sources.py'))['fetch'];records=[]
    for sport,gid,team,url in SOURCES:
        body,r=fetch(url);row={'sport':sport,'eventId':gid,'team':team,'source':url,'httpStatus':r.get('httpStatus'),'sourceVersion':r.get('sourceVersion'),'retrievedAt':r.get('retrievedAt'),'lastModified':r.get('lastModified'),'bytes':r.get('bytes'),'completeAvailability':False,'startingLineupComplete':False,'forecastGateReleased':False}
        if body and 'pdf' not in url:
            try:
                a=canonical_article(body,r.get('finalUrl') or url);row.update(status='canonical_article_parsed',metadata={k:a[k] for k in ('headline','datePublished','dateModified') if k in a});freeze_json(OUT/'primary-private'/(hashlib.sha256(url.encode()).hexdigest()+'.json'),a)
            except ValueError as e:row.update(status='original_canonical_article_unverified',candidateMetadata=published_metadata(body),reason=str(e))
        elif body:row.update(status='primary_pdf_captured',publicationTimeVerified=False,reason='Document date/path is not proof of original publication edition; depth chart is not confirmed injury clearance')
        else:row.update(status='unavailable_within_capture_budget',error=r.get('error'),reason=r.get('message'))
        records.append(row);print(json.dumps(row),flush=True)
    report={'records':records,'canonicalArticles':sum(r.get('status')=='canonical_article_parsed' for r in records),'strictNewMatchups':0,'allUnknownsRemainUnknown':True,'cpuSeconds':time.process_time()-cpu};freeze_json(OUT/'primary-evidence.json',report)

def starters():
    """Explicit reviewed primary fact, with unique static identity reference.

    This is partial evidence, never a claim of complete historical roster or
    availability. No statistical outcome or postgame lineup supplies the fact.
    """
    import pyarrow.parquet as pq
    from modeling.overnight_v20.state import digest
    sources=json.loads((OUT/'primary-evidence.json').read_text());path=ROOT/'artifacts/parallel-v19/sources/players.parquet';players=pq.read_table(path,columns=['gsis_id','display_name','position']).to_pylist();matches=[p for p in players if p['display_name']=='Cooper Rush' and p['position']=='QB']
    if len(matches)!=1:raise ValueError('Ambiguous primary-reported quarterback identity')
    facts=[]
    for row in sources['records']:
        if row['team'] not in ('ATL','PIT'):continue
        article=json.loads((OUT/'primary-private'/(hashlib.sha256(row['source'].encode()).hexdigest()+'.json')).read_text());body=article['articleBody']
        if 'Cooper Rush' not in body or ('starting quarterback' not in body if row['team']=='ATL' else 'Cooper Rush will get the start' not in body):raise ValueError('Primary source no longer corroborates reviewed starter fact')
        facts.append({'gameId':'2026_01_ATL_PIT','teamId':'ATL','playerId':matches[0]['gsis_id'],'playerName':'Cooper Rush','fact':'reported_starting_quarterback','classification':'explicit_primary_report','source':row['source'],'sourceVersion':row['sourceVersion'],'publishedAt':row['metadata']['datePublished'],'modifiedAt':row['metadata']['dateModified'],'retrievedAt':row['retrievedAt'],'completeAvailability':False,'strictFullGameQualified':False,'identitySourceSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'identityReferenceIsHistoricalRoster':False,'postgameParticipationUsed':False})
    freeze_json(OUT/'starter-facts.json',facts);print(json.dumps({'corroboratingSources':len(facts),'strictNewFullGames':0}))

if __name__=='__main__':
    if '--starter-facts' in sys.argv:starters()
    else:run()
