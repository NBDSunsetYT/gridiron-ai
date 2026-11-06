"""Immutable earlier-game features; outcome joins happen after forecasts.

These are conditional corrected-history diagnostics, not publication-verified
pregame forecasts. Missing final box rows are ungraded, never invented zeros.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import numpy as np
from ..overnight_v20 import data
from ..integration_v22.datasets import cfb_packets,nfl_packets,protected,examined
from ..accuracy_v20.quality import aware
from ..fullgame_v23.io import ROOT

FOOT_STATS=('passingAttempts','passingYards','passingTouchdowns','interceptions','carries','rushingYards','rushingTouchdowns','targets','receptions','receivingYards','receivingTouchdowns')
NBA_STATS=('minutes','points','rebounds','assists','threePointersMade','steals','blocks','turnovers','pointsReboundsAssists','pointsRebounds','pointsAssists','reboundsAssists','doubleDouble','tripleDouble')
def excluded_validation():
    import json
    ids=set(examined());p=ROOT/'artifacts/fullgame-v23/protocol.json'
    if p.exists():ids.update(g for gs in json.load(p.open())['selection'].values() for g in gs)
    return ids|protected()

def packets(sport):
    import pyarrow.parquet as pq
    banned=protected()
    if sport=='NBA':
        result=[]
        for g in data.archives('NBA').values():
            if g['id'] in banned:continue
            game={'id':g['id'],'sport':sport,'at':g['at'],'season':g['season'],'teams':{}}
            for team,raw in g['teams'].items():
                ps={}
                for p in g['players']:
                    if str(p['team_id'])!=team:continue
                    values={k:float(p.get(v) or 0) for k,v in [('minutes','minutes'),('points','points'),('assists','assists'),('steals','steals'),('blocks','blocks'),('turnovers','turnovers'),('threePointersMade','three_point_field_goals_made'),('fieldGoalAttempts','field_goals_attempted'),('threePointAttempts','three_point_field_goals_attempted'),('freeThrowAttempts','free_throws_attempted')] if p.get(v) is not None or p.get('did_not_play') is True}
                    if p.get('offensive_rebounds') is not None and p.get('defensive_rebounds') is not None:values['rebounds']=float(p['offensive_rebounds']+p['defensive_rebounds'])
                    if all(k in values for k in ('points','rebounds','assists')):
                        a,b,c=(values[k] for k in ('points','rebounds','assists'));values.update(pointsReboundsAssists=a+b+c,pointsRebounds=a+b,pointsAssists=a+c,reboundsAssists=b+c)
                    if all(k in values for k in ('points','rebounds','assists','steals','blocks')):
                        n=sum(values[k]>=10 for k in ('points','rebounds','assists','steals','blocks'));values.update(doubleDouble=float(n>=2),tripleDouble=float(n>=3))
                    if values:ps[str(int(p['athlete_id']))]={'stats':values,'position':p.get('athlete_position_abbreviation','unknown')}
                game['teams'][team]={'players':ps,'totals':{'score':float(raw['team_score'])},'opponent':str(raw['opponent_team_id'])}
                if raw['team_home_away']=='home':game['home']=team
                else:game['away']=team
            if len(game['teams'])==2 and 'home' in game and 'away' in game:result.append(game)
    else:
        if sport=='CFB':result=cfb_packets()[0]
        else:
            result=nfl_packets()[0];schedule={g['id']:g for g in data.packets('NFL')}
            for year in (2024,):
                p=ROOT/f'artifacts/fullgame-v23/sources/stats_player_week_{year}.parquet'
                teamfile=ROOT/f'artifacts/fullgame-v23/sources/stats_team_week_{year}.parquet'
                if not p.exists():continue
                players=pq.read_table(p).to_pylist();teams=pq.read_table(teamfile).to_pylist();group=defaultdict(list)
                for r in players:group[r['game_id']].append(r)
                for gid,rows in group.items():
                    if gid in banned or gid not in schedule:continue
                    g=deepcopy(schedule[gid]);g['teams']={t:{'players':{},'totals':{'score':schedule[gid]['teams'][t]['totals']['score']},'opponent':o} for t,o in [(g['home'],g['away']),(g['away'],g['home'])]}
                    for r in rows:
                        if r['team'] not in g['teams']:continue
                        mapping={'passingAttempts':'attempts','passingYards':'passing_yards','passingTouchdowns':'passing_tds','interceptions':'passing_interceptions','carries':'carries','rushingYards':'rushing_yards','rushingTouchdowns':'rushing_tds','targets':'targets','receptions':'receptions','receivingYards':'receiving_yards','receivingTouchdowns':'receiving_tds'}
                        g['teams'][r['team']]['players'][r['player_id']]={'stats':{k:float(r[v]) for k,v in mapping.items() if r.get(v) is not None},'position':r.get('position','unknown')}
                    result.append(g)
        # Enrich older NFL and CFB labels from independently archived boxes.
        for g in result:
            for v in g['teams'].values():
                for p in v['players'].values():
                    if sport=='CFB':p['stats'].pop('targets',None) # The repaired box has no verified target field.
        if sport=='CFB':
            box={}
            for year in (2024,2025):
                for r in pq.read_table(ROOT/f'artifacts/overnight-v21/external/CFB-player_box_{year}.parquet').to_pylist():
                    key=('cfb:espn:'+str(int(r['game_id'])),'cfb:espn:'+str(int(r['team_id'])),'cfb:espn:'+str(int(r['athlete_id'])));values=box.setdefault(key,{})
                    for k in ('passingTouchdowns','interceptions','rushingTouchdowns','receivingTouchdowns'):
                        if r.get(k) is not None:
                            try:values[k]=float(r[k])
                            except (ValueError,TypeError):pass
            for g in result:
                for t,v in g['teams'].items():
                    for pid,p in v['players'].items():p['stats'].update(box.get((g['id'],t,pid),{}))
        else:
            for year in (2022,2023):
                p=ROOT/f'artifacts/integration-v22/external/stats_player_week_{year}.parquet'
                index={(r['game_id'],r['player_id']):r for r in pq.read_table(p).to_pylist()}
                for g in result:
                    if g['season']!=year:continue
                    for t,v in g['teams'].items():
                        for pid,rec in v['players'].items():
                            raw=index.get((g['id'],pid),{})
                            for k,key in [('passingTouchdowns','passing_tds'),('interceptions','passing_interceptions'),('rushingTouchdowns','rushing_tds'),('receivingTouchdowns','receiving_tds')]:
                                if raw.get(key) is not None:rec['stats'][k]=float(raw[key])
    return sorted((g for g in result if g['id'] not in banned),key=lambda g:(g['at'],g['id']))

def records(games,sport):
    history=defaultdict(list);result=[];stats=NBA_STATS if sport=='NBA' else FOOT_STATS
    for g in games:
        cutoff=aware(g['at'])-timedelta(hours=48)
        for team,other in [(g['home'],g['away']),(g['away'],g['home'])]:
            own=[h for h in history[team] if aware(h['at'])<cutoff][-8:];opp=[h for h in history[other] if aware(h['at'])<cutoff][-8:]
            if len(own)<3 or len(opp)<3:continue
            universe=sorted({p for h in own[-5:] for p in h['teams'][team]['players'] if isinstance(p,str) and p and p not in ('None','nan')})
            for player in universe+['__team__']:
                for stat in (('teamPoints',) if player=='__team__' else stats):
                    vals=[];appear=[]
                    for h in own:
                        v=h['teams'][team]['totals'].get('score') if player=='__team__' else h['teams'][team]['players'].get(player,{}).get('stats',{}).get(stat)
                        if v is not None:vals.append(float(v));appear.append(h)
                    if len(vals)<3:continue
                    if player!='__team__':
                        needed='minutes' if sport=='NBA' else 'passingAttempts' if stat.startswith('passing') or stat=='interceptions' else 'carries' if stat.startswith('rushing') or stat=='carries' else 'receptions'
                        if not any(h['teams'][team]['players'].get(player,{}).get('stats',{}).get(needed,0)>0 for h in own):continue
                    trend=vals[-5:];mean=float(np.mean(trend));std=float(np.std(trend));team_stat=[h['teams'][team]['totals']['score'] for h in own[-5:]];def_stat=[h['teams'][h['teams'][other]['opponent']]['totals']['score'] for h in opp[-5:]];minutes=[]
                    if player!='__team__':minutes=[h['teams'][team]['players'].get(player,{}).get('stats',{}).get('minutes',0) for h in own[-5:]]
                    role='team' if player=='__team__' else 'NBA' if sport=='NBA' else 'QB' if any(h['teams'][team]['players'].get(player,{}).get('stats',{}).get('passingAttempts',0)>0 for h in own) else 'runner' if sum(h['teams'][team]['players'].get(player,{}).get('stats',{}).get('carries',0) for h in own)>0 else 'receiver'
                    def sum_stat(h,t,k):return sum(p['stats'].get(k,0) for p in h['teams'][t]['players'].values())
                    opstat='passingAttempts' if stat.startswith('passing') or stat=='interceptions' else 'carries' if stat.startswith('rushing') else ('receptions' if sport=='CFB' else 'targets') if stat.startswith('receiving') or stat=='receptions' else 'minutes' if sport=='NBA' else stat
                    observed_op=g['teams'][team]['players'].get(player,{}).get('stats',{}).get(opstat) if player!='__team__' else None
                    prior_op=[h['teams'][team]['players'].get(player,{}).get('stats',{}).get(opstat) for h in own[-5:]] if player!='__team__' else []
                    ratios=[h['teams'][team]['players'][player]['stats'][stat]/h['teams'][team]['players'][player]['stats'][opstat] for h in own[-5:] if player in h['teams'][team]['players'] and h['teams'][team]['players'][player]['stats'].get(opstat,0)>0 and stat in h['teams'][team]['players'][player]['stats']] if player!='__team__' else []
                    x=[vals[-1],mean,float(np.mean(vals[-3:])),float(np.mean(vals)),std,len(vals),int(team==g['home']),float(np.mean(team_stat)),float(np.mean(def_stat)),min(20,(aware(g['at'])-aware(own[-1]['at'])).total_seconds()/86400),float(np.mean(minutes)) if minutes else 0,float(len(appear))/len(own),float(np.mean([v for v in prior_op if v is not None])) if any(v is not None for v in prior_op) else mean,float(np.mean(ratios)) if ratios else 1,float(np.mean([sum_stat(h,h['teams'][other]['opponent'],stat) for h in opp[-5:]])) if stat!='teamPoints' else float(np.mean(def_stat))]
                    weights=np.power(.6,np.arange(len(trend)-1,-1,-1));ewma=float(np.dot(weights,trend)/weights.sum());actual=g['teams'][team]['totals'].get('score') if player=='__team__' else g['teams'][team]['players'].get(player,{}).get('stats',{}).get(stat)
                    result.append({'gameId':g['id'],'at':g['at'],'season':g['season'],'team':team,'player':player,'stat':stat,'role':role,'x':x,'baseline':mean,'ewma':ewma,'priorCount':len(vals),'y':actual,'opportunity':observed_op,'featureLastGame':max(h['at'] for h in own+opp),'missingAvailability':True,'tier':'conditional_box_history'})
        for t in g['teams']:history[t].append(g)
    return result
