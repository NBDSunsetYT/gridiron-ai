"""One preregistered, bounded V28 rotation experiment; not betting accuracy.

Uses earlier corrected history, not historical source editions. Historical
rosters are inferred only from earlier appearances. Unknown availability is
an explicit unweighted scenario. Target boxes are fetched after freezing each
prediction. No champion, protected cohort, or old forecast is changed.
"""
import sys,json,gzip,hashlib,runpy,time,resource,re
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.completion.data import packets,enrich_packets
from modeling.dynamic_v24.completion.additional_data import recent_nba_packets
from modeling.dynamic_v24.stat_data import excluded_validation
from modeling.integration_v22.datasets import protected
from modeling.fullgame_v23.rotation import MinutesPrior,draw_minutes,lineup_tape,VERSION
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import digest
from modeling.accuracy_v20.quality import aware
from modeling.accuracy_v25.joint_session import bounded_call
CONFIRM='--confirmation' in sys.argv
OUT=ROOT/('artifacts/forecast-certification-v28/nba-rotation-r2' if CONFIRM else 'artifacts/forecast-certification-v28/nba-rotation-r1')

def blocked():
    ids=protected()|set(excluded_validation())
    for p in (ROOT/'artifacts').glob('**/*protocol*.json'):
        ids.update(re.findall(r'nba:espn:\d+',p.read_text(errors='replace')))
    for p in (ROOT/'docs/research').glob('V2[67]*R*.json.gz'):
        raw=gzip.decompress(p.read_bytes()).decode();ids.update('nba:espn:'+v for v in re.findall(r'"eventId"\s*:\s*"(\d+)"',raw))
        data=json.loads(raw)
        for game in data.get('games',[]) if isinstance(data,dict) else []:
            if isinstance(game,dict) and game.get('sport')=='NBA':
                for values in game.get('inputGameIds',{}).values():ids.update('nba:espn:'+str(v) for v in values)
    return ids

def metrics(rows,field):
    e=np.array([r[field]-r['actual'] for r in rows]);return {'observations':len(rows),'MAE':float(np.mean(abs(e))),'RMSE':float(np.sqrt(np.mean(e**2))),'bias':float(np.mean(e))} if len(e) else None

def paired(rows):
    grouped=defaultdict(list)
    for r in rows:grouped[r['gameId']].append(abs(r['jointMean']-r['actual'])-abs(r['freshRolling']-r['actual']))
    x=np.array([np.mean(v) for v in grouped.values()]);rng=np.random.default_rng(280028)
    b=np.mean(rng.choice(x,(4000,len(x)),replace=True),axis=1)
    return {'games':len(x),'meanGameMAEDelta':float(np.mean(x)),'interval95':np.quantile(b,[.025,.975]).tolist(),'negativeFavorsCandidate':True} if len(x) else None

def run():
    start=time.monotonic();cpu=time.process_time();banned=blocked()
    candidates=[g for g in json.loads((OUT.parent/'schedule-candidates.json').read_text()) if g['final'] and g['id'] not in banned and ('2026-11-07T00:00Z'<=g['at']<'2026-11-08T00:00Z' if CONFIRM else g['at']<'2026-11-07T00:00Z')]
    candidates=sorted(candidates,key=lambda g:(aware(g['at']),g['id']))[:16]
    if not candidates:raise ValueError('No new chronological rotation cases')
    target_ids={g['id'] for g in candidates}
    # Never load the target box labels into the feature history.
    old=enrich_packets(packets('NBA'),'NBA');fresh,meta=recent_nba_packets(source_folder=OUT.parent/'fresh-nba',exclude=target_ids)
    history=sorted({g['id']:g for g in old+fresh if g['id'] not in protected()|target_ids}.values(),key=lambda g:(aware(g['at']),g['id']))
    prior=MinutesPrior().fit([g for g in history if aware(g['at'])<aware(candidates[0]['at'])],candidates[0]['at'])
    protocol={'version':VERSION,'selected':[g['id'] for g in candidates],'exclusionHash':digest(sorted(banned)),'sourceVersions':meta['sourceVersions'],'modelHash':prior.modelHash,'trainingCutoff':prior.cutoff,'seed':280028,'rotationDrawsPerTeam':512,'oneCandidateOnly':True,'confirmation':CONFIRM,'hypothesis':'Previously omitted zero-minute mass can reduce spreading minutes across bench players' if CONFIRM else 'Complete-roster empirical Bayes priors can repair omitted participants','strictPregame':False,'scope':'chronological conditional corrected-history rotation diagnostic','reference':'previous five observed player minutes, across teams; stale-bank June-history reference also shown','selectionBeforeTargetGrading':True,'availabilityScenario':'Sourced out excluded; other unknowns conditionally active, up to 15 by earlier minutes; no scenario weights','overtimePolicy':'Do not grade final OT minutes as regulation minutes','promotionRule':'No promotion; original historical publication and complete historical roster evidence absent','codeHashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'modeling/fullgame_v23/rotation.py',ROOT/'modeling/dynamic_v24/completion/additional_data.py']}}
    freeze_json(OUT/'protocol.json',protocol)
    source=runpy.run_path(str(ROOT/'scripts/v28-sources.py'));parser=runpy.run_path(str(ROOT/'scripts/v26-forecast.py'));reports=json.loads((OUT.parent/('historical-nba-injuries-r2.json' if CONFIRM else 'historical-nba-injuries.json')).read_text());results=[];errors=[]
    for game in candidates:
        cutoff=game['at'];past=[g for g in history if aware(g['at'])<aware(cutoff)];latest={};recent=defaultdict(list)
        for g in past:
            for tid,t in g['teams'].items():
                recent[tid].append(g)
                for pid,p in t['players'].items():latest[pid]=(g,tid,p)
        pred={};teams=[]
        for team in game['teams']:
            tid=team['id'];roster={}
            for g in recent[tid][-8:]:
                for pid,p in g['teams'][tid]['players'].items():
                    if latest[pid][1]==tid:roster[pid]={'name':p.get('name',pid),'teamId':tid}
            priors=prior.project(roster,past,cutoff);facts={}
            for report in reports:
                if not report.get('issuedAt') or aware(report['issuedAt'])>=aware(cutoff):continue
                for fact in report.get('rows',[]):
                    if fact.get('date')!=aware(cutoff).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date().isoformat() or parser['norm'](fact.get('team'))!=parser['norm'](team['name']) or not fact.get('name'):continue
                    matches=[pid for pid,p in roster.items() if parser['norm'](p['name'])==parser['norm'](fact['name'])]
                    if len(matches)==1:facts[matches[0]]={'status':fact['status'].lower(),'source':report['source'],'sourceVersion':report['sourceVersion'],'publishedAt':report['issuedAt'],'editionHistoricallyVerified':False}
            forced=[pid for pid in priors if facts.get(pid,{}).get('status') in ('available','active')]
            permitted=forced+[pid for pid in sorted(priors,key=lambda p:priors[p]['mean'],reverse=True) if pid not in forced and facts.get(pid,{}).get('status') not in ('out','inactive','suspended')][:max(0,15-len(forced))];decisions={pid:pid in permitted for pid in priors}
            try:r=draw_minutes(priors,facts,decisions,n=512,seed=280028,hurdle=CONFIRM)
            except ValueError as e:errors.append({'gameId':game['id'],'teamId':tid,'error':str(e)});continue
            for i,pid in enumerate(r['players']):
                values=[];stale=[]
                for g in past:
                    for t in g['teams'].values():
                        p=t['players'].get(pid)
                        if p and p['stats'].get('minutes') is not None:values.append(p['stats']['minutes'])
                for g in old:
                    if aware(g['at'])>=aware(cutoff):continue
                    for t in g['teams'].values():
                        p=t['players'].get(pid)
                        if p and p['stats'].get('minutes') is not None:stale.append(p['stats']['minutes'])
                d=r['draws'][:,i];pred[pid]={'teamId':tid,'name':roster[pid]['name'],'freshRolling':0. if CONFIRM and facts.get(pid,{}).get('status') in ('out','inactive','suspended') else float(np.mean(values[-5:])) if values else None,'staleRolling':float(np.mean(stale[-5:])) if stale else None,'hierarchicalMean':priors[pid]['mean'],'jointMean':float(np.mean(d)),'median':float(np.median(d)),'interval90':np.quantile(d,[.05,.95]).tolist(),'samples':d.tolist(),'availability':r['sourceAvailability'][pid],'conditionalActive':decisions[pid],'historyGames':priors[pid]['historyGames']}
            teams.append({'teamId':tid,'roster':len(roster),'priorMeanSum':sum(v['mean'] for v in priors.values()),'allBudgetsExact':bool(np.all(r['draws'].sum(axis=1)==240)),'maximumRhat':r['maximumRhat'],'samplerConverged':r['samplerConverged'],'sourcedStatuses':len(facts),'unknownAvailability':sum(pid not in facts for pid in priors),'unweightedScenarioDecisions':decisions,'sampledFullGames':0})
        snapshot={'gameId':game['id'],'eventAt':cutoff,'frozenAt':datetime.now(timezone.utc).isoformat(),'protocolHash':digest(protocol),'priorHistoryEnd':max(g['at'] for g in past),'inputGameIds':[g['id'] for g in past],'targetFinalInputs':False,'players':pred,'teams':teams}
        snapshot['sha256']=digest(snapshot);freeze_json(OUT/'frozen'/(game['id'].split(':')[-1]+'.json'),snapshot)
        body,receipt=source['fetch']('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+game['id'].split(':')[-1])
        if not body:errors.append({'gameId':game['id'],'error':'Final grading source unavailable'});continue
        final=json.loads(body);c=final['header']['competitions'][0]
        if str(final['header']['id'])!=game['id'].split(':')[-1] or c['status']['type']['completed'] is not True:raise ValueError('Final identity/status mismatch')
        overtime=int(c['status'].get('period',4))>4;actual={}
        for t in final.get('boxscore',{}).get('players',[]):
            tid=str(t['team']['id'])
            for group in t.get('statistics',[]):
                for p in group.get('athletes',[]):
                    stat=parser['parse_line'](group.get('keys',[]),p.get('stats',[]));value=stat.get('minutes')
                    if p.get('didNotPlay') is True:value=0.
                    if value is not None:actual[str(p['athlete']['id'])]={'minutes':value,'teamId':tid,'explicitDNP':p.get('didNotPlay') is True}
        rows=[]
        for pid,p in pred.items():
            a=actual.get(pid)
            if not a or a['teamId']!=p['teamId'] or p['freshRolling'] is None or overtime:continue
            x=np.array(p['samples']);y=a['minutes'];crps=float(np.mean(abs(x-y))-.5*np.mean(abs(x[:,None]-x[None,:])))
            rows.append({k:v for k,v in p.items() if k!='samples'}|{'gameId':game['id'],'playerId':pid,'actual':y,'covered90':p['interval90'][0]<=y<=p['interval90'][1],'CRPS':crps})
        missing=[{'playerId':pid,'minutes':a['minutes']} for pid,a in actual.items() if a['minutes']>0 and pid not in pred]
        case={'gameId':game['id'],'at':cutoff,'forecastSHA256':snapshot['sha256'],'outcomeSourceVersion':receipt['sourceVersion'],'overtime':overtime,'teams':teams,'rows':rows,'actualPlayers':len(actual),'predictedPlayers':len(pred),'activeActualPlayers':sum(a['minutes']>0 for a in actual.values()),'coveredActualPlayers':sum(a['minutes']>0 and pid in pred for pid,a in actual.items()),'missingParticipants':missing,'unmodeledActualMinutes':sum(x['minutes'] for x in missing),'ungradedAbsentFinalRows':len(set(pred)-set(actual))}
        freeze_json(OUT/'graded'/(game['id'].split(':')[-1]+'.json'),case);results.append(case)
        print(json.dumps({'gameId':game['id'],'graded':len(rows),'OT':overtime,'missingActualParticipants':len(missing),'minuteBudgetPass':all(t['allBudgetsExact'] for t in teams)}),flush=True)
    rows=[r for c in results for r in c['rows']];stale=[r for r in rows if r['staleRolling'] is not None];teams=[t for c in results for t in c['teams']]
    report={'protocol':protocol,'games':len(results),'regulationGradedGames':sum(bool(c['rows']) for c in results),'observations':len(rows),'freshRolling':metrics(rows,'freshRolling'),'unconstrainedHierarchical':metrics(rows,'hierarchicalMean'),'jointConditionalMinutes':metrics(rows,'jointMean'),'staleVersusFreshCommonPopulation':{'observations':len(stale),'stale':metrics(stale,'staleRolling'),'fresh':metrics(stale,'freshRolling'),'joint':metrics(stale,'jointMean')},'coverage90':float(np.mean([r['covered90'] for r in rows])) if rows else None,'CRPS':float(np.mean([r['CRPS'] for r in rows])) if rows else None,'pairedGameMAE':paired(rows),'windows':{date:{'games':sum(c['at'][:10]==date for c in results),'fresh':metrics([r for c in results if c['at'][:10]==date for r in c['rows']],'freshRolling'),'joint':metrics([r for c in results if c['at'][:10]==date for r in c['rows']],'jointMean')} for date in sorted({c['at'][:10] for c in results})},'rotationDraws':len(teams)*512,'exactTeamBudgets':sum(t['allBudgetsExact'] for t in teams),'teamScenarios':len(teams),'samplerConvergedTeams':sum(t['samplerConverged'] for t in teams),'missingActualParticipantCount':sum(len(c['missingParticipants']) for c in results),'unmodeledActualMinutes':sum(c['unmodeledActualMinutes'] for c in results),'sourceStatusFactsMatched':sum(t['sourcedStatuses'] for t in teams),'strictQualifiedFullGames':0,'mechanicallyCertifiedCompleteGames':0,'promoted':False,'decision':'Conditional minutes component only; reject full-game eligibility without complete sourced participants, converged scenario law, rebound/shot compatibility and historical point-in-time editions','errors':errors,'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    freeze_json(OUT/'results.json',report);print(json.dumps({k:report[k] for k in ('games','observations','freshRolling','jointConditionalMinutes','pairedGameMAE','samplerConvergedTeams','teamScenarios','sourceStatusFactsMatched','cpuSeconds','wallSeconds')}),flush=True)

if __name__=='__main__':
    with bounded_call(180,360):run()
