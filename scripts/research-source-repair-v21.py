"""New-season, frozen-hypothesis test of CFB accounting and NBA minutes.

Only earlier completed appearances enter forecast features. Repaired boxes are
research copies; V16/V20 archives, production and financial data stay intact.
"""
import sys,json,gzip,pickle,types,random,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from datetime import timedelta
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.io import OUT,fetch
from modeling.evidence_v21.runtime import job
from modeling.evidence_v21.football_boxes import repaired_packet,completion_evidence
from modeling.evidence_v21.opportunities import LineupMinutes
from modeling.evidence_v21.protection import protected_ids,assert_unexposed
from modeling.overnight_v20 import data
from modeling.overnight_v20.cohort import training_rows,point_grade,official_box
from modeling.overnight_v20.state import read,atomic
from modeling.accuracy_v20.projections import LeagueOpportunityModels
from modeling.accuracy_v20.quality import aware
from modeling.accuracy_v20.outcomes import normalize_nba_final
from modeling.football_data_v16 import load_football
from modeling.nba_v15 import load_nba
from modeling.iterative_learning import freeze_json
import pyarrow.parquet as pq
import pyarrow as pa
import pyarrow.compute as pc
def unpack(p):return json.loads(gzip.decompress(p.read_bytes()))
def selection(campaign='source-repair'):
 p=read(OUT/'protocol-final.json');excluded=set(p['excludedEvaluationIds'])|set(p['additionalSourceExposureExclusions']);sealed={g['id'] for gs in p['sealedFinal'].values() for g in gs};excluded|=sealed
 for group in ['selection','componentSelection']:
  excluded|={g['id'] for gs in p[group].values() for g in gs}
 for protocol in ['independent-protocol.json','season-confirmation-protocol.json',*(['source-repair-protocol.json'] if campaign=='clean-confirmation' else [])]:excluded|={g['id'] for gs in read(OUT/protocol)['selection'].values() for g in gs}
 excluded|=protected_ids(p)
 result={};cfb={};cols=['game_id','homeTeamId','awayTeamId','season','wallclock']
 for r in pq.read_table('/tmp/gridiron-cfb-public-pbp-2026.parquet',columns=cols).to_pylist():
  if not r['wallclock']:continue
  at=aware(r['wallclock']).isoformat();gid='cfb:espn:'+str(int(r['game_id']));h='cfb:espn:'+str(int(r['homeTeamId']));a='cfb:espn:'+str(int(r['awayTeamId']))
  # Previously discussed Ohio State–USC is diagnostic/development exposure.
  if {h,a}=={'cfb:espn:194','cfb:espn:30'}:excluded.add(gid)
  if not '2026-10-01'<=at[:10]<'2026-11-01':continue
  g=cfb.setdefault(gid,{'id':gid,'at':at,'home':h,'away':a,'season':int(r['season']),'sport':'CFB'});g['at']=min(g['at'],at)
 nba={}
 for r in pq.read_table(OUT/'external/NBA-team_box_2027.parquet',columns=['game_id','team_id','opponent_team_id','game_date_time','season','team_home_away']).to_pylist():
  at=aware(str(r['game_date_time'])).isoformat()
  if not ('2026-10-28' if campaign=='clean-confirmation' else '2026-10-30')<=at[:10]<'2026-11-05':continue
  gid='nba:espn:'+str(int(r['game_id']));g=nba.setdefault(gid,{'id':gid,'at':at,'season':int(r['season']),'sport':'NBA'});g[r['team_home_away']]=str(int(r['team_id']))
 for s,gs in [('CFB',cfb),('NBA',nba)]:
  eligible=sorted([g for g in gs.values() if g['id'] not in excluded and 'home' in g and 'away' in g],key=lambda g:g['id']);random.Random(21321).shuffle(eligible);result[s]=sorted(eligible[:40],key=lambda g:g['at'])
 if campaign=='clean-confirmation':
  nfl={}
  for r in pq.read_table(OUT/'external/nfl-2026.parquet',columns=['game_id','home_team','away_team','season','time_of_day','game_date']).to_pylist():
   if not r['time_of_day'] or not '2026-10-01'<=r['game_date']<'2026-11-05':continue
   g=nfl.setdefault(r['game_id'],{'id':r['game_id'],'home':r['home_team'],'away':r['away_team'],'season':int(r['season']),'sport':'NFL','at':r['time_of_day']});g['at']=min(g['at'],r['time_of_day'])
  values=sorted([g for g in nfl.values() if g['id'] not in excluded],key=lambda g:g['id']);random.Random(21321).shuffle(values);result['NFL']=sorted(values[:40],key=lambda g:g['at'])
 versions={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('/tmp/gridiron-cfb-public-pbp-2026.parquet'),*sorted((OUT/'external').glob('CFB-*.parquet')),*sorted((OUT/'external').glob('NBA-*.parquet'))]}
 if campaign=='clean-confirmation':versions[str(OUT/'external/nfl-2026.parquet')]=hashlib.sha256((OUT/'external/nfl-2026.parquet').read_bytes()).hexdigest()
 return {'id':campaign,'selection':result,'sourceVersions':versions,'sealedIds':sorted(sealed),'protectedTrainingIds':sorted(protected_ids(p)),'excludedIdsSha256':hashlib.sha256(json.dumps(sorted(excluded)).encode()).hexdigest(),'seed':21321,'hypotheses':{'CFB':'Anonymous PBP passers share a TEAM ID across opponents, and known QB rows omit some incompletions. Use exact-ID final player/team boxes for strictly earlier statistical appearances; do not infer missing play participants. Compare the same hurdle estimator before/after input repair.','NBA':'Confirm unchanged starter-state and hurdle minutes models on a genuinely new NBA season.','NFL':'Confirm unchanged hurdle opportunity model on new 2026 games, with both protected cohorts excluded from training.'},'primaryStatistics':{'CFB':['passingAttempts','passingYards'],'NBA':['minutes','rebounds'],'NFL':['passingYards']},'parameters':'Unchanged existing hurdle regularization and starter-state parameters; no calibration or post-selection hyperparameter tuning.','tier':'conditional_corrected_history_component','strictPregamePublicationVerified':False,'promotionAllowed':False,'fullGameSimulations':0,'sealedFinalAccessAllowed':False}
def run():
 p=read(OUT/(CAMPAIGN+'-protocol.json'));sealed=protected_ids(p);folder=OUT/CAMPAIGN;folder.mkdir(exist_ok=True)
 for path,sha in p['sourceVersions'].items():
  if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen research source changed: '+path)
 rawcfb=data.packets('CFB');npth=OUT/'source-repair/CFB-2026-normalized.pickle'
 if npth.exists():new=pickle.loads(npth.read_bytes())
 else:
  new=load_football('/tmp/gridiron-cfb-public-pbp-2026.parquet','CFB')
  with npth.open('xb') as f:pickle.dump(new,f)
 constructor=types.FunctionType(data.packets.__code__,{**data.packets.__globals__,'archives':lambda s:new});rawcfb=sorted([g for g in rawcfb+constructor('CFB') if g['id'] not in sealed and g['at']<'2026-11-05'],key=lambda g:g['at']);pr=defaultdict(list);tr=defaultdict(list)
 # Partition by exact IDs before any individual game normalization; sealed
 # outcomes are excluded before row materialization.
 for year in [2024,2025,2026]:
  for name,target in [('player',pr),('team',tr)]:
   table=pq.read_table(OUT/'external'/('CFB-'+name+'_box_'+str(year)+'.parquet'));hidden=[int(g.split(':')[-1]) for g in sealed if g.startswith('cfb:espn:')];table=table.filter(pc.invert(pc.is_in(table['game_id'],value_set=pa.array(hidden,type=table['game_id'].type))))
   for r in table.to_pylist():
    gid='cfb:espn:'+str(int(r['game_id']))
    if gid not in sealed:target[gid].append(r)
 repaired=[];failures=[];byraw={g['id']:g for g in rawcfb}
 for g in rawcfb:
  try:repaired.append(repaired_packet(g,pr[g['id']],tr[g['id']]))
  except (ValueError,KeyError,TypeError) as e:failures.append({'eventId':g['id'],'reason':str(e)})
 valid={g['id'] for g in repaired};matched=[g for g in rawcfb if g['id'] in valid]
 nba_new=load_nba(OUT/'external/NBA-player_box_2027.parquet',OUT/'external/NBA-team_box_2027.parquet');nba_constructor=types.FunctionType(data.packets.__code__,{**data.packets.__globals__,'archives':lambda s:nba_new});nba_all=sorted([g for g in data.packets('NBA')+nba_constructor('NBA') if g['id'] not in sealed and g['at']<'2026-11-05'],key=lambda g:g['at']);all_packets={'CFB':{'raw':matched,'box':repaired},'NBA':{'raw':nba_all}}
 if 'NFL' in p['selection']:
  nf=pickle.loads((OUT/'independent/NFL-2026-normalized.pickle').read_bytes());nc=types.FunctionType(data.packets.__code__,{**data.packets.__globals__,'archives':lambda s:nf});all_packets['NFL']={'raw':sorted([g for g in data.packets('NFL')+nc('NFL') if g['id'] not in sealed],key=lambda g:g['at'])}
 diagnostic_rows=pq.read_table('/tmp/gridiron-cfb-public-pbp-2024.parquet',columns=['pass_attempt','passer_player_id']).to_pylist();negative=sum(r['pass_attempt'] and (r['passer_player_id'] or 0)<0 for r in diagnostic_rows);book_checks=[];repaired_map={g['id']:g for g in repaired}
 # Independent gamebook counting fixtures, not score-based model targets.
 for gid,expected in [('cfb:espn:401635556',{'cfb:espn:256':73,'cfb:espn:153':79}),('cfb:espn:401643793',{'cfb:espn:2050':71,'cfb:espn:256':63}),('cfb:espn:401628497',{'cfb:espn:135':66,'cfb:espn:130':61})]:
  g=repaired_map[gid];got={t:g['teams'][t]['totals']['plays'] for t in expected}
  if got!=expected:raise ValueError('Independent printed offensive-play accounting fixture failed: '+gid)
  book_checks.append({'eventId':gid,'expected':expected,'actual':got,'passed':True,'sourceManifest':'artifacts/overnight-v21/gamebooks/manifest.json'})
 findings={'repairedHistoricalGames':len(repaired),'rejectedHistoricalGames':len(failures),'rejections':dict(Counter(x['reason'] for x in failures)),'negativePasserRows':negative,'negativePasserRowSource':'2024 public PBP, measured from raw flags','independentGamebookChecks':book_checks,'sources':p['sourceVersions'],'originalArchivesChanged':False,'targetsAndDropbacksStillUnverified':True};atomic(folder/'input-coverage.json',findings);result={'tier':p['tier'],'leagues':{},'promotions':0,'fullGameSimulations':0,'strictQualifiedForecasts':0,'probabilityMetrics':None}
 def public_fetch(url):
  b,r=fetch(url);return b,{**r,'sha256':r.get('sourceVersion')}
 official=types.FunctionType(official_box.__code__,{**official_box.__globals__,'OUT':OUT,'fetch':public_fetch,'_NFL_MAP':None,'_SCHEDULE':None})
 for sport in [s for s in ['CFB','NBA','NFL'] if s in p['selection']]:
  games=[{**g,'cohort':5} for g in p['selection'][sport]]
  if not games:continue
  sf=folder/sport;sf.mkdir(exist_ok=True);cutoff=(min(aware(g['at']) for g in games)-timedelta(hours=6)).isoformat();fp=sf/'forecasts.json.gz';pred=[];models={};reasons=[]
  if fp.exists():pred=unpack(fp)['rows']
  else:
   extra={}
   for variant,packets in all_packets[sport].items():
    train,ids=training_rows(packets,cutoff);assert_unexposed(ids,sealed);m=LeagueOpportunityModels(sport).fit(train,cutoff);head=None
    if sport=='NBA':
     past={g['id']:g for g in packets if aware(g['end'])+timedelta(hours=6)<aware(cutoff)}
     for r in train:
      if r['stat']=='minutes' and r['player']!='__team__':r['actualStarter']=past[r['gameId']]['teams'][r['team']]['players'].get(r['player'],{}).get('starter') is True
     head=LineupMinutes().fit(train,cutoff)
    models[variant]={'hurdle':m,'minutes':head,'trainingIds':sorted(ids)};hist=defaultdict(list)
    for g in packets:
     for t in [g['home'],g['away']]:hist[t].append(g)
    for g in games:
     for t in [g['home'],g['away']]:
      frame=[r for r in data.features_for(g,t,hist,sport) if r['player']!='__team__' and not r['player'].split(':')[-1].startswith('-')];by=defaultdict(list)
      for r in frame:by[r['stat']].append(r)
      if not frame:reasons.append({'eventId':g['id'],'team':t,'variant':variant,'reason':'Three earlier eligible team/opponent appearances unavailable'})
      for stat,rs in by.items():
       if stat not in m.models:continue
       values=m.predict(stat,rs)
       for r,v in zip(rs,values):
        key=(g['id'],t,r['player'],stat);record=extra.setdefault(key,{'gameId':g['id'],'team':t,'player':r['player'],'stat':stat,'role':r['role'],'cohort':5,'season':g['season'],'featureCutoff':r['featureCutoff'],'predictions':{}});record['predictions'][variant+'_hurdle']=float(v);record['predictions'][variant+'_rolling5']=r['baseline']
      if sport=='NBA' and 'minutes' in by:
       try:
        values=head.predict_team(by['minutes'],expected_team_minutes=240.)
        for r,v in zip(by['minutes'],values):extra[(g['id'],t,r['player'],'minutes')]['predictions']['lineup_state_minutes']=float(v)
       except ValueError as e:reasons.append({'eventId':g['id'],'team':t,'reason':str(e)})
   pred=list(extra.values());freeze_json(fp,{'rows':pred,'fitCutoff':cutoff,'games':games,'hypothesis':p['hypotheses'][sport],'forecastsFrozenBeforeGrading':True,'missingFrames':reasons,'tier':p['tier'],'newFullGameSimulations':0,'injuryAndLineupStillUnknown':True})
   with (sf/'models.pickle').open('xb') as f:pickle.dump(models,f)
   if sport=='CFB':freeze_json(sf/'earlier-completion-counts.json.gz',completion_evidence(repaired,cutoff))
  boxes={};pending=[]
  for g in games:
   try:
    if sport in ('CFB','NFL'):box=official(g,[])
    else:
     path=sf/(g['id'].replace(':','_')+'-outcome.json.gz')
     if path.exists():box=unpack(path)['box']
     else:
      body,r=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+g['id'].split(':')[-1])
      if body is None:raise ValueError('Official outcome unavailable')
      box=normalize_nba_final(json.loads(body),g['id'],g['home'],g['away']);freeze_json(path,{'box':box,'source':r,'forGradingOnly':True})
    boxes[g['id']]=box
   except (ValueError,KeyError,TypeError) as e:pending.append({'eventId':g['id'],'reason':str(e)})
  grades=point_grade(pred,boxes,sport);freeze_json(sf/'grades.json.gz',grades)
  from importlib.machinery import SourceFileLoader
  metrics=SourceFileLoader('v21_paired_metrics',str(ROOT/'scripts/research-independent-v21.py')).load_module();cats={stat:{family:{ref:metrics.paired([r for r in grades if r['stat']==stat],family,ref) for ref in ['raw_rolling5','raw_hurdle'] if any(ref in r['predictions'] for r in grades if r['stat']==stat)} for family in sorted({f for r in grades if r['stat']==stat for f in r['predictions']})} for stat in sorted({r['stat'] for r in grades})};r={'selectedGames':len(games),'gradedGames':len({r['gameId'] for r in grades}),'observations':len(grades),'missingFrames':reasons,'pending':pending,'categories':cats,'untouchedFinalTest':False,'strictEligibleGames':0,'candidateDecision':'No promotion: conditional corrected-history evidence only; full-game calibration/uncertainty/lineup checks unresolved'};atomic(sf/'results.json',r);result['leagues'][sport]=r;print(json.dumps({'stage':'source_repair_validation','sport':sport,'games':r['gradedGames'],'rows':len(grades),'pending':pending}),flush=True)
 atomic(folder/'results.json',result);return {'gradedGames':{s:r['gradedGames'] for s,r in result['leagues'].items()},'repairedHistoricalGames':len(repaired),'strictEligibleGames':0,'newCompleteGameSimulations':0,'productionWrites':0}
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--register',action='store_true');parser.add_argument('--campaign',choices=['source-repair','clean-confirmation'],default='source-repair');args=parser.parse_args();CAMPAIGN=args.campaign
 if args.register:
  p=OUT/(CAMPAIGN+'-protocol.json')
  if p.exists():raise SystemExit('Source-repair protocol is already frozen')
  atomic(p,selection(CAMPAIGN));print('Frozen new-season source-repair selection')
 else:print(json.dumps(job('source-repair-components',run,cpu=1200,wall=1800,revision='clean-confirmation-r1' if CAMPAIGN=='clean-confirmation' else 'source-repair-r1'),indent=2))
