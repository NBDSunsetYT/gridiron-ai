"""Read-only historical adapters; correction publication remains unverified.

Outcome boxes establish historical counting labels, never current availability.
All protected IDs are removed before either fitting or lag construction.
"""
from collections import defaultdict,Counter
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import csv,math
import pyarrow.parquet as pq
from .io import ROOT,OUT
from ..overnight_v20 import data
from ..overnight_v20.state import read
from ..evidence_v21.protection import protected_ids
from ..evidence_v21.football_boxes import repaired_packet

def protected():return protected_ids(read(ROOT/'artifacts/overnight-v21/protocol-final.json'))

def examined():
    p=read(ROOT/'artifacts/overnight-v21/protocol-final.json');ids=set(p['excludedEvaluationIds'])|set(p.get('additionalSourceExposureExclusions',[]))|protected()
    for path in (ROOT/'artifacts/overnight-v21').glob('*protocol*.json'):
        v=read(path)
        for key in ['selection','componentSelection','sealedFinal']:
            for games in v.get(key,{}).values():ids.update(g['id'] for g in games)
    return ids

def cfb_packets():
    players={};teams={};failures=[];out=[]
    for season in [2024,2025]:
        for kind,cache in [('player',players),('team',teams)]:
            for row in pq.read_table(ROOT/f'artifacts/overnight-v21/external/CFB-{kind}_box_{season}.parquet').to_pylist():cache.setdefault(str(int(row['game_id'])),[]).append(row)
    banned=protected()
    for g in data.packets('CFB'):
        if g['id'] in banned:continue
        key=g['id'].split(':')[-1]
        try:out.append(repaired_packet(g,players.get(key,[]),teams.get(key,[])))
        except ValueError as e:failures.append({'eventId':g['id'],'reason':str(e)})
    return out,{'reconciledGames':len(out),'rejected':failures,'originalPublicationVerified':False}

def nfl_packets():
    schedule={r['game_id']:r for r in csv.DictReader((ROOT/'artifacts/parallel-v19/sources/nfl-games.csv').open())};pout=[];raw=[];banned=protected();rejected=[]
    mapping={'passingAttempts':'attempts','passingYards':'passing_yards','completions':'completions','targets':'targets','receptions':'receptions','receivingYards':'receiving_yards','carries':'carries','rushingYards':'rushing_yards'}
    for year in [2022,2023]:
        ps=defaultdict(list)
        for r in pq.read_table(OUT/f'external/stats_player_week_{year}.parquet').to_pylist():
            if r['season_type']=='REG' and int(r['week'])<=18:ps[r['game_id']].append(r);raw.append(r)
        ts=defaultdict(dict)
        for r in pq.read_table(OUT/f'external/stats_team_week_{year}.parquet').to_pylist():
            if r['season_type']=='REG' and int(r['week'])<=18:ts[r['game_id']][r['team']]=r
        for gid,teams in ts.items():
            if gid in banned:continue
            s=schedule.get(gid)
            if not s or set(teams)!={s['home_team'],s['away_team']}:rejected.append({'id':gid,'reason':'schedule/team identity'});continue
            at=datetime.fromisoformat(s['gameday']+'T'+s['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
            g={'id':gid,'sport':'NFL','at':at.isoformat(),'end':(at+timedelta(hours=8)).isoformat(),'season':year,'week':int(s['week']),'home':s['home_team'],'away':s['away_team'],'teams':{},'correctionPublication':'unverified','endTimePolicy':'conservative kickoff+8h historical embargo, not an observed final whistle'}
            try:
                for team,r in teams.items():
                    players={}
                    for p in ps[gid]:
                        if p['team']!=team or not p['player_id'] or sum(float(p.get(k) or 0) for k in ['attempts','carries','targets','receptions'])<=0:continue
                        stats={k:float(p[v]) for k,v in mapping.items()}
                        if not all(math.isfinite(v) for v in stats.values()):raise ValueError('Missing counting label')
                        players[p['player_id']]={'stats':stats,'position':p['position'],'name':p['player_display_name'],'starter':None}
                    totals={k:float(r[v]) for k,v in mapping.items()};totals.update(score=float(s['home_score'] if team==g['home'] else s['away_score']),plays=float(r['attempts']+r['carries']+r['sacks_suffered']),dropbacks=float(r['attempts']+r['sacks_suffered']))
                    for stat in ['passingAttempts','passingYards','completions','receptions','receivingYards','carries','rushingYards']:
                        if abs(sum(p['stats'][stat] for p in players.values())-totals[stat])>1e-6:raise ValueError('Player/team mismatch '+stat)
                    g['teams'][team]={'players':players,'totals':totals,'opponent':r['opponent_team']}
                pout.append(g)
            except ValueError as e:rejected.append({'id':gid,'reason':str(e)})
    return sorted(pout,key=lambda g:(g['at'],g['id'])),raw,{'reconciledGames':len(pout),'rejected':rejected,'originalPublicationVerified':False}

def all_packets():
    nfl,raw,nc=nfl_packets();cfb,cc=cfb_packets();banned=protected();nba=[g for g in data.packets('NBA') if g['id'] not in banned]
    return {'NFL':nfl,'CFB':cfb,'NBA':nba},raw,{'NFL':nc,'CFB':cc,'NBA':{'reconciledGames':len(nba),'originalPublicationVerified':False}}
