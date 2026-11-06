"""Point-in-time source lineage and diagnostic negative controls.

An archived fact may be retrieved today only if its original edition and public
availability before the prediction cutoff are independently verified. A date
printed on a corrected final box is not such verification.
"""
from copy import deepcopy
from datetime import timedelta
import numpy as np
from ..accuracy_v20.quality import aware

FORBIDDEN={'y','opportunity','actualteamopportunity','actualgamemisses','actualminutes',
           'finalscore','homefinalscore','awayfinalscore','finalinjurystatus','finallineup',
           'actualstarters','settledoutcome','outcomelabel','finalroster'}


def feature_names_guard(names):
    if any(str(name).replace('_','').lower() in FORBIDDEN for name in names):
        raise ValueError('Contemporary outcome/participation field in forecast features')


def source_fact_guard(fact, cutoff, target_event):
    when=aware(cutoff)
    if not fact.get('sourceVersion') or not str(fact.get('source','')).startswith('https://'):
        raise ValueError('Source and exact edition required')
    published=aware(fact.get('publishedAt'));available=aware(fact.get('availableAt'))
    edition=aware(fact.get('editionPublishedAt'));retrieved=aware(fact.get('retrievedAt'))
    if max(published,available,edition)>=when:raise ValueError('Future publication, availability or corrected edition')
    if available<max(published,edition) or retrieved<available:raise ValueError('Inconsistent source availability lineage')
    if retrieved>=when and fact.get('originalEditionVerified') is not True:
        raise ValueError('Later retrieval requires verification of the archived original edition')
    kind=fact.get('kind');role=fact.get('sourceRole')
    if kind=='historical_statistics':
        if fact.get('eventId')==target_event or aware(fact.get('gameEndedAt'))>=when:
            raise ValueError('Current or future game results cannot be pregame history')
    elif kind in ('injury','lineup','participation'):
        if fact.get('eventId')!=target_event or role not in ('official_pregame_report','verified_pregame_projection'):
            raise ValueError('Final participation/rosters cannot replace pregame evidence')
        if fact.get('status') not in ('confirmed','projected','uncertain','unavailable'):
            raise ValueError('Explicit evidence status required; unknown is not healthy')
    elif kind=='market':
        if fact.get('eventId')!=target_event or aware(fact.get('capturedAt'))>=when:
            raise ValueError('Market quote captured after the prediction cutoff')
        if fact.get('product') not in ('sportsbook','event_contract'):
            raise ValueError('Market product must remain explicit')
    else:raise ValueError('Unsupported source-fact role')
    return {'kind':kind,'verifiedBeforeCutoff':True,'availabilityStatus':fact.get('status'),
            'unconditionalForecastAuthorized':False}


def forecast_lineage_guard(features, facts, cutoff, target_event, training_through):
    """New research ingress only; mechanics/model certification is additional."""
    from .evaluation import feature_guard
    if aware(training_through)>=aware(cutoff):raise ValueError('Fit must precede prediction cutoff')
    for row in features:
        feature_names_guard(row)
        feature_names_guard(row.get('featureNames',[]))
        if row.get('gameId')!=target_event or aware(row.get('at'))<aware(cutoff):
            raise ValueError('Forecast identity/cutoff differs from the target event')
    audited=[source_fact_guard(f,cutoff,target_event) for f in facts]
    if {'historical_statistics','injury','lineup','participation'}-{r['kind'] for r in audited}:
        raise ValueError('Required historical evidence domains are incomplete')
    if any(r['kind'] in ('injury','lineup','participation') and r['availabilityStatus']!='confirmed' for r in audited):
        raise ValueError('Uncertain/projected participation requires separately validated scenarios; no unconditional forecast')
    # Use the actual prediction cutoff for the historical embargo, rather than
    # silently admitting information that arrived between forecast and kickoff.
    check=[dict(r,at=cutoff) for r in features]
    result=feature_guard(check,training_through,evidence_tier='strict_pregame')
    return result|{'lineage':audited,'jointMechanicsCertificateStillRequired':True}


def shuffle_control(features, kind, seed=250025):
    rows=deepcopy(features);rng=np.random.default_rng(seed)
    if kind=='player_identity':
        players=sorted({r['player'] for r in rows if r['player']!='__team__'})
        mapping=dict(zip(players,rng.permutation(players)))
        for r in rows:r['player']=mapping.get(r['player'],r['player'])
    elif kind=='team_score_context':
        games=sorted({r['gameId'] for r in rows});mapping=dict(zip(games,rng.permutation(games)))
        context={}
        for r in features:context.setdefault((r['gameId'],r['team']),r)
        for row in rows:
            candidates=[r for (g,t),r in context.items() if g==mapping[row['gameId']]]
            donor=next((r for r in candidates if r['x'][6]==row['x'][6]),candidates[0])
            # Only the documented legacy own/opponent score-context fields are
            # shuffled. Other opportunity/ability features deliberately remain.
            row['x'][7:9]=donor['x'][7:9]
    elif kind=='future_history':
        for r in rows:r['featureLastGame']=(aware(r['at'])+timedelta(minutes=1)).isoformat()
    else:raise ValueError('No synthetic market quotes or unspecified control features')
    return rows
