"""Recover additional dated public facts, without rewriting graded forecasts."""
import sys,json,re
from pathlib import Path
from collections import defaultdict,Counter
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.io import OUT,fetch,canonical_article
from modeling.evidence_v21.availability import nfl_article_statuses
from modeling.evidence_v21.tiers import timestamped_fact
from modeling.evidence_v21.runtime import job
from modeling.overnight_v20 import data
from modeling.overnight_v20.state import read,atomic
from modeling.accuracy_v20.quality import aware
from modeling.iterative_learning import freeze_json
import pickle
import pyarrow.parquet as pq

def run():
 p=read(OUT/'independent-protocol.json');facts=[];sources=[];errors=[];nfl=data.archives('NFL');current=pickle.loads((OUT/'independent/NFL-2026-normalized.pickle').read_bytes());nfl_games={**nfl['games'],**current['games']};cfb=data.archives('CFB')['games'];crosswalk=ROOT/'artifacts/parallel-v19/sources/players.parquet';full_names=defaultdict(set)
 for r in pq.read_table(crosswalk,columns=['gsis_id','display_name']).to_pylist():
  if r['gsis_id'] and r['display_name']:full_names[r['gsis_id']].add(r['display_name'])
 def names(games,team,at):
  out=defaultdict(set)
  for g in games.values():
   if aware(g['lastObservedAt'])+timedelta(hours=6)>=aware(at):continue
   for pid,pl in g['players'].items():
    if pl['team']==team:
     # The PBP name is abbreviated; join full names through its exact GSIS ID,
     # and only for IDs already observed on this team before the cutoff.
     # No fuzzy surname match or future final roster is used.
     for name in {pl['name'],*full_names.get(pid,set())}:out[re.sub('[^a-z0-9]','',name.lower())].add(pid)
  return out
 for week in [6,7]:
  url=f'https://www.nfl.com/news/nfl-week-{week}-injury-report-2026-season';body,receipt=fetch(url)
  try:
   article=canonical_article(body,url);rows=nfl_article_statuses(article);count=0
   for g in p['selection']['NFL']:
    if g['id'].split('_')[1]!=f'{week:02}':continue
    cutoff=(aware(g['at'])-timedelta(minutes=30)).isoformat()
    try:proof=timestamped_fact(url,receipt['sourceVersion'],article['datePublished'],receipt['retrievedAt'],cutoff,article.get('dateModified'))
    except ValueError as e:errors.append({'eventId':g['id'],'source':url,'reason':str(e)});continue
    for team in [g['home'],g['away']]:
     registry=names(nfl_games,team,g['at'])
     for row in rows:
      if row['teamId']!=team:continue
      ids=registry.get(re.sub('[^a-z0-9]','',row['playerName'].lower()),set());pid=next(iter(ids)) if len(ids)==1 else None;facts.append({**proof,**row,'eventId':g['id'],'sport':'NFL','playerId':pid,'kind':'official_league_injury_designation','identityStatus':'resolved_earlier_team_history' if pid else 'unresolved_prior_identity','availability':'confirmed_out' if row['status']=='out' else 'uncertain','completeReport':False,'practiceParticipation':'not_in_this_summary','sourceRole':'primary_official_league','insertedIntoPreviousForecast':False});count+=1
   sources.append({'url':url,'datePublished':article['datePublished'],'dateModified':article.get('dateModified'),'explicitDesignationsParsed':len(rows),'selectedGameFacts':count,'sourceVersion':receipt['sourceVersion']})
  except (ValueError,KeyError,TypeError) as e:errors.append({'source':url,'reason':str(e)})
 url='https://www.statecollege.com/articles/penn-state-football/penn-state-qb-drew-allar-active-pair-of-starters-questionable-against-ohio-state/'
 body,receipt=fetch(url);gid='cfb:espn:401628539';g=next(g for g in p['selection']['CFB'] if g['id']==gid)
 try:
  article=canonical_article(body,url);proof=timestamped_fact(url,receipt['sourceVersion'],article['datePublished'],receipt['retrievedAt'],(aware(g['at'])-timedelta(minutes=30)).isoformat(),article.get('dateModified'))
  if 'Drew Allar Active' not in article['headline']:raise ValueError('Exact reported availability claim absent')
  registry=names(cfb,g['home'],g['at']);ids=registry.get('drewallar',set());pid=next(iter(ids)) if len(ids)==1 else None;facts.append({**proof,'sport':'CFB','eventId':gid,'teamId':g['home'],'playerId':pid,'playerName':'Drew Allar','status':'reported_active','availability':'reported_active_unrestricted_usage_not_confirmed','kind':'reported_game_day_availability','sourceRole':'dated_secondary_report_citing_Big_Ten','primaryConferenceReportRecovered':False,'completeReport':False,'insertedIntoPreviousForecast':False});sources.append({'url':url,'datePublished':article['datePublished'],'dateModified':article.get('dateModified'),'selectedGameFacts':1,'sourceVersion':receipt['sourceVersion']})
 except (ValueError,KeyError,TypeError) as e:errors.append({'source':url,'reason':str(e)})
 freeze_json(OUT/'evidence'/('availability-recovery-'+REVISION+'.json.gz'),{'facts':facts,'sources':sources,'errors':errors,'previousForecastsChanged':False});coverage={'facts':len(facts),'bySport':dict(Counter(f['sport'] for f in facts)),'mapped':sum(f['playerId'] is not None for f in facts),'events':len({f['eventId'] for f in facts}),'sources':sources,'errors':errors,'strictCompleteInputGames':0,'retroactivelyInsertedIntoPredictions':False,'remaining':'NFL summary designations do not supply complete practice/starting-lineup evidence. The CFB secondary report is not an independently recovered primary conference list. Unknown players remain unknown.'};atomic(OUT/'evidence'/('availability-recovery-'+REVISION+'-coverage.json'),coverage);return {'recoveredFacts':len(facts),'mappedIdentities':coverage['mapped'],'coveredEvents':coverage['events'],'strictCompleteGames':0,'originalForecastsChanged':False}
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--revision',default='availability-r4');args=parser.parse_args();REVISION=args.revision;print(json.dumps(job('additional-availability',run,cpu=180,wall=600,revision=REVISION),indent=2))
