"""Mode A source event adapter, including primary-book accounting repairs.

This is deliberately not pregame feature reconstruction. It preserves source
play IDs and anonymous TEAM credits and never infers a starter from a final box.
"""
from collections import Counter
import re
from .replay import ordered_rows,finite,pid,clock_seconds
from .gamebook import raw_kind

def cfb_kernel_rows(raw,game):
    teams=game['teams'];owners={p:t for t,v in teams.items() for p in v['players']};out=[];skipped=Counter()
    for r in ordered_rows(raw,'CFB'):
        if r.get('_duplicateOf'):skipped['independent_primary_duplicate']+=1;continue
        q=int(r.get('period') or 0);team=pid(r.get('pos_team_id'),'CFB');primary=r.get('_primaryAccounting') or {};kind=primary.get('kind',raw_kind(r));no_play=primary.get('noPlay',bool(r.get('penalty_no_play')) or bool(re.search(r'\bNO PLAY\b',r.get('text',''),re.I)))
        if not 1<=q<=4 or team not in teams or kind is None:skipped['not_supported_regulation_action']+=1;continue
        # A credited live-ball penalty has a reconciled stat but not yet a
        # complete joint spot/enforcement law. Do not turn it into a free play.
        if no_play or r.get('penalty_flag') or 'PENALTY' in r.get('text',''):
            skipped['penalty_not_jointly_modeled']+=1;continue
        if kind=='spike':skipped['team_spike_separate_replay_only']+=1;continue
        if kind not in ('pass','rush','sack','kneel','punt','field_goal'):continue
        if r.get('down') is None or r.get('start.yardsToEndzone') is None or not 0<float(r['start.yardsToEndzone'])<100:skipped['missing_state']+=1;continue
        def actor(name):
            value=pid(r.get(name+'_player_id'),'CFB');return value if value in owners and owners[value]==team else ''
        qb=actor('passer');runner=actor('rusher');receiver=actor('receiver')
        if primary.get('actorId'):
            if kind in ('pass','sack'):qb=primary['actorId']
            elif kind=='rush':runner=primary['actorId']
        complete=kind=='pass' and primary.get('complete',bool(r.get('completion')) or r.get('type.text')=='Passing Touchdown')
        yards=primary.get('yards')
        if yards is None:yards=finite(r.get('yds_sacked')) if kind=='sack' else finite(r.get('yds_receiving')) if complete else finite(r.get('yds_rushed')) if kind in ('rush','kneel') else 0
        if kind=='sack' and yards>0:raise ValueError('Contradictory source sack gain')
        out.append({'sourcePlayId':str(r['id']),'game':game['id'],'at':game['at'],'sport':'CFB','o':team,'d':next(t for t in teams if t!=team),'kind':kind,'down':int(r['down']),'distance':max(1,finite(r.get('distance'),10)),'field':float(r['start.yardsToEndzone']),'clock':(4-q)*900+clock_seconds(r['clock.displayValue']),'quarter':q,'script':finite(r.get('start.pos_score_diff')),'elapsed':None,'yards':int(yards),'complete':int(complete),'int':int(bool(r.get('int'))),'fumble':int(bool(r.get('pos_fumble_lost'))),'qb':qb,'runner':runner,'receiver':receiver,'made':int(primary.get('made',bool(r.get('fg_made')) or r.get('type.text')=='Field Goal Good')),'puntNet':finite(r.get('yds_punted'))-finite(r.get('yds_punt_return')),'outOfBounds':bool(re.search(r'out of bounds|out-of-bounds',r.get('text',''),re.I)),'drive':str(r.get('drive.id')),'firstDownPenalty':False,'independentlyCorrected':bool(primary)})
    for i,r in enumerate(out[:-1]):
        following=out[i+1]
        if r['quarter']==following['quarter']:
            delta=r['clock']-following['clock']
            if 0<=delta<=90:r['elapsed']=delta
    return out,{'rows':len(out),'independentlyCorrectedRows':sum(r['independentlyCorrected'] for r in out),'anonymousQuarterbackRows':sum(r['kind'] in ('pass','sack') and not r['qb'] for r in out),'skipped':dict(skipped),'finalBoxConditioning':'mechanics_only','missingIdentityMeans':'TEAM, never an arbitrary quarterback'}

def nfl_kernel_rows(raw,game):
    owners={p:t for t,v in game['teams'].items() for p in v['players']};out=[];skipped=Counter();ordered=ordered_rows(raw,'NFL')
    for i,r in enumerate(ordered):
        team=r.get('posteam');kind='sack' if r.get('sack') else 'kneel' if r.get('qb_kneel') else 'pass' if r.get('pass_attempt') else 'rush' if r.get('rush_attempt') else 'punt' if r.get('punt_attempt') else 'field_goal' if r.get('field_goal_attempt') else None
        if r.get('qtr',0)>4 or team not in game['teams'] or not kind or r.get('extra_point_attempt') or r.get('two_point_attempt'):continue
        if r.get('penalty') or r.get('no_play'):skipped['penalty_not_jointly_modeled']+=1;continue
        if r.get('down') is None or r.get('yardline_100') is None or not 0<float(r['yardline_100'])<100:skipped['missing_state']+=1;continue
        def actor(name):
            p=r.get(name+'_player_id');return p if owners.get(p)==team else ''
        complete=kind=='pass' and bool(r.get('complete_pass'));yards=finite(r.get('passing_yards')) if complete else finite(r.get('rushing_yards')) if kind in ('rush','kneel') else finite(r.get('yards_gained')) if kind=='sack' else 0;elapsed=None
        if i+1<len(ordered) and ordered[i+1].get('qtr')==r['qtr']:
            delta=finite(r['quarter_seconds_remaining'])-finite(ordered[i+1].get('quarter_seconds_remaining'))
            if 0<=delta<=90:elapsed=delta
        out.append({'sourcePlayId':str(r['play_id']),'game':game['id'],'at':game['at'],'sport':'NFL','o':team,'d':next(t for t in game['teams'] if t!=team),'kind':kind,'down':int(r['down']),'distance':max(1,finite(r.get('ydstogo'),10)),'field':float(r['yardline_100']),'clock':finite(r.get('game_seconds_remaining')),'quarter':int(r['qtr']),'script':finite(r.get('score_differential')),'elapsed':elapsed,'yards':int(yards),'complete':int(complete),'int':int(bool(r.get('interception'))),'fumble':int(bool(r.get('fumble_lost'))),'qb':actor('passer'),'runner':actor('rusher'),'receiver':actor('receiver'),'made':int(r.get('field_goal_result')=='made'),'puntNet':finite(r.get('kick_distance'))-finite(r.get('return_yards')),'outOfBounds':bool(r.get('out_of_bounds')),'drive':str(r.get('fixed_drive')),'firstDownPenalty':False})
    return out,{'rows':len(out),'skipped':dict(skipped),'sourceIdsRetained':True,'finalBoxConditioning':'mechanics_only'}
