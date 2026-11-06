"""Independent box accounting admission; preserve rejected source documents."""
import math
SHOT_FIELDS=('field_goals_attempted','field_goals_made','three_point_field_goals_attempted','three_point_field_goals_made','free_throws_attempted','free_throws_made')
def audit(game):
    reasons=[]
    for team,totals in game['teams'].items():
        players=[p for p in game['players'] if str(p['team_id'])==str(team)]
        for stat in SHOT_FIELDS:
            expected=totals.get(stat)
            if expected is None or not math.isfinite(float(expected)):
                reasons.append(str(team)+':missing_team_'+stat);continue
            if any(p.get(stat) is None and float(p.get('minutes') or 0)>0 for p in players):
                reasons.append(str(team)+':missing_player_'+stat);continue
            observed=sum(float(p.get(stat) or 0) for p in players)
            if abs(observed-float(expected))>1e-7:reasons.append(str(team)+':player_team_'+stat)
        if totals.get('team_score') is None or any(p.get('points') is None and float(p.get('minutes') or 0)>0 for p in players):reasons.append(str(team)+':missing_scoring_evidence')
        elif abs(sum(float(p.get('points') or 0) for p in players)-float(totals['team_score']))>1e-7:reasons.append(str(team)+':player_team_points')
    return {'gameId':game['id'],'usable':not reasons,'reasons':reasons,'originalSourceModified':False,'injuryOrLineupVerified':False}
