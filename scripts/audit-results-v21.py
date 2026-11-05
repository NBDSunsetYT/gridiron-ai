"""Read-only forecast diagnostics. Original models and grades stay immutable."""
import sys,json,gzip,pickle,types
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.io import OUT
from modeling.evidence_v21.rates import factor_attribution
from modeling.evidence_v21.quality import record
from modeling.evidence_v21.runtime import job
from modeling.overnight_v20 import data
from modeling.overnight_v20.state import read,atomic
from modeling.accuracy_v20.quality import aware
from modeling.iterative_learning import freeze_json,digest

def unpack(path):return json.loads(gzip.decompress(path.read_bytes()))
def audit():
 p=read(OUT/'protocol-final.json');sealed={g['id'] for gs in p['sealedFinal'].values() for g in gs};packets={s:[g for g in data.packets(s) if g['id'] not in sealed] for s in ['NFL','CFB','NBA']};hist={}
 new=pickle.loads((OUT/'independent/NFL-2026-normalized.pickle').read_bytes());constructor=types.FunctionType(data.packets.__code__,{**data.packets.__globals__,'archives':lambda s:new});packets['NFL']=sorted(packets['NFL']+constructor('NFL'),key=lambda g:g['at'])
 for s,gs in packets.items():
  h=defaultdict(list)
  for g in gs:
   for t in [g['home'],g['away']]:h[t].append(g)
  hist[s]=h
 findings={'tier':'conditional_component_diagnostics','causalAttributionClaim':False,'ungradedGames':[],'attribution':{},'referenceComparisons':{},'sourceLimits':[]};parts=defaultdict(list);quality=[];ambiguous=[]
 for folder in sorted((OUT/'components').glob('*-*')):
  fp=folder/'forecasts.json.gz'
  if not fp.exists():continue
  snap=unpack(fp);sport=folder.name.split('-')[0];grades=unpack(folder/'grades.json.gz');graded={r['gameId'] for r in grades};lookup={(r['gameId'],r['team'],r['player'],r['stat']):r for r in grades};budget={(r['gameId'],r['team']):r.get('teamBudgets',{}) for r in snap.get('budgets',[]) if 'teamBudgets' in r}
  for g in snap['games']:
   if g['id'] not in graded:
    detail=[]
    for t in [g['home'],g['away']]:
     own=[h for h in hist[sport][t] if aware(h['end']).timestamp()+21600<aware(g['at']).timestamp()];opp=g['away'] if t==g['home'] else g['home'];other=[h for h in hist[sport][opp] if aware(h['end']).timestamp()+21600<aware(g['at']).timestamp()];detail.append({'team':t,'earlierTeamAppearances':len(own),'earlierOpponentAppearances':len(other),'minimumRequired':3})
    findings['ungradedGames'].append({'eventId':g['id'],'sport':sport,'reason':'No pregame feature frame met the existing three-earlier-appearances requirement','coverage':detail,'forecastRows':sum(r['gameId']==g['id'] for r in snap['rows'])})
  for r in grades:
   stat=r['stat'];op='minutes' if sport=='NBA' else 'passingAttempts' if stat=='passingYards' else 'targets' if stat in ('receivingYards','receptions') else 'carries' if stat=='rushingYards' else None
   if not op:continue
   o=lookup.get((r['gameId'],r['team'],r['player'],op))
   if not o:continue
   family='opportunity_hurdle' if sport=='NBA' else 'team_budget_shares'
   if family not in r['predictions'] or family not in o['predictions']:continue
   yp=r['predictions'][family];opred=o['predictions'][family];y=r['actual'];oa=o['actual'];key=sport+':'+stat
   if min(opred,oa)<=0:
    parts[key].append({'eventId':r['gameId'],'playerId':r['player'],'status':'zero_observed_or_predicted_opportunity','absoluteError':abs(yp-y),'opportunityPrediction':opred,'actualOpportunity':oa});continue
   terms=factor_attribution([opred,yp/opred],[oa,y/oa]);parts[key].append({'eventId':r['gameId'],'playerId':r['player'],'status':'decomposed','signedError':yp-y,'opportunityError':terms[0],'efficiencyError':terms[1],'prediction':yp,'actual':y,'opportunityPrediction':opred,'actualOpportunity':oa,'meaning':'Exact symmetric product decomposition, not proof of causal attribution'})
 for key,rs in parts.items():
  ds=[r for r in rs if r['status']=='decomposed'];findings['attribution'][key]={'observations':len(rs),'decomposed':len(ds),'zeroOpportunityCases':len(rs)-len(ds),'meanAbsoluteOpportunityContribution':float(np.mean([abs(r['opportunityError']) for r in ds])) if ds else None,'meanAbsoluteEfficiencyContribution':float(np.mean([abs(r['efficiencyError']) for r in ds])) if ds else None,'opportunityDominantFraction':float(np.mean([abs(r['opportunityError'])>abs(r['efficiencyError']) for r in ds])) if ds else None,'separatePaceAndParticipationCausalAttribution':'Not identifiable from available historical pregame evidence. NBA rebound density versus on-court exposure requires current-game PBP outcome reconstruction, not guessed minutes proxies.'}
 # Correct per-game/player quality coverage remains inspectable after a partial
 # resume, independently of whether a forecast cohort was loaded from disk.
 for s in ['NFL','CFB','NBA']:
  facts=unpack(OUT/('evidence/NBA-expanded.json.gz'))['facts'] if s=='NBA' else unpack(OUT/'evidence/NFL-primary-facts.json.gz') if s=='NFL' else []
  upcoming=[(g,'batch1',facts) for g in p['componentSelection'][s]]+[(g,'batch2',[]) for g in read(OUT/'independent-protocol.json')['selection'][s]]
  for g,batch,game_facts in upcoming:
   owners=defaultdict(set)
   for t in [g['home'],g['away']]:
    for r in data.features_for(g,t,hist[s],s):
     if r['player']!='__team__':owners[r['player']].add(t)
   bad={pid for pid,ts in owners.items() if len(ts)>1};quality.append({**record(g,game_facts,digest(p['sourceFiles']),consistency={'ownership':not bad}),'batch':batch})
   if bad:ambiguous.append({'eventId':g['id'],'players':sorted(bad),'reason':'Earlier-roster participant appears in both candidate team frames; unconditional output blocked'})
   for pid,teams in owners.items():
    for t in teams:quality.append({**record(g,game_facts,digest(p['sourceFiles']),pid,t,{'ownership':pid not in bad}),'batch':batch})
 findings['quality']={'records':len(quality),'tierCounts':dict(Counter(q['tier'] for q in quality)),'strictGames':sum(q['playerId'] is None and q['tier']=='strict_pregame' for q in quality),'ambiguousOwners':ambiguous,'rebuiltFromImmutableSnapshots':True,'sourceFactsInsertedRetroactivelyIntoForecasts':False};findings['knownLimitations']=['Actual injury and starting-lineup effects cannot be identified causally from a missing pregame report.','Component means do not supply moneyline calibration, joint prediction intervals or full-game simulation accuracy.','An improvement against rolling averages is not necessarily an improvement against the existing hurdle comparator.','No sealed final-test outcomes opened; all candidate comparisons are exploratory conditional research.']
 from importlib.machinery import SourceFileLoader
 module=SourceFileLoader('independent_metrics',str(ROOT/'scripts/research-independent-v21.py')).load_module()
 for sport in ['NFL','CFB','NBA']:
  first=[]
  for f in sorted((OUT/'components').glob(sport+'-*/grades.json.gz')):first+=unpack(f)
  second=unpack(OUT/'independent'/sport/'grades.json.gz');stats=['minutes','rebounds'] if sport=='NBA' else ['passingYards','receivingYards','rushingYards']
  findings['referenceComparisons'][sport]={label:{stat:{f:module.paired([r for r in rr if r['stat']==stat],f,'opportunity_hurdle') for f in sorted({f for r in rr if r['stat']==stat for f in r['predictions']})} for stat in stats} for label,rr in [('batch1',first),('batch2',second)]}
 freeze_json(OUT/'diagnostics/factor-attribution.json.gz',dict(parts));freeze_json(OUT/'diagnostics/quality-reconstructed.json.gz',quality);atomic(OUT/'diagnostics/results.json',findings);return {'ungradedExplained':len(findings['ungradedGames']),'attributionCategories':len(parts),'strictGames':findings['quality']['strictGames'],'newCompleteGameSimulations':0}
if __name__=='__main__':print(json.dumps(job('diagnostic-audit',audit,cpu=240,wall=600,revision='audit-r1'),indent=2))
