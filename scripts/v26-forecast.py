"""Freeze actual pregame rolling references; never pretend they are joint games.

Only earlier verified-final boxes, captured rosters and explicit availability
facts enter these numbers. Uncertain roles remain conditional. Full-game and
probability outputs are withheld until their separate gates pass.
"""
import sys,json,gzip,hashlib,math,re
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import digest
from modeling.iterative_learning import freeze_json
from modeling.accuracy_v20.quality import aware

VERSION='rolling5-prospective-reference-26.0'


def norm(value):return re.sub('[^a-z0-9]','',str(value).lower())


def number(value):
    if value is None or str(value).strip() in ('','--','DNP','-'):return None
    try:
        if ':' in str(value):
            a,b=str(value).split(':');value=float(a)+float(b)/60
        result=float(value)
        return result if math.isfinite(result) else None
    except ValueError:return None


def parse_line(keys,values):
    result={}
    direct={'passingYards':'passingYards','passingTouchdowns':'passingTouchdowns','interceptions':'interceptions',
            'rushingAttempts':'carries','rushingYards':'rushingYards','rushingTouchdowns':'rushingTouchdowns',
            'receptions':'receptions','receivingYards':'receivingYards','receivingTouchdowns':'receivingTouchdowns',
            'receivingTargets':'targets','minutes':'minutes','points':'points','rebounds':'rebounds','assists':'assists',
            'steals':'steals','blocks':'blocks','turnovers':'turnovers','offensiveRebounds':'offensiveRebounds','defensiveRebounds':'defensiveRebounds'}
    for key,raw in zip(keys,values):
        if key in direct and (value:=number(raw)) is not None:result[direct[key]]=value
        elif key in ('completions/passingAttempts','completions-passingAttempts'):
            pair=re.fullmatch(r'(\d+)[/\-](\d+)',str(raw))
            if pair:result.update(passingCompletions=float(pair[1]),passingAttempts=float(pair[2]))
        elif key in ('fieldGoalsMade-fieldGoalsAttempted','threePointFieldGoalsMade-threePointFieldGoalsAttempted','freeThrowsMade-freeThrowsAttempted'):
            pair=re.fullmatch(r'(\d+)-(\d+)',str(raw))
            if pair:
                made,attempt={'fieldGoalsMade-fieldGoalsAttempted':('fieldGoalsMade','fieldGoalAttempts'),
                              'threePointFieldGoalsMade-threePointFieldGoalsAttempted':('threePointersMade','threePointAttempts'),
                              'freeThrowsMade-freeThrowsAttempted':('freeThrowsMade','freeThrowAttempts')}[key]
                result[made]=float(pair[1]);result[attempt]=float(pair[2])
    for stat,parts in [('pointsReboundsAssists',['points','rebounds','assists']),('pointsRebounds',['points','rebounds']),('pointsAssists',['points','assists']),('reboundsAssists',['rebounds','assists'])]:
        if all(k in result for k in parts):result[stat]=sum(result[k] for k in parts)
    return result


def body(receipt):
    raw=gzip.decompress((ROOT/receipt['object']).read_bytes())
    if hashlib.sha256(raw).hexdigest()!=receipt['sourceVersion']:raise ValueError('Source edition mismatch')
    return json.loads(raw)


def normalized(data,sport):
    comp=data['header']['competitions'][0]
    if comp['status']['type']['completed'] is not True:raise ValueError('Only completed historical sources can supply inputs')
    result={'eventId':str(data['header']['id']),'at':comp['date'],'teams':{}}
    for t in comp['competitors']:
        score=number(t.get('score'))
        if score is None:raise ValueError('Verified historical team score missing')
        result['teams'][str(t['team']['id'])]={'score':score,'players':{},'totals':{}}
    for team in data.get('boxscore',{}).get('players',[]):
        tid=str(team['team']['id'])
        if tid not in result['teams']:raise ValueError('Historical player-team identity mismatch')
        for group in team.get('statistics',[]):
            keys=group.get('keys',[])
            if not keys:continue
            totals=parse_line(keys,group.get('totals',[]));result['teams'][tid]['totals'].update(totals)
            for athlete in group.get('athletes',[]):
                pid=str(athlete['athlete']['id']);row=result['teams'][tid]['players'].setdefault(pid,{'name':athlete['athlete']['displayName'],'stats':{}})
                # "active" in a final ESPN box is not pregame health. Do not
                # filter positive minutes using that unrelated provider flag.
                row['stats'].update(parse_line(keys,athlete.get('stats',[])))
    return result


def roster_players(data):
    values=data.get('athletes',[]);rows=[]
    for value in values:rows.extend(value['items'] if 'items' in value else [value])
    return {str(p['id']):{'name':p.get('displayName',p.get('fullName')),'position':p.get('position',{}).get('abbreviation')} for p in rows}


def main():
    manifest=json.load(open(ROOT/'artifacts/accuracy-v26/prospective-inputs-r1.json'))
    histories={};rosters={};source_receipts=[]
    for r in manifest['sources']:
        if 'error' in r:continue
        receipt=r['receipt'];source_receipts.append(receipt)
        if r['kind']=='history':histories[(r['sport'],r['eventId'])]=normalized(body(receipt),r['sport'])
        else:
            d=body(receipt)
            if str(d['team']['id'])!=r['teamId'] or d['season']['year']!=r['season']:raise ValueError('Roster season/team mismatch')
            rosters[(r['sport'],r['teamId'])]=roster_players(d)
    out=ROOT/'artifacts/accuracy-v26/source-probes'
    nba=json.load(open(out/'nba-current-rows.json'))
    nfl=json.load(open(out/'nfl-article-facts.json'))
    captured=datetime.now(timezone.utc).isoformat();games=[]
    for target in manifest['targets']:
        if aware(captured)>=aware(target['eventAt']):raise ValueError('Prospective forecast missed kickoff: '+target['eventId'])
        for receipt in source_receipts:
            if aware(receipt['retrievedAt'])>=aware(captured):raise ValueError('Source was not available by frozen cutoff')
        sport=target['sport'];team_rows=[];all_players=[];history_refs={}
        for team in target['teams']:
            tid=team['teamId'];history=[histories[(sport,i)] for i in target['historyIds'][tid] if (sport,i) in histories]
            if any(aware(g['at'])>=aware(captured) or g['eventId']==target['eventId'] for g in history):raise ValueError('Future/current game input')
            history_refs[tid]=[g['eventId'] for g in history]
            rows=rosters[(sport,tid)];scores=[];allowed=[]
            for g in history:
                if tid not in g['teams']:raise ValueError('Requested team absent from historical game')
                scores.append(g['teams'][tid]['score']);allowed.append(next(t['score'] for i,t in g['teams'].items() if i!=tid))
            team_rows.append({'teamId':tid,'name':team['name'],'side':team['side'],'priorGames':len(history),
                              'pastMeanScored':float(np.mean(scores)) if scores else None,
                              'pastMeanAllowed':float(np.mean(allowed)) if allowed else None})
            for pid,p in rows.items():
                appearances=[(g['eventId'],g['at'],g['teams'][tid]['players'][pid]['stats']) for g in history if pid in g['teams'][tid]['players']]
                values=defaultdict(list)
                for gid,at,stats in appearances:
                    for stat,value in stats.items():values[stat].append((gid,at,value))
                if sport=='NBA':
                    if len(values.get('minutes',[]))<3 or np.mean([v[2] for v in values['minutes']])<10:continue
                    facts=[f for f in nba if f.get('name') and norm(f['team'])==norm(team['name']) and norm(f['name'])==norm(p['name']) and f['date']==aware(target['eventAt']).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date().isoformat()]
                    availability=facts[-1]['status'].lower() if facts else 'unknown_not_assumed_healthy'
                elif sport=='NFL':
                    facts=[f for f in nfl['facts'] if f['teamId']==team['abbreviation'] and norm(f['playerName'])==norm(p['name'])]
                    availability=facts[-1]['status'] if facts else 'unknown_not_assumed_healthy'
                else:availability='unknown_college_report_incomplete'
                relevant=['minutes','points','rebounds','assists','threePointersMade','fieldGoalAttempts','steals','blocks','turnovers','pointsReboundsAssists'] if sport=='NBA' else ['passingAttempts','passingCompletions','passingYards','passingTouchdowns','interceptions','carries','rushingYards','rushingTouchdowns','receptions','receivingYards','receivingTouchdowns','targets']
                forecasts={}
                for stat in relevant:
                    sample=values.get(stat,[])
                    if len(sample)<3:continue
                    x=[v[2] for v in sample]
                    forecasts[stat]={'mean':float(np.mean(x)),'median':float(np.median(x)),'observations':len(x),
                                      'historicalRange':[min(x),max(x)],'predictionInterval90':None,
                                      'intervalReason':'Five recent games do not establish validated 90% prediction coverage',
                                      'sourceGameIds':[v[0] for v in sample]}
                if not forecasts:continue
                if availability in ('out','doubtful'):
                    all_players.append({'playerId':pid,'teamId':tid,'name':p['name'],'availability':availability,'withheld':'Unavailable/uncertain status; no actual position or contract settlement invented','reference':None});continue
                all_players.append({'playerId':pid,'teamId':tid,'name':p['name'],'position':p['position'],'availability':availability,
                                    'reference':forecasts,'conditionalOn':'Player available and recent role continuing; lineup/restrictions unverified',
                                    'approvedRoute':None,'independentlyValidated':False})
        # Keep score diagnostics separate from a qualified full-game forecast.
        conditional_score={}
        for t in team_rows:
            other=next(x for x in team_rows if x['teamId']!=t['teamId'])
            conditional_score[t['teamId']]=(t['pastMeanScored']+other['pastMeanAllowed'])/2 if t['pastMeanScored'] is not None and other['pastMeanAllowed'] is not None else None
        game={'sport':sport,'eventId':target['eventId'],'eventAt':target['eventAt'],'forecastCapturedAt':captured,
              'modelVersion':VERSION,'teams':team_rows,'players':all_players,'inputGameIds':history_refs,
              'sourceTimestampsVerifiedBeforeCapture':True,'prospectiveCapture':True,
              'modeBConditionalReferences':{'score':conditional_score,'purpose':'Reference baseline, not a mechanically certified joint forecast'},
              'qualifiedFinalScore':None,'winProbabilities':None,'spreadProbabilities':None,'totalProbabilities':None,
              'modeAStatus':'withheld_missing_joint_mechanics_and_probability_validation',
              'modeCStatus':'marketless_no_verified_matching_prices_or_settlement','marketPrices':None,'clv':None,
              'simulationCount':0,'strictPregameQualified':False,'productionEligible':False,
              'blockers':['confirmed_or_supported_lineup_scenarios_missing','participant_restrictions_incomplete','model_bound_joint_mechanics_certificate_missing','independent_probability_validation_missing']+(['cfb_administrative_clock_and_pace_uncertified'] if sport=='CFB' else [])}
        game['predictionHash']=digest(game);games.append(game)
    result={'version':VERSION,'createdAt':captured,'methodCodeSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'sourceManifestSHA256':hashlib.sha256((ROOT/'artifacts/accuracy-v26/prospective-inputs-r1.json').read_bytes()).hexdigest(),
            'games':games,'historicalSourceCount':len(histories),'currentRosters':len(rosters),
            'sourceEditions':[{'url':r['url'],'sourceVersion':r['sourceVersion'],'capturedAt':r['retrievedAt']} for r in source_receipts],
            'newStrictFullGameForecasts':0,'newModelFits':0,'newMonteCarloGames':0,'productionPromotions':0,
            'accuracyMetrics':None,'accuracyReason':'Future outcomes unknown; conditional references awaiting prospective grading'}
    result['sha256']=digest(result)
    freeze_json(ROOT/'artifacts/accuracy-v26/prospective-reference-r1.json',result)
    freeze_json(ROOT/'docs/research/V26_PROSPECTIVE_R1.json.gz',result)
    print(json.dumps({'games':len(games),'playersWithNumericalReferences':sum(bool(p.get('reference')) for g in games for p in g['players']),
                      'knownUnavailableWithheld':sum(not p.get('reference') for g in games for p in g['players']),
                      'capturedAt':captured,'futureOutcomesRead':False,'newFullGameForecasts':0}),flush=True)


if __name__=='__main__':main()
