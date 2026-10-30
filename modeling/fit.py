"""Fit auditable, conditional play-resampling models from authorized historical data.
No NFL probabilities are embedded in this module. See docs/SIMULATION.md.
"""
import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime, timezone

VERSION = "pbp-empirical-2.0.0"
ENHANCED_VERSION = "pbp-conditional-4.0.0"
PLAY_TYPES = {"pass", "rush", "sack", "punt", "field_goal", "kneel", "spike", "extra_point", "two_point"}
REQUIRED = {"game_id", "played_at", "offense", "defense", "down", "yards_to_go", "yardline_100", "seconds_remaining", "score_diff", "play_type", "yards_gained", "elapsed_seconds", "drive_start", "complete_pass", "interception", "fumble_lost", "field_goal_made", "punt_yards", "turnover_return_yards", "passer_id", "receiver_id", "rusher_id"}


def utc(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Timezone-aware ISO timestamps are required") from exc
    if result.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def integer(row, key, minimum, maximum, default=None):
    raw = row.get(key, default)
    if raw is None or raw == "":
        raise ValueError(f"Missing {key}")
    value = float(raw)
    if not math.isfinite(value) or int(value) != value or not minimum <= value <= maximum:
        raise ValueError(f"{key} must be an integer between {minimum} and {maximum}")
    return int(value)


def fit_csv(raw, source, as_of, team_min_plays=100, options=None):
    if not isinstance(raw, str) or not raw.strip() or len(raw.encode()) > 20_000_000:
        raise ValueError("Historical CSV required, at most 20 MB")
    if not isinstance(source, str) or not source.strip() or len(source) > 2000:
        raise ValueError("Source/license provenance is required")
    cutoff = utc(as_of)
    if cutoff > datetime.now(timezone.utc):
        raise ValueError("Evidence cutoff cannot be in the future")
    if not isinstance(team_min_plays, int) or not 100 <= team_min_plays <= 10000:
        raise ValueError("teamMinPlays must be 100..10000")
    reader = csv.DictReader(io.StringIO(raw))
    if not REQUIRED.issubset(reader.fieldnames or []):
        raise ValueError("Missing CSV columns: " + ", ".join(sorted(REQUIRED - set(reader.fieldnames or []))))
    options = options or {}
    if not isinstance(options, dict) or set(options)-{'recencyHalfLifeDays', 'conditionalShrinkage', 'strictAvailability'}:
        raise ValueError('Unknown fitting options')
    half_life=options.get('recencyHalfLifeDays')
    if half_life is not None and (isinstance(half_life,bool) or not isinstance(half_life,(int,float)) or not 30<=half_life<=1460):
        raise ValueError('Recency half-life must be30..1460 days')
    for key in ('conditionalShrinkage','strictAvailability'):
        if key in options and not isinstance(options[key],bool):
            raise ValueError(key+' must be boolean')
    rows, seen, games, teams = [], set(), {}, Counter()
    availability_verified=True
    for index, row in enumerate(reader):
        if index >= 100000:
            raise ValueError("Maximum 100,000 plays per fitted artifact; partition historical data explicitly")
        played = utc(row["played_at"])
        if played >= cutoff:
            raise ValueError(f"Row {index + 2} is at/after cutoff; look-ahead evidence rejected")
        available=utc(row['available_at']) if row.get('available_at') else None
        collected=utc(row['collected_at']) if row.get('collected_at') else None
        if available and (available<played or available>=cutoff):
            raise ValueError('Historical availability must follow its event and precede the evidence cutoff')
        if collected and (collected<played or available and collected<available):
            raise ValueError('Collection cannot precede event/source availability')
        if options.get('strictAvailability') and (not available or not collected or collected>=cutoff or not row.get('source_version') or row.get('reliability')!='verified'):
            raise ValueError('Strict availability requires pre-cutoff available_at/collected_at, source_version and verified reliability on every row')
        availability_verified=availability_verified and bool(available and collected and collected<cutoff and row.get('source_version') and row.get('reliability')=='verified')
        kind = row["play_type"]
        if kind not in PLAY_TYPES:
            raise ValueError(f"Unsupported play_type {kind!r}; normalize source explicitly")
        game = row["game_id"].strip()
        offense, defense = row["offense"].strip(), row["defense"].strip()
        if not game or not offense or not defense or offense == defense:
            raise ValueError("Valid game, offense and distinct defense required")
        # Explicit play IDs are preferred; otherwise identical complete rows are duplicates.
        identity = (game, row.get("play_id") or json.dumps(row, sort_keys=True))
        if identity in seen:
            raise ValueError("Duplicate historical play")
        seen.add(identity)
        avail = json.loads(row.get("availability") or "{}")
        if not isinstance(avail, dict) or any(not isinstance(k, str) or v not in ("active", "limited", "inactive") for k, v in avail.items()):
            raise ValueError("availability must be JSON playerId: active|limited|inactive")
        p = {
            "game": game, "at": played.isoformat(), "o": offense, "d": defense,
            "down": integer(row, "down", 1, 4), "distance": integer(row, "yards_to_go", 1, 100),
            "field": integer(row, "yardline_100", 1, 99), "clock": integer(row, "seconds_remaining", 0, 3600),
            "script": integer(row, "score_diff", -100, 100), "kind": kind,
            "yards": integer(row, "yards_gained", -99, 99), "elapsed": integer(row, "elapsed_seconds", 1, 90),
            "start": integer(row, "drive_start", 0, 1), "complete": integer(row, "complete_pass", 0, 1),
            "int": integer(row, "interception", 0, 1), "fumble": integer(row, "fumble_lost", 0, 1),
            "fg": integer(row, "field_goal_made", 0, 1), "punt": integer(row, "punt_yards", 0, 100),
            "return": integer(row, "turnover_return_yards", 0, 100),
            "qb": row["passer_id"].strip(), "receiver": row["receiver_id"].strip(), "runner": row["rusher_id"].strip(),
            "availability": avail,
            "sourceAvailableAt":available.isoformat() if available else None,
            "collectedAt":collected.isoformat() if collected else None,
            "sourceVersion":row.get('source_version') or None,
            "reliability":row.get('reliability') or 'availability_unverified',
        }
        if p["complete"] and (kind != "pass" or not p["qb"] or not p["receiver"] or p["int"]):
            raise ValueError("Completed passes need passer+receiver and cannot also be interceptions")
        if kind in ("pass","spike") and not p["qb"]:
            raise ValueError("Every pass/spike needs an identified passer")
        if kind in ("rush", "kneel") and not p["runner"]:
            raise ValueError("Rushes require rusher identity")
        if p["int"] and kind != "pass":
            raise ValueError("Interception must be a passing event")
        if any(avail.get(player) == "inactive" for player in (p["qb"], p["receiver"], p["runner"]) if player):
            raise ValueError("Inactive player participates in a play; reconcile source data")
        games[game] = played.isoformat()
        for field in ('epa','success','air_yards','yards_after_catch'):
            value=row.get(field)
            if value not in (None,''):
                value=float(value)
                if not math.isfinite(value):raise ValueError('Nonfinite optional research statistic')
                if field=='success' and value not in (0,1):raise ValueError('success must be0 or1')
                p[field]=value
        if kind not in ("extra_point", "two_point"):
            teams[offense] += 1
        rows.append(p)
    if len(games) < 4:
        raise ValueError("Insufficient evidence: at least four distinct historical games required")
    eligible = sorted(team for team, n in teams.items() if n >= team_min_plays)
    if len(eligible) < 2:
        raise ValueError("Insufficient evidence: at least two teams with 100+ plays required")
    version=ENHANCED_VERSION if options else VERSION
    model = {"version": version, "source": source.strip(), "asOf": cutoff.isoformat(),
             "sha256": hashlib.sha256(raw.encode()).hexdigest(), "teamMinPlays": team_min_plays,
             "teams": eligible, "rows": rows,"dataAvailabilityVerified":availability_verified,"teamResearch":research_features(rows)}
    if options:
        model['modelOptions']=options
        if options.get('conditionalShrinkage'):
            model['shrinkageFit']=fit_shrinkage(rows)
    return {"model": model, "summary": {"plays": len(rows), "games": len(games), "teams": dict(teams),
            "eligibleTeams": eligible, "source": source.strip(), "asOf": cutoff.isoformat(),
            "inputDataVersion": model["sha256"], "modelVersion": version,
            "dataAvailabilityVerified":availability_verified,
            "options":options,"shrinkageFit":model.get('shrinkageFit'),
            "verification": "User-supplied source; not independently authenticated or licensed by this software"}}


def research_features(rows):
    """Traceable historical features; missing snaps/routes/weather stay missing."""
    output={}
    for team in sorted(set(r['o'] for r in rows)|set(r['d'] for r in rows)):
        offense=[r for r in rows if r['o']==team and r['kind'] in ('pass','rush','sack')]
        defense=[r for r in rows if r['d']==team and r['kind'] in ('pass','rush','sack')]
        if not offense:continue
        passes=[r for r in offense if r['kind'] in ('pass','sack')];neutral=[r for r in offense if abs(r['script'])<=7 and r['clock']>120]
        def metric(data,key):
            observed=[r[key] for r in data if key in r]
            return {'value':sum(observed)/len(observed) if observed else None,'sampleSize':len(observed)}
        targets=Counter(r['receiver'] for r in passes if r['receiver']);carries=Counter(r['runner'] for r in offense if r['kind']=='rush' and r['runner'])
        output[team]={'historicalOffenseEPA':metric(offense,'epa'),'historicalDefenseEPAAllowed':metric(defense,'epa'),'historicalSuccessRate':metric(offense,'success'),'games':len({r['game'] for r in offense}),'offensivePlays':len(offense),'passPlays':len(passes),'neutralPassRate':sum(r['kind'] in ('pass','sack') for r in neutral)/len(neutral) if neutral else None,'sackRate':sum(r['kind']=='sack' for r in passes)/len(passes) if passes else None,'turnoverRate':sum(bool(r['int'] or r['fumble']) for r in offense)/len(offense),'explosivePassRate20Yards':sum(r['kind']=='pass' and r['complete'] and r['yards']>=20 for r in passes)/len(passes) if passes else None,'redZonePlays':sum(r['field']<=20 for r in offense),'targetShares':{p:n/sum(targets.values()) for p,n in targets.items()},'carryShares':{p:n/sum(carries.values()) for p,n in carries.items()},'routeParticipation':None,'snapShares':None,'pressureRate':None,'coverage':'Normalized historical supported plays; penalties and unsupported events excluded. These are descriptive source features, not independent matchup-adjusted projections.'}
    return output


def fit_shrinkage(rows):
    """Select conditional-pool prior strength on strictly later historical games."""
    ordered=sorted({r['game'] for r in rows},key=lambda game:min(r['at'] for r in rows if r['game']==game))
    split=max(2,int(.8*len(ordered)))
    training=set(ordered[:split]);from collections import defaultdict
    detailed=defaultdict(Counter);background=defaultdict(Counter)
    key=lambda r:(r['o'],r['d'],r['down'],0 if r['field']<=20 else 1 if r['field']<=50 else 2,0 if r['distance']<=3 else 1 if r['distance']<=7 else 2)
    for r in rows:
        if r['game'] in training and r['kind'] not in ('extra_point','two_point'):
            detailed[key(r)][r['kind']]+=1;background[(r['o'],r['down'])][r['kind']]+=1
    curve=[]
    for strength in (5,20,50):
        total_loss,n=0.,0
        for r in rows:
            if r['game'] in training or r['kind'] in ('extra_point','two_point'):continue
            parent=background[(r['o'],r['down'])];local=detailed[key(r)]
            if sum(parent.values())<5:continue
            base=(parent[r['kind']]+.5)/(sum(parent.values())+.5*len(PLAY_TYPES))
            probability=(local[r['kind']]+strength*base)/(sum(local.values())+strength)
            total_loss-=math.log(max(probability,1e-12));n+=1
        if n:curve.append({'priorPlays':strength,'validationPlays':n,'logLoss':total_loss/n})
    if not curve:raise ValueError('Insufficient chronological evidence to fit conditional-pool shrinkage')
    return {'priorPlays':min(curve,key=lambda r:r['logLoss'])['priorPlays'],'validation':curve,'trainingGames':len(training),'heldoutGames':len(ordered)-len(training),'method':'Chronological next-play-kind validation; regularization is not a fabricated injury adjustment'}
