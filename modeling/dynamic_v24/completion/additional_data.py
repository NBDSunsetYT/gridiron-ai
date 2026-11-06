"""Newly acquired public NFL 2025 counting history; not pregame editions."""
import csv
from collections import defaultdict
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import pyarrow.parquet as pq
from .data import packets as previous_packets
from ...integration_v22.datasets import protected
from ...overnight_v20.data import ROOT

FOLDER=ROOT/'artifacts/dynamic-v24/completion-r4/additional-nfl-sources'
MAP={'passingAttempts':'attempts','passingYards':'passing_yards','passingTouchdowns':'passing_tds','interceptions':'passing_interceptions','completions':'completions','carries':'carries','rushingYards':'rushing_yards','rushingTouchdowns':'rushing_tds','targets':'targets','receptions':'receptions','receivingYards':'receiving_yards','receivingTouchdowns':'receiving_tds'}

def raw_rows(years=(2019,2020,2021,2025)):
    hidden=protected()
    return [r for year in years for r in pq.read_table(FOLDER/f'stats_player_week_{year}.parquet',filters=[('game_id','not in',list(hidden))]).to_pylist()]

def packets(sport):
    if sport!='NFL':return previous_packets(sport)
    games=previous_packets('NFL');schedule={r['game_id']:r for r in csv.DictReader((ROOT/'artifacts/parallel-v19/sources/nfl-games.csv').open())};players=defaultdict(list);teams=defaultdict(dict);hidden=protected()
    for row in raw_rows():
        if row['season_type']=='REG':players[row['game_id']].append(row)
    for year in (2019,2020,2021,2025):
        for row in pq.read_table(FOLDER/f'stats_team_week_{year}.parquet',filters=[('game_id','not in',list(hidden))]).to_pylist():
            if row['season_type']=='REG':teams[row['game_id']][row['team']]=row
    for gid,ts in teams.items():
        s=schedule.get(gid)
        if not s or set(ts)!={s['home_team'],s['away_team']} or s['home_score']=='' or s['away_score']=='':continue
        at=datetime.fromisoformat(s['gameday']+'T'+s['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(ZoneInfo('UTC'));g={'id':gid,'sport':'NFL','at':at.isoformat(),'end':(at+timedelta(hours=8)).isoformat(),'season':int(s['season']),'home':s['home_team'],'away':s['away_team'],'teams':{}}
        valid=True
        for team,t in ts.items():
            ps={r['player_id']:{'stats':{k:float(r[v]) for k,v in MAP.items() if r.get(v) is not None},'position':r.get('position','unknown'),'starter':None} for r in players[gid] if r['team']==team and r.get('player_id') and sum(float(r.get(k) or 0) for k in ('attempts','carries','targets','receptions'))>0};totals={k:float(t[v]) for k,v in MAP.items() if t.get(v) is not None};totals['score']=float(s['home_score'] if team==g['home'] else s['away_score'])
            for stat in ('passingAttempts','passingYards','completions','receptions','receivingYards','carries','rushingYards'):
                if stat not in totals or abs(sum(p['stats'].get(stat,0) for p in ps.values())-totals[stat])>1e-7:valid=False
            g['teams'][team]={'players':ps,'totals':totals,'opponent':t['opponent_team']}
        if valid:games.append(g)
    return sorted(games,key=lambda g:(g['at'],g['id']))
