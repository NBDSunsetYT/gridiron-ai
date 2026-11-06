"""Earlier-game opportunity features; contemporary outcomes are label-only.

Archived corrected boxes lack original publication editions. Every row remains
conditional history, even when its lag is safely before the prediction cutoff.
"""
from collections import defaultdict
from datetime import timedelta
from types import FunctionType
import numpy as np
from .. import stat_data
from ...accuracy_v20.quality import aware

EXTRA_NBA=('fieldGoalAttempts','threePointAttempts','freeThrowAttempts')
EXTRA_FOOT=('passingCompletions',)
NAMES=('team_op_mean','team_op_last','opponent_allowed_op','share_mean','share_last',
       'share_sd','observed_participation','starter_fraction','starter_missing',
       'game_misses_mean','game_misses_missing')

def opportunity(sport,stat):
    if sport=='NBA':return 'minutes'
    if stat.startswith('passing') or stat=='interceptions':return 'passingAttempts'
    if stat.startswith('rushing') or stat=='carries':return 'carries'
    return 'receptions' if sport=='CFB' else 'targets'

def total(game,team,stat):
    official=game['teams'][team].get('totals',{}).get(stat)
    if official is not None:return float(official)
    values=[p['stats'].get(stat) for p in game['teams'][team]['players'].values()]
    values=[v for v in values if v is not None]
    return float(sum(values)) if values else None

def game_misses(game):
    pairs=[(total(game,t,'fieldGoalAttempts'),total(game,t,'fieldGoalsMade')) for t in game['teams']]
    if any(a is None or b is None or a<b for a,b in pairs):return None
    return float(sum(a-b for a,b in pairs))

def enrich_packets(games,sport):
    # No contemporary starter flag is used by features. This metadata is carried
    # into *later* game's history, not into its own feature vector.
    if sport=='NBA':
        from ...overnight_v20 import data
        banned=stat_data.protected()
        for raw in data.archives('NBA').values():
            if raw['id'] in banned:continue
            game=next((g for g in games if g['id']==raw['id']),None)
            if game is None:continue
            for p in raw['players']:
                t=str(p['team_id']);pid=str(int(p['athlete_id']))
                if t not in game['teams'] or pid not in game['teams'][t]['players']:continue
                target=game['teams'][t]['players'][pid]
                if isinstance(p.get('starter'),bool):target['starter']=p['starter']
                for stat,key in [('fieldGoalsMade','field_goals_made'),('offensiveRebounds','offensive_rebounds'),('defensiveRebounds','defensive_rebounds')]:
                    if p.get(key) is not None:target['stats'][stat]=float(p[key])
    else:
        for g in games:
            for team in g['teams'].values():
                for p in team['players'].values():
                    if 'completions' in p['stats']:p['stats']['passingCompletions']=p['stats']['completions']
    return games

def records(games,sport):
    # Reuse the frozen feature algorithm without changing its module globals.
    fn=FunctionType(stat_data.records.__code__,{**stat_data.records.__globals__,
        'NBA_STATS':stat_data.NBA_STATS+EXTRA_NBA,'FOOT_STATS':stat_data.FOOT_STATS+EXTRA_FOOT})
    rows=fn(games,sport);by_game=defaultdict(list)
    for row in rows:by_game[row['gameId']].append(row)
    history=defaultdict(list)
    for game in games:
        cutoff=aware(game['at'])-timedelta(hours=48)
        current=list(by_game[game['id']])
        for team_row in list(current):
            if team_row['player']!='__team__':continue
            team=team_row['team'];other=game['teams'][team]['opponent'];own=[g for g in history[team] if aware(g['at'])<cutoff][-5:];opp=[g for g in history[other] if aware(g['at'])<cutoff][-5:]
            own_mean=float(np.mean([g['teams'][team]['totals']['score'] for g in own]));opp_mean=float(np.mean([g['teams'][other]['totals']['score'] for g in opp]));score=team_row['y'];other_score=game['teams'][other]['totals']['score'];wins=float(np.mean([g['teams'][team]['totals']['score']>g['teams'][g['teams'][team]['opponent']]['totals']['score'] for g in own]))
            for stat,label,baseline in [('moneyline',float(score>other_score) if score!=other_score else None,wins),('spread',score-other_score,own_mean-opp_mean),('total',score+other_score,own_mean+opp_mean)]:
                clone={**team_row,'stat':stat,'y':label,'baseline':baseline,'ewma':baseline};current.append(clone);rows.append(clone)
        for row in current:
            team=row['team'];other=game['teams'][team]['opponent'];own=[g for g in history[team] if aware(g['at'])<cutoff][-5:];opp=[g for g in history[other] if aware(g['at'])<cutoff][-5:]
            op=opportunity(sport,row['stat']);vol=[total(g,team,op) for g in own];vol=[v for v in vol if v is not None]
            shares=[];starts=[];appear=0
            for g in own:
                p=g['teams'][team]['players'].get(row['player']);den=total(g,team,op)
                if p and p['stats'].get(op) is not None:
                    appear+=1
                    if den and den>0:shares.append(p['stats'][op]/den)
                    if isinstance(p.get('starter'),bool):starts.append(float(p['starter']))
            allowed=[total(g,g['teams'][other]['opponent'],op) for g in opp];allowed=[v for v in allowed if v is not None]
            misses=[game_misses(g) for g in own+opp];misses=[v for v in misses if v is not None]
            extra=[np.mean(vol) if vol else 0,vol[-1] if vol else 0,np.mean(allowed) if allowed else 0,np.mean(shares) if shares else 0,shares[-1] if shares else 0,np.std(shares) if shares else 0,appear/max(1,len(own)),np.mean(starts) if starts else 0,float(not starts),np.mean(misses) if misses else 0,float(not misses)]
            row['x']=[*row['x'],*map(float,extra)]
            row['featureNames']=['legacy_'+str(i) for i in range(15)]+list(NAMES)
            row['opportunityKind']=op;row['actualTeamOpportunity']=total(game,team,op);row['actualGameMisses']=game_misses(game)
            row['missingEvidence']=['injury','confirmed_lineup','original_statistics_publication']
            row['sourceEditionVerified']=False
        for team in game['teams']:history[team].append(game)
    return rows

LABELS={'y','opportunity','actualTeamOpportunity','actualGameMisses'}
def features_only(rows):return [{k:v for k,v in r.items() if k not in LABELS} for r in rows]

def packets(sport):
    """Reuse validated history and append already-owned, unexposed CFB season.

    Exact-ID filtering occurs before materializing external box rows. Existing
    sealed/confirmation ID sets are never changed or graded.
    """
    games=stat_data.packets(sport)
    if sport!='CFB':return games
    from pathlib import Path
    import pickle,pyarrow as pa,pyarrow.parquet as pq,pyarrow.compute as pc
    from ...overnight_v20 import data
    from ...evidence_v21.football_boxes import repaired_packet
    root=Path(__file__).resolve().parents[3];path=root/'artifacts/overnight-v21/source-repair/CFB-2026-normalized.pickle'
    if not path.exists():return games
    raw=pickle.load(path.open('rb'));ctor=FunctionType(data.packets.__code__,{**data.packets.__globals__,'archives':lambda _:raw});banned=stat_data.protected();hidden=[int(g.split(':')[-1]) for g in banned if g.startswith('cfb:espn:')];boxes={}
    for kind in ('player','team'):
        table=pq.read_table(root/f'artifacts/overnight-v21/external/CFB-{kind}_box_2026.parquet');table=table.filter(pc.invert(pc.is_in(table['game_id'],value_set=pa.array(hidden,type=table['game_id'].type))));group=defaultdict(list)
        for row in table.to_pylist():group[str(int(row['game_id']))].append(row)
        boxes[kind]=group
    known={g['id'] for g in games}
    for g in ctor('CFB'):
        if g['id'] in banned or g['id'] in known or g['at']>='2026-11-05':continue
        key=g['id'].split(':')[-1]
        try:
            repaired=repaired_packet(g,boxes['player'].get(key,[]),boxes['team'].get(key,[]))
            for t,team in repaired['teams'].items():
                for p in team['players'].values():p['stats'].pop('targets',None)
                for r in boxes['player'].get(key,[]):
                    pid='cfb:espn:'+str(int(r['athlete_id'])) if r.get('athlete_id') is not None else None
                    if pid not in team['players'] or 'cfb:espn:'+str(int(r['team_id']))!=t:continue
                    for stat in ('passingTouchdowns','interceptions','rushingTouchdowns','receivingTouchdowns'):
                        if r.get(stat) is not None:
                            try:team['players'][pid]['stats'][stat]=float(r[stat])
                            except (ValueError,TypeError):pass
            games.append(repaired)
        except (ValueError,KeyError,TypeError):continue
    return sorted(games,key=lambda g:(g['at'],g['id']))
