"""Official-box-checked NBA full-event replay and constrained court accounting."""
from collections import Counter,defaultdict
import re,math
from .court import game_exposures,player_id
from .replay import name_key,nba_book_players,clock_seconds,finite
from .modes import Mode,label
from .ordering import canonical_order
def replay(game,events,book_text,ctx):
    if ctx['mode']!=Mode.MECHANICS:raise ValueError('Actual NBA substitutions/boxes cannot enter pregame forecasts')
    exposure=game_exposures(game,events);teams=list(game['teams']);home=next(t for t,v in game['teams'].items() if v['team_home_away']=='home');away=next(t for t in teams if t!=home);owners={player_id(p['athlete_id']):str(p['team_id']) for p in game['players']};catalog=defaultdict(set)
    for p in game['players']:catalog[(str(p['team_id']),name_key(p['athlete_display_name']))].add(player_id(p['athlete_id']))
    official=nba_book_players(book_text,away,home);book={};unmapped=[]
    for p in official:
        ids=catalog[(p['team'],name_key(p['name']))]
        if len(ids)!=1:unmapped.append({'team':p['team'],'name':p['name']});continue
        book[next(iter(ids))]=p
    stats=defaultdict(Counter);unresolved=[];score={t:0 for t in teams};seen=set();dup=0;court={(r['eventId'],r['team']):r['players'] for r in exposure['eventCourts']};offcourt=[];foul_events=Counter();team_events=Counter();possession=Counter();last_shooter=None
    events=canonical_order(events)
    explicit_fouls={(r['period_number'],r['clock_display_value'],player_id(r.get('athlete_id_1'))) for r in events if 'foul' in str(r.get('type_text','')).lower() and 'turnover' not in str(r.get('type_text','')).lower() and 'technical' not in str(r.get('type_text','')).lower()}
    for r in events:
        event=str(r['id']);typ=(r.get('type_text') or '').lower();text=(r.get('text') or '');low=text.lower();p=player_id(r.get('athlete_id_1'));second=player_id(r.get('athlete_id_2'));third=player_id(r.get('athlete_id_3'));team=owners.get(p);raw_team=str(int(r['team_id'])) if r.get('team_id') is not None and math.isfinite(r['team_id']) else None
        if event in seen:dup+=1;continue
        seen.add(event)
        def credit(pid,k,n=1):
            if pid not in owners:unresolved.append({'event':event,'reason':'unmapped_actor','stat':k});return
            floor=court.get((event,owners[pid]));
            if floor is not None and pid not in floor:offcourt.append({'event':event,'player':pid,'stat':k})
            stats[pid][k]+=n
        value=int(finite(r.get('score_value')));scoring=bool(r.get('scoring_play'));shooting=bool(r.get('shooting_play'));attempt=int(finite(r.get('points_attempted')))
        if 'free throw' in low:
            credit(p,'freeThrowAttempts');made=' makes ' in low
            if made:credit(p,'freeThrowsMade');credit(p,'points');score[team]+=1
            # Technical/dead-ball FT administration is not treated as an
            # additional possession or a rebound on earlier missed FTs.
            continue
        if shooting and attempt in (2,3):
            made=scoring and value in (2,3);credit(p,'fieldGoalAttempts');credit(p,'threePointAttempts',int(attempt==3));
            if made:
                credit(p,'fieldGoalsMade');credit(p,'threePointersMade',int(attempt==3));credit(p,'points',value);score[team]+=value;possession[team]+=1
                if ' assists)' in low or ' assists' in low:
                    if second==p:unresolved.append({'event':event,'reason':'self_assist'})
                    else:credit(second,'assists')
            if ' blocks ' in low or ' block' in low:
                blocker=second if second in owners and owners[second]!=team else third
                if blocker:credit(blocker,'blocks')
            last_shooter=team;continue
        if 'offensive rebound' in low or 'defensive rebound' in low:
            if p in owners:credit(p,'offensiveRebounds' if 'offensive rebound' in low else 'defensiveRebounds')
            else:team_events['rebound']+=1
            if 'defensive rebound' in low and last_shooter:possession[last_shooter]+=1
            continue
        if 'turnover' in typ or typ in ('traveling','double dribble','palming'):
            if p in owners:credit(p,'turnovers');possession[team]+=1
            else:team_events['turnover']+=1
            if 'offensive foul' in typ and p in owners and (r['period_number'],r['clock_display_value'],p) not in explicit_fouls:credit(p,'fouls')
            if 'steal' in low and second in owners:credit(second,'steals')
            continue
        if 'foul' in typ:
            # Personal box PF excludes technical, defensive three seconds,
            # delay-of-game and team fouls. Preserve administration separately.
            if any(k in typ for k in ['technical','defensive three','double technical']):team_events['technical_or_administrative_foul']+=1
            elif p in owners:credit(p,'fouls');foul_events[p]+=1
    comparisons=[];minutes=[];columns=['points','fieldGoalsMade','fieldGoalAttempts','threePointersMade','threePointAttempts','freeThrowsMade','freeThrowAttempts','offensiveRebounds','defensiveRebounds','assists','steals','blocks','turnovers','fouls']
    for pid,p in book.items():
        for k in columns:comparisons.append({'player':pid,'team':p['team'],'stat':k,'replayed':stats[pid][k],'official':p['stats'][k],'equal':stats[pid][k]==p['stats'][k]})
        lo,hi=exposure['players'][pid]['minuteBounds'];seconds=p['seconds'];minutes.append({'player':pid,'officialSeconds':seconds,'reconstructedBoundsSeconds':[lo*60,hi*60],'exact':abs(hi-lo)<1e-7,'insideBounds':lo*60-1e-6<=seconds<=hi*60+1e-6,'withinOfficialWholeSecondRounding':lo*60-.5-1e-6<=seconds<=hi*60+.5+1e-6})
    q=max(int(r['period_number']) for r in events);length=2880+300*max(0,q-4);budgets={t:sum(p['seconds'] for p in book.values() if p['team']==t) for t in teams};observed={t:game['teams'][t]['team_score'] for t in teams};final={t:score[t] for t in teams};lineups=[r for r in exposure['eventCourts'] if r['players'] is not None]
    return label({'gameId':game['id'],'periods':q,'overtimePeriods':max(0,q-4),'scores':final,'referenceScores':observed,'scoreReconciled':final==observed,'officialPlayerRows':len(official),'unmappedOfficialPlayers':unmapped,'statComparisons':comparisons,'allPlayerStatsReconciled':all(v['equal'] for v in comparisons),'minutes':minutes,'officialTeamSeconds':budgets,'expectedTeamSeconds':5*length,'minuteBudgetReconciled':all(abs(n-5*length)<1e-6 for n in budgets.values()),'reconstructedPlayerMinutesAllExact':all(v['exact'] and v['insideBounds'] for v in minutes),'identifiedCourtEventRows':len(lineups),'totalCourtEventRows':len(exposure['eventCourts']),'allEventLineupsIdentified':exposure['allEventLineupsIdentified'],'offCourtCredits':offcourt,'unresolvedEvents':unresolved,'teamAdministrativeEvents':dict(team_events),'duplicateEventIds':dup,'teamPossessionLowerBound':dict(possession),'possessionCaveat':'Exact possession boundaries require FT trip, team/dead-ball rebound and technical administration; this tally is not claimed exact.','completeAccountingReplay':all(v['equal'] for v in comparisons) and not unmapped and final==observed and not unresolved and not offcourt,'participationInterpretation':'Actual historical substitution constraints and final rosters; not pregame evidence.'},ctx)
