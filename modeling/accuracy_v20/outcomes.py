"""Strict NBA final-box adapter, grading only; never pregame feature input."""
import math,re
from collections import defaultdict
MAP={'MIN':'minutes','PTS':'points','REB':'rebounds','AST':'assists','TO':'turnovers','STL':'steals','BLK':'blocks','OREB':'offensiveRebounds','DREB':'defensiveRebounds','PF':'fouls'}
VERSION='nba-supported-category-finalbox-20.1.1'
def scalar(v):
    if isinstance(v,str) and ':' in v:
        a,b=v.split(':');return float(a)+float(b)/60
    n=float(v)
    if not math.isfinite(n) or n<0:raise ValueError('Invalid official NBA count/minutes')
    return n
def pair(v):
    a,b=map(scalar,str(v).split('-'))
    if a>b:raise ValueError('Made shots exceed attempts')
    return a,b
def normalize_nba_final(payload,event_id,home,away):
    if str(payload['header']['id'])!=event_id.split(':')[-1]:raise ValueError('NBA final event identity mismatch')
    c=payload['header']['competitions'][0]
    if not c['status']['type'].get('completed'):raise ValueError('NBA outcome is not final')
    sides={x['homeAway']:x for x in c['competitors']}
    if str(sides['home']['team']['id'])!=home or str(sides['away']['team']['id'])!=away:raise ValueError('NBA final team identity mismatch')
    scores={home:scalar(sides['home']['score']),away:scalar(sides['away']['score'])};players={};support={};totals={};checks=[];unmapped=[];missing_minutes=[];source_totals={str(t['team']['id']):{s['name']:s['displayValue'] for s in t['statistics']} for t in payload['boxscore']['teams']}
    for t in payload['boxscore']['players']:
        team=str(t['team']['id'])
        if team not in scores or team in support:raise ValueError('NBA player-team box identity mismatch')
        available=None;aggregate=defaultdict(float);played=0;unsupported=set()
        for category in t['statistics']:
            labels=category['labels']
            if 'PTS' not in labels:continue
            category_supported={MAP[k] for k in labels if k in MAP}|({'fieldGoalAttempts','fieldGoalsMade'} if 'FG' in labels else set())|({'threePointAttempts','threePointersMade'} if '3PT' in labels else set())|({'freeThrowAttempts','freeThrowsMade'} if 'FT' in labels else set())
            for row in category['athletes']:
                if row.get('didNotPlay') is True:continue
                values=dict(zip(labels,row['stats']));p={}
                for k,v in values.items():
                    if k=='MIN' and v in ('--','',None):unsupported.add('minutes');missing_minutes.append({'team':team,'playerId':row['athlete'].get('id')});continue
                    if k in MAP:p[MAP[k]]=scalar(v)
                for k,made,attempts in [('FG','fieldGoalsMade','fieldGoalAttempts'),('3PT','threePointersMade','threePointAttempts'),('FT','freeThrowsMade','freeThrowAttempts')]:
                    if k in values:p[made],p[attempts]=pair(values[k])
                if not all(k in p for k in ['points','fieldGoalsMade','threePointersMade','freeThrowsMade']):raise ValueError('NBA scoring category incomplete')
                if p['points']!=2*p['fieldGoalsMade']+p['threePointersMade']+p['freeThrowsMade']:raise ValueError('NBA individual scoring does not reconcile')
                if all(k in p for k in ['rebounds','offensiveRebounds','defensiveRebounds']) and p['rebounds']!=p['offensiveRebounds']+p['defensiveRebounds']:raise ValueError('NBA individual rebounds do not reconcile')
                for k,v in p.items():aggregate[k]+=v
                if not row['athlete'].get('id'):
                    # Do not guess an athlete from a surname. Unmapped nonzero
                    # categories are withheld for the entire team; explicit zero
                    # counting fields cannot change that category's total.
                    unmapped.append({'team':team,'stats':p,'sourceShortName':row['athlete'].get('shortName'),'identityResolved':False});unsupported.update(k for k,v in p.items() if v!=0);continue
                pid='nba:espn:'+str(row['athlete']['id'])
                if pid in players:raise ValueError('NBA duplicate athlete identity')
                players[pid]={'team':team,'stats':p};played+=1
            available=category_supported
        if available is None or played<5:raise ValueError('NBA mapped final player category incomplete')
        available-=unsupported
        if aggregate['points']!=scores[team]:
            available.discard('points');checks.append({'team':team,'stat':'points','equal':False,'playerSum':aggregate['points'],'verifiedTeamScore':scores[team]})
        if 'minutes' in available and not 235<=aggregate['minutes']<=400:available.remove('minutes');missing_minutes.append({'team':team,'reason':'Total official player minutes are incomplete'})
        independent=source_totals.get(team,{})
        for source_key,made,attempts in [('fieldGoalsMade-fieldGoalsAttempted','fieldGoalsMade','fieldGoalAttempts'),('threePointFieldGoalsMade-threePointFieldGoalsAttempted','threePointersMade','threePointAttempts'),('freeThrowsMade-freeThrowsAttempted','freeThrowsMade','freeThrowAttempts')]:
            if source_key in independent:
                expected=pair(independent[source_key])
                for stat,value in zip([made,attempts],expected):
                    if stat in available and value!=aggregate[stat]:available.remove(stat);checks.append({'team':team,'stat':stat,'equal':False})
        for source_key,stat in [('totalRebounds','rebounds'),('offensiveRebounds','offensiveRebounds'),('defensiveRebounds','defensiveRebounds'),('assists','assists'),('steals','steals'),('blocks','blocks'),('turnovers','turnovers')]:
            if stat in available and source_key in independent:
                equal=scalar(independent[source_key])==aggregate[stat];checks.append({'team':team,'stat':stat,'equal':equal})
                if not equal:available.remove(stat)
        support[team]=sorted(available);totals[team]=dict(aggregate)
    if set(support)!=set(scores):raise ValueError('NBA two-team final box incomplete')
    return {'eventId':event_id,'sport':'NBA','scores':scores,'players':players,'supportedStatisticsByTeam':support,'teamStatTotals':totals,'outcomesVerified':True,'verifiedScope':'Final team scores and supported individual categories only','notForPregameFeatures':True,'accountingChecks':checks,'unmapped':unmapped,'missingMinutes':missing_minutes,'originalPublicationVerified':False,'policy':'Missing minutes are unavailable, not zero. Unmapped nonzero or unreconciled counting categories are withheld; no player-name guess is made.'}
