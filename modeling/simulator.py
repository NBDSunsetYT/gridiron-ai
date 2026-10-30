"""Conditional empirical play-by-play NFL simulator; never supplies default rates.

Mechanics are deterministic NFL-style transitions; all sampled event frequencies,
yards, play clocks, player identities and kick success come from fitted evidence.
This is an auditable research baseline, not a validated professional odds model.
"""
import argparse
import json
import math
import random
import sys
import bisect
from collections import Counter, defaultdict
from datetime import datetime, timezone

try:
    from .fit import VERSION, ENHANCED_VERSION, utc
except ImportError:
    from fit import VERSION, ENHANCED_VERSION, utc

STATS = ("passingAttempts", "completions", "passingYards", "passingTouchdowns", "interceptions", "targets", "receptions", "receivingYards", "receivingTouchdowns", "carries", "rushingYards", "rushingTouchdowns")
ENGINE_VERSION = 'pbp-runtime-4.0.0'


def wilson(success, n):
    if not n:
        return [0.0, 1.0]
    p, z = success / n, 1.959963984540054
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0, center - radius), min(1, center + radius)]


def histogram_summary(hist, n):
    missing = n - sum(hist.values())
    hist = hist.copy()
    if missing:
        hist[0] += missing
    ordered = sorted(hist.items())
    def quantile(p):
        target, cumulative = max(1, math.ceil(n * p)), 0
        for value, count in ordered:
            cumulative += count
            if cumulative >= target:
                return value
        return ordered[-1][0]
    return {"mean": sum(v * c for v, c in ordered) / n,
            "median": quantile(.5), "interval90": [quantile(.05), quantile(.95)],
            "histogram": [{"value": value, "count": count} for value, count in ordered]}


def zone(field):
    return 0 if field <= 20 else 1 if field <= 50 else 2


def distance_bucket(distance):
    return 0 if distance <= 3 else 1 if distance <= 7 else 2


def script_bucket(diff):
    return -1 if diff < -7 else 1 if diff > 7 else 0


class Evidence:
    def __init__(self, model, home, away, scenario=None, game_weights=None):
        if model.get("version") not in (VERSION,ENHANCED_VERSION) or not model.get("source") or not model.get("sha256"):
            raise ValueError("A fitted model artifact with provenance is required")
        if home == away or home not in model.get("teams", []) or away not in model.get("teams", []):
            raise ValueError("Select two distinct teams with sufficient fitted evidence")
        self.pools, self.conversions, self.starts = defaultdict(list), defaultdict(list), defaultdict(list)
        self.start_rows=defaultdict(list)
        self.games, self.counts, self.rows = set(), Counter(), []
        self.backoff = Counter()
        self.options=model.get('modelOptions',{})
        self.prior_strength=model.get('shrinkageFit',{}).get('priorPlays') if self.options.get('conditionalShrinkage') else None
        self.weighted_cdf={};self.row_weights={}
        self.weighted=bool(game_weights or self.options.get('recencyHalfLifeDays'))
        if scenario:
            if set(scenario) != {"playerId", "status"} or scenario["status"] not in ("active", "limited", "inactive"):
                raise ValueError("Scenario requires playerId and active|limited|inactive status")
        for row in model["rows"]:
            if row["o"] not in (home, away):
                continue
            if scenario and row.get("availability", {}).get(scenario["playerId"]) != scenario["status"]:
                continue
            self.rows.append(row)
            weight=(game_weights or {}).get(row['game'],1.)
            half_life=self.options.get('recencyHalfLifeDays')
            if half_life:weight*=math.exp(-math.log(2)*(utc(model['asOf'])-utc(row['at'])).total_seconds()/(86400*half_life))
            if not math.isfinite(weight) or weight<=0:raise ValueError('Historical game weights must be finite and positive')
            self.row_weights[id(row)]=weight
            self.games.add(row["game"])
            if row["kind"] in ("extra_point", "two_point"):
                self.conversions[row["o"]].append(row)
                continue
            self.counts[row["o"]] += 1
            team, down, z, d, s, late = row["o"], row["down"], zone(row["field"]), distance_bucket(row["distance"]), script_bucket(row["script"]), (row["clock"] <= 120 or 1800 < row["clock"] <= 1920)
            for key in ((team, row["d"], down, z, d, s, late), (team, down, z, d, s, late),
                        (team, down, z, d), (team, down)):
                self.pools[key].append(row)
            if row["start"]:
                self.starts[team].append(row["field"])
                self.start_rows[team].append(row)
        minimum = model["teamMinPlays"]
        for team in (home, away):
            if self.counts[team] < minimum or len(self.starts[team]) < 4 or len(self.conversions[team]) < 5:
                raise ValueError(f"Insufficient evidence for {team}: requires {minimum} plays, four drive starts and five conversions in the selected scenario")
            if any(len(self.pools[(team, down)]) < 3 for down in (1, 2, 3, 4)):
                raise ValueError(f"Insufficient evidence for {team}: requires at least three plays on every down")
        if len(self.games) < 4:
            raise ValueError("Insufficient scenario evidence: at least four historical games required")
        if self.weighted:
            for pool in list(self.pools.values())+list(self.conversions.values()):
                total=0.;cdf=[]
                for row in pool:total+=self.row_weights[id(row)];cdf.append(total)
                self.weighted_cdf[id(pool)]=(cdf,total)

    def draw(self,rng,pool):
        if not self.weighted:return pool[rng.randrange(len(pool))]
        cdf,total=self.weighted_cdf.get(id(pool),(None,None))
        if cdf is None:
            total=0.;cdf=[]
            for row in pool:total+=self.row_weights[id(row)];cdf.append(total)
        return pool[min(len(pool)-1,bisect.bisect_right(cdf,rng.random()*total))]

    def sample(self, rng, team, defense, down, field, distance, diff, clock):
        z, d, s, late = zone(field), distance_bucket(distance), script_bucket(diff), clock <= 120
        keys = ((team, defense, down, z, d, s, late), (team, down, z, d, s, late),
                (team, down, z, d), (team, down))
        for depth, key in enumerate(keys):
            pool = self.pools.get(key)
            if pool and len(pool) >= 3:
                if self.prior_strength and depth<len(keys)-1:
                    parent=next((self.pools[k] for k in keys[depth+1:] if self.pools.get(k)),None)
                    if parent and rng.random()>len(pool)/(len(pool)+self.prior_strength):pool=parent
                self.backoff[depth] += 1
                return self.draw(rng,pool)
        raise ValueError("No applicable historical play pool")

    def start(self, rng, team):
        return self.draw(rng,self.start_rows[team])['field']

    def conversion(self, rng, team, diff, late):
        pool = self.conversions[team]
        contextual = [p for p in pool if script_bucket(p["script"]) == script_bucket(diff) and (p["clock"] <= 120 or 1800 < p["clock"] <= 1920) == late]
        if len(contextual) >= 3:
            pool = contextual
        row = self.draw(rng,pool)
        return (2 if row["kind"] == "two_point" else 1) if row["fg"] else 0


def simulate_game(evidence, rng, teams, postseason=False, trace=False):
    scores = [0, 0]
    offense = rng.randrange(2)  # Fair coin is a game rule, not a fitted performance parameter.
    first_receiver = offense
    field = evidence.start(rng, teams[offense])
    down, distance, clock = 1, min(10, field), 1800
    half, overtime, ot_possessions, plays, drives = 1, False, set(), 0, 1
    player = defaultdict(Counter)
    totals = Counter()
    log = []
    overtime_periods = 0
    while True:
        if clock <= 0:
            if half == 1:
                half, clock, offense = 2, 1800, 1 - first_receiver
                field = evidence.start(rng, teams[offense])
                down, distance = 1, min(10, field)
                drives += 1
            elif not overtime:
                if scores[0] != scores[1]:
                    break
                overtime, overtime_periods, clock = True, 1, 900 if postseason else 600
                offense, ot_possessions = rng.randrange(2), set()
                field = evidence.start(rng, teams[offense])
                down, distance = 1, min(10, field)
                drives += 1
            elif not postseason:
                break
            else:
                overtime_periods += 1
                if overtime_periods > 8:
                    raise ValueError("Simulation cannot resolve postseason overtime after eight periods")
                clock = 900
        defense = 1 - offense
        if plays >= 600:
            raise ValueError("Simulation exceeded 600 plays: inspect source clock data")
        p = evidence.sample(rng, teams[offense], teams[defense], down, field, distance,
                            scores[offense] - scores[defense], clock)
        plays += 1
        clock -= min(clock, p["elapsed"])
        totals["plays"] += 1
        kind, yards, possession_change, scored, safety = p["kind"], p["yards"], False, False, False
        old_field, old_down = field, down
        if kind == "pass":
            player[p["qb"]]["passingAttempts"] += 1
            if p["receiver"]:
                player[p["receiver"]]["targets"] += 1
            if p["int"]:
                player[p["qb"]]["interceptions"] += 1
                totals["interceptions"] += 1
                field = 100 - max(0, min(100, field - yards)) - p["return"]
                possession_change = True
            elif p["complete"]:
                player[p["qb"]]["completions"] += 1
                player[p["qb"]]["passingYards"] += min(yards, field)
                player[p["receiver"]]["receptions"] += 1
                player[p["receiver"]]["receivingYards"] += min(yards, field)
                field -= yards
            # Incomplete pass advances no yards even if source air_yards was supplied incorrectly.
            else:
                yards = 0
        elif kind in ("rush", "kneel"):
            player[p["runner"]]["carries"] += 1
            player[p["runner"]]["rushingYards"] += min(yards, field)
            field -= yards
        elif kind == "sack":
            totals["sacks"] += 1
            field -= yards
        elif kind == "spike":
            player[p['qb']]['passingAttempts']+=1
            yards = 0
        elif kind == "punt":
            totals["punts"] += 1
            landing = field - p["punt"]
            field = 80 if landing <= 0 else 100 - landing - p["return"]
            possession_change = True
        elif kind == "field_goal":
            totals["fieldGoalAttempts"] += 1
            if p["fg"]:
                totals["fieldGoals"] += 1
                scores[offense] += 3
                scored = True
                field = evidence.start(rng, teams[defense])
            else:
                field = max(1, min(80, 100 - old_field - 7))  # Missed kick: spot of kick, own20 minimum.
            possession_change = True
        if not possession_change and kind not in ("field_goal", "punt"):
            if p["fumble"]:
                totals["fumblesLost"] += 1
                field = 100 - max(0, min(100, field)) - p["return"]
                possession_change = True
            elif field <= 0:
                totals["touchdowns"] += 1
                scores[offense] += 6
                if kind == "pass":
                    player[p["qb"]]["passingTouchdowns"] += 1
                    player[p["receiver"]]["receivingTouchdowns"] += 1
                elif kind in ("rush", "kneel"):
                    player[p["runner"]]["rushingTouchdowns"] += 1
                scores[offense] += evidence.conversion(rng, teams[offense], scores[offense] - scores[defense], clock <= 120)
                scored, possession_change = True, True
                field = evidence.start(rng, teams[defense])
            elif field >= 100:
                totals["safeties"] += 1
                scores[defense] += 2
                scored, safety, possession_change = True, True, True
                field = evidence.start(rng, teams[defense])
            elif yards >= distance:
                down, distance = 1, min(10, field)
            else:
                down, distance = down + 1, max(1, distance - yards)
                if down > 4:
                    field, possession_change = 100 - field, True
        if overtime and safety:
            if trace:
                log.append({"play":plays,"drive":drives,"offense":teams[offense],"defense":teams[defense],"kind":kind,"safety":True,"score":list(scores),"fieldBefore":old_field,"field":field,"down":old_down,"nextDown":1,"clock":clock,"half":half,"overtime":True,"passerId":p.get('qb') or None,"receiverId":p.get('receiver') or None,"rusherId":p.get('runner') or None,"historicalGameId":p.get('game'),"historicalEventAt":p.get('at')})
            break
        # Defensive return scores are linked to the same turnover event.
        if possession_change and field <= 0:
            scores[defense] += 6 + evidence.conversion(rng, teams[defense], scores[defense] + 6 - scores[offense], clock <= 120)
            totals["defensiveTouchdowns"] += 1
            scored = True
            if overtime:
                if trace:
                    log.append({"play":plays,"drive":drives,"offense":teams[offense],"defense":teams[defense],"kind":kind,"defensiveTouchdown":True,"score":list(scores),"down":old_down,"clock":clock,"half":half,"overtime":True,"historicalGameId":p.get('game'),"historicalEventAt":p.get('at')})
                break
            field = evidence.start(rng, teams[offense])
            # Scoring defense kicks back to previous offense.
            possession_change = False
            down, distance = 1, min(10, field)
            drives += 1
        if trace:
            log.append({"play":plays,"drive":drives,"offense": teams[offense],"defense":teams[defense], "kind": kind, "yards": yards, "score": list(scores), "fieldBefore":old_field,"field": field, "down": old_down, "nextDown": 1 if possession_change else down, "clock": clock,"half":half, "overtime": overtime,"passerId":p.get('qb') or None,"receiverId":p.get('receiver') or None,"rusherId":p.get('runner') or None,"historicalGameId":p.get('game'),"historicalEventAt":p.get('at')})
        if possession_change:
            if overtime:
                ot_possessions.add(offense)
                # Both offenses receive a possession, unless a defensive score ends the game.
                if len(ot_possessions) == 2 and scores[0] != scores[1]:
                    break
            offense = defense
            field = max(1, min(99, field))
            down, distance = 1, min(10, field)
            drives += 1
        if overtime and scored and len(ot_possessions) == 2 and scores[0] != scores[1]:
            break
    totals["drives"] = drives
    totals["overtime"] = int(overtime)
    return scores, player, totals, log


def evaluate_contract(contract, scores, players):
    kind = contract.get("kind")
    if kind == "home_win":
        if scores[0] == scores[1]:
            rule = contract.get("equality", "push")
            if rule not in ("push", "yes", "no"):
                raise ValueError("equality must be push|yes|no")
            return None if rule == "push" else rule == "yes"
        return scores[0] > scores[1]
    if kind == "spread":
        value = scores[0] - scores[1]
    elif kind == "total":
        value = scores[0] + scores[1]
    elif kind == "team_total":
        if contract.get("team") not in ("home", "away"):
            raise ValueError("team_total requires home|away")
        value = scores[0 if contract["team"] == "home" else 1]
    elif kind == "player":
        stat = contract.get("stat")
        if stat == "touchdowns":
            data = players.get(contract.get("playerId"), {})
            value = data.get("receivingTouchdowns", 0) + data.get("rushingTouchdowns", 0)
        else:
            if stat not in STATS:
                raise ValueError("Unsupported player stat")
            value = players.get(contract.get("playerId"), {}).get(stat, 0)
    else:
        raise ValueError("Unknown contract kind")
    threshold = contract.get("threshold")
    if not isinstance(threshold, (float, int)) or not math.isfinite(threshold) or contract.get("direction") not in ("over", "under"):
        raise ValueError("Finite threshold and over|under direction required")
    if value == threshold:
        rule = contract.get("equality", "push")
        if rule not in ("push", "yes", "no"):
            raise ValueError("equality must be push|yes|no")
        return None if rule == "push" else rule == "yes"
    return value > threshold if contract["direction"] == "over" else value < threshold


def simulate(model, home, away, simulations=10000, seed=1, event_start=None, contracts=None, scenario=None, postseason=False, parameter_uncertainty=None, representative_games=0, **kwargs):
    if not isinstance(simulations, int) or not 1 <= simulations <= 100000:
        raise ValueError("simulations must be an integer 1..100000")
    if not isinstance(seed, int) or abs(seed) > 2**53:
        raise ValueError("Integer seed required")
    cutoff = utc(model.get("asOf", ""))
    if not event_start or utc(event_start) <= cutoff:
        raise ValueError("eventStart must be after the historical evidence cutoff")
    contracts = contracts or []
    if parameter_uncertainty:
        validate_parameter_config(parameter_uncertainty)
        if len({r['game'] for r in model['rows'] if r['o'] in (home,away)})<8:
            raise ValueError('Parameter uncertainty requires at least8 historical game blocks')
    if not isinstance(contracts, list) or len(contracts) > 32:
        raise ValueError("At most32 contract definitions")
    ids = [c.get("id") for c in contracts]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Contracts need distinct nonempty IDs")
    evidence = Evidence(model, home, away, scenario)
    if not isinstance(representative_games,int) or not 0<=representative_games<=3:raise ValueError('representativeGames must be0..3')
    known_players = {r[k] for r in evidence.rows for k in ("qb", "receiver", "runner") if r[k]}
    for contract in contracts:
        if contract.get("kind") == "player" and contract.get("playerId") not in known_players:
            raise ValueError("Player contract has no historical evidence in the selected scenario")
        evaluate_contract(contract, [0, 1], {})  # Validate before expensive work.
    rng = random.Random(seed)
    scores_hist = [Counter(), Counter()]
    total_hist, margin_hist = Counter(), Counter()
    player_hist = defaultdict(lambda: defaultdict(Counter))
    outcomes = {i: Counter() for i in ids}
    joint = Counter()
    all_totals, wins, ties = Counter(), 0, 0
    convergence = []
    representatives=[]
    checkpoints = {max(1, simulations // 10), max(1, simulations // 2), simulations}
    for index in range(simulations):
        scores, players, totals, trace = simulate_game(evidence, rng, [home, away], postseason,index<representative_games)
        if index<representative_games:representatives.append({'index':index,'score':scores,'players':dict(players),'environment':dict(totals),'plays':trace})
        wins += scores[0] > scores[1]
        ties += scores[0] == scores[1]
        for side in (0, 1):
            scores_hist[side][scores[side]] += 1
        total_hist[sum(scores)] += 1
        margin_hist[scores[0] - scores[1]] += 1
        for name, stats in players.items():
            for stat, value in stats.items():
                player_hist[name][stat][value] += 1
        all_totals.update(totals)
        joint_outcomes = []
        for contract in contracts:
            result = evaluate_contract(contract, scores, players)
            key = "push" if result is None else "yes" if result else "no"
            outcomes[contract["id"]][key] += 1
            joint_outcomes.append(key)
        if contracts:
            joint["|".join(joint_outcomes)] += 1
        if index + 1 in checkpoints:
            n = index + 1
            convergence.append({"simulations": n, "homeWinProbability": wins / n, "monteCarloSE": math.sqrt((wins / n) * (1 - wins / n) / n)})
    probabilities = []
    for contract in contracts:
        count = outcomes[contract["id"]]
        p = count["yes"] / simulations
        probabilities.append({"id": contract["id"], "probability": p, "pushProbability": count["push"] / simulations,
                              "conditionalNonPushProbability": count["yes"] / (simulations - count["push"]) if simulations != count["push"] else None,
                              "monteCarloSE": math.sqrt(p * (1 - p) / simulations), "monteCarloInterval95": wilson(count["yes"], simulations),
                              "settlement": contract})
    result={"modelVersion": model['version'],"engineVersion":ENGINE_VERSION, "inputDataVersion": model["sha256"], "provenance": model["source"], "evidenceCutoff": model["asOf"],
            "eventStart": event_start, "simulations": simulations, "seed": seed, "scenario": scenario,
            "home": home, "away": away, "homeWinProbability": wins / simulations, "awayWinProbability": (simulations - wins - ties) / simulations,
            "tieProbability": ties / simulations, "monteCarloInterval95": wilson(wins, simulations),
            "scoreDistributions": {home: histogram_summary(scores_hist[0], simulations), away: histogram_summary(scores_hist[1], simulations)},
            "totalDistribution": histogram_summary(total_hist, simulations), "marginDistribution": histogram_summary(margin_hist, simulations),
            "players": {name: {stat: histogram_summary(stats.get(stat, Counter()), simulations) for stat in STATS} for name, stats in player_hist.items()},
            "contracts": probabilities,"representativeGames":representatives, "jointOutcomes": [{"outcomes": k.split("|"), "count": v} for k, v in joint.items()],
            "convergence": convergence, "gameEnvironment": {k: v / simulations for k, v in all_totals.items()},
            "evidence": {"plays": len(evidence.rows), "games": len(evidence.games), "teamPlays": dict(evidence.counts),
                         "backoffCounts": {str(k): v for k, v in evidence.backoff.items()},"availabilityVerified":model.get('dataAvailabilityVerified',False),"modelOptions":model.get('modelOptions',{}),"shrinkageFit":model.get('shrinkageFit'),"teamResearch":{team:model.get('teamResearch',{}).get(team) for team in (home,away)}},
            "uncertainty": {"monteCarlo": "Wilson95% binomial sampling interval conditional on the fitted artifact; shrinks with simulation count.",
                            "modelInterval": None, "model": "Parameter/model uncertainty is not estimated. More games do not validate source data, injury assumptions, missing features or empirical backoff."},
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "limitations": ["Unvalidated conditional empirical play bootstrap; not evidence of beating market prices.",
                            "No penalties, special-team return fumbles, timeouts, replay, weather-adjustment fit or roster projection. Historical durations approximate clock management.",
                            "Sparse matchups back off to team/down pools; inspect backoffCounts. Historical player usage may not match a future roster.",
                            "Injury scenarios require labeled comparable historical plays; no arbitrary injury multipliers.",
                            "Scoring transitions follow an NFL-style baseline; ties push unless contract explicitly supplies equality semantics.",
                            "Historical source has not been independently verified; no real historical backtest has been run by this service."]}
    if parameter_uncertainty:
        result['uncertainty']['parameterBootstrap']=parameter_bootstrap(model,home,away,seed,contracts,scenario,postseason,parameter_uncertainty)
        result['uncertainty']['modelInterval']=result['uncertainty']['parameterBootstrap']['homeWinInterval95']
        result['uncertainty']['model']='Game-block Bayesian bootstrap parameter interval estimated separately from base-run Monte Carlo error; structural and cohort uncertainty remain unestimated.'
    return result


def validate_parameter_config(config):
    if not isinstance(config,dict) or set(config)-{'replicates','gamesPerReplicate'}:raise ValueError('Invalid parameter uncertainty configuration')
    replicates=config.get('replicates',20);count=config.get('gamesPerReplicate',1000)
    if not isinstance(replicates,int) or not 10<=replicates<=40 or not isinstance(count,int) or not 100<=count<=2000:raise ValueError('Parameter bootstrap requires10..40 replicates and100..2000 complete games per replicate')
    return replicates,count


def parameter_bootstrap(model,home,away,seed,contracts,scenario,postseason,config):
    replicates,count=validate_parameter_config(config)
    games=sorted({r['game'] for r in model['rows'] if r['o'] in (home,away)})
    if len(games)<8:raise ValueError('Parameter uncertainty requires at least8 historical game blocks')
    rng=random.Random(seed^0x5a17);home_estimates=[];contract_estimates={c['id']:[] for c in contracts};inner_variances=[]
    for index in range(replicates):
        weights={game:max(1e-12,rng.expovariate(1)) for game in games}
        evidence=Evidence(model,home,away,scenario,weights);stream=random.Random(seed+7919*(index+1));wins=0;hits=Counter()
        for _ in range(count):
            score,players,_,_=simulate_game(evidence,stream,[home,away],postseason);wins+=score[0]>score[1]
            for c in contracts:hits[c['id']]+=evaluate_contract(c,score,players) is True
        p=wins/count;home_estimates.append(p);inner_variances.append(p*(1-p)/count)
        for c in contracts:contract_estimates[c['id']].append(hits[c['id']]/count)
    def interval(values):
        ordered=sorted(values);return[ordered[max(0,int(.025*len(ordered)))],ordered[min(len(ordered)-1,math.ceil(.975*len(ordered))-1)]]
    mean=sum(home_estimates)/replicates;raw_variance=sum((p-mean)**2 for p in home_estimates)/(replicates-1);inner=sum(inner_variances)/replicates
    return{'method':'Bayesian bootstrap of whole historical-game weights; all related plays share a block weight. Quantile spread includes finite inner-run numerical noise.','replicates':replicates,'gamesPerReplicate':count,'completeGames':replicates*count,'historicalGameBlocks':len(games),'homeWinInterval95':interval(home_estimates),'homeWinParameterSDNoiseCorrected':math.sqrt(max(0,raw_variance-inner)),'meanInnerMonteCarloSE':math.sqrt(inner),'contracts':{key:{'parameterInterval95':interval(values)} for key,values in contract_estimates.items()},'seed':seed^0x5a17,'limitations':'Not structural uncertainty, future roster/availability uncertainty or proof of calibration; increasing the base simulation count does not narrow this independent bootstrap interval.'}


def main():
    request = json.load(sys.stdin)
    if request.get("action") == "fit":
        try:
            from .fit import fit_csv
        except ImportError:
            from fit import fit_csv
        result = fit_csv(request["csv"], request["source"], request["asOf"], request.get("teamMinPlays", 100),request.get('options'))
    else:
        result = simulate(request["model"], request["home"], request["away"], request.get("simulations", 10000), request.get("seed", 1), request.get("eventStart"), request.get("contracts"), request.get("scenario"), request.get("postseason", False),parameter_uncertainty=request.get('parameterUncertainty'),representative_games=request.get('representativeGames',0))
    json.dump(result, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
