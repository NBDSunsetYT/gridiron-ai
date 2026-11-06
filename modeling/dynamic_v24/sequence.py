"""Forward event reconstruction for conditional next-event diagnostics.

Source rows are edition-corrected archives, not proof of the original live feed
arrival times. No future box, WP, EPA, drive-result or final-score features.
"""
from collections import defaultdict,Counter
from datetime import datetime,timezone
import math,re
from .state import DynamicState
from ..integration_v22.datasets import protected
from ..fullgame_v23.ordering import canonical_order
from ..fullgame_v23.replay import finite

NFL_COLUMNS=['game_id','play_id','game_date','home_team','away_team','posteam','defteam','qtr','quarter_seconds_remaining','down','ydstogo','yardline_100','score_differential','play_type','no_play','penalty','penalty_yards','pass_attempt','rush_attempt','sack','complete_pass','incomplete_pass','interception','fumble_lost','yards_gained','field_goal_attempt','field_goal_result','punt_attempt','touchdown','td_team','qb_spike','qb_kneel','fixed_drive','receiver_player_id','passer_player_id','rusher_player_id','time_of_day']
CFB_COLUMNS=['game_id','id','sequenceNumber','wallclock','homeTeamId','awayTeamId','pos_team_id','def_pos_team_id','period','clock.displayValue','down','distance','start.yardsToEndzone','start.pos_score_diff','pass_attempt','completion','rush','sack','int','pos_fumble_lost','yds_sacked','yds_rushed','yds_receiving','penalty_flag','penalty_no_play','type.text','text','punt','fg_attempt','fg_made','touchdown','offense_score_play','drive.id','receiver_player_id','passer_player_id','rusher_player_id']
NBA_COLUMNS=['game_id','id','sequence_number','game_date_time','period_number','clock_display_value','type_text','text','team_id','athlete_id_1','athlete_id_2','athlete_id_3','home_team_id','away_team_id','shooting_play','points_attempted','scoring_play','score_value','coordinate_x','coordinate_y']
def clock(v):
    m,s=str(v).split(':');return float(m)*60+float(s)
def sid(v):
    try:return str(int(v)) if v is not None and math.isfinite(float(v)) else None
    except (ValueError,TypeError):return None
def football_game(raw,sport):
    nfl=sport=='NFL';rows=sorted(raw,key=lambda r:r['play_id'] if nfl else finite(r.get('sequenceNumber',r.get('id'))));first=rows[0];teams=[str(first['home_team']),str(first['away_team'])] if nfl else ['cfb:espn:'+sid(first['homeTeamId']),'cfb:espn:'+sid(first['awayTeamId'])];gid=str(first['game_id']) if nfl else 'cfb:espn:'+sid(first['game_id']);state=DynamicState(sport,teams);result=[];seen=set();drives=[];current=None;errors=Counter()
    for r in rows:
        uid=str(r.get('play_id' if nfl else 'id'))
        if uid in seen:errors['duplicate_id']+=1;continue
        seen.add(uid);team=r.get('posteam') if nfl else 'cfb:espn:'+str(sid(r.get('pos_team_id')));q=int(finite(r.get('qtr' if nfl else 'period')))
        if team not in teams or not 1<=q<=4:continue
        try:c=finite(r['quarter_seconds_remaining']) if nfl else clock(r['clock.displayValue']);state.tick(q,c)
        except (ValueError,KeyError,TypeError):errors['invalid_clock']+=1;continue
        no_play=bool(r.get('no_play' if nfl else 'penalty_no_play'));penalty=bool(r.get('penalty' if nfl else 'penalty_flag'))
        down=r.get('down');distance=r.get('ydstogo' if nfl else 'distance');field=r.get('yardline_100' if nfl else 'start.yardsToEndzone');drive=str(r.get('fixed_drive' if nfl else 'drive.id'))
        if no_play:
            state.observe({'id':uid,'team':team,'kind':'penalty','gain':0});continue
        kind='pass' if r.get('pass_attempt') or r.get('sack') else 'rush' if r.get('rush_attempt' if nfl else 'rush') else 'field_goal' if r.get('field_goal_attempt' if nfl else 'fg_attempt') else 'punt' if r.get('punt_attempt' if nfl else 'punt') else None
        if kind is None or down is None or field is None:continue
        if r.get('qb_spike' if nfl else 'kneel_down') or r.get('qb_kneel'):errors['clock_management_excluded']+=1;continue
        # The raw source explicitly provides the pre-snap differential.
        diff=finite(r.get('score_differential' if nfl else 'start.pos_score_diff'));state.score[team]=max(diff,0);state.score[next(t for t in teams if t!=team)]=max(-diff,0)
        base,dynamic=state.features(team,down=int(down),distance=finite(distance,10),field=finite(field));base.update(team=team,opponent=next(t for t in teams if t!=team));features={**base,**dynamic};row={'eventId':uid,'gameId':gid,'sport':sport,'base':base,'dynamic':dynamic,'features':features,'y':kind,'clock':c,'quarter':q,'team':team,'kind':kind};result.append(row)
        comp=bool(r.get('complete_pass' if nfl else 'completion'));gain=finite(r.get('yards_gained')) if nfl else finite(r.get('yds_sacked')) if r.get('sack') else finite(r.get('yds_receiving')) if kind=='pass' and comp else finite(r.get('yds_rushed'));td=bool(r.get('touchdown')) and (r.get('td_team')==team if nfl else bool(r.get('offense_score_play')));fg=r.get('field_goal_result')=='made' if nfl else bool(r.get('fg_made'));turn=bool(r.get('interception' if nfl else 'int')) or bool(r.get('fumble_lost' if nfl else 'pos_fumble_lost'))
        if current is None or (current['drive'],current['team'])!=(drive,team):
            if current:drives.append(current)
            current={'drive':drive,'team':team,'features':dict(features),'base':dict(base),'dynamic':dict(dynamic),'eventId':uid,'gameId':gid,'sport':sport,'y':False}
        current['y']=current['y'] or td or kind=='field_goal' and fg
        row['template']={'o':team,'kind':'sack' if r.get('sack') else kind,'down':int(down),'distance':finite(distance,10),'field':finite(field),'clock':(4-q)*900+c,'quarter':q,'script':diff,'yards':gain,'complete':int(comp),'int':int(bool(r.get('interception' if nfl else 'int'))),'fumble':int(bool(r.get('fumble_lost' if nfl else 'pos_fumble_lost'))),'elapsed':None,'made':fg}
        actor=r.get('passer_player_id') if kind=='pass' else r.get('rusher_player_id');failed_fourth=int(down)==4 and kind in ('pass','rush') and gain<finite(distance,10) and not penalty
        state.observe({'id':uid,'team':team,'kind':'sack' if r.get('sack') else kind,'actor':str(actor) if actor else None,'gain':gain,'success':gain>=finite(distance,10),'turnover':turn,'points':6 if td else 3 if kind=='field_goal' and fg else 0,'possessionEnd':td or turn or failed_fourth or kind in ('field_goal','punt'),'driveScored':td or kind=='field_goal' and fg})
        # Scoring/turnover consequences become features only after observation.
    if current:drives.append(current)
    return {'gameId':gid,'teams':teams,'actions':result,'drives':drives,'errors':dict(errors),'tier':'conditional_next_event','fullPregameEvidence':False}

def nba_game(raw,game):
    gid='nba:espn:'+str(int(raw[0]['game_id']));teams=list(game['teams']);owners={sid(p['athlete_id']):str(p['team_id']) for p in game['players']};state=DynamicState('NBA',teams);known={t:set() for t in teams};errors=Counter();shots=[];actions=[]
    # The observed starting five is a conditional initial state, not a claim
    # of a recovered pregame announcement. No future lineup constraint solver.
    for t in teams:
        starters=[sid(p['athlete_id']) for p in game['players'] if str(p['team_id'])==t and p.get('starter')]
        if len(starters)!=5:return {'gameId':gid,'shots':[],'actions':[],'errors':{'missing_observed_starting_five':1}}
        state.set_lineup(t,starters);known[t].update(starters)
    try:rows=canonical_order(raw)
    except ValueError:return {'gameId':gid,'shots':[],'actions':[],'errors':{'ambiguous_correction_order':1}}
    seen=set();last_period=1
    for r in rows:
        uid=str(r['id']);q=int(r['period_number']);typ=(r.get('type_text') or '').lower();text=(r.get('text') or '').lower();actor=sid(r.get('athlete_id_1'));team=owners.get(actor) or sid(r.get('team_id'));rem=clock(r['clock_display_value'])
        if uid in seen:errors['duplicate_id']+=1;continue
        seen.add(uid)
        if q!=last_period:
            # Later-period lineups remain UNKNOWN until forward evidence
            # establishes them. Never infer them from future actions.
            state.lineups={};known={t:set() for t in teams};last_period=q
        if q>4:continue
        if team not in teams:
            try:state.tick(q,rem)
            except ValueError:errors['clock_revision']+=1
            continue
        # Pre-next-event features use the previous observed time; shot-release
        # conditioning below may additionally use this shot's known location.
        base,dynamic=state.features(team,actor=actor);base.update(team=team,opponent=next(t for t in teams if t!=team),workload_minutes_missing=float(team not in state.lineups))
        if team not in state.lineups:
            for key in ('workload_actor_minutes','workload_consecutive_minutes','workload_rest_since_exit'):base[key]=0
            dynamic['fatigue_stint_square']=0
        try:state.tick(q,rem)
        except ValueError:errors['clock_revision']+=1;continue
        if 'substitution' in typ:
            incoming=actor;outgoing=sid(r.get('athlete_id_2'))
            if team in state.lineups and outgoing in state.lineups[team] and incoming not in state.lineups[team]:state.set_lineup(team,[incoming if p==outgoing else p for p in state.lineups[team]])
            else:state.lineups.pop(team,None);errors['unidentified_forward_lineup']+=1
            known[team].add(incoming);continue
        made=' makes ' in text if 'free throw' in text else bool(r.get('scoring_play'));value=int(finite(r.get('points_attempted')));shot=bool(r.get('shooting_play')) and value in (2,3)
        action='two' if shot and value==2 else 'three' if shot else 'free_throws' if 'free throw' in text else 'turnover' if 'turnover' in typ or typ in ('traveling','double dribble','palming') else None
        ordinary_first_ft=bool(re.search(r'free throw 1 of [23]',text))
        if action and (action!='free_throws' or ordinary_first_ft):
            # Current shooter/location cannot enter pre-action selection.
            b={k:v for k,v in base.items() if not k.startswith('workload_actor') and k not in ('workload_consecutive_minutes','workload_fouls','workload_rest_since_exit')};d={k:v for k,v in dynamic.items() if not k.startswith('recent_actor') and k not in ('fatigue_stint_square','fatigue_volume_interaction')};actions.append({'gameId':gid,'eventId':uid,'sport':'NBA','base':b,'dynamic':d,'features':{**b,**d},'y':action})
        if shot:
            b=dict(base);b.update(actor=actor or 'unknown',shotValue=value,shotX=finite(r.get('coordinate_x')),shotY=finite(r.get('coordinate_y')),shotLocationMissing=float(r.get('coordinate_x') is None or r.get('coordinate_y') is None));shots.append({'gameId':gid,'eventId':uid,'sport':'NBA','base':b,'dynamic':dynamic,'features':{**b,**dynamic},'y':int(made),'observedLineupKnown':team in state.lineups,'conditioning':'Known shooter and shot location at release; not a pre-possession actor forecast'})
        # Unknown later-period lineups are explicitly absent, not backfilled.
        if actor and team in state.lineups and actor not in state.lineups[team]:errors['offcourt_source_action']+=1;state.lineups.pop(team,None)
        state.observe({'id':uid,'team':team,'kind':'foul' if 'foul' in typ else action or typ,'actor':actor,'success':made if shot else False,'gain':int(made)*value if shot else 0,'points':int(finite(r.get('score_value'))) if r.get('scoring_play') else 0,'turnover':action=='turnover','possessionEnd':action=='turnover' or shot and made})
    return {'gameId':gid,'shots':shots,'actions':actions,'errors':dict(errors),'lineupScope':'Forward-only; later-period unknown lineups are not reconstructed from future events','tier':'conditional_next_event'}
