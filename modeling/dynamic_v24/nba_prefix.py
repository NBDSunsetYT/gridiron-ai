"""Observed first-period ledger prefix; no future lineup smoothing."""
import re,math
from ..fullgame_v23.accounting import BasketballLedger
from ..fullgame_v23.ordering import canonical_order
from ..fullgame_v23.replay import finite
from .sequence import sid,clock
def checkpoint(game,events,after_remaining=360):
    teams=list(game['teams']);owners={sid(p['athlete_id']):str(p['team_id']) for p in game['players'] if float(p.get('minutes') or 0)>0};ledger=BasketballLedger(teams,owners)
    for t in teams:
        starters=[sid(p['athlete_id']) for p in game['players'] if str(p['team_id'])==t and p.get('starter') and float(p.get('minutes') or 0)>0];ledger.set_lineup(t,starters)
    previous=720;first=None;seen=set();count=0
    for r in canonical_order(events):
        if int(r['period_number'])!=1:break
        uid=str(r['id'])
        if uid in seen:continue
        seen.add(uid);count+=1;remaining=clock(r['clock_display_value']);ledger.tick(previous-remaining);previous=remaining;typ=(r.get('type_text') or '').lower();text=(r.get('text') or '').lower();p=sid(r.get('athlete_id_1'));b=sid(r.get('athlete_id_2'));c=sid(r.get('athlete_id_3'));team=owners.get(p) or sid(r.get('team_id'));reset=False;off=None
        if team not in teams:continue
        if 'substitution' in typ:
            if p not in owners or b not in owners or owners[p]!=owners[b] or b not in ledger.lineups[team]:raise ValueError('Prefix substitution cannot be verified')
            ledger.set_lineup(team,[p if v==b else v for v in ledger.lineups[team]]);continue
        if r.get('shooting_play') and int(finite(r.get('points_attempted'))) in (2,3):
            if first is None:first=team
            made=bool(r.get('scoring_play'));assist=b if made and 'assist' in text and owners.get(b)==team else None;block=next((v for v in (b,c) if owners.get(v) in teams and owners[v]!=team),None) if 'block' in text else None;ledger.shot(team,p,int(r['points_attempted']),made,assist,block);reset=made;off=next(t for t in teams if t!=team) if made else None
        elif 'free throw' in text:
            m=re.search(r'free throw (\d) of (\d)',text)
            if not m:raise ValueError('Unverified FT trip in observed prefix')
            ledger.free_throw(team,p,' makes ' in text,m[1]==m[2],technical='technical' in text);reset=m[1]==m[2] and ' makes ' in text and 'technical' not in text;off=next(t for t in teams if t!=team) if reset else None
        elif 'rebound' in text:
            if ledger.live_rebound is not None:
                defensive=team!=ledger.live_rebound;ledger.rebound(team,p,team_rebound=p not in owners);reset=defensive;off=team if defensive else None
        elif 'turnover' in typ or typ in ('traveling','double dribble','palming'):
            if first is None:first=team
            if p in owners:ledger.turnover(team,p,b if 'steal' in text and owners.get(b)!=team else None)
            reset=True;off=next(t for t in teams if t!=team)
        elif 'foul' in typ and 'technical' not in typ and p in owners:ledger.foul(team,p)
        if reset and off and remaining<=after_remaining:
            elapsed=720-remaining;ledger.verify(elapsed)
            home=next(t for t,v in game['teams'].items() if v['team_home_away']=='home');away=next(t for t in teams if t!=home)
            if ledger.team[home]['points']!=r.get('home_score') or ledger.team[away]['points']!=r.get('away_score'):raise ValueError('Observed prefix scoring does not reconcile with source anchor')
            if any(p in ledger.lineups[t] and ledger.players[p]['fouls']>=6 for t in teams for p in ledger.lineups[t]):raise ValueError('Disqualified actual lineup')
            return {'ledger':ledger,'period':1,'remaining':remaining,'offense':off,'firstPossessionTeam':first,'shotClock':24,'prefixEvents':count,'actualClockElapsed':elapsed,'scope':'Observed first-period snapshot after verified possession reset. No later box counts used to fill actual statistics.'}
    raise ValueError('No supported first-period checkpoint')
