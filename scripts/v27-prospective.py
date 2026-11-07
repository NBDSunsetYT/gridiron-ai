"""Capture three NEW prospective numerical references using V26 parsers.

The six V26 target IDs are excluded both as targets and as historical inputs.
No target final source is read, no missing lineup or price is invented, and no
uncertified joint simulation is run. This is a bounded local research command.
"""
import sys,runpy,json,hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import digest
from modeling.accuracy_v20.quality import aware
OUT=ROOT/'artifacts/evidence-and-joint-v27'
recovery=runpy.run_path(str(ROOT/'scripts/v27-recover.py'));fetch=recovery['fetch']
old=runpy.run_path(str(ROOT/'scripts/v26-capture.py'));parsers=runpy.run_path(str(ROOT/'scripts/v26-forecast.py'))
BANNED=old['hidden_ids']()|{e for s,e in old['TARGETS']}
DATES={'NFL':'20261108','CFB':'20261114','NBA':'20261108'}


def payload(url):
    body,receipt=fetch(url)
    if body is None or not receipt.get('sourceVersion') or receipt.get('httpStatus')!=200:raise ValueError('Verified source unavailable: '+url)
    return json.loads(body),receipt


def run():
    targets=[];sources=[]
    for sport,date in DATES.items():
        league=old['LEAGUES'][sport];url='https://site.api.espn.com/apis/site/v2/sports/'+league+'/scoreboard?dates='+date
        board,receipt=payload(url);candidates=[g for g in board.get('events',[]) if str(g['id']) not in BANNED and g.get('status',{}).get('type',{}).get('state')=='pre' and aware(g['date'])>aware(receipt['retrievedAt'])]
        if not candidates:targets.append({'sport':sport,'withheld':'No unprotected future event in requested source schedule'});continue
        event=min(candidates,key=lambda g:(g['date'],g['id']));eid=str(event['id']);preview,pr=payload('https://site.api.espn.com/apis/site/v2/sports/'+league+'/summary?event='+eid);comp=preview['header']['competitions'][0]
        if str(preview['header']['id'])!=eid or comp['status']['type']['state']!='pre':raise ValueError('Target is not strictly pregame')
        histories={};rosters={};receipts=[receipt,pr];teams=[]
        for t in comp['competitors']:
            tid=str(t['team']['id']);teams.append({'teamId':tid,'name':t['team']['displayName'],'side':t['homeAway'],'abbreviation':t['team']['abbreviation']})
            prior=next((r['events'] for r in preview.get('lastFiveGames',[]) if str(r['team']['id'])==tid),[]);ids=[str(g['id']) for g in sorted(prior,key=lambda g:g['gameDate']) if str(g['id']) not in BANNED and aware(g['gameDate'])<aware(pr['retrievedAt'])][-5:];history=[]
            for gid in ids:
                # No V26 target outcome can enter V27 fitting or references.
                assert gid not in BANNED
                d,r=payload('https://site.api.espn.com/apis/site/v2/sports/'+league+'/summary?event='+gid)
                if str(d['header']['id'])!=gid or not d['header']['competitions'][0]['status']['type']['completed']:raise ValueError('Prior game is not verified final')
                history.append(parsers['normalized'](d,sport));receipts.append(r)
            histories[tid]=history
            rd,rr=payload('https://site.api.espn.com/apis/site/v2/sports/'+league+'/teams/'+tid+'/roster?season='+str(preview['header']['season']['year']))
            if str(rd['team']['id'])!=tid:raise ValueError('Roster team identity mismatch')
            rosters[tid]=parsers['roster_players'](rd);receipts.append(rr)
        cutoff=datetime.now(timezone.utc).isoformat()
        if aware(cutoff)>=aware(comp['date']) or any(aware(r['retrievedAt'])>=aware(cutoff) for r in receipts):raise ValueError('All sources must precede the actual forecast capture and event')
        players=[];score={};stats=['minutes','points','rebounds','assists','threePointersMade','fieldGoalAttempts','pointsReboundsAssists'] if sport=='NBA' else ['passingAttempts','passingYards','carries','rushingYards','receptions','receivingYards','passingTouchdowns','receivingTouchdowns','rushingTouchdowns']
        for t in teams:
            tid=t['teamId'];history=histories[tid];other=next(x['teamId'] for x in teams if x['teamId']!=tid);oh=histories[other]
            scored=[g['teams'][tid]['score'] for g in history];allowed=[next(v['score'] for key,v in g['teams'].items() if key!=other) for g in oh]
            score[tid]=(float(np.mean(scored))+float(np.mean(allowed)))/2 if scored and allowed else None
            for pid,p in rosters[tid].items():
                values={stat:[g['teams'][tid]['players'][pid]['stats'][stat] for g in history if pid in g['teams'][tid]['players'] and stat in g['teams'][tid]['players'][pid]['stats']] for stat in stats};point={k:{'mean':float(np.mean(v)),'median':float(np.median(v)),'observations':len(v),'predictionInterval90':None,'intervalReason':'No validated predictive interval from this small rolling reference'} for k,v in values.items() if len(v)>=3}
                if not point or sport=='NBA' and (not values['minutes'] or np.mean(values['minutes'])<10):continue
                last3=history[-3:];opportunity='minutes' if sport=='NBA' else 'passingAttempts' if p['position']=='QB' else 'carries' if p['position']=='RB' else 'targets'
                past=sum(g['teams'][tid]['players'].get(pid,{}).get('stats',{}).get(opportunity,0) for g in last3);den=sum(sum(x['stats'].get(opportunity,0) for x in g['teams'][tid]['players'].values()) for g in last3)
                players.append({'playerId':pid,'teamId':tid,'name':p['name'],'position':p['position'],'availability':'unknown_not_assumed_healthy','confirmedStarter':None,'reference':point,'priorRole':{'scope':'observed_prior_games_only_not_starting_confirmation','opportunity':opportunity,'last3Volume':past,'shareOfObservedTeamCredits':past/den if den else None,'sourceGameIds':[g['eventId'] for g in last3]},'conditionalOn':'Player available and earlier role continuing; injuries, starter status and restrictions incomplete'})
        game={'sport':sport,'eventId':eid,'eventAt':comp['date'],'forecastCapturedAt':cutoff,'teams':teams,'players':players,'modelVersion':'V26-rolling-reference-reused-V27','inputGameIds':{t:[g['eventId'] for g in h] for t,h in histories.items()},'modeBConditionalReferences':{'score':score,'purpose':'Simple reference, not joint simulator'},'simulationCount':0,'qualifiedFinalScore':None,'winProbabilities':None,'spreadProbabilities':None,'totalProbabilities':None,'marketPrices':None,'clv':None,'strictPregameQualified':False,'productionEligible':False,'blockers':['complete_availability_and_lineup_evidence_missing','participant_restrictions_unverified','model_bound_full_game_pace_certification_incomplete','independent_joint_probability_validation_missing']}
        game['predictionHash']=digest(game);targets.append(game);sources.extend(receipts)
    report={'version':'prospective-reference-27.0','createdAt':datetime.now(timezone.utc).isoformat(),'games':[g for g in targets if 'predictionHash' in g],'withheldTargets':[g for g in targets if 'predictionHash' not in g],'sourceEditions':[{'source':r['url'],'sourceVersion':r['sourceVersion'],'capturedAt':r['retrievedAt']} for r in sources],'newStrictFullGameForecasts':0,'newMonteCarloGames':0,'modelFits':0,'V26TargetOutcomesRead':False,'V26ForecastsChanged':False,'methodCodeSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    report['sha256']=digest(report);freeze_json(OUT/'prospective-r1.json',report);freeze_json(ROOT/'docs/research/V27_PROSPECTIVE_R1.json.gz',report)
    print(json.dumps({'games':[(g['sport'],g['eventId'],g['eventAt']) for g in report['games']],'players':sum(len(g['players']) for g in report['games']),'strictForecasts':0,'V26TargetsExcluded':True}))


if __name__=='__main__':run()
