"""Concurrent NFL/CFB source reconstruction with immutable provenance objects.
Missing timestamps remain missing. No database, account or financial operation.
"""
import sys,json,gzip,hashlib,re,os,time,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.reconstruction_v19.evidence import Evidence,reconstruct,KINDS,aware
from modeling.iterative_learning import freeze_json
from modeling.structural_v18.data import archives
import pyarrow.parquet as pq
import pyarrow.compute as pc
OUT=ROOT/'artifacts/parallel-v19';SRC=OUT/'sources'
URLS={**{f'injuries_{y}':f'https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{y}.parquet' for y in [2024,2025]},'depth_charts_2025':'https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2025.parquet','snap_counts_2025':'https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2025.parquet','nfl_official':'https://www.49ers.com/news/brock-purdy-jauan-jennings-out-vs-cardinals-inactives-for-week-3-azvssf','cfb_official':'https://s3.amazonaws.com/sidearm.sites/mac-sports/documents/2025/11/8/2025_FB_Availability_Report_11_8.pdf'}
def fetch(pair):
    name,url=pair;receipt_path=SRC/(name+'.receipt.json')
    if receipt_path.exists():return json.load(receipt_path.open())
    try:
        with urllib.request.urlopen(url,timeout=25) as r:
            data=r.read(15000001)
            if len(data)>15000000:raise ValueError('Source exceeds bounded 15 MB download')
            now=datetime.now(timezone.utc).isoformat();sha=hashlib.sha256(data).hexdigest();p=SRC/'objects'/(sha+'.gz');p.parent.mkdir(exist_ok=True)
            if not p.exists():p.write_bytes(gzip.compress(data,mtime=0))
            receipt={'name':name,'url':url,'sha256':sha,'bytes':len(data),'retrievedAt':now,'httpStatus':r.status,'lastModified':r.headers.get('Last-Modified'),'etag':r.headers.get('ETag'),'objectPath':str(p.relative_to(ROOT))}
    except Exception as e:receipt={'name':name,'url':url,'retrievedAt':datetime.now(timezone.utc).isoformat(),'error':type(e).__name__+': '+str(e),'httpStatus':getattr(e,'code',None)}
    freeze_json(receipt_path,receipt);return receipt
def body(receipt):return gzip.decompress((ROOT/receipt['objectPath']).read_bytes())
def record(receipt,sport,kind,value,**kw):return Evidence(sport,kind,receipt['url'],receipt['sha256'],receipt['retrievedAt'],value=value,**kw)

def nfl_contexts(protocol,receipts):
    depth=pq.read_table(SRC/'depth_charts_2025.parquet');inj=pq.read_table(SRC/'injuries_2025.parquet').to_pylist();stats=archives('NFL');allfacts={};contexts=[]
    for game in protocol['selection']['NFL']:
        facts=[]
        for team in [game['home'],game['away']]:
            team_table=depth.filter(pc.and_(pc.equal(depth['team'],team),pc.less(depth['dt'],game['at'])))
            if len(team_table):
                latest=pc.max(team_table['dt']).as_py();current=team_table.filter(pc.equal(team_table['dt'],latest)).to_pylist();qbs={r['gsis_id']:r for r in current if r['pos_abb']=='QB' and r['pos_rank']==1 and r['gsis_id']}
                for row in {r['gsis_id']:r for r in current if r['gsis_id']}.values():
                    facts.append(record(receipts['depth_charts_2025'],'NFL','depth_chart',{'rank':row['pos_rank'],'position':row['pos_abb'],'name':row['player_name'],'projectedNotConfirmed':True},confidence='provider_snapshot',published_at=row['dt'],observed_at=row['dt'],team_id=team,player_id=row['gsis_id']))
                if len(qbs)==1:
                    pid,row=next(iter(qbs.items()));facts.append(record(receipts['depth_charts_2025'],'NFL','starting_quarterback',{'name':row['player_name'],'status':'projected_depth_chart','confirmedStarter':False},confidence='provider_snapshot',published_at=row['dt'],observed_at=row['dt'],team_id=team,player_id=pid))
            week=int(game['id'].split('_')[1])
            for row in inj:
                if row['team']==team and row['season']==game['season'] and row['week']==week:
                    facts.append(record(receipts['injuries_2025'],'NFL','injury',{'status':row['report_status'],'practice':row['practice_status'],'injury':row['report_primary_injury'],'name':row['full_name']},confidence='unverified_timestamp',team_id=team,player_id=row['gsis_id'],event_id=game['id'],missing_reason='2025 provider schema has no date_modified/publication timestamp; week is not a publication time.'))
        for f in facts:allfacts[f.id]=f
        contexts.append(reconstruct(facts,'NFL',game['id'],[game['home'],game['away']],game['at']))
    return contexts,allfacts

def cfb_contexts(protocol,receipts):
    # Uniform schema; an indexed report/image without version/publication proof
    # is a source-discovery lead, never an invented player availability record.
    return [reconstruct([],'CFB',g['id'],[g['home'],g['away']],g['at']) for g in protocol['selection']['CFB']],{}

def source_cases(receipts):
    cases=[];facts=[];n=receipts['nfl_official'];text=body(n).decode();published=re.search(r'"datePublished":"([^"]+)"',text);modified=re.search(r'"dateModified":"([^"]+)"',text)
    if published and 'from questionable to OUT' in text:
        depth=pq.read_table(SRC/'depth_charts_2025.parquet').to_pylist()
        for name in ['Brock Purdy','Jauan Jennings']:
            ids={r['gsis_id'] for r in depth if r['team']=='SF' and r['player_name']==name and r['gsis_id'] and r['dt']<'2025-09-21T20:25:00Z'}
            if len(ids)==1:facts.append(record(n,'NFL','availability',{'name':name,'status':'out','timestampBasis':'Official article JSON-LD publication and modification'},confidence='official_confirmed',published_at=published[1],modified_at=modified[1] if modified else None,team_id='SF',player_id=ids.pop(),event_id='2025_03_ARI_SF'))
    cases.append(reconstruct(facts,'NFL','2025_03_ARI_SF',['SF','ARI'],'2025-09-21T20:25:00Z'))
    m=receipts['cfb_official'];uploaded=parsedate_to_datetime(m['lastModified']).astimezone(timezone.utc).isoformat();from pypdf import PdfReader
    import io
    pdf=PdfReader(io.BytesIO(body(m)));data=archives('CFB');g=next(g for g in data['games'].values() if g['firstObservedAt'].startswith('2025-11-08') and 'Bowling Green' in str(g.get('homeName'))+str(g.get('awayName')) and 'Eastern Michigan' in str(g.get('homeName'))+str(g.get('awayName')));facts=[];unmapped=0
    for page,term in zip(pdf.pages,['Bowling Green','Eastern Michigan']):
        team=g['home'] if term in g['homeName'] else g['away'];names=defaultdict(set)
        for prior in data['games'].values():
            if prior['lastObservedAt']>=g['firstObservedAt']:continue
            for pid,p in prior['players'].items():
                if p['team']==team:names[re.sub(r'[^a-z0-9]','',p['name'].lower())].add(pid)
        rows=page.extract_text(extraction_mode='layout').splitlines();start=False;boundary=40
        for line in rows:
            if 'OUT' in line and 'questionable' in line.lower():start=True;boundary=(line.index('OUT')+3+line.lower().index('questionable'))//2;continue
            if not start:continue
            for part,status in [(line[:boundary],'out'),(line[boundary:],'questionable')]:
                match=re.match(r'^\s*\d+\s+(.+?)\s*$',part)
                if not match:continue
                name=re.sub(r'\s*\(Season\)','',match[1]).strip();key=re.sub(r'[^a-z0-9]','',name.lower());ids=names.get(key,set());pid=next(iter(ids)) if len(ids)==1 else None;unmapped+=int(pid is None)
                facts.append(record(m,'CFB','availability',{'name':name,'status':status,'timestampBasis':'Official public S3 object Last-Modified, cross-checked with PDF creation/modification date. This is source-object version time, not a claimed editorial publication minute.','identityMapped':pid is not None},confidence='provider_snapshot',published_at=uploaded,modified_at=uploaded,team_id=team,player_id=pid,event_id=g['id']))
    context=reconstruct(facts,'CFB',g['id'],[g['home'],g['away']],g['firstObservedAt']);context['unmappedPlayerNames']=unmapped;context['sourceObjectTimeNotEditorialPublication']=True;cases.append(context)
    return cases

def main():
    protocol=json.load((OUT/'protocol.json').open());cpu=time.process_time()
    with ThreadPoolExecutor(max_workers=2) as pool:receipts={r['name']:r for r in pool.map(fetch,URLS.items())}
    if any('error' in r for r in receipts.values()):raise RuntimeError('A required reconstruction source failed; inspect source receipts')
    with ThreadPoolExecutor(max_workers=2) as pool:
        nfl=pool.submit(nfl_contexts,protocol,receipts);cfb=pool.submit(cfb_contexts,protocol,receipts);contexts1,facts1=nfl.result();contexts2,facts2=cfb.result()
    cases=source_cases(receipts);report={'NFL':{'games':len(contexts1),'anyProjectedQB':sum(c['coverage']['starting_quarterback']['records']>0 for c in contexts1),'anyInjuryEvidence':sum(c['coverage']['injury']['records']>0 for c in contexts1),'confirmedCompleteLineups':sum(c['lineupConfirmed'] for c in contexts1)},'CFB':{'games':len(contexts2),'anyProjectedQB':0,'anyInjuryEvidence':0,'confirmedCompleteLineups':0},'sourceQualificationCases':[{'sport':c['sport'],'eventId':c['eventId'],'acceptedFacts':len(c['accepted']),'strictFullInputReconstruction':False} for c in cases],'sources':receipts,'cpuSeconds':time.process_time()-cpu,'financialDatabaseOperations':0,'limitations':['NFL 2025 injury file lacks publication timestamps; none was invented.','Depth charts are projected provider snapshots, not confirmed starting lineups.','Conference web archive URLs returned 404 in the direct client; indexed images and mutable reports without version/publication proof are not treated as pregame evidence.','The CFB MAC source qualification case is separate from the locked validation cohort, not an outcome-selected extra evaluation game.','Historical weather runs expose initialization, which is not public availability; hindcast/version/issue-time proof is required before model use.','No complete pregame roster, practice, weather, transaction and snap-publication archive was established for every validation game.']}
    freeze_json(OUT/'evidence.json.gz',{'facts':[f.json() for f in {**facts1,**facts2}.values()],'contexts':{'NFL':contexts1,'CFB':contexts2},'sourceCases':cases});freeze_json(ROOT/'docs/reports/parallel-v19-source-coverage.json',report);print(json.dumps({s:report[s] for s in ['NFL','CFB']}|{'sourceCases':report['sourceQualificationCases'],'cpuSeconds':report['cpuSeconds']}))
if __name__=='__main__':main()
