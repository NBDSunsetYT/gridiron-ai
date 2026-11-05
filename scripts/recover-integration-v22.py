"""Bounded primary-source recovery, separate from frozen statistical forecasts."""
import sys,re,json,types
from pathlib import Path
from collections import defaultdict,Counter
from datetime import timedelta
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.integration_v22.io import OUT,fetch
from modeling.integration_v22.runtime import job
from modeling.integration_v22.datasets import nfl_packets,protected
from modeling.overnight_v20.state import read,atomic
from modeling.overnight_v20 import sources
from modeling.evidence_v21.availability import nfl_article_statuses,article_timestamp,injury_tables,NFL_HEADINGS
from modeling.evidence_v21.io import canonical_article,published_metadata
from modeling.evidence_v21.tiers import timestamped_fact
from modeling.accuracy_v20.quality import aware
from modeling.iterative_learning import freeze_json
class Visible(HTMLParser):
    """Ignore related JSON scripts; keep published visible injury list lines."""
    def __init__(self):super().__init__();self.text=[];self.skip=0
    def handle_starttag(self,t,a):
        if t in ('script','style'):self.skip+=1
    def handle_endtag(self,t):
        if t in ('script','style'):self.skip-=1
        if t in ('li','h1','h2','h3','h4','div','p'):self.text.append('\n')
    def handle_data(self,d):
        if not self.skip:self.text.append(d)
def run():
    protocol=read(OUT/'protocol.json');games={s:[g for ws in vals for g in ws] for s,vals in protocol['selection'].items()};packets,raw,_=nfl_packets();facts=[];errors=[];documents=[];names=defaultdict(set)
    banned=protected()
    for r in raw:
        if r.get('player_display_name') and r['game_id'] not in banned:names[(r['team'],sources.norm(r['player_display_name']))].add(r['player_id'])
    url='https://www.nfl.com/news/week-5-injury-report-for-2023-nfl-season';b,r=fetch(url)
    if b:
        article=canonical_article(b,url);parser=Visible();parser.feed(b.decode());rows=[];team=None
        for line in ''.join(parser.text).splitlines():
            line=line.strip()
            if line in NFL_HEADINGS:team=line
            if team and re.match(r'^(OUT|DOUBTFUL|QUESTIONABLE):',line):
                try:rows.extend(nfl_article_statuses({'articleBody':team+'\n'+line}))
                except ValueError as e:errors.append({'source':url,'lineSha256':__import__('hashlib').sha256(line.encode()).hexdigest(),'reason':str(e),'accepted':False})
        for g in games['NFL']:
            if int(g['id'].split('_')[1])!=5:continue
            cutoff=(aware(g['at'])-timedelta(minutes=30)).isoformat()
            try:proof=timestamped_fact(url,r['sourceVersion'],article['datePublished'],r['retrievedAt'],cutoff,article.get('dateModified'))
            except ValueError as e:errors.append({'eventId':g['id'],'reason':str(e),'source':url});continue
            for row in rows:
                if row['teamId'] not in (g['home'],g['away']):continue
                ids={p['player_id'] for p in raw if p['game_id'] not in banned and p['team']==row['teamId'] and sources.norm(p.get('player_display_name'))==sources.norm(row['playerName']) and (p['season']<2023 or p['season']==2023 and p['week']<5)};pid=next(iter(ids)) if len(ids)==1 else None
                facts.append({**proof,**row,'eventId':g['id'],'sport':'NFL','playerId':pid,'kind':'official_league_injury_designation','sourceRole':'primary_league','identityStatus':'resolved_earlier_team_history' if pid else 'unresolved','availability':'confirmed_out' if row['status']=='out' else 'uncertain','practiceParticipation':'not_in_summary','completeReport':False})
        documents.append({'url':url,'datePublished':article['datePublished'],'dateModified':article.get('dateModified'),'explicitDesignations':len(rows),'sourceVersion':r['sourceVersion'],'bodyFinding':'Canonical JSON-LD omits visible injury lists; parsed visible HTML lists, scripts excluded.'})
    # Read a small predeclared sample of official PDF report dates per window.
    sample=[]
    for ws in protocol['selection']['NBA']:
        if ws:sample.extend(ws[:2])
    def wrapped(url):
        body,receipt=fetch(url);return body,{**receipt,'sha256':receipt.get('sourceVersion',receipt.get('sha256'))}
    nba=types.FunctionType(sources.nba_evidence.__code__,{**sources.nba_evidence.__globals__,'fetch':wrapped,'protocol':lambda:{'selection':{'NBA':sample}}})();facts.extend(nba['facts']);freeze_json(OUT/'evidence/NBA-primary.json.gz',nba)
    # Date-only college pages are retained as lower-confidence documents. A
    # URL date or the retrieval timestamp is never promoted to publication time.
    for url in ['https://utsports.com/news/2025/10/10/football-fb-preview-12-12-vols-back-in-neyland-to-host-razorbacks','https://theamerican.org/sports/2025/10/11/pa_navy_tem_101125.aspx','https://www.secsports.com/fbreports-archive']:
        b,r=fetch(url);record={'source':url,'httpStatus':r.get('httpStatus'),'sourceVersion':r.get('sourceVersion'),'retrievedAt':r['retrievedAt'],'strictPregameFactAccepted':False,'role':'primary_document_inventory'}
        if b:
            record['publishedMetadata']=published_metadata(b)
            try:article=canonical_article(b,url);record.update(datePublished=article.get('datePublished'),dateModified=article.get('dateModified'))
            except ValueError as e:record['blocker']=str(e)+'; no verifiable per-record pregame timestamp recovered'
        documents.append(record)
    freeze_json(OUT/'evidence/facts.json.gz',{'facts':facts,'documents':documents,'errors':errors,'previousForecastsChanged':False})
    coverage={'factsByLeague':dict(Counter(f['sport'] for f in facts)),'eventsByLeague':{s:len({f['eventId'] for f in facts if f['sport']==s}) for s in games},'resolvedIdentities':sum(f.get('playerId') is not None for f in facts),'strictCompleteGames':0,'confirmedCompleteStartingLineups':0,'productionWrites':0,'factsInsertedIntoFrozenForecasts':0,'unknownIsHealthy':False,'primaryDocuments':documents,'rejectedFacts':errors,'NBAReportChecks':nba['reports'],'remaining':'NFL designations do not establish complete participation/starting lineups. CFB dated public pages lack recovered versioned publication timestamps. NBA reports list injuries, not complete rotations or future minutes.'};atomic(OUT/'evidence/coverage.json',coverage);return coverage
if __name__=='__main__':
    import hashlib
    path=OUT/'specs/evidence-r3.json'
    if '--register' in sys.argv:
        if path.exists():raise ValueError('Evidence registration already exists')
        files=[Path(__file__),ROOT/'modeling/integration_v22/io.py'];atomic(path,{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'boundedSourceScope':'Week5 NFL2023; first2 selected games per NBA window; three official CFB inventory pages','mutationOfForecasts':False});print('Registered bounded recovery')
    else:print(json.dumps(job('evidence-r3',run,cpu=240,wall=1200),indent=2))
