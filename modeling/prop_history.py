"""Automatic historical-statistic evidence. No simulated games or invented priors.

These are explicitly conditional on a recorded participation/usage game. They are
not calibrated next-game forecasts, and do not claim fitted injury/weather effects.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math

VERSION = 'observed-player-games-12.0.0'
NFL_FIELDS = {'passingYards':'passing_yards','passingTouchdowns':'passing_tds',
              'passingAttempts':'attempts','completions':'completions','interceptions':'passing_interceptions',
              'rushingYards':'rushing_yards','carries':'carries','rushingTouchdowns':'rushing_tds',
              'receivingYards':'receiving_yards','receptions':'receptions','receivingTouchdowns':'receiving_tds'}


def finite(value):
    if value is None or value == '' or isinstance(value, bool):return None
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (TypeError,ValueError):return None


def summarize(logs):
    """Compact histograms, retaining cohort game IDs for auditing, never plays."""
    output={}
    for stat in NFL_FIELDS:
        samples=[(g['id'],g['values'][stat]) for g in logs if stat in g['values']][-12:]
        if len(samples)<5:continue
        histogram=Counter(value for _,value in samples)
        output[stat]={'histogram':[{'value':x,'count':n} for x,n in sorted(histogram.items())],
                      'sampleSize':len(samples),'historicalGameIds':[g for g,_ in samples],
                      'coverage':'Published games with recorded player participation; zero-opportunity absences are not inferred.'}
    return output


def nfl_history(data, fetcher=None, now=None):
    from .public_research import fetch_dataset, validate_game, current_rosters, injury_records, _integer
    now=now or datetime.now(timezone.utc)
    if set(data)-{'game'}:raise ValueError('Only a verified scheduled game may be supplied')
    game=validate_game(data.get('game'),now);fetcher=fetcher or fetch_dataset
    datasets={kind:fetcher(kind,game['season']) for kind in ('rosters','player_stats')}
    teams={game['home'],game['away']}
    roster,week=current_rosters(datasets['rosters'].rows(),teams,game['week'])
    if not roster or week<game['week']-1:raise ValueError('A current verified NFL roster is unavailable; historical names cannot establish current identity')
    sources=[v.metadata for v in datasets.values()];injuries=[]
    try:
        source=fetcher('injuries',game['season']);sources.append(source.metadata)
        injuries=injury_records(list(source.rows()),teams,game['week'],source.metadata)
    except (ValueError,OSError):
        sources.append({'id':'nflverse-injuries','status':'unavailable','checkedAt':now.isoformat()})
    restricted={r['playerId'] for r in injuries if r['status'] in ('out','injured_reserve','questionable','doubtful')}
    logs=defaultdict(dict)
    for row in datasets['player_stats'].rows():
        pid=row.get('player_id');w=_integer(row.get('week'));team=row.get('team')
        if pid not in roster or roster[pid].get('team')!=team or row.get('season_type')!='REG' or not 0<w<game['week']:continue
        # Week is known before kickoff; unpublished future rows are excluded.
        gid=row.get('game_id') or f"{game['season']}:week:{w}:{team}"
        values={stat:v for stat,key in NFL_FIELDS.items() if (v:=finite(row.get(key))) is not None}
        if not values:continue
        if any(values.get(k,0)<0 for k in ('passingAttempts','completions','carries','receptions')):continue
        td_keys=('rushingTouchdowns','receivingTouchdowns')
        if all(k in values for k in td_keys):values['touchdowns']=sum(values[k] for k in td_keys)
        entry={'id':gid,'week':w,'values':values}
        if gid in logs[pid] and logs[pid][gid]!=entry:raise ValueError('Conflicting duplicate official player-game statistics')
        logs[pid][gid]=entry
    players={};catalog=[];withheld={}
    for pid,record in roster.items():
        raw=record.get('espn_id');espn=str(int(float(raw))) if raw and finite(raw) is not None else None
        catalog.append({'id':pid,'espnId':espn,'name':record.get('full_name'),'team':record.get('team')})
        if pid in restricted or record.get('status')!='ACT':
            withheld[pid]='Current injury/roster evidence does not support unrestricted availability; no fitted availability mixture exists.';continue
        ordered=sorted(logs.get(pid,{}).values(),key=lambda r:r['week'])
        if not ordered or ordered[-1]['week']<game['week']-3:
            withheld[pid]='No recent verified player-game statistics are available.';continue
        dist=summarize(ordered)
        # Touchdown totals require both published rushing and receiving totals.
        td=[g for g in ordered[-12:] if 'touchdowns' in g['values']]
        if len(td)>=5:
            bins=Counter(g['values']['touchdowns'] for g in td)
            dist['touchdowns']={'histogram':[{'value':v,'count':n} for v,n in sorted(bins.items())],'sampleSize':len(td),'historicalGameIds':[g['id'] for g in td]}
        if dist:players[pid]=dist
    fingerprint=hashlib.sha256(json.dumps([VERSION,game,players,withheld],sort_keys=True).encode()).hexdigest()
    return {'sport':'NFL','gameId':game['id'],'eventStart':game['startTime'],'method':'empirical_history',
            'modelVersion':VERSION,'inputVersion':fingerprint,'players':players,'playerCatalog':catalog,
            'sources':sources,'injuries':injuries,'withheldPlayers':withheld,'calibrated':False,
            'calculatedAt':now.isoformat(),'limitations':[
                'Historical participation-conditioned frequency, not a calibrated next-game or full-game simulation probability.',
                'At most twelve recent published games; at least five observations are required per statistic.',
                'Opponent, usage changes, teammate injuries and weather are not numerically adjusted without a validated effect model.',
                'The interval describes finite historical sample uncertainty, not all structural or availability uncertainty.',
                'A distributional candidate is not promoted without independent chronological validation.']}


def source_flag(value):
    return value is True or type(value) in (int,float) and value == 1


def cfb_history(data):
    """Whole-game published stat events, including overtime and NCAA sack rushing.

    This deliberately does not sum the simulator's filtered regulation-only play
    pool. Missing participant/stat coverage invalidates the affected team-game.
    """
    from .cfb_public_research import source_file, _id
    from .fit import utc
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    from datetime import timedelta
    if not isinstance(data,dict) or set(data)-{'game'}:raise ValueError('Only a verified CFB event is accepted')
    game=data.get('game')
    if not isinstance(game,dict):raise ValueError('A verified CFB event is required')
    home,away=_id(game['home']['espnId']),_id(game['away']['espnId']);event=_id(game['espnGameId'])
    if home==away or game['id']!='cfb:espn:'+event or game['home']['id']!='cfb:espn:'+home or game['away']['id']!='cfb:espn:'+away:raise ValueError('Exact separate CFB identities are required')
    if utc(game['startTime'])<=datetime.now(timezone.utc) or game.get('status')!='scheduled':raise ValueError('Only a verified future pregame event is supported')
    if type(game.get('season')) is not int or not datetime.now(timezone.utc).year-1<=game['season']<=datetime.now(timezone.utc).year+1:raise ValueError('Unsupported CFB season')
    source=source_file(game['season'])
    columns=['game_id','pos_team_id','status_type_completed','wallclock','passer_player_id','receiver_player_id','rusher_player_id',
             'passer_player_name','receiver_player_name','rusher_player_name','pass_attempt','sack','rush','completion','int',
             'yds_receiving','yds_rushed','yds_sacked','xp_attempt','two_point_conv_result','penalty_no_play','penalty_negated_play','offense_score_play','td_play']
    table=pq.read_table(source['path'],columns=columns)
    wanted=__import__('pyarrow').array([int(game['home']['espnId']),int(game['away']['espnId'])])
    rows=table.filter(pc.is_in(table['pos_team_id'],value_set=wanted)).to_pylist();del table
    entries={};catalog={};invalid=defaultdict(set);rejected=Counter();cutoff=utc(game['startTime'])
    def identity(v):
        n=finite(v)
        if n is None or n<=0 or int(n)!=n:raise ValueError('Missing exact source participant')
        return 'cfb:espn:'+str(int(n))
    def entry(row,pid,name):
        gid='cfb:espn:'+str(int(row['game_id']));team='cfb:espn:'+str(int(row['pos_team_id']));at=utc(row['wallclock'])
        catalog[pid]={'id':pid,'name':name,'team':team}
        return entries.setdefault((gid,pid),{'id':gid,'team':team,'at':at,'values':Counter(),'roles':set()})
    for row in rows:
        if not source_flag(row['status_type_completed']) or source_flag(row['penalty_no_play']) or source_flag(row['penalty_negated_play']) or source_flag(row['xp_attempt']) or row['two_point_conv_result'] in ('success','failure'):continue
        try:
            gid='cfb:espn:'+str(int(row['game_id']));team='cfb:espn:'+str(int(row['pos_team_id']));at=utc(row['wallclock'])
            if at>=cutoff:continue
            touchdown=source_flag(row['offense_score_play']) and source_flag(row['td_play'])
            if source_flag(row['sack']):
                pid=identity(row['passer_player_id']);e=entry(row,pid,row.get('passer_player_name'));yards=finite(row['yds_sacked'])
                if yards is None or yards>0:raise ValueError('NCAA sack yardage missing')
                e['roles'].add('rushing');e['values']['carries']+=1;e['values']['rushingYards']+=yards
            elif source_flag(row['pass_attempt']):
                pid=identity(row['passer_player_id']);e=entry(row,pid,row.get('passer_player_name'));e['roles'].add('passing')
                e['values']['passingAttempts']+=1;e['values']['interceptions']+=int(source_flag(row['int']))
                if source_flag(row['completion']):
                    rid=identity(row['receiver_player_id']);r=entry(row,rid,row.get('receiver_player_name'));yards=finite(row['yds_receiving'])
                    if yards is None:raise ValueError('Passing/receiving yards missing')
                    r['roles'].add('receiving');r['values']['receptions']+=1;r['values']['receivingYards']+=yards;r['values']['receivingTouchdowns']+=int(touchdown)
                    e['values']['completions']+=1;e['values']['passingYards']+=yards;e['values']['passingTouchdowns']+=int(touchdown)
                elif row['receiver_player_id'] is not None:
                    r=entry(row,identity(row['receiver_player_id']),row.get('receiver_player_name'));r['roles'].add('receiving')
            elif source_flag(row['rush']):
                pid=identity(row['rusher_player_id']);e=entry(row,pid,row.get('rusher_player_name'));yards=finite(row['yds_rushed'])
                if yards is None:raise ValueError('Rushing yards missing')
                e['roles'].add('rushing');e['values']['carries']+=1;e['values']['rushingYards']+=yards;e['values']['rushingTouchdowns']+=int(touchdown)
        except (ValueError,TypeError,KeyError) as error:
            rejected[str(error)]+=1
            if 'gid' in locals() and 'team' in locals():
                roles={'rushing'} if source_flag(row['rush']) or source_flag(row['sack']) else {'passing','receiving'} if source_flag(row['pass_attempt']) else {'passing','receiving','rushing'}
                invalid[(gid,team)].update(roles)
    by_player=defaultdict(list)
    stat_roles={'passing':('passingYards','passingTouchdowns','passingAttempts','completions','interceptions'),
                'receiving':('receivingYards','receptions','receivingTouchdowns'),'rushing':('rushingYards','carries','rushingTouchdowns')}
    for (gid,pid),e in entries.items():
        values={stat:e['values'][stat] for role,stats in stat_roles.items() if role in e['roles'] and role not in invalid.get((gid,e['team']),set()) for stat in stats}
        if not values:continue
        by_player[pid].append({'id':gid,'at':e['at'],'values':values})
    players={}
    for pid,logs in by_player.items():
        ordered=sorted(logs,key=lambda x:x['at'])
        if datetime.now(timezone.utc)-ordered[-1]['at']>timedelta(days=35):continue
        dist=summarize(ordered)
        if dist:players[pid]=dist
    fingerprint=hashlib.sha256(json.dumps([VERSION,game['id'],source['sha256'],players],sort_keys=True).encode()).hexdigest()
    return {'sport':'CFB','gameId':game['id'],'eventStart':game['startTime'],'method':'empirical_history','modelVersion':VERSION,
            'inputVersion':fingerprint,'players':players,'playerCatalog':list(catalog.values()),'sources':[{'id':'sportsdataverse-cfb','url':source['url'],'collectedAt':source['collectedAt'],'sha256':source['sha256']}],
            'coverage':{'rejectedTeamGames':len(invalid),'rejectionReasons':dict(rejected),'observedPlayers':len(by_player),'observedGameCounts':dict(Counter(len(v) for v in by_player.values()))},
            'calculatedAt':datetime.now(timezone.utc).isoformat(),'calibrated':False,'limitations':[
                'Historical usage-conditioned frequency from completed game stat events including overtime; not a calibrated next-game forecast.',
                'Statistic cohorts with missing participant/stat coverage are excluded. Penalty-negated plays are excluded; NCAA sacks count as rushing.',
                'Current college roster, injury, transfer and snap restrictions are unverified. Conditional participation is not an availability forecast.',
                'Opponent changes, teammate injuries, weather and structural uncertainty are not numerically adjusted without validated models.']}
