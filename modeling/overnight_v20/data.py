"""Time-ordered feature construction from owned, checksum-addressed archives.

Past team appearances, including non-participation, form the player universe.
Current final rosters/outcomes never select who receives a pregame forecast.
Missing historic injury/lineup publication is UNKNOWN, never 'healthy'.
"""
from collections import defaultdict
from datetime import datetime,timezone
import pickle
from pathlib import Path
from ..structural_v18.models import OPPORTUNITY

ROOT=Path(__file__).resolve().parents[2]
FOOTBALL=('passingAttempts','passingYards','targets','receptions','receivingYards','carries','rushingYards')
BASKETBALL=('minutes','points','fieldGoalAttempts','threePointAttempts','freeThrowAttempts','rebounds','assists','steals','blocks','turnovers')
NBA_MAP={'minutes':'minutes','points':'points','fieldGoalAttempts':'field_goals_attempted','threePointAttempts':'three_point_field_goals_attempted','freeThrowAttempts':'free_throws_attempted','rebounds':None,'assists':'assists','steals':'steals','blocks':'blocks','turnovers':'turnovers'}
def stamp(v):return datetime.fromisoformat(str(v).replace('Z','+00:00')).timestamp()

def archives(sport):
    if sport!='NBA':
        data=pickle.load((ROOT/'artifacts/learning-v16/datasets'/f'{sport}-repaired.pickle').open('rb'))
        return data
    previous=pickle.load((ROOT/'artifacts/engine-v15/nba/owned-dataset.cache').open('rb'))
    current=pickle.load((ROOT/'artifacts/learning-v16/datasets/NBA-repaired.pickle').open('rb'))
    return {**previous,**current}

def packets(sport):
    data=archives(sport);result=[]
    if sport!='NBA':
        by_team=defaultdict(lambda:defaultdict(int))
        for row in data['rows']:
            if row['kind'] in ('pass','sack','rush','kneel'):
                by_team[(row['game'],row['o'])]['plays']+=1
                by_team[(row['game'],row['o'])]['dropbacks']+=int(row['kind'] in ('pass','sack'))
        for game in data['games'].values():
            if game['plays']<50:continue
            teams={}
            for side,other,score in [(game['home'],game['away'],game['actualHome']),(game['away'],game['home'],game['actualAway'])]:
                players={p:{'stats':{s:float(v['stats'].get(s,0)) for s in FOOTBALL},'starter':None} for p,v in game['players'].items() if v['team']==side}
                if not players:break
                totals={s:sum(v['stats'][s] for v in players.values()) for s in FOOTBALL}
                totals.update(score=float(score),plays=by_team[(game['id'],side)]['plays'],dropbacks=by_team[(game['id'],side)]['dropbacks'])
                teams[side]={'players':players,'totals':totals,'opponent':other}
            if len(teams)==2:result.append({'id':game['id'],'sport':sport,'at':game['firstObservedAt'],'end':game['lastObservedAt'],'season':game['season'],'home':game['home'],'away':game['away'],'teams':teams})
    else:
        for game in data.values():
            if len(game['teams'])!=2:continue
            teams={};home=None;away=None
            for tid,t in game['teams'].items():
                ps=[p for p in game['players'] if str(p['team_id'])==str(tid) and p.get('minutes') is not None and p['minutes']>0]
                minutes=sum(float(p['minutes']) for p in ps)
                if len(ps)<5 or not 235<=minutes<=400 or sum(float(p['points']) for p in ps)!=float(t['team_score']):break
                players={str(int(p['athlete_id'])):{'stats':{s:float(p.get(raw) or 0) if raw else float(p['offensive_rebounds']+p['defensive_rebounds']) for s,raw in NBA_MAP.items()},'starter':bool(p.get('starter'))} for p in ps}
                totals={s:sum(p['stats'][s] for p in players.values()) for s in BASKETBALL};totals.update(score=float(t['team_score']),plays=float(t['field_goals_attempted']+t.get('total_turnovers',t.get('turnovers',0))),dropbacks=0)
                teams[str(tid)]={'players':players,'totals':totals,'opponent':str(t['opponent_team_id'])}
                if t['team_home_away']=='home':home=str(tid)
                else:away=str(tid)
            if len(teams)==2 and home and away:result.append({'id':game['id'],'sport':sport,'at':game['at'],'end':game['at'],'season':game['season'],'home':home,'away':away,'teams':teams})
    return sorted(result,key=lambda g:(g['at'],g['id']))

def mean(values):return float(sum(values)/len(values)) if len(values) else 0.

def features_for(game,team,history,sport):
    own=[g for g in history.get(team,[]) if stamp(g['end'])+6*3600<stamp(game['at'])][-8:]
    opponent=game['away'] if team==game['home'] else game['home']
    other=[g for g in history.get(opponent,[]) if stamp(g['end'])+6*3600<stamp(game['at'])][-8:]
    if min(len(own),len(other))<3:return []
    stats=BASKETBALL if sport=='NBA' else FOOTBALL
    player_ids=sorted({pid for g in own[-5:] if g['season']==game['season'] for pid in g['teams'][team]['players']})+['__team__']
    rows=[]
    for pid in player_ids:
        games=[{'stats':g['teams'][team]['totals'],'starter':None} if pid=='__team__' else g['teams'][team]['players'].get(pid) for g in own]
        participation=[int(p is not None) for p in games]
        targets=(*stats,'score','plays','dropbacks') if pid=='__team__' else stats
        prior={s:[p['stats'].get(s,0) if p else 0. for p in games] for s in targets}
        starts=[int(p is not None and p.get('starter') is True) for p in games]
        common=[len(own),len(other),int(team==game['home']),min(14,(stamp(game['at'])-stamp(own[-1]['end']))/86400),mean(participation[-3:]),mean(participation[-5:]),mean(starts[-3:])]
        names=['team_games','opponent_games','home','rest_days','participation3','participation5','starts3']
        for s in stats:
            common.extend([prior[s][-1],mean(prior[s][-3:]),mean(prior[s][-5:])]);names.extend([s+'_last',s+'_mean3',s+'_mean5'])
        for s in (*stats,'score','plays','dropbacks'):
            common.extend([mean([g['teams'][team]['totals'][s] for g in own[-5:]]),mean([g['teams'][g['teams'][opponent]['opponent']]['totals'][s] for g in other[-5:]])]);names.extend(['team_'+s,'opponent_allowed_'+s])
        # Role is inferred strictly from past actions. It is not an official position.
        role='NBA' if sport=='NBA' else 'QB' if sum(prior['passingAttempts']) else 'runner' if sum(prior['carries'])>sum(prior['targets']) else 'receiver'
        for s in targets:
            if pid!='__team__' and sport!='NBA':
                opportunity='passingAttempts' if s.startswith('passing') else 'carries' if s in ('carries','rushingYards','rushingTouchdowns') else 'targets'
                if not sum(prior[opportunity]):continue
            x=[*common,prior[s][-1],mean(prior[s][-3:]),mean(prior[s][-5:]),mean(prior[s]),mean([float(g['teams'][team]['totals'][s]) for g in own[-5:]])]
            rows.append({'gameId':game['id'],'at':game['at'],'season':game['season'],'team':team,'player':pid,'stat':s,'role':role,'x':x,'featureNames':names+['target_last','target_mean3','target_mean5','target_mean8','team_target_mean5'],'baseline':mean(prior[s][-5:]),'highVolume':mean(prior[s][-5:]),'featureCutoff':max(g['end'] for g in own+other),'injuryStatus':'unknown'})
    return rows

def build_dataset(sport,end):
    """Never visit outcomes in a reserved final period during development."""
    history=defaultdict(list);rows=[];games=[]
    for game in packets(sport):
        if game['at']>=end:continue
        current=[]
        for team in (game['home'],game['away']):current.extend(features_for(game,team,history,sport))
        for row in current:
            actual={'stats':game['teams'][row['team']]['totals'],'starter':None} if row['player']=='__team__' else game['teams'][row['team']]['players'].get(row['player']);row['y']=actual['stats'].get(row['stat'],0.) if actual else 0.;row['actualParticipated']=actual is not None
            row['actualStarter']=actual.get('starter') if actual else False
            row['opportunity']=actual['stats'].get(OPPORTUNITY.get(row['stat'],''),0.) if actual else 0.
        if current:rows.extend(current);games.append(game)
        for team in (game['home'],game['away']):history[team].append(game)
    return rows,games
