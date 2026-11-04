"""Preserve categorical draw order independently of JSON object key sorting.

Ordering does not change categorical masses, but it DOES change which category
a fixed uniform variate selects. Legacy fitted JSON snapshots sorted mappings;
their original support order can be recovered from pinned earlier play rows.
No coefficient, observation, forecast, outcome or probability is repaired here.
"""
from collections import Counter
import copy
import math
from .iterative_learning import digest

ROLES=('qb','receiver','runner')


def derive_draw_order(model,rows):
    if model['sport'] not in ('NFL','CFB'):raise ValueError('Football order recovery requires a football artifact')
    needed={}
    for team,games in model['histories'].items():
        for gid,h in sorted(games.items(),key=lambda item:item[1]['at'])[-3:]:needed[(team,gid)]={role:Counter() for role in ROLES}
    cutoff=model['fittingCutoff'];first_year=str(int(cutoff[:4])-1);training=set(model['trainingGameIds']);clock_cohorts={}
    for r in rows:
        key=(r.get('o'),r['game'])
        if r['game'] not in training or r['at'][:4]<first_year or r['at']>=cutoff:continue
        kind=r['kind'];conditions={'qb':kind in ('pass','sack'),'receiver':kind=='pass','runner':kind in ('rush','kneel')}
        if model.get('conditionalClock') and kind in ('pass','rush','sack','punt','field_goal','kneel','penalty'):
            from .football_v16 import clock_key
            ck=clock_key(kind,r['complete'],r['clock'],r['script'])
            if ck in model['conditionalClock']:clock_cohorts.setdefault(ck,[]).append(r['elapsed'])
        if key not in needed:continue
        for role in ROLES:
            if conditions[role] and r.get(role):needed[key][role][r[role]]+=1
    orders={}
    for (team,gid),roles in needed.items():
        original=model['histories'][team][gid]
        for role,count in roles.items():
            if dict(count)!=original[role]:raise ValueError('Pinned training participation does not match the fitted artifact; no draw order was guessed')
        orders.setdefault(team,{})[gid]={role:list(count) for role,count in roles.items()}
    if set(clock_cohorts)!=set(model.get('conditionalClock',{})) or any(v!=model['conditionalClock'][k] for k,v in clock_cohorts.items()):
        raise ValueError('Pinned conditional-clock cohorts differ from the fitted artifact')
    value={'version':'random-draw-order-2','modelSha256':model['sha256'],'roleOrders':orders,'conditionalClockOrder':list(clock_cohorts)}
    return value|{'sha256':digest(value)}


def restore_draw_order(model,artifact):
    value={k:v for k,v in artifact.items() if k!='sha256'}
    if digest(value)!=artifact['sha256'] or artifact['modelSha256']!=model['sha256']:raise ValueError('Categorical order artifact checksum or model identity mismatch')
    restored=copy.deepcopy(model)
    for team,games in artifact['roleOrders'].items():
        for gid,roles in games.items():
            for role,ids in roles.items():
                counts=restored['histories'][team][gid][role]
                if len(ids)!=len(set(ids)) or set(ids)!=set(counts):raise ValueError('Categorical support changed; refusing a different model')
                restored['histories'][team][gid][role]={pid:counts[pid] for pid in ids}
    keys=artifact.get('conditionalClockOrder',[]);clock=restored.get('conditionalClock',{})
    if len(keys)!=len(set(keys)) or set(keys)!=set(clock):raise ValueError('Missing or changed conditional-clock draw order')
    if 'conditionalClock' in restored:restored['conditionalClock']={key:clock[key] for key in keys}
    if digest({k:v for k,v in restored.items() if k!='sha256'})!=model['sha256']:raise ValueError('Fitted parameters changed during order restoration')
    return restored


def canonical_categorical_support(choices,weights):
    """For future model generations: stable arrays BEFORE simulation and storage.

    Exact category->weight equivalence, with an explicit seeded draw convention.
    This function is not retroactively applied to an archived forecast.
    """
    if len(choices)!=len(weights) or len(set(choices))!=len(choices):raise ValueError('Unique categories and aligned weights required')
    if any(not math.isfinite(w) or w<0 for w in weights):raise ValueError('Finite nonnegative category masses required')
    return tuple(zip(*sorted(zip(choices,weights)))) if len(choices) else ((),())
