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

def recent_nba_packets(year=2027,*,root=ROOT,exclude=(),source_folder=None):
    """Read an owned missing season explicitly; old protocols retain defaults.

    Final boxes are historical labels/earlier inputs, never current lineups.
    Original historical publication is unverified. A future capture can bind
    the exact local edition before its cutoff without backdating old sources.
    """
    from .nba_quality import audit
    import hashlib
    from pathlib import Path
    root=Path(root).resolve();folder=Path(source_folder).resolve() if source_folder else root/'artifacts/overnight-v21/external';banned=protected()|set(exclude);hidden=[int(g.split(':')[-1]) for g in banned if g.startswith('nba:espn:')]
    files={k:folder/f'NBA-{k}_box_{year}.parquet' for k in ('player','team')};raw={}
    for kind,path in files.items():
        if not path.exists():raise ValueError('Owned NBA season file unavailable: '+str(path))
        rows=pq.read_table(path,filters=[('game_id','not in',hidden)] if hidden else None).to_pylist();group=defaultdict(list)
        for r in rows:group[str(int(r['game_id']))].append(r)
        raw[kind]=group
    out=[];rejected=[]
    for gid,teams in raw['team'].items():
        players=raw['player'].get(gid,[]);tid={str(int(t['team_id'])):t for t in teams};times={str(t['game_date_time']) for t in teams}
        if len(tid)!=2 or len(times)!=1:rejected.append({'gameId':gid,'reason':'Team/time identity mismatch'});continue
        at=teams[0]['game_date_time'].isoformat();game={'id':'nba:espn:'+gid,'at':at,'season':year,'teams':tid,'players':players}
        qa=audit(game)
        if not qa['usable']:rejected.append(qa);continue
        packet={'id':game['id'],'at':at,'sport':'NBA','season':year,'teams':{},'sourceEditionVerifiedForHistoricalCutoff':False}
        for team,t in tid.items():
            ps={}
            for p in players:
                if str(int(p['team_id']))!=team:continue
                minutes=p.get('minutes')
                if minutes is None and p.get('did_not_play') is not True:continue
                stats={'minutes':float(minutes or 0)}
                for stat,key in [('points','points'),('fieldGoalAttempts','field_goals_attempted'),('fieldGoalsMade','field_goals_made'),('threePointAttempts','three_point_field_goals_attempted'),('threePointersMade','three_point_field_goals_made'),('freeThrowAttempts','free_throws_attempted'),('assists','assists'),('steals','steals'),('blocks','blocks'),('turnovers','turnovers'),('offensiveRebounds','offensive_rebounds'),('defensiveRebounds','defensive_rebounds')]:
                    if p.get(key) is not None:stats[stat]=float(p[key])
                if all(k in stats for k in ('offensiveRebounds','defensiveRebounds')):stats['rebounds']=stats['offensiveRebounds']+stats['defensiveRebounds']
                if all(k in stats for k in ('points','rebounds','assists')):
                    a,b,c=(stats[k] for k in ('points','rebounds','assists'));stats.update(pointsReboundsAssists=a+b+c,pointsRebounds=a+b,pointsAssists=a+c,reboundsAssists=b+c)
                ps[str(int(p['athlete_id']))]={'name':p['athlete_display_name'],'position':p.get('athlete_position_abbreviation','unknown'),'starter':p.get('starter'),'historicalDidNotPlay':p.get('did_not_play') is True,'stats':stats}
            packet['teams'][team]={'players':ps,'totals':{'score':float(t['team_score'])},'opponent':str(int(t['opponent_team_id']))}
            side=t.get('team_home_away',t.get('home_away'))
            if side in ('home','away'):packet[side]=team
        if 'home' not in packet or 'away' not in packet:rejected.append({'gameId':gid,'reason':'Home/away source identity missing'});continue
        out.append(packet)
    return sorted(out,key=lambda g:(g['at'],g['id'])),{'sourceVersions':{str(p.relative_to(root) if p.is_relative_to(root) else p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in files.values()},'admittedGames':len(out),'rejected':rejected,'originalHistoricalPublicationVerified':False,'activeFlagNotUsedAsHealth':True}

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
