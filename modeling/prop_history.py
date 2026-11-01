"""Automatic historical-statistic evidence. No simulated games or invented priors.

These are explicitly conditional on a recorded participation/usage game. They are
not calibrated next-game forecasts, and do not claim fitted injury/weather effects.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math

VERSION = 'observed-player-games-12.1.0'
NFL_FIELDS = {'passingYards':'passing_yards','passingTouchdowns':'passing_tds',
              'passingAttempts':'attempts','completions':'completions','interceptions':'passing_interceptions',
              'rushingYards':'rushing_yards','carries':'carries','rushingTouchdowns':'rushing_tds',
              'receivingYards':'receiving_yards','receptions':'receptions','receivingTouchdowns':'receiving_tds','targets':'targets'}


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
        samples=[(g['id'],g['values'][stat]) for g in logs if stat in g['values']][-24:]
        if not samples:continue
        histogram=Counter(value for _,value in samples)
        output[stat]={'histogram':[{'value':x,'count':n} for x,n in sorted(histogram.items())],
                      'sampleSize':len(samples),'historicalGameIds':[g for g,_ in samples],
                      'coverage':'Published games with recorded player participation; zero-opportunity absences are not inferred.'}
    return output


def nfl_history(data, fetcher=None, now=None):
    from .public_research import fetch_dataset, validate_game, current_rosters, injury_records, _integer
    from .hierarchical_props import attach_models
    from concurrent.futures import ThreadPoolExecutor,as_completed
    now=now or datetime.now(timezone.utc)
    if set(data)-{'game','unstartedGameIds'}:raise ValueError('Only a verified scheduled game and source schedule exclusions may be supplied')
    unstarted=data.get('unstartedGameIds',[])
    if not isinstance(unstarted,list) or len(unstarted)>128 or any(not isinstance(v,str) or len(v)>100 for v in unstarted):raise ValueError('Bounded verified schedule exclusions required')
    game=validate_game(data.get('game'),now);fetcher=fetcher or fetch_dataset
    specs=[('rosters',game['season']),('player_stats',game['season']),('player_stats',game['season']-1),('injuries',game['season']),('snaps',game['season']),('team_stats',game['season']),('depth',game['season'])]
    datasets={};sources=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        pending={pool.submit(fetcher,kind,year):(kind,year) for kind,year in specs}
        for future in as_completed(pending):
            kind,year=pending[future]
            try:datasets[(kind,year)]=future.result()
            except (ValueError,OSError,KeyError):
                if kind in ('rosters','player_stats') and year==game['season']:raise
                sources.append({'id':'nflverse-'+kind,'season':year,'status':'unavailable','checkedAt':now.isoformat()})
    current=datasets[('player_stats',game['season'])];roster_source=datasets[('rosters',game['season'])]
    teams={game['home'],game['away']};roster,week=current_rosters(roster_source.rows(),teams,game['week'])
    if not roster or week<game['week']-1:raise ValueError('A current verified NFL roster is unavailable; historical names cannot establish current identity')
    # Test/custom fetchers must not relabel the same asset as a different season.
    prior=datasets.get(('player_stats',game['season']-1))
    if prior is current or prior and prior.metadata.get('url')==current.metadata.get('url'):datasets.pop(('player_stats',game['season']-1),None)
    sources.extend({**v.metadata,'season':year} for (kind,year),v in datasets.items())
    injury_source=datasets.get(('injuries',game['season']))
    injuries=injury_records(list(injury_source.rows()),teams,game['week'],injury_source.metadata) if injury_source else []
    restricted={r['playerId'] for r in injuries if r['status'] in ('out','injured_reserve','questionable','doubtful')}
    logs=defaultdict(dict);records=[];seen={}
    passing={'passingYards','passingAttempts','completions','interceptions','passingTouchdowns'}
    for (kind,season),source in datasets.items():
        if kind!='player_stats':continue
        for row in source.rows():
            pid=row.get('player_id');w=_integer(row.get('week'));team=row.get('team');position=row.get('position') or roster.get(pid,{}).get('position')
            if not pid or (position not in ('QB','RB','WR','TE') and pid not in roster) or row.get('season_type')!='REG' or not 0<w<=18 or season==game['season'] and w>=game['week']:continue
            if row.get('season') and _integer(row['season'])!=season:continue
            gid=row.get('game_id') or f'{season}:week:{w}:{team}'
            if gid in unstarted:continue
            if sum(finite(row.get(k)) or 0 for k in ('attempts','carries','targets','receptions'))<=0:continue
            values={stat:v for stat,key in NFL_FIELDS.items() if (v:=finite(row.get(key))) is not None and (stat not in passing or position=='QB')}
            if any(values.get(k,0)<0 for k in ('passingAttempts','completions','carries','receptions','targets')):continue
            if all(k in values for k in ('rushingTouchdowns','receivingTouchdowns')):values['touchdowns']=values['rushingTouchdowns']+values['receivingTouchdowns']
            identity=(season,gid,pid);entry={'id':gid,'season':season,'week':w,'team':team,'values':values}
            if identity in seen:
                if seen[identity]!=entry:raise ValueError('Conflicting duplicate official player-game statistics')
                continue
            seen[identity]=entry
            records.extend({'player':pid,'position':position,'season':season,'week':w,'game':gid,'stat':stat,'value':value} for stat,value in values.items())
            if pid in roster and (season<game['season'] or roster[pid].get('team')==team):logs[pid][(season,gid)]=entry
    players={};catalog=[];withheld={};usage={}
    snap_source=datasets.get(('snaps',game['season']));snap_rows=list(snap_source.rows()) if snap_source else []
    depth_source=datasets.get(('depth',game['season']));depth_rows=list(depth_source.rows()) if depth_source else []
    team_source=datasets.get(('team_stats',game['season']));team_rows=[r for r in team_source.rows() if r.get('team') in teams and 0<_integer(r.get('week'))<game['week'] and r.get('game_id') not in unstarted] if team_source else []
    for pid,record in roster.items():
        raw=record.get('espn_id');espn=str(int(float(raw))) if raw and finite(raw) is not None else None
        catalog.append({'id':pid,'espnId':espn,'name':record.get('full_name'),'team':record.get('team'),'position':record.get('position')})
        if pid in restricted or record.get('status')!='ACT':
            withheld[pid]='Current injury/roster evidence does not support unrestricted availability; no fitted availability mixture exists.';continue
        ordered=sorted(logs.get(pid,{}).values(),key=lambda r:(r['season'],r['week']))
        if not ordered:
            withheld[pid]='No verified current- or previous-season player-game statistics establish this player’s usage.';continue
        dist=summarize(ordered)
        td=[g for g in ordered[-24:] if 'touchdowns' in g['values']]
        if td:
            bins=Counter(g['values']['touchdowns'] for g in td);dist['touchdowns']={'histogram':[{'value':v,'count':n} for v,n in sorted(bins.items())],'sampleSize':len(td),'historicalGameIds':[g['id'] for g in td]}
        if dist:players[pid]=dist
        recent=[g for g in ordered if g['season']==game['season']][-4:]
        usage[pid]={'currentSeasonGames':len([g for g in ordered if g['season']==game['season']]),'previousSeasonGames':len([g for g in ordered if g['season']<game['season']]),'recentGameLogs':recent,'position':record.get('position'),
                    'snapCounts':[{k:r.get(k) for k in ('game_id','week','offense_snaps','offense_pct')} for r in snap_rows if record.get('pfr_id') and r.get('pfr_player_id')==record.get('pfr_id') and r.get('game_id') not in unstarted and 0<_integer(r.get('week'))<game['week']][-4:],
                    'depthCharts':[{k:r.get(k) for k in ('dt','pos_abb','pos_rank')} for r in depth_rows if r.get('gsis_id')==pid and r.get('dt') and r['dt']<=now.isoformat()[:10]][-3:]}
    artifacts=attach_models(players,catalog,records,game['season'])
    fingerprint=hashlib.sha256(json.dumps([VERSION,game,players,withheld,usage,artifacts],sort_keys=True).encode()).hexdigest()
    return {'sport':'NFL','gameId':game['id'],'eventStart':game['startTime'],'method':'empirical_history',
            'modelVersion':VERSION,'inputVersion':fingerprint,'players':players,'playerCatalog':catalog,
            'sources':sources,'injuries':injuries,'withheldPlayers':withheld,'calibrated':False,'playerUsage':usage,
            'distributionModelValidation':artifacts,'teamEvidence':team_rows[-20:],
            'featureCoverage':{'currentAndPreviousSeason':True,'snapCounts':snap_source is not None,'depthCharts':depth_source is not None,'opponentStatistics':team_source is not None,'weatherNumericAdjustment':False,'coachingNumericAdjustment':False,'injuryAdjustment':'Verified restrictions withhold unsupported availability; no arbitrary multiplier.'},
            'calculatedAt':now.isoformat(),'limitations':[
                'Conditional player-stat research. Validated partial-pooling distributions are used only when chronological holdout improvement is supported; other rows remain labeled historical frequency.',
                'Current and previous published seasons are considered. No five-game cutoff is applied; sample size and uncertainty are shown.',
                'Quarterback changes, team/role changes, opponent, teammate injuries and weather are not arbitrary numeric adjustments. Total structural uncertainty is not fully quantified.',
                'Chronological player-stat validation does not establish prospective contract calibration or historical source publication times. No market advantage is claimed.']}


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
    sources=[{'id':'sportsdataverse-cfb','url':source['url'],'collectedAt':source['collectedAt'],'sha256':source['sha256'],'season':game['season']}]
    columns=['game_id','pos_team_id','status_type_completed','wallclock','passer_player_id','receiver_player_id','rusher_player_id',
             'passer_player_name','receiver_player_name','rusher_player_name','pass_attempt','sack','rush','completion','int',
             'yds_receiving','yds_rushed','yds_sacked','xp_attempt','two_point_conv_result','penalty_no_play','penalty_negated_play','offense_score_play','td_play']
    schema=pq.ParquetFile(source['path']).schema.names
    extras=[k for k in ('week','season','seasonType') if k in schema]
    table=pq.read_table(source['path'],columns=columns+extras)
    wanted=__import__('pyarrow').array([int(game['home']['espnId']),int(game['away']['espnId'])])
    rows=table.filter(pc.is_in(table['pos_team_id'],value_set=wanted)).to_pylist();del table
    for r in rows:r['_sourceSeason']=game['season']
    try:
        prior=source_file(game['season']-1)
        if prior['url']!=source['url'] and prior['sha256']!=source['sha256']:
            schema=pq.ParquetFile(prior['path']).schema.names;extra=[k for k in ('week','season','seasonType') if k in schema]
            table=pq.read_table(prior['path'],columns=columns+extra);older=table.filter(pc.is_in(table['pos_team_id'],value_set=wanted)).to_pylist();del table
            for r in older:r['_sourceSeason']=game['season']-1
            rows.extend(older);sources.append({'id':'sportsdataverse-cfb-previous','url':prior['url'],'collectedAt':prior['collectedAt'],'sha256':prior['sha256'],'season':game['season']-1})
    except (ValueError,OSError,RuntimeError):sources.append({'id':'sportsdataverse-cfb-previous','status':'unavailable','checkedAt':datetime.now(timezone.utc).isoformat()})
    entries={};catalog={};invalid=defaultdict(set);rejected=Counter();cutoff=utc(game['startTime'])
    def identity(v):
        n=finite(v)
        if n is None or n<=0 or int(n)!=n:raise ValueError('Missing exact source participant')
        return 'cfb:espn:'+str(int(n))
    def entry(row,pid,name):
        gid='cfb:espn:'+str(int(row['game_id']));team='cfb:espn:'+str(int(row['pos_team_id']));at=utc(row['wallclock'])
        if pid not in catalog or catalog[pid]['observedAt']<at.isoformat():catalog[pid]={'id':pid,'name':name,'team':team,'observedAt':at.isoformat()}
        return entries.setdefault((gid,pid),{'id':gid,'team':team,'at':at,'values':Counter(),'roles':set(),'season':row['_sourceSeason'],'week':int(row.get('week') or 0)})
    for row in rows:
        if row.get('seasonType') not in (None,2):continue
        if not source_flag(row['status_type_completed']) or source_flag(row['penalty_no_play']) or source_flag(row['penalty_negated_play']) or source_flag(row['xp_attempt']) or row['two_point_conv_result'] in ('success','failure'):continue
        try:
            gid='cfb:espn:'+str(int(row['game_id']));team='cfb:espn:'+str(int(row['pos_team_id']));at=utc(row['wallclock'])
            if at>=cutoff or at>=datetime.now(timezone.utc):continue
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
    by_player=defaultdict(list);records=[]
    stat_roles={'passing':('passingYards','passingTouchdowns','passingAttempts','completions','interceptions'),
                'receiving':('receivingYards','receptions','receivingTouchdowns'),'rushing':('rushingYards','carries','rushingTouchdowns')}
    for (gid,pid),e in entries.items():
        values={stat:e['values'][stat] for role,stats in stat_roles.items() if role in e['roles'] and role not in invalid.get((gid,e['team']),set()) for stat in stats}
        if not values:continue
        by_player[pid].append({'id':gid,'at':e['at'],'values':values,'season':e['season'],'week':e['week']})
        for role,stats in stat_roles.items():
            records.extend({'player':pid,'position':'CFB_'+role.upper(),'season':e['season'],'week':e['week'],'game':gid,'stat':stat,'value':value} for stat,value in values.items() if stat in stats and e['week']>0)
    players={}
    for pid,logs in by_player.items():
        ordered=sorted(logs,key=lambda x:x['at'])
        if datetime.now(timezone.utc)-ordered[-1]['at']>timedelta(days=550):continue
        dist=summarize(ordered)
        if dist:players[pid]=dist
    from .hierarchical_props import attach_models
    artifacts=attach_models(players,list(catalog.values()),records,game['season'],sport='CFB')
    fingerprint=hashlib.sha256(json.dumps([VERSION,game['id'],[s.get('sha256') for s in sources],players],sort_keys=True).encode()).hexdigest()
    return {'sport':'CFB','gameId':game['id'],'eventStart':game['startTime'],'method':'empirical_history','modelVersion':VERSION,
            'inputVersion':fingerprint,'players':players,'playerCatalog':list(catalog.values()),'sources':sources,'distributionModelValidation':artifacts,
            'coverage':{'rejectedTeamGames':len(invalid),'rejectionReasons':dict(rejected),'observedPlayers':len(by_player),'observedGameCounts':dict(Counter(len(v) for v in by_player.values()))},
            'calculatedAt':datetime.now(timezone.utc).isoformat(),'calibrated':False,'limitations':[
                'Current- and previous-season usage-conditioned player-stat evidence, including overtime. Partial-pooling models require chronological holdout improvement; no minimum of five player games is imposed. Estimates are not calibrated next-game forecasts.',
                'Statistic cohorts with missing participant/stat coverage are excluded. Penalty-negated plays are excluded; NCAA sacks count as rushing.',
                'Current college roster, injury, transfer and snap restrictions are unverified. Conditional participation is not an availability forecast.',
                'Opponent changes, teammate injuries, weather and structural uncertainty are not numerically adjusted without validated models.']}
