"""Preregistered conditional mean/exposure comparisons. No hosted/full-game work."""
import sys,json,gzip,pickle,hashlib,types
from pathlib import Path
from collections import defaultdict,Counter
from datetime import timedelta
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.runtime import job
from modeling.evidence_v21.protection import protected_ids
from modeling.evidence_v21.io import OUT,fetch
from modeling.evidence_v21.opportunities import LineupMinutes,FootballShares
from modeling.evidence_v21.basketball import game_exposures
from modeling.evidence_v21.rebounds import CourtRebounds
from modeling.evidence_v21.quality import record
from modeling.overnight_v20 import data
from modeling.overnight_v20.cohort import training_rows,point_fit,point_predict,point_grade,lineup,official_box
from modeling.overnight_v20.state import read,atomic
from modeling.accuracy_v20.projections import LeagueOpportunityModels
from modeling.accuracy_v20.benchmarks import OpponentAdjustedRolling
from modeling.accuracy_v20.outcomes import normalize_nba_final
from modeling.iterative_learning import freeze_json,digest
from modeling.accuracy_v20.quality import aware
from modeling.structural_v18.models import error_metrics
import pyarrow.parquet as pq

def unpack(path):return json.loads(gzip.decompress(path.read_bytes()))
def primary(s):return 'rebounds' if s=='NBA' else 'passingYards'
def comparison(rows,family):
 rs=[r for r in rows if family in r['predictions'] and 'rolling5' in r['predictions']];by=defaultdict(list)
 for r in rs:by[r['gameId']].append(abs(r['predictions'][family]-r['actual'])-abs(r['predictions']['rolling5']-r['actual']))
 if not rs:return None
 sums=np.asarray([[sum(v),len(v)] for g,v in sorted(by.items())]);rng=np.random.default_rng(21021);ix=rng.integers(0,len(sums),(2000,len(sums)));draw=sums[ix].sum(axis=1);return {'games':len(by),'observations':len(rs),'metrics':error_metrics([r['actual'] for r in rs],[r['predictions'][family] for r in rs]),'baseline':error_metrics([r['actual'] for r in rs],[r['predictions']['rolling5'] for r in rs]),'pairedMAEDelta':{'mean':float(sums[:,0].sum()/sums[:,1].sum()),'bootstrap95':np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist(),'unit':'game-clustered player-observation MAE','negativeIsBetter':True}}

def run():
 p=read(OUT/'protocol-final.json');frozen=OUT/'components';frozen.mkdir(exist_ok=True);packets={s:data.packets(s) for s in ['NFL','CFB','NBA']};reserved=protected_ids(p);source={s:data.archives(s) for s in ['NFL','CFB','NBA']};source['NBA']={g['id']:g for g in source['NBA'].values()};facts={'NFL':unpack(OUT/'evidence/NFL-primary-facts.json.gz'),'CFB':[],'NBA':unpack(OUT/'evidence/NBA-expanded.json.gz')['facts']};history={};exposure_cache={};exposure_errors=[]
 def public_fetch(url):
  b,r=fetch(url);return b,{**r,'sha256':r.get('sourceVersion')}
 verified_football_box=types.FunctionType(official_box.__code__,{**official_box.__globals__,'OUT':OUT,'fetch':public_fetch,'_NFL_MAP':None,'_SCHEDULE':None})
 for f in facts['NFL']:f.setdefault('status','unknown')
 for s,gs in packets.items():
  h=defaultdict(list)
  for g in gs:
   if g['id'] in reserved:continue
   for t in [g['home'],g['away']]:h[t].append(g)
  history[s]=h;packets[s]=[g for g in gs if g['id'] not in reserved]
 cs=['id','sequence_number','period_number','clock_display_value','type_text','text','athlete_id_1','athlete_id_2','athlete_id_3','game_id'];nbapbp=pq.read_table('/tmp/gridiron-nba-pbp-2025.parquet',columns=cs).to_pylist();pbp_by=defaultdict(list)
 for r in nbapbp:pbp_by['nba:espn:'+str(int(r['game_id']))].append(r)
 def exposures(ids):
  for gid in ids:
   if gid in exposure_cache:continue
   path=OUT/'court-exposures'/(gid.replace(':','_')+'.json.gz')
   if path.exists():exposure_cache[gid]=unpack(path);continue
   try:
    if gid not in pbp_by:raise ValueError('Historical PBP not covered')
    value=game_exposures(source['NBA'][gid],pbp_by[gid]);freeze_json(path,value);exposure_cache[gid]=value
   except ValueError as e:exposure_cache[gid]=None;exposure_errors.append({'eventId':gid,'reason':str(e)})
 report={'tier':'conditional_corrected_history_component_diagnostics','newCompleteGameSimulations':0,'productionPromotion':False,'strictQualifiedForecasts':0,'leagues':{},'moneylineAndTeamScoreMetrics':None,'probabilityReason':'Full-game input/evidence gates remain unresolved. Point means are not calibrated outcome probabilities. No invented historical prop thresholds.'};allgrades=defaultdict(list);quality=[];decisions=[]
 for cohort in range(4):
  for sport in ['NFL','CFB','NBA']:
   allgames=p['componentSelection'][sport];bounds=['2024-12-15','2024-12-22','2025-01-01','2025-01-12','2025-03-01'] if sport=='NFL' else ['2024-10-01','2024-10-08','2024-10-15','2024-10-22','2024-11-01'] if sport=='CFB' else ['2024-11-01','2024-11-08','2024-11-15','2024-11-22','2024-12-01'];games=[{**g,'cohort':cohort} for g in allgames if bounds[cohort]<=g['at'][:10]<bounds[cohort+1]]
   if not games:continue
   folder=frozen/(sport+'-'+str(cohort));folder.mkdir(exist_ok=True);fp=folder/'forecasts.json.gz';cutoff=(min(aware(g['at']) for g in games)-timedelta(hours=6)).isoformat();train,ids=training_rows(packets[sport],cutoff);head=None;court={};failures=[]
   if fp.exists():predictions=unpack(fp)['rows']
   else:
    baseline=point_fit(train);predictions,_=point_predict(baseline,games,packets[sport],{'facts':facts[sport]});hurdle=LeagueOpportunityModels(sport).fit(train,cutoff);opp={};grouped=defaultdict(list)
    for r in train:
     if r['player']!='__team__':grouped[r['stat']].append(r)
    for stat,rs in grouped.items():
     try:opp[stat]=OpponentAdjustedRolling().fit(rs)
     except ValueError:pass
    if sport=='NBA':
     past={g['id']:g for g in packets['NBA'] if aware(g['end'])+timedelta(hours=6)<aware(cutoff)}
     for r in train:
      if r['stat']=='minutes' and r['player']!='__team__':r['actualStarter']=past[r['gameId']]['teams'][r['team']]['players'].get(r['player'],{}).get('starter') is True
     try:head=LineupMinutes().fit(train,cutoff)
     except ValueError as e:failures.append({'stage':'minutes_fit','reason':str(e)})
     earlier=sorted([g for g in source['NBA'].values() if aware(g['at'])+timedelta(hours=6)<aware(cutoff) and g['id'] not in reserved],key=lambda g:g['at'])[-500:];exposures([g['id'] for g in earlier])
     for label,use in [('on_court_rebounds',True),('proxy_rebounds',False)]:
      try:court[label]=CourtRebounds(use).fit(earlier,exposure_cache,cutoff)
      except ValueError as e:failures.append({'stage':label,'reason':str(e)})
     ot=[int(round((sum(float(v.get('minutes') or 0) for v in g['players'])/2-240)/25)>0) for g in earlier];expected_minutes=240+25*(sum(ot)+.5)/(len(ot)+1)
    else:
     try:head=FootballShares(sport).fit(train,cutoff)
     except ValueError as e:failures.append({'stage':'football_share_fit','reason':str(e)})
    extra={};budgets=[]
    for g in games:
     full=[];lf=lineup(g,{'facts':facts[sport]})
     for team in [g['home'],g['away']]:full.extend(data.features_for(g,team,history[sport],sport))
     owners=defaultdict(set)
     for r in full:
      if r['player']!='__team__':owners[r['player']].add(r['team'])
     ambiguous={pid for pid,ts in owners.items() if len(ts)>1}
     quality.append(record(g,facts[sport],digest(p['sourceFiles']),consistency={'ownership':not ambiguous}))
     by=defaultdict(list)
     for r in full:
      if r['player']!='__team__' and not r['player'].split(':')[-1].startswith('-') and r['player'] not in ambiguous:by[r['stat']].append(r)
     for stat,rs in by.items():
      values={}
      if stat in hurdle.models:values['opportunity_hurdle']=hurdle.predict(stat,rs)
      if stat in opp:values['opponent_adjusted_rolling']=opp[stat].predict(rs)
      for i,r in enumerate(rs):
       k=(g['id'],r['team'],r['player'],stat);extra[k]={family:0. if r['player'] in lf[r['team']]['inactive'] else float(v[i]) for family,v in values.items()}
     for team in [g['home'],g['away']]:
      rs=[r for r in full if r['team']==team and r['player'] not in ambiguous];inactive=lf[team]['inactive']
      for pid in {r['player'] for r in rs if r['player']!='__team__'}:quality.append(record(g,facts[sport],digest(p['sourceFiles']),pid,team,{'ownership':True}))
      try:
       if sport=='NBA' and head:
        mr=[r for r in rs if r['stat']=='minutes' and r['player']!='__team__'];mins=head.predict_team(mr,inactive,expected_minutes);mp={r['player']:float(v) for r,v in zip(mr,mins)}
        for pid,v in mp.items():extra[(g['id'],team,pid,'minutes')]['lineup_state_minutes']=v
        own=[(source['NBA'][h['id']]['teams'][team],source['NBA'][h['id']]['teams'][str(source['NBA'][h['id']]['teams'][team]['opponent_team_id'])]) for h in history[sport][team] if aware(h['end'])+timedelta(hours=6)<aware(g['at'])][-5:];other=g['away'] if team==g['home'] else g['home'];against=[(source['NBA'][h['id']]['teams'][other],source['NBA'][h['id']]['teams'][str(source['NBA'][h['id']]['teams'][other]['opponent_team_id'])]) for h in history[sport][other] if aware(h['end'])+timedelta(hours=6)<aware(g['at'])][-5:]
        for name,m in court.items():
         estimates,detail=m.predict_team(mp,own,against)
         for pid,v in estimates.items():extra[(g['id'],team,pid,'rebounds')][name]=float(v)
         budgets.append({'gameId':g['id'],'team':team,'variant':name,'minutesSum':float(sum(mp.values())),'expectedTeamMinutes':expected_minutes,'reboundDetails':detail})
       elif sport!='NBA' and head:
        est,detail=head.predict_team(rs,inactive)
        for (pid,stat),v in est.items():extra.setdefault((g['id'],team,pid,stat),{})['team_budget_shares']=v
        budgets.append({'gameId':g['id'],'team':team,**detail})
      except (ValueError,KeyError) as e:failures.append({'gameId':g['id'],'team':team,'reason':str(e)})
    predictions=[{**r,'predictions':{**r['predictions'],**extra.get((r['gameId'],r['team'],r['player'],r['stat']),{})},'tier':'conditional_diagnostic','unconditionalPublicationSuppressed':True} for r in predictions if r['player']!='__team__'];freeze_json(fp,{'rows':predictions,'games':games,'fitCutoff':cutoff,'trainingGameIds':sorted(ids),'modelCodeSha256':read(OUT/'execution-r1.json'),'predictionsFrozenBeforeGrading':True,'historicalReplay':True,'budgets':budgets,'failures':failures,'wholeGameSimulationCount':0})
    with (folder/'models.pickle').open('xb') as f:pickle.dump({'baseline':baseline,'hurdle':hurdle,'opponent':opp,'head':head,'court':court},f)
   # Only now open current-event outcomes. They never select player inputs.
   boxes={}
   for g in games:
    try:
     if sport=='NBA':
      path=OUT/'outcomes'/(g['id'].replace(':','_')+'.json.gz')
      if path.exists():box=unpack(path)['box']
      else:
       b,receipt=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+g['id'].split(':')[-1])
       if b is None:raise ValueError('Official final box unavailable')
       box=normalize_nba_final(json.loads(b),g['id'],g['home'],g['away']);freeze_json(path,{'box':box,'source':receipt,'forGradingOnly':True})
     else:box=verified_football_box(g,packets[sport])
     boxes[g['id']]=box
    except (ValueError,KeyError,TypeError) as e:failures.append({'gameId':g['id'],'stage':'official_grading','reason':str(e)})
   grades=point_grade(predictions,boxes,sport);freeze_json(folder/'grades.json.gz',grades);allgrades[sport].extend(grades);print(json.dumps({'stage':'component_cohort','sport':sport,'cohort':cohort,'games':len(games),'gradedGames':len({r['gameId'] for r in grades}),'rows':len(grades),'failures':len(failures)}),flush=True)
   atomic(folder/'receipt.json',{'games':len(games),'failures':failures,'fitCutoff':cutoff,'tier':'conditional_diagnostic','newCompleteGameSimulations':0})
 for sport,rows in allgrades.items():
  cats={stat:{family:comparison([r for r in rows if r['stat']==stat],family) for family in sorted({f for r in rows if r['stat']==stat for f in r['predictions']})} for stat in sorted({r['stat'] for r in rows})};report['leagues'][sport]={'gradedGames':len({r['gameId'] for r in rows}),'observations':len(rows),'primaryStatistic':primary(sport),'categories':cats,'windows':{str(c):{stat:{f:comparison([r for r in rows if r['cohort']==c and r['stat']==stat],f) for f in sorted({f for r in rows if r['cohort']==c and r['stat']==stat for f in r['predictions']})} for stat in cats} for c in range(4)}}
  for statistic in (['rebounds','minutes'] if sport=='NBA' else [primary(sport)]):
   for family,c in cats.get(statistic,{}).items():
    if family in ('rolling5','ridge','boosted','hierarchical','hybrid','opportunity_hurdle','opponent_adjusted_rolling') or not c:continue
    decisions.append({'sport':sport,'family':family,'primary':statistic,'result':c,'productionPromotion':False,'researchDecision':'not_qualified','reasons':['Conditional historical tier lacks complete original pregame evidence','Matched joint-game probability/calibration/interval validation not executed',*(['Primary improvement not established by paired interval'] if c['pairedMAEDelta']['bootstrap95'][1]>=0 else []),*(['Fewer than 200 independent games'] if c['games']<200 else [])]})
 report['decisions']=decisions;report['evidence']={'records':len(quality),'tierCounts':dict(Counter(q['tier'] for q in quality)),'completePregameGames':sum(q['playerId'] is None and q['tier']=='strict_pregame' for q in quality),'unknownNeverHealthy':True};report['onCourtReconstruction']={'completedGames':sum(v is not None for v in exposure_cache.values()),'fullyIdentifiedGames':sum(v is not None and v['complete'] for v in exposure_cache.values()),'failures':exposure_errors};freeze_json(OUT/'components/quality.json.gz',quality);atomic(OUT/'components/results.json',report);return {'gradedGames':{s:l['gradedGames'] for s,l in report['leagues'].items()},'playerStatObservations':sum(len(rs) for rs in allgrades.values()),'sourceTier':'conditional_diagnostic','strictQualifiedForecasts':report['evidence']['completePregameGames'],'newCompleteGameSimulations':0,'promotions':0}
if __name__=='__main__':print(json.dumps(job('statistical-components',run,cpu=1800,wall=2400),indent=2))
