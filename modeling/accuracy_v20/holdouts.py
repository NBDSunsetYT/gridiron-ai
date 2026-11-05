"""Append-only exposure exclusions; never rewrite a frozen test manifest."""
from zoneinfo import ZoneInfo
from .quality import aware
def exposed(game,notices):
    for notice in notices:
        target=notice['excludeFromFutureUntouchedClaims']
        if game['sport']!=target['sport'] or aware(game['at']).astimezone(ZoneInfo('America/New_York')).date().isoformat()!=target['localDate']:continue
        if not game.get('home') or not game.get('away'):return True # Resolve identity before any untouched-test claim.
        if {game['home'],game['away']}==set(target.get('teamIds',[])):return True
    return False
def assert_untouched(games,evaluated_ids,notices):
    reused=sorted(g['id'] for g in games if g['id'] in evaluated_ids);leaked=sorted(g['id'] for g in games if exposed(g,notices))
    if reused or leaked:raise ValueError('Final test contains previously evaluated or exposed events')
    return {'reservedGames':len(games),'gradedIntersection':reused,'externalExposureMatches':leaked,'graded':False}
