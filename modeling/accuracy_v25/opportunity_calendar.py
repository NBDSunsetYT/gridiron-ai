"""One structural candidate: shared calendar exposure, not appearance means.

No injury probability, player replacement, artificial target or efficiency
multiplier is inferred. Unknown historical credits remain unknown.
"""
import math
import numpy as np


def requested_team_total(game,raw,sport,team,stat):
    if stat=='passingYards':
        source=next((t for t in raw.get('boxscore',{}).get('teams',[]) if str(t['team']['id'])==team),None)
        fields={r['name']:r.get('displayValue') for r in (source or {}).get('statistics',[])}
        try:
            net=float(fields['netPassingYards'])
            if sport=='NFL':
                # ESPN's NFL passing-group total can be net while individual
                # QB yards are gross. Sacks are deducted from team passing only.
                import re
                pair=re.fullmatch(r'(\d+)-(\d+)',fields['sacksYardsLost'])
                if not pair:return None
                return net+float(pair[2])
            if sport=='CFB':return net # NCAA sacks belong to rushing.
        except (KeyError,TypeError,ValueError):return None
    return game['teams'][team]['totals'].get(stat)


def observed(game,raw,sport,team,player,stat):
    t=game['teams'][team];p=t['players'].get(player)
    if p is not None and stat in p['stats']:
        return p['stats'][stat],'published_player_stat'
    if sport=='NBA':
        source=next((t for t in raw.get('boxscore',{}).get('players',[]) if str(t['team']['id'])==team),None)
        rows=[a for g in (source or {}).get('statistics',[]) for a in g.get('athletes',[]) if str(a['athlete']['id'])==player]
        if rows and all(a.get('didNotPlay') is True and not a.get('stats') for a in rows):
            return 0.,'explicit_historical_DNP_not_current_health'
        # Missing NBA minute totals/rounded time cannot prove an absent actor
        # had precisely zero minutes. Do not fill this source gap.
        return None,'missing_player_or_unverified_opportunity_coverage'
    count={'passingYards':'passingAttempts','passingCompletions':'passingAttempts','passingTouchdowns':'passingAttempts',
           'carries':'carries','rushingYards':'carries','rushingTouchdowns':'carries',
           'receivingYards':'receptions','receivingTouchdowns':'receptions','receptions':'receptions',
           'passingAttempts':'passingAttempts','targets':'targets'}.get(stat)
    if not count:return None,'unsupported_zero_inference'
    total=t['totals'].get(count)
    actual=sum(p['stats'].get(count,0) for p in t['players'].values())
    stat_total=requested_team_total(game,raw,sport,team,stat)
    stat_sum=sum(p['stats'].get(stat,0) for p in t['players'].values())
    if total is not None and stat_total is not None and math.isclose(actual,total,rel_tol=0,abs_tol=1e-9) and math.isclose(stat_sum,stat_total,rel_tol=0,abs_tol=1e-9):
        # These are historical team opportunity credits, not an assertion that
        # the player was available then or is healthy now. Anonymous credits
        # would make reconciliation fail and remain unassigned.
        return 0.,'complete_historical_team_opportunities'
    return None,'anonymous_or_incomplete_team_opportunities'


def project(history,raw_by_id,sport,team,player,stat):
    appearance=[g['teams'][team]['players'][player]['stats'][stat] for g in history
                if player in g['teams'][team]['players'] and stat in g['teams'][team]['players'][player]['stats']]
    if len(appearance)<3:return None
    cells=[observed(g,raw_by_id[g['eventId']],sport,team,player,stat) for g in history]
    if any(v is None for v,reason in cells):return None
    calendar=[v for v,reason in cells]
    return {'reference':float(np.mean(appearance)),'candidate':float(np.mean(calendar)),
            'referenceMedian':float(np.median(appearance)),'candidateMedian':float(np.median(calendar)),
            'referenceDistribution':appearance,'candidateDistribution':calendar,
            'appearanceGames':len(appearance),'calendarGames':len(calendar),
            'zeroProofs':[{'eventId':g['eventId'],'reason':reason} for g,(v,reason) in zip(history,cells) if reason!='published_player_stat'],
            'productionEligible':False,'availabilityModel':'not_supplied','conditionalResearchOnly':True}
