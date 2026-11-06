"""A second, preregistered conditional component batch on new game identities.

No sealed outcomes, hosted compute, production writes, fake full-game trials,
or repeatedly tuned final tests. Forecasts are durable before grading.
"""
import sys,json,gzip,pickle,hashlib,random,types
from pathlib import Path
from collections import defaultdict,Counter
from datetime import timedelta
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.io import OUT,fetch
from modeling.evidence_v21.runtime import job
from modeling.evidence_v21.protection import protected_ids
from modeling.evidence_v21.rates import HierarchicalRates,proportional_budget
from modeling.evidence_v21.opportunities import LineupMinutes
from modeling.overnight_v20 import data
from modeling.overnight_v20.cohort import training_rows,point_fit,point_predict,point_grade,official_box,lineup
from modeling.overnight_v20.state import read,atomic
from modeling.football_data_v16 import load_football
from modeling.accuracy_v20.projections import LeagueOpportunityModels
from modeling.accuracy_v20.outcomes import normalize_nba_final
from modeling.accuracy_v20.quality import aware
from modeling.structural_v18.models import OPPORTUNITY,error_metrics
from modeling.iterative_learning import freeze_json
import pyarrow.parquet as pq

def unpack(path):return json.loads(gzip.decompress(path.read_bytes()))
def source_metadata(campaign='independent'):
 p=read(OUT/'protocol-final.json');excluded=set(p['excludedEvaluationIds'])|set(p['additionalSourceExposureExclusions'])|{g['id'] for key in ['selection','componentSelection','sealedFinal'] for gs in p[key].values() for g in gs};result={}
 raw=pq.read_table(OUT/'external/nfl-2026.parquet',columns=['game_id','home_team','away_team','season','time_of_day','game_date']).to_pylist();gs={}
 for r in raw:
  if r['time_of_day'] and '2026-10-01'<=r['game_date']<'2026-11-01':
   v=gs.setdefault(r['game_id'],{'id':r['game_id'],'at':r['time_of_day'],'sport':'NFL','home':r['home_team'],'away':r['away_team'],'season':int(r['season'])});v['at']=min(v['at'],r['time_of_day'])
 if campaign=='season-confirmation':excluded|={g['id'] for vals in read(OUT/'independent-protocol.json')['selection'].values() for g in vals}
 for s in ['NFL','CFB','NBA']:
  start,end=(('2025-11-01','2025-12-01') if s=='CFB' else ('2025-12-01','2026-01-01')) if campaign=='season-confirmation' else (('2024-11-01','2024-12-01') if s=='CFB' else ('2024-12-01','2025-01-01'))
  eligible=([] if campaign=='season-confirmation' else list(gs.values())) if s=='NFL' else [{'id':g['id'],'at':g['at'],'home':g['home'],'away':g['away'],'sport':s,'season':g['season']} for g in data.packets(s) if start<=g['at'][:10]<end]
  eligible=sorted([g for g in eligible if g['id'] not in excluded],key=lambda g:g['id']);random.Random(21210).shuffle(eligible);result[s]=sorted(eligible[:40 if s=='NFL' else 80 if s=='CFB' else 100],key=lambda g:g['at'])
 return {'id':campaign,'seed':21210,'selection':result,'excludedIdsSha256':hashlib.sha256(json.dumps(sorted(excluded)).encode()).hexdigest(),'sealedIds':sorted(g['id'] for gs in p['sealedFinal'].values() for g in gs),'families':['rolling5','ridge','hierarchical','boosted','hybrid','opportunity_hurdle','exposure_shrunk_efficiency','proportional_hurdle_minutes','lineup_state_minutes'],'hypotheses':{'NFL_CFB':'Separate exposure-weighted, role-shrunk efficiencies from hurdle opportunity volumes, rather than allocating quarterback opportunities by raw historical count alone.','NBA':'Use participation-gated hurdle workloads with capped multiplicative team reconciliation; compare to both the unconstrained hurdle and starter-state model. Shrink rebound rates by exposure.'},'parameters':'Fixed training-only EB exposure variance ratio clipped [1,100], residual opponent Ridge100; hurdle unchanged. No tuning after grading.','tier':'conditional_corrected_history_component','promotionAllowed':False,'newCompleteGameSimulations':0,'sealedFinalGradingAllowed':False,'finalTestClaim':False,'sourceVersion':hashlib.sha256((OUT/'external/nfl-2026.parquet').read_bytes()).hexdigest(),'crossSeasonConfirmation':campaign=='season-confirmation','confirmationMeaning':'Locked additional season; no parameter changes after batch2. NFL already tested on independent 2026 games; do not repeat them.' if campaign=='season-confirmation' else None}

def paired(rows,family,reference):
 rr=[r for r in rows if family in r['predictions'] and reference in r['predictions']]
 if not rr:return None
 by=defaultdict(list)
 for r in rr:by[r['gameId']].append(abs(r['predictions'][family]-r['actual'])-abs(r['predictions'][reference]-r['actual']))
 sums=np.array([[sum(v),len(v)] for _,v in sorted(by.items())]);rng=np.random.default_rng(21210);draw=sums[rng.integers(0,len(sums),(2000,len(sums)))].sum(axis=1)
 return {'games':len(by),'observations':len(rr),'candidate':error_metrics([r['actual'] for r in rr],[r['predictions'][family] for r in rr]),'reference':error_metrics([r['actual'] for r in rr],[r['predictions'][reference] for r in rr]),'pairedMAEDelta':float(sums[:,0].sum()/sums[:,1].sum()),'bootstrap95':np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist(),'referenceFamily':reference,'unit':'game-clustered observation MAE'}

def run():
 protocol=read(OUT/(CAMPAIGN+'-protocol.json'));reserved=protected_ids(protocol);folder=OUT/CAMPAIGN;folder.mkdir(exist_ok=True);result={'tier':protocol['tier'],'leagues':{},'newCompleteGameSimulations':0,'promotions':0,'moneylineMetrics':None,'reason':'Conditional component tests; original pregame lineup/availability and joint full-game gates remain unresolved.'}
 nfl_path=OUT/'independent/NFL-2026-normalized.pickle'
 if nfl_path.exists():new=pickle.loads(nfl_path.read_bytes())
 else:
  new=load_football(OUT/'external/nfl-2026.parquet','NFL')
  with nfl_path.open('xb') as f:pickle.dump(new,f)
 # Reuse the unchanged packet constructor with a dependency-injected research
 # archive. The production/V20 archive and its function globals stay intact.
 pack_nfl=types.FunctionType(data.packets.__code__,{**data.packets.__globals__,'archives':lambda s:new})
 old_nfl=data.packets('NFL');all_packets={'NFL':sorted(old_nfl+pack_nfl('NFL'),key=lambda g:g['at']),'CFB':data.packets('CFB'),'NBA':data.packets('NBA')}
 for s in all_packets:all_packets[s]=[g for g in all_packets[s] if g['id'] not in reserved]
 def public_fetch(url):
  body,rec=fetch(url);return body,{**rec,'sha256':rec.get('sourceVersion')}
 official=types.FunctionType(official_box.__code__,{**official_box.__globals__,'OUT':OUT,'fetch':public_fetch,'_NFL_MAP':None,'_SCHEDULE':None})
 for s in ['CFB','NBA','NFL']:
  if not protocol['selection'][s]:continue
  sf=folder/s;sf.mkdir(exist_ok=True);games=[{**g,'cohort':4} for g in protocol['selection'][s]];packets=all_packets[s];cutoff=(min(aware(g['at']) for g in games)-timedelta(hours=6)).isoformat();fp=sf/'forecasts.json.gz';failures=[]
  if fp.exists():snapshot=unpack(fp);pred=snapshot['rows']
  else:
   train,ids=training_rows(packets,cutoff);baseline=point_fit(train);hurdle=LeagueOpportunityModels(s).fit(train,cutoff);rate=HierarchicalRates(s).fit(train,cutoff);head=None
   if s=='NBA':
    past={g['id']:g for g in packets if aware(g['end'])+timedelta(hours=6)<aware(cutoff)}
    for r in train:
     if r['stat']=='minutes' and r['player']!='__team__':r['actualStarter']=past[r['gameId']]['teams'][r['team']]['players'].get(r['player'],{}).get('starter') is True
    head=LineupMinutes().fit(train,cutoff)
   pred,_=point_predict(baseline,games,packets,{'facts':[]});hist=defaultdict(list)
   for g in packets:
    for t in [g['home'],g['away']]:hist[t].append(g)
   extra={};budgets=[];missing=[]
   for g in games:
    for t in [g['home'],g['away']]:
     frame=[r for r in data.features_for(g,t,hist,s) if r['player']!='__team__' and not r['player'].split(':')[-1].startswith('-')];groups=defaultdict(list)
     for r in frame:groups[r['stat']].append(r)
     if not frame:missing.append({'eventId':g['id'],'team':t,'reason':'Fewer than three eligible earlier team or opponent appearances / no prior-known participants'})
     estimated={stat:{r['player']:float(v) for r,v in zip(rs,hurdle.predict(stat,rs))} for stat,rs in groups.items() if stat in hurdle.models}
     for stat,vals in estimated.items():
      for pid,v in vals.items():extra[(g['id'],t,pid,stat)]={'opportunity_hurdle':v}
     if s=='NBA' and 'minutes' in groups:
      rs=groups['minutes'];raw=[estimated['minutes'][r['player']] for r in rs]
      try:
       # 240 regulation player-minutes. This component experiment does not
       # label the budget an overtime simulation or claim a complete game.
       kl=proportional_budget(raw,240,48);state=head.predict_team(rs,expected_team_minutes=240)
       for r,a,b in zip(rs,kl,state):extra[(g['id'],t,r['player'],'minutes')].update(proportional_hurdle_minutes=float(a),lineup_state_minutes=float(b))
       estimated['minutes']={r['player']:float(v) for r,v in zip(rs,kl)};budgets.append({'eventId':g['id'],'team':t,'regulationMinuteBudget':float(sum(kl)),'overtimeNotSimulated':True})
      except ValueError as e:failures.append({'eventId':g['id'],'team':t,'reason':str(e)})
     for stat,rs in groups.items():
      op=OPPORTUNITY.get(stat)
      if op not in estimated:continue
      known=[r for r in rs if (stat,r['role']) in rate.parameters and r['player'] in estimated[op]]
      if not known:continue
      values=rate.predict(known,[estimated[op][r['player']] for r in known])
      for r,v in zip(known,values):extra.setdefault((g['id'],t,r['player'],stat),{})['exposure_shrunk_efficiency']=float(v)
   pred=[{**r,'predictions':{**r['predictions'],**extra.get((r['gameId'],r['team'],r['player'],r['stat']),{})}} for r in pred if r['player']!='__team__'];snapshot={'rows':pred,'games':games,'fitCutoff':cutoff,'trainingIds':sorted(ids),'predictionsFrozenBeforeGrading':True,'tier':protocol['tier'],'availability':'unknown; no fabricated active or healthy labels','missingFrames':missing,'failures':failures,'budgets':budgets,'wholeGameSimulationCount':0};freeze_json(fp,snapshot)
   with (sf/'models.pickle').open('xb') as f:pickle.dump({'baseline':baseline,'hurdle':hurdle,'rates':rate,'minutes':head},f)
  boxes={}
  for g in games:
   try:
    if s=='NBA':
     path=sf/(g['id'].replace(':','_')+'-outcome.json.gz')
     if path.exists():box=unpack(path)['box']
     else:
      body,receipt=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+g['id'].split(':')[-1])
      if body is None:raise ValueError('Official final source unavailable')
      box=normalize_nba_final(json.loads(body),g['id'],g['home'],g['away']);freeze_json(path,{'box':box,'source':receipt,'forGradingOnly':True})
    elif s=='NFL':
     actual=new['games'][g['id']];box={'eventId':g['id'],'sport':s,'players':actual['players'],'scores':{g['home']:actual['actualHome'],g['away']:actual['actualAway']},'supportedStatisticsByTeam':{t:list(data.FOOTBALL) for t in [g['home'],g['away']]},'outcomesVerified':True,'outcomeSource':'Checksum-verified nflverse 2026 public PBP; statistics derived by existing accounting normalizer. Original publication unverified.','notForPregameFeatures':True}
    else:box=official(g,packets)
    boxes[g['id']]=box
   except (ValueError,KeyError,TypeError) as e:failures.append({'eventId':g['id'],'reason':str(e),'stage':'grading'})
  grades=point_grade(pred,boxes,s);freeze_json(sf/'grades.json.gz',grades);stats=sorted({r['stat'] for r in grades});r={'selectedGames':len(games),'forecastGames':len({r['gameId'] for r in pred}),'gradedGames':len({r['gameId'] for r in grades}),'observations':len(grades),'failures':failures,'missingFrames':snapshot.get('missingFrames',[]),'categories':{stat:{family:{ref:paired([r for r in grades if r['stat']==stat],family,ref) for ref in ['rolling5','opportunity_hurdle'] if any(ref in r['predictions'] for r in grades if r['stat']==stat)} for family in sorted({k for row in grades if row['stat']==stat for k in row['predictions']})} for stat in stats},'strictEligibleForecasts':0,'heldOutAfterHypothesisFreeze':True,'untouchedFinalTest':False};atomic(sf/'results.json',r);result['leagues'][s]=r;print(json.dumps({'stage':'independent_component_complete','sport':s,'games':r['gradedGames'],'rows':len(grades),'failures':failures}),flush=True)
 atomic(folder/'results.json',result);return {'gradedGames':{s:r['gradedGames'] for s,r in result['leagues'].items()},'strictEligibleGames':0,'newCompleteGameSimulations':0,'promotions':0}

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--register',action='store_true');parser.add_argument('--campaign',choices=['independent','season-confirmation'],default='independent');args=parser.parse_args();CAMPAIGN=args.campaign
 if args.register:
  path=OUT/(CAMPAIGN+'-protocol.json')
  if path.exists():raise SystemExit('Protocol already frozen; do not overwrite it')
  atomic(path,source_metadata(CAMPAIGN));print('Frozen metadata-only independent selection')
 else:print(json.dumps(job('independent-components',run,cpu=1200,wall=2400,revision='season-r3' if CAMPAIGN=='season-confirmation' else 'independent-r2'),indent=2))
