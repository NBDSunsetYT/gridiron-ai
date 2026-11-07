"""Recover public primary editions and independent mechanics books, bounded.

Current mutable pages do not become historical pregame editions merely because
their URL includes a year. Publication fields are kept distinct from retrieval.
"""
import sys,json,runpy,gzip,hashlib,re,subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import read
from modeling.iterative_learning import freeze_json
from modeling.evidence_v21.io import canonical_article,published_metadata
from modeling.fullgame_v23.evidence import nba_rows
from modeling.overnight_v20.data import archives
OUT=ROOT/'artifacts/evidence-and-joint-v27'
capture=runpy.run_path(str(ROOT/'scripts/v26-capture.py'))
capture['get'].__globals__['OUT']=OUT/'source-probes'
get=capture['get']


def fetch(url):
    cache=OUT/'source-probes';receipt=cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if not receipt.exists() and len(list(cache.glob('*.json')))>=100:raise RuntimeError('V27 cumulative 100-request source budget exhausted')
    return get(url)


def books():
    games={g['id']:g for g in archives('NBA').values()};selection=read(OUT/'selection.json')['selection']['NBA']
    body,receipt=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams')
    if body is None:raise ValueError('Public NBA team identity source unavailable')
    teams={str(x['team']['id']):x['team']['abbreviation'] for s in json.loads(body)['sports'] for l in s['leagues'] for x in l['teams']}
    result={};dates=set()
    for gid in selection:
        game=games[gid];date=datetime.fromisoformat(game['at']).astimezone(ZoneInfo('America/New_York')).strftime('%Y%m%d');dates.add(date)
        sides={r['team_home_away']:teams[str(t)] for t,r in game['teams'].items()};url='https://statsdmz.nba.com/pdfs/'+date+'/'+date+'_'+sides['away']+sides['home']+'_book.pdf'
        raw,r=fetch(url)
        if raw is None:result[gid]={'source':url,'httpStatus':r.get('httpStatus'),'reason':'Independent book unavailable'};continue
        path=OUT/'books'/(gid.replace(':','_')+'.pdf');path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
        text=path.with_suffix('.txt');subprocess.run(['pdftotext','-layout',str(path),str(text)],check=True,timeout=15)
        result[gid]={'source':url,'sourceVersion':r['sourceVersion'],'textPath':str(text.relative_to(ROOT)),'retrievedAt':r['retrievedAt'],'scope':'final_mechanics_only'}
    freeze_json(OUT/'books.json',result)
    injury=[]
    for date in sorted(dates):
        formatted=date[:4]+'-'+date[4:6]+'-'+date[6:]
        url='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'+formatted+'_05PM.pdf';body,r=fetch(url)
        item={'source':url,'receipt':r}
        if body is not None:
            try:
                rows,issued=nba_rows(body);item.update(publishedAt=issued,facts=rows,status='parsed',editionType='publisher_dated_original_pdf',completeLineup=False)
            except ValueError as e:item.update(status='parse_failed',reason=str(e))
        else:item.update(status='unavailable')
        injury.append(item)
    freeze_json(OUT/'historical-nba-reports.json',injury)
    return {'books':sum('textPath' in r for r in result.values()),'booksRequested':len(result),'injuryDocuments':sum(r['status']=='parsed' for r in injury),'injuryRows':sum(len(r.get('facts',[])) for r in injury)}


def articles():
    sources=[
      ('NFL','2024_03_JAX_BUF','BUF','https://www.buffalobills.com/news/bills-list-5-players-inactive-vs-jaguars-week-3-mnf'),
      ('NFL','2024_03_JAX_BUF','JAX','https://www.jaguars.com/news/k000034-jaguars-in-and-out-2024-week-3-evan-engram-darnell-savage-out'),
      ('NBA',None,'NOP','https://www.nba.com/pelicans/news/injury-report-seven-pelicans-out-for-wednesday-game-at-okc')]
    report=[]
    for sport,gid,team,url in sources:
        body,r=fetch(url);item={'sport':sport,'eventId':gid,'team':team,'receipt':r}
        if body:
            try:
                article=canonical_article(body,r.get('finalUrl') or url);item['article']={k:article[k] for k in ('headline','datePublished','dateModified','articleBody') if k in article};item['status']='canonical_article_parsed'
                item['factsRequireExplicitExtraction']=True
            except ValueError as e:item.update(status='canonical_metadata_unavailable',reason=str(e),candidateMetadata=published_metadata(body))
        else:item['status']='source_unavailable'
        report.append(item)
    freeze_json(OUT/'historical-primary-articles.json',report)
    return {'primaryArticlesAccessed':sum(r['receipt'].get('httpStatus')==200 for r in report),'canonicalArticlesParsed':sum(r['status']=='canonical_article_parsed' for r in report)}


if __name__=='__main__':
    print(json.dumps(books()),flush=True);print(json.dumps(articles()),flush=True)
    print(json.dumps({'newRequests':capture['REQUESTS'][0],'productionWrites':0,'V26ForecastChanges':0}))
