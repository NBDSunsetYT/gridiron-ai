"""Independent, event-chronological football research normalization.

Unlike the legacy CFB adapter, elapsed clock is measured from this snap to the
next recorded snap in the SAME quarter, including between-play runoff. The
legacy adapter and its frozen artifacts are deliberately left unchanged.
Historical publication/correction availability remains explicitly unverified.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path

from .fit import utc

NORMALIZER_VERSION='combined-scoring-snap-clock-v16.0'


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def ident(value, sport):
    if value is None or value == '':
        return ''
    if sport == 'CFB':
        return 'cfb:espn:'+str(int(value))
    return str(value)


def load_football(path, sport):
    """Return independent observations and final-game metadata, never fitted together.

    Callers MUST select strictly earlier games before fitting. Finals returned
    separately are only for subsequent evaluation. No market-price columns are
    read. No historical availability timestamp is invented.
    """
    import pyarrow.parquet as pq
    if sport not in ('NFL', 'CFB'):
        raise ValueError('Football source sport must be NFL or CFB')
    if sport == 'CFB':
        columns = ['game_id','id','season','homeTeamId','awayTeamId','homeTeamName','awayTeamName',
                   'homeFinalScore','awayFinalScore','status_type_completed','wallclock','period',
                   'pos_team_id','def_pos_team_id','down','distance','start.yardsToEndzone',
                   'start.adj_TimeSecsRem','start.pos_score_diff','pass_attempt','completion','sack','touchdown',
                   'rush','kneel_down','punt','fg_attempt','fg_made','xp_attempt','xp_made',
                   'two_point_conv_result','int','pos_fumble_lost','yds_rushed','yds_receiving',
                   'yds_sacked','yds_punted','yds_punt_return','passer_player_id','receiver_player_id',
                   'rusher_player_id','passer_player_name','receiver_player_name','rusher_player_name',
                   'penalty_flag','penalty_no_play','penalty_declined','penalty_offset','yds_penalty',
                   'end.down','end.distance','end.yardsToEndzone','firstD_by_penalty','drive.id']
    else:
        columns = ['game_id','play_id','season','week','home_team','away_team','home_score','away_score',
                   'time_of_day','qtr','posteam','defteam','down','ydstogo','yardline_100','game_seconds_remaining',
                   'score_differential','pass_attempt','complete_pass','sack','rush_attempt','qb_kneel','qb_spike',
                   'punt_attempt','field_goal_attempt','field_goal_result','extra_point_attempt','extra_point_result',
                   'two_point_attempt','two_point_conv_result','interception','fumble_lost','yards_gained',
                   'kick_distance','return_yards','play_type','touchdown','pass_touchdown','rush_touchdown','passer_player_id','receiver_player_id','rusher_player_id',
                   'passer_player_name','receiver_player_name','rusher_player_name','penalty','no_play',
                   'penalty_yards','penalty_team','first_down_penalty','fixed_drive','season_type',
                   'lateral_reception','lateral_rush','lateral_return']
    p = pq.ParquetFile(path)
    raw = p.read(columns=[c for c in columns if c in p.schema.names]).to_pylist()
    raw.sort(key=lambda r: (str(r['game_id']), int(r.get('id') if sport == 'CFB' else r.get('play_id') or 0)))
    games, rows, rejected = {}, [], Counter()
    for index, r in enumerate(raw):
        try:
            event = utc(r.get('wallclock') if sport == 'CFB' else r.get('time_of_day'))
            game = ('cfb:espn:' if sport == 'CFB' else '')+str(r['game_id'])
            home = ident(r.get('homeTeamId') if sport == 'CFB' else r.get('home_team'),sport)
            away = ident(r.get('awayTeamId') if sport == 'CFB' else r.get('away_team'),sport)
            quarter = int(r.get('period') if sport == 'CFB' else r.get('qtr'))
            if sport == 'CFB' and r.get('status_type_completed') is not True:
                raise ValueError('incomplete')
            if sport == 'NFL' and r.get('season_type') not in ('REG','POST'):
                raise ValueError('unsupported season type')
            hs = r.get('homeFinalScore') if sport == 'CFB' else r.get('home_score')
            aws = r.get('awayFinalScore') if sport == 'CFB' else r.get('away_score')
            if not all(finite(v) for v in (hs,aws)):
                raise ValueError('missing final identity')
            g = games.setdefault(game, {'id':game,'sport':sport,'season':int(r['season']),
                'home':home,'away':away,'homeName':r.get('homeTeamName',home),'awayName':r.get('awayTeamName',away),
                'firstObservedAt':event.isoformat(),'lastObservedAt':event.isoformat(),
                'actualHome':int(hs),'actualAway':int(aws),'players':{},'plays':0})
            g['firstObservedAt'] = min(g['firstObservedAt'],event.isoformat())
            g['lastObservedAt'] = max(g['lastObservedAt'],event.isoformat())
            offense = ident(r.get('pos_team_id') if sport == 'CFB' else r.get('posteam'),sport)
            defense = ident(r.get('def_pos_team_id') if sport == 'CFB' else r.get('defteam'),sport)
            if offense not in (home,away) or defense not in (home,away) or offense == defense:
                raise ValueError('possession identity')
            # Player outcomes used ONLY for evaluation, including observed OT.
            qb=ident(r.get('passer_player_id'),sport);receiver=ident(r.get('receiver_player_id'),sport);runner=ident(r.get('rusher_player_id'),sport)
            penalty = bool(r.get('penalty_flag') if sport=='CFB' else r.get('penalty'))
            negated = bool(r.get('penalty_no_play') if sport=='CFB' else r.get('no_play') or r.get('play_type')=='no_play')
            is_sack = bool(r.get('sack'))
            is_pass = bool(r.get('pass_attempt')) and not is_sack
            is_run = bool(r.get('rush') if sport=='CFB' else r.get('rush_attempt')) and not is_sack
            complete = bool(r.get('completion') if sport=='CFB' else r.get('complete_pass'))
            intercept = bool(r.get('int') if sport=='CFB' else r.get('interception'))
            y = r.get('yds_sacked') if is_sack and sport=='CFB' else r.get('yds_receiving') if is_pass and complete and sport=='CFB' else r.get('yds_rushed') if is_run and sport=='CFB' else r.get('yards_gained')
            yards = int(y) if finite(y) else 0
            if not negated:
                def stat(pid,name,amount):
                    if not pid:return
                    p=g['players'].setdefault(pid,{'team':offense,'stats':{},'name':pid})
                    p['stats'][name]=p['stats'].get(name,0)+amount
                for pid,key in [(qb,'passer_player_name'),(receiver,'receiver_player_name'),(runner,'rusher_player_name')]:
                    if pid and r.get(key):
                        g['players'].setdefault(pid,{'team':offense,'stats':{},'name':r[key]})['name']=r[key]
                if is_pass:
                    stat(qb,'passingAttempts',1);stat(qb,'completions',int(complete));stat(qb,'passingYards',yards if complete else 0);stat(qb,'interceptions',int(intercept))
                    if receiver:stat(receiver,'targets',1)
                    if complete:stat(receiver,'receptions',1);stat(receiver,'receivingYards',yards)
                if is_run:stat(runner,'carries',1);stat(runner,'rushingYards',yards)
                if is_sack and sport=='CFB':stat(qb,'carries',1);stat(qb,'rushingYards',yards)
            if not 1<=quarter<=4:
                raise ValueError('overtime not regulation training')
            clock = r.get('start.adj_TimeSecsRem') if sport=='CFB' else r.get('game_seconds_remaining')
            if not finite(clock):raise ValueError('clock unavailable')
            clock=int(clock)
            if r.get('xp_attempt') if sport=='CFB' else r.get('extra_point_attempt'):
                kind='extra_point';made=bool(r.get('xp_made')) if sport=='CFB' else r.get('extra_point_result')=='good'
            elif r.get('two_point_conv_result') in ('success','failure'):
                kind='two_point';made=r['two_point_conv_result']=='success'
            else:
                kind=None;made=False
            if kind:
                rows.append({'game':game,'at':event.isoformat(),'sport':sport,'o':offense,'d':defense,
                    'kind':kind,'made':int(made),'quarter':quarter,'clock':clock})
                # ESPN often attaches a PAT to the touchdown's play row.
                # Preserve BOTH observations, rather than dropping the TD.
                if not (sport=='CFB' and r.get('touchdown') and (is_run or is_pass)):continue
            down=r.get('down');distance=r.get('distance') if sport=='CFB' else r.get('ydstogo');field=r.get('start.yardsToEndzone') if sport=='CFB' else r.get('yardline_100')
            if not all(finite(v) for v in (down,distance,field)) or not 1<=down<=4 or not 1<=field<=99 or not 0<=distance<=100:
                raise ValueError('state unavailable')
            down,distance,field=int(down),max(1,int(distance)),int(field)
            # Use consecutive recorded snap starts; never substitute play-end
            # clocks, a fixed minimum, or next-quarter time as observed runoff.
            # Assigned in a second pass across accepted snapshots, so excluded
            # events do not silently lose their between-snap clock consumption.
            elapsed=None
            if penalty and negated:
                # Only an observed standalone, enforced no-play penalty is
                # modeled. Live-ball penalties/laterals remain explicit gaps.
                py=r.get('yds_penalty') if sport=='CFB' else r.get('penalty_yards')
                if isinstance(py,str):
                    try:py=float(py)
                    except ValueError:py=None
                if not finite(py):raise ValueError('penalty distance unavailable')
                if sport=='CFB':
                    nf=r.get('end.yardsToEndzone')
                    if not finite(nf):raise ValueError('penalty field unavailable')
                    yards=field-int(nf)
                else:yards=-int(py) if r.get('penalty_team')==r.get('posteam') else int(py)
                kind='penalty'
            elif negated or penalty:raise ValueError('unsupported live-ball penalty')
            elif is_sack:kind='sack'
            elif is_pass:kind='pass'
            elif is_run:kind='kneel' if r.get('kneel_down' if sport=='CFB' else 'qb_kneel') else 'rush'
            elif r.get('punt' if sport=='CFB' else 'punt_attempt'):kind='punt'
            elif r.get('fg_attempt' if sport=='CFB' else 'field_goal_attempt'):kind='field_goal'
            else:raise ValueError('unsupported play')
            if kind in ('pass','sack') and not qb or kind in ('rush','kneel') and not runner:
                raise ValueError('participant missing')
            if kind=='pass' and complete and not receiver:raise ValueError('receiver missing')
            punt=r.get('yds_punted') if sport=='CFB' else r.get('kick_distance')
            returned=r.get('yds_punt_return') if sport=='CFB' else r.get('return_yards')
            made=bool(r.get('fg_made')) if sport=='CFB' else r.get('field_goal_result')=='made'
            rows.append({'game':game,'at':event.isoformat(),'sport':sport,'o':offense,'d':defense,
                'kind':kind,'down':down,'distance':distance,'field':field,'clock':clock,'quarter':quarter,
                'script':int(r.get('start.pos_score_diff') if sport=='CFB' else r.get('score_differential') or 0),
                'elapsed':elapsed,'yards':yards,'complete':int(complete),'int':int(intercept),
                'fumble':int(bool(r.get('pos_fumble_lost') if sport=='CFB' else r.get('fumble_lost'))),
                'qb':qb,'receiver':receiver,'runner':runner,'made':int(made),'home':int(offense==home),
                'puntNet':int(punt or 0)-int(returned or 0),'drive':str(r.get('drive.id') if sport=='CFB' else r.get('fixed_drive')),
                'firstDownPenalty':bool(r.get('firstD_by_penalty') if sport=='CFB' else r.get('first_down_penalty'))})
            g['plays']+=1
        except (ValueError,TypeError,OverflowError) as e:
            rejected[str(e)]+=1
    groups=defaultdict(list)
    for r in rows:
        if r['kind'] not in ('extra_point','two_point'):
            groups[(r['game'],r['quarter'])].append(r)
    accepted=[]
    for group in groups.values():
        for i,r in enumerate(group):
            end=group[i+1]['clock'] if i+1<len(group) else (4-r['quarter'])*900
            elapsed=r['clock']-end
            if 0<=elapsed<=90:
                r['elapsed']=elapsed;accepted.append(r)
            else:rejected['snap-to-snap clock unavailable']+=1
    accepted.extend(r for r in rows if r['kind'] in ('extra_point','two_point'))
    return {'sport':sport,'rows':accepted,'games':games,'source':str(path),
        'sourceSha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'normalizerVersion':NORMALIZER_VERSION,
        'publicationAvailabilityVerified':False,'rejected':dict(rejected)}


def training_before(dataset, cutoff, excluded_game=None):
    """Whole-game embargo: even earlier plays of an in-progress game are excluded."""
    when=utc(cutoff)
    eligible={g['id'] for g in dataset['games'].values()
              if g['id']!=excluded_game and utc(g['lastObservedAt'])<when}
    return [r for r in dataset['rows'] if r['game'] in eligible and utc(r['at'])<when]
