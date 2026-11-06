"""Bounded new-cohort primary evidence recovery. Finals never qualify lineups."""
import sys,types,json,re,hashlib,importlib.util
from pathlib import Path
from collections import Counter
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.fullgame_v23.io import OUT,fetch
from modeling.fullgame_v23.runtime import job
from modeling.fullgame_v23.evidence import nba_rows
from modeling.overnight_v20 import sources
from modeling.overnight_v20.state import atomic,read
from modeling.iterative_learning import freeze_json
from modeling.accuracy_v20.quality import aware,assess
from modeling.evidence_v21.availability import nfl_article_statuses,NFL_HEADINGS
from modeling.evidence_v21.io import canonical_article
from modeling.evidence_v21.tiers import timestamped_fact
spec=importlib.util.spec_from_file_location('replay23',ROOT/'scripts/fullgame-v23.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
spec2=importlib.util.spec_from_file_location('visible22',ROOT/'scripts/recover-integration-v22.py');visible=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(visible)

def run():
    packets,_=runner.inputs()
    from modeling.overnight_v20.data import packets as projection_packets
    nba_meta={g['id']:g for g in projection_packets('NBA')};sample=[nba_meta[g] for g in runner.SELECTION['NBA']]
    def wrapped(url):
        b,r=fetch(url);return b,{**r,'sha256':r.get('sourceVersion',r.get('sha256'))}
    nba=types.FunctionType(sources.nba_evidence.__code__,{**sources.nba_evidence.__globals__,'fetch':wrapped,'nba_rows':nba_rows,'protocol':lambda:{'selection':{'NBA':sample}}})();facts=nba['facts'];documents=[];errors=[];banned=runner.protected()
    import pyarrow.parquet as pq
    weekly=pq.read_table(OUT/'sources/stats_player_week_2024.parquet').to_pylist()
    for gid in runner.SELECTION['NFL']:
        g=packets['NFL'][gid];week=int(gid.split('_')[1]);url=f'https://www.nfl.com/news/week-{week}-injury-report-for-2024-nfl-season';b,r=fetch(url)
        if not b:documents.append({'source':url,'status':r.get('httpStatus'),'blocker':'public_document_unavailable'});continue
        try:
            article=canonical_article(b,url);cutoff=(aware(g['at'])-timedelta(minutes=30)).isoformat();proof=timestamped_fact(url,r['sourceVersion'],article['datePublished'],r['retrievedAt'],cutoff,article.get('dateModified'));v=visible.Visible();v.feed(b.decode());team=None;rows=[]
            for line in ''.join(v.text).splitlines():
                line=line.strip()
                if line in NFL_HEADINGS:team=line
                if team and re.match(r'^(OUT|DOUBTFUL|QUESTIONABLE):',line):
                    try:rows+=nfl_article_statuses({'articleBody':team+'\n'+line})
                    except ValueError as e:errors.append({'source':url,'reason':str(e),'scope':'unresolved item retained as missing, other lines continue'})
            selected=[row for row in rows if row['teamId'] in (g['home'],g['away'])]
            for row in selected:
                ids={p['player_id'] for p in weekly if p['game_id'] not in banned and p['week']<week and p['team']==row['teamId'] and sources.norm(p.get('player_display_name'))==sources.norm(row['playerName'])};pid=next(iter(ids)) if len(ids)==1 else None
                facts.append({**proof,**row,'sport':'NFL','eventId':gid,'playerId':pid,'identityStatus':'earlier_team_history' if pid else 'unresolved','completeReport':False,'unknownIsHealthy':False})
            documents.append({'source':url,'publication':article['datePublished'],'modified':article.get('dateModified'),'sourceVersion':r['sourceVersion'],'facts':len(selected)})
        except (ValueError,KeyError) as e:errors.append({'source':url,'reason':str(e)})
    coverage=[]
    for sport,ids in runner.SELECTION.items():
        for gid in ids:
            g=packets[sport][gid];cutoff=(aware(g['at'])-timedelta(minutes=30)).isoformat();fs=[f for f in facts if f['sport']==sport and f['eventId']==gid]
            # A report with some injured names is never a full starting five,
            # active roster, participation forecast or uncertainty model.
            quality=assess(sport,gid,cutoff,{},model_uncertainty=None)
            coverage.append({'sport':sport,'gameId':gid,'cutoff':cutoff,'factsRecovered':len(fs),'resolvedPlayerFacts':sum(bool(f.get('playerId')) for f in fs),'completeStartingLineup':False,'completeAvailabilityEvidence':False,'quality':quality,'strictlyQualified':False,'mechanicsCertificate':'only 3/4/4 independent books/boxes tested; unchanged minimum is 12 model-bound games','existingHurdleProjectionIsNotJointDistribution':True,'conditionalFactsAvailable':bool(fs)})
    result={'facts':facts,'documents':documents,'errors':errors,'NBAReportChecks':nba['reports'],'NBAUnmapped':nba['unmapped'],'coverage':coverage,'strictEligibleGames':0,'financialOrProductionWrites':0,'unknownIsHealthy':False,'CFBBlocker':'No timestamp-verified complete pregame injury/lineup/participation evidence for selected 2024 non-SEC/Minnesota games or GT-Georgia was recovered; final gamebooks cannot supply it.'}
    freeze_json(OUT/'evidence/recovery-r4.json.gz',result);atomic(OUT/'evidence/coverage-r4.json',{k:v for k,v in result.items() if k!='facts'}|{'factsByLeague':dict(Counter(f['sport'] for f in facts))});return {'factsByLeague':dict(Counter(f['sport'] for f in facts)),'strictEligibleGames':0,'documents':len(documents),'NBAReports':len(nba['reports'])}
if __name__=='__main__':
    if '--register' in sys.argv:
        freeze_json(OUT/'specs/evidence-r4.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'modeling/fullgame_v23/io.py',ROOT/'modeling/fullgame_v23/evidence.py',ROOT/'scripts/fullgame-v23.py']},'sourceBudget':'NFL weeks 2/3/5 2024 and four NBA report dates, two reports/date; no access bypass','protectedCohortsReadForTuning':False})
    else:print(json.dumps(job('evidence-r4',run,cpu=240,wall=900),indent=2))
