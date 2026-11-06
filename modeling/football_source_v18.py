"""Point-cutoff transition observations from the existing public PBP archive.

Final scores and final player totals are never included in fitting metadata.
Unverified return flags remain null. Missing kickoff data is not own-25 data.
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import hashlib,math
import pyarrow.parquet as pq
from .fit import utc
def observed_flag(value):
    if isinstance(value,bool):return value
    if isinstance(value,(int,float)) and math.isfinite(value) and value in (0,1):return bool(value)
    return None

def eligible_training(rows,cutoff,banned):
    """One frozen protection set per job; no policy-file read per play."""
    cut=utc(cutoff)
    if any(utc(r['at'])>=cut for r in rows):raise ValueError('Training rows must strictly precede cutoff')
    return [r for r in rows if r['game'] not in banned and r['at'][:4]>=str(int(cutoff[:4])-1)]

def transition_evidence(paths,sport,cutoff,_raw_cache=None):
    cutoff=utc(cutoff);out=[];versions=[];rejected=defaultdict(int)
    for path in paths:
        path=Path(path);cache=_raw_cache if _raw_cache is not None else {};identity=(str(path.resolve()),path.stat().st_size,path.stat().st_mtime_ns)
        if identity in cache:
            version,raw=cache[identity];versions.append(version)
        else:
            version=hashlib.sha256(path.read_bytes()).hexdigest();versions.append(version);schema=pq.ParquetFile(path).schema.names
        names=['game_id','play_id','id','qtr','period','time_of_day','wallclock','posteam','defteam','pos_team_id','def_pos_team_id','down','yardline_100','start.yardsToEndzone','game_seconds_remaining','start.adj_TimeSecsRem','score_differential','start.pos_score_diff','kickoff_attempt','kickoff_play','punt_attempt','punt','interception','int','fumble_lost','pos_fumble_lost','return_touchdown','return_yards','yds_punt_return','yds_int_return','yds_fumble_return','yds_kickoff_return','extra_point_attempt','xp_attempt','two_point_attempt','two_point_conv_result','fixed_drive','drive.id','field_goal_attempt','fg_attempt','pass_attempt','rush_attempt','rush','sack','no_play','penalty_no_play','type.text','out_of_bounds','qb_spike']
        from .integration_v22.datasets import protected
        banned=protected();hidden=[int(g.split(':')[-1]) for g in banned if g.startswith('cfb:espn:')] if sport=='CFB' else [g for g in banned if g[:4].isdigit() and '_' in g]
        filters=[('game_id','not in',hidden)] if hidden else None
        if identity not in cache:
            raw=pq.read_table(path,columns=[k for k in names if k in schema],filters=filters).to_pylist();raw.sort(key=lambda r:(str(r['game_id']),int(r.get('play_id') or r.get('id') or 0)));cache[identity]=(version,raw)
        seen=set();previous={};half_seen=set()
        def ident(v):return ('cfb:espn:'+str(int(v))) if sport=='CFB' and v is not None else v
        for r in raw:
            try:at=utc(r.get('time_of_day') if sport=='NFL' else r.get('wallclock'))
            except ValueError:rejected['unverified_timestamp']+=1;continue
            if at>=cutoff:continue
            gid=('cfb:espn:' if sport=='CFB' else '')+str(r['game_id']);q=int(r.get('qtr') or r.get('period') or 0)
            if not 1<=q<=4:continue
            team=ident(r.get('posteam') if sport=='NFL' else r.get('pos_team_id'));clock=r.get('game_seconds_remaining') if sport=='NFL' else r.get('start.adj_TimeSecsRem');diff=r.get('score_differential') if sport=='NFL' else r.get('start.pos_score_diff');base={'game':gid,'at':at.isoformat(),'sport':sport,'team':team};typ=str(r.get('type.text') or '')
            if r.get('extra_point_attempt') or r.get('xp_attempt') or r.get('two_point_attempt') or r.get('two_point_conv_result') in ('success','failure'):
                if clock is not None and diff is not None and math.isfinite(clock) and math.isfinite(diff):out.append({**base,'kind':'two_point' if r.get('two_point_attempt') or r.get('two_point_conv_result') in ('success','failure') else 'extra_point','clock':int(clock),'script':int(diff)})
            for kind,flag in [('interception',r.get('interception') or r.get('int')),('fumble',r.get('fumble_lost') or r.get('pos_fumble_lost')),('punt',r.get('punt_attempt') or r.get('punt')),('kickoff',r.get('kickoff_attempt') or r.get('kickoff_play'))]:
                if not flag:continue
                td=observed_flag(r.get('return_touchdown'))
                if td is None and sport=='CFB' and typ:
                    known={'interception':('Pass Interception','Interception Return Touchdown'),'fumble':('Fumble Recovery (Opponent)','Fumble Return Touchdown'),'punt':('Punt','Punt Return Touchdown'),'kickoff':('Kickoff','Kickoff Return Touchdown')}[kind]
                    td=typ.endswith('Return Touchdown') if typ in known else None
                returned=r.get('return_yards') if sport=='NFL' else r.get({'interception':'yds_int_return','fumble':'yds_fumble_return','punt':'yds_punt_return','kickoff':'yds_kickoff_return'}[kind]);out.append({**base,'kind':kind,'returnTouchdown':None if td is None else bool(td),'returnYards':None if returned is None else float(returned)})
            live=r.get('down') is not None and any(r.get(k) for k in ['pass_attempt','rush_attempt','rush','sack','punt_attempt','punt','field_goal_attempt','fg_attempt']) and not (r.get('no_play') or r.get('penalty_no_play'))
            if live:
                field=r.get('yardline_100') if sport=='NFL' else r.get('start.yardsToEndzone')
                out.append({**base,'kind':'play_metadata','down':r.get('down'),'field':field,'isSpike':observed_flag(r.get('qb_spike')),'outOfBounds':observed_flag(r.get('out_of_bounds'))})
            if live and team:
                drive=str(r.get('fixed_drive') if sport=='NFL' else r.get('drive.id'));key=(gid,team,drive);field=r.get('yardline_100') if sport=='NFL' else r.get('start.yardsToEndzone')
                if key not in seen and field is not None and 0<float(field)<100:
                    prev=previous.get(gid);cause=None;half_key=(gid,1 if q<=2 else 2)
                    if prev:
                        if prev.get('kickoff_attempt') or prev.get('kickoff_play'):cause='kickoff' if half_key not in half_seen else 'post_score'
                        elif prev.get('punt_attempt') or prev.get('punt'):cause='post_punt'
                        elif prev.get('interception') or prev.get('int') or prev.get('fumble_lost') or prev.get('pos_fumble_lost') or prev.get('field_goal_attempt') or prev.get('fg_attempt'):cause='post_turnover'
                    if cause:out.append({**base,'kind':'drive_start','cause':cause,'field':int(field),'positionSource':'Observed receiving offense first legal snap after actual transition'})
                    seen.add(key);half_seen.add(half_key)
            # Retain kicks/turnovers while scanning administrative rows up to
            # the first receiving snap; do not infer a cause from a final score.
            if live or any(r.get(k) for k in ['kickoff_attempt','kickoff_play','punt_attempt','punt','interception','int','fumble_lost','pos_fumble_lost','field_goal_attempt','fg_attempt']):previous[gid]=r
    return {'cutoff':cutoff.isoformat(),'sourceVersion':hashlib.sha256('|'.join(versions).encode()).hexdigest(),'rows':out,'rejected':dict(rejected),'usesFinalScores':False}

def augment_rows(rows,evidence,position_files=()):
    from copy import deepcopy
    index=defaultdict(list)
    for r in evidence['rows']:
        if r['kind']=='play_metadata':index[(r['game'],r['at'],r['team'],r['down'],r['field'])].append(r)
    positions={}
    for path in position_files:
        path=Path(path)
        if not path.exists():continue
        schema=pq.ParquetFile(path).schema.names
        if not {'game_id','player_id','position'}.issubset(schema):continue
        for r in pq.read_table(path,columns=['game_id','player_id','position']).to_pylist():
            if r.get('player_id') and r.get('position'):positions[(str(r['game_id']),r['player_id'])]=r['position']
    result=[]
    for original in rows:
        r=deepcopy(original);matches=index.get((r['game'],utc(r['at']).isoformat(),r['o'],r.get('down'),r.get('field')),[])
        for field in ['isSpike','outOfBounds']:
            values={m[field] for m in matches if m[field] is not None}
            if len(values)==1:
                value=next(iter(values))
                if field=='isSpike' and value:r['kind']='spike'
                else:r[field]=value
        for role in ['qb','receiver','runner']:
            if r.get(role) and (r['game'],r[role]) in positions:r[role+'Position']=positions[(r['game'],r[role])]
        result.append(r)
    return result
