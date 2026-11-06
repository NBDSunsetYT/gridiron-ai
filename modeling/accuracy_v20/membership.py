"""Exact, timestamped roster-ownership resolution; never infer availability."""
from .quality import aware
def resolve_membership(sport,event_id,player_id,candidate_teams,cutoff,facts):
    canonical=('nba:espn:'+player_id) if sport=='NBA' and not player_id.startswith('nba:espn:') else player_id;eligible=[]
    for f in facts:
        if f['sport']!=sport or f['playerId']!=canonical or event_id not in f['eventIds']:continue
        if aware(f['availableAt'])>aware(cutoff) or f['teamId'] not in candidate_teams:continue
        if f.get('sourceVerified') is not True or not f.get('sourceVersion'):continue
        eligible.append(f)
    if not eligible:return {'status':'ambiguous','candidateTeams':sorted(candidate_teams),'reason':'No exact pre-cutoff source verifies ownership','availability':'unknown'}
    latest=max(f['availableAt'] for f in eligible);selected=[f for f in eligible if f['availableAt']==latest];teams={f['teamId'] for f in selected}
    if len(teams)!=1:return {'status':'conflicting_sources','candidateTeams':sorted(teams),'availability':'unknown'}
    return {'status':'resolved','teamId':next(iter(teams)),'availableAt':latest,'sources':sorted({f['source'] for f in selected}),'sourceVersions':sorted({f['sourceVersion'] for f in selected}),'availability':'unknown','interpretation':'Pregame transaction ownership, not active status, starter confirmation or expected minutes.'}
