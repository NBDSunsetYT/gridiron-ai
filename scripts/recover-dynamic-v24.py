"""Bounded primary evidence recovery; never edits frozen forecasts."""
import sys,types,json,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.io import OUT,fetch
from modeling.dynamic_v24.runtime import job
from modeling.overnight_v20 import sources
from modeling.overnight_v20.data import packets
from modeling.overnight_v20.state import atomic,read
from modeling.fullgame_v23.evidence import nba_rows
from modeling.evidence_v21.io import canonical_article,published_metadata
from modeling.iterative_learning import freeze_json
def run():
    selected=read(OUT/'specs/sequential-r3.json')['selection']['NBA'];ids=[w['validation'][0]['id'] for w in selected];meta={g['id']:g for g in packets('NBA')};sample=[meta[g] for g in ids if g in meta]
    def wrapped(url):
        b,r=fetch(url);return b,{**r,'sha256':r.get('sourceVersion',r.get('sha256'))}
    nba=types.FunctionType(sources.nba_evidence.__code__,{**sources.nba_evidence.__globals__,'fetch':wrapped,'nba_rows':nba_rows,'protocol':lambda:{'selection':{'NBA':sample}}})();documents=[]
    for url in ['https://www.nfl.com/news/week-13-injury-report-for-2022-nfl-season','https://www.nfl.com/news/week-7-injury-report-for-2023-nfl-season','https://www.patriots.com/news/week-13-patriots-bills-injury-report','https://theamerican.org/sports/2025/8/5/fbavail.aspx','https://www.secsports.com/fbreports-archive']:
        b,r=fetch(url);d={'source':url,'sourceVersion':r.get('sourceVersion'),'retrievedAt':r['retrievedAt'],'httpStatus':r.get('httpStatus'),'completePregameLineupEstablished':False}
        if b:
            try:a=canonical_article(b,url);d.update(publishedAt=a.get('datePublished'),modifiedAt=a.get('dateModified'),role='publisher_dated_inventory_not_complete_evidence')
            except ValueError as e:d.update(publishedMetadata=published_metadata(b),reason=str(e),strictTimestampVerified=False)
        documents.append(d)
    result={'NBAFacts':nba['facts'],'NBAReports':nba['reports'],'NBAUnmapped':nba['unmapped'],'primaryDocuments':documents,'newStrictPregameGames':0,'newStrictLiveReplayGames':0,'unknownMeansHealthy':False,'historicalEditionArrivalTimesRecovered':False,'reason':'Individual injury statuses and dated inventory pages do not supply complete participation, lineups, weather or source-arrival-complete live snapshots.'};freeze_json(OUT/'evidence/recovery-r1.json.gz',result);atomic(OUT/'evidence/coverage.json',{k:v for k,v in result.items() if k!='NBAFacts'}|{'newNBAFacts':len(nba['facts'])});return {'newNBAFacts':len(nba['facts']),'primaryDocuments':len(documents),'newStrictPregameGames':0}
if __name__=='__main__':
    if '--register' in sys.argv:freeze_json(OUT/'specs/evidence-r1.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'modeling/dynamic_v24/io.py',ROOT/'modeling/fullgame_v23/evidence.py']},'limit':'Two NBA dates, two official reports/date; five primary inventory pages; no private APIs'})
    else:print(json.dumps(job('evidence-r1',run,cpu=180,wall=420),indent=2))
