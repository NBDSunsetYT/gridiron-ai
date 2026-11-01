"""Separate NCAA Division-I empirical complete-game simulation protocol.

No NFL rates, player identities or model artifacts are accepted. Outcomes are
sampled from an explicitly fitted CFB play corpus. This is an uncalibrated
research baseline; unsupported roster/injury/weather effects stay unavailable.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone

from .fit import fit_csv, VERSION, ENHANCED_VERSION, utc
from .simulator import (Evidence, STATS, histogram_summary, wilson,
                        evaluate_contract, validate_selected_outcomes,
                        combination_summary, validate_parameter_config)

MODEL_VERSION = 'cfb-pbp-empirical-8.0.0'
ENGINE_VERSION = 'cfb-pbp-runtime-8.0.0'
RULES_VERSION = 'ncaa-2026-di-v1'
RULES_URL = 'https://ncaaorg.s3.amazonaws.com/championships/sports/football/rules/PRMFB_RulesBook.pdf'
RULES_SHA256 = '2a9e63b038b6efc70ad846487f33fdda175993c2229c911c3e06291ec74a9dd5'
RULE_CHANGES_URL = 'https://ncaaorg.s3.amazonaws.com/championships/sports/football/rules/2026PRMFB_2026RuleChanges.pdf'
STATISTICS_SOURCE = 'https://fs.ncaa.org.s3.amazonaws.com/Docs/stats/Stats_Manuals/Football.pdf'


def fit_cfb_csv(raw, source, as_of, team_min_plays=100, options=None):
    """Validate the existing normalized play protocol, with explicit CFB IDs.

    CFB game-clock deltas may legitimately be zero. Generic source validation
    uses a temporary positive clock value, after which the original observed
    zero is restored. No second is added to the fitted or simulated CFB clock.
    """
    if not isinstance(raw, str) or not raw.strip() or len(raw.encode()) > 20_000_000:
        raise ValueError('A bounded, normalized CFB historical corpus is required')
    reader = csv.DictReader(io.StringIO(raw))
    fields = reader.fieldnames or []
    if 'sport' not in fields:
        raise ValueError('Every CFB historical play must explicitly identify sport=CFB')
    rows, stopped = [], []
    for index, row in enumerate(reader):
        if index >= 100000:
            raise ValueError('Maximum 100,000 CFB plays per fitted artifact')
        if row.get('sport') != 'CFB':
            raise ValueError('NFL and CFB historical plays must never share a fitted artifact')
        for key in ('offense', 'defense'):
            if not str(row.get(key, '')).startswith('cfb:'):
                raise ValueError('CFB team identities require an explicit cfb: namespace')
        for key in ('passer_id', 'receiver_id', 'rusher_id'):
            if row.get(key) and not row[key].startswith('cfb:'):
                raise ValueError('CFB player identities require an explicit cfb: namespace')
        if row.get('play_type') == 'sack' and not row.get('passer_id'):
            raise ValueError('CFB sacks require the identified quarterback for NCAA rushing statistics')
        if row.get('play_type') == 'sack' and float(row.get('yards_gained',0)) >= 0:
            raise ValueError('An NCAA sack must have negative observed rushing yardage')
        try:
            seconds = float(row.get('elapsed_seconds', ''))
        except (TypeError, ValueError) as exc:
            raise ValueError('Observed CFB game-clock deltas are required') from exc
        if not math.isfinite(seconds) or int(seconds) != seconds or not 0 <= seconds <= 90:
            raise ValueError('Observed CFB game-clock deltas must be integers 0..90')
        stopped.append(seconds == 0)
        normalized = dict(row)
        if seconds == 0:
            normalized['elapsed_seconds'] = '1'
        rows.append(normalized)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    result = fit_csv(stream.getvalue(), source, as_of, team_min_plays, options)
    model = result['model']
    for row, was_stopped in zip(model['rows'], stopped):
        if was_stopped:
            row['elapsed'] = 0
    for fitted, original in zip(model['rows'], rows):
        if original.get('turnover_net') not in (None, ''):
            net=float(original['turnover_net'])
            if not math.isfinite(net) or int(net)!=net or not -199<=net<=199:
                raise ValueError('Observed CFB turnover field-position change must be an integer -199..199')
            fitted['turnoverNet']=int(net)
    model.update(version=MODEL_VERSION, sport='CFB', sourceDatasetSport='CFB',
                 rulesVersion=RULES_VERSION, rulesSource=RULES_URL,
                 sourceSha256=hashlib.sha256(raw.encode()).hexdigest(),
                 syntheticEvidence='synthetic' in source.lower() or any(
                     r.get('reliability', '').lower() == 'synthetic' for r in rows))
    model['sha256'] = hashlib.sha256(json.dumps({
        'source': model['sourceSha256'], 'model': MODEL_VERSION,
        'rules': RULES_VERSION, 'asOf': model['asOf'], 'options': model.get('modelOptions', {})
    }, sort_keys=True).encode()).hexdigest()
    result['summary'].update(sport='CFB', modelVersion=MODEL_VERSION,
                             inputDataVersion=model['sha256'], rulesVersion=RULES_VERSION,
                             syntheticEvidence=model['syntheticEvidence'])
    result['summary']['limitations'] = limitations()
    # Validate overtime evidence before accepting a publishable artifact.
    eligible = model.get('teams', [])
    if len(eligible) >= 2:
        CFBEvidence(model, eligible[0], eligible[1])
    return result


def limitations():
    return [
        'Uncalibrated CFB historical play-resampling baseline; no market advantage or prospective accuracy is established.',
        'Player statistics emerge from shared plays. Historical usage does not establish future depth charts, transfers or snap restrictions.',
        'Injury scenarios require labeled comparable CFB historical cohorts. Unsupported quarterback, injury, weather, conference or talent multipliers are not applied.',
        'Exact opponent/down/field/script pools back off to team/down evidence; conference, strength-of-schedule and talent are not independently fitted causal adjustments.',
        'Observed CFB game-clock deltas approximate tempo, stoppages and management. Timeouts, replay, penalties and explicit two-minute clock administration are not individually simulated.',
        'NCAA core scoring and overtime use the 2026 Division-I protocol. Rare one-point try safeties, defensive try returns, fair-catch kicks, kickoff-return touchdowns, blocked-kick returns and special-team return fumbles are outside coverage.',
        'Two-point outcomes use team evidence where sufficient, otherwise labeled CFB-only league conversion evidence. Conversion attempts do not add ordinary player statistics.',
        'Monte Carlo intervals measure numerical sampling noise. More complete games do not establish calibration or resolve model/availability uncertainty.',
    ]


class CFBEvidence(Evidence):
    def __init__(self, model, home, away, scenario=None, game_weights=None):
        if (model.get('sport') != 'CFB' or model.get('sourceDatasetSport') != 'CFB'
                or model.get('version') != MODEL_VERSION or model.get('rulesVersion') != RULES_VERSION):
            raise ValueError('A separate fitted CFB artifact with the supported NCAA rules version is required')
        if not all(isinstance(value, str) and value.startswith('cfb:') for value in (home, away)):
            raise ValueError('CFB team identities require the cfb: namespace')
        # Reuse generic empirical pooling, never NFL priors or transition rules.
        view = dict(model, version=ENHANCED_VERSION if model.get('modelOptions') else VERSION)
        super().__init__(view, home, away, scenario, game_weights)
        memberships=defaultdict(set)
        for row in self.rows:
            for key in ('qb','receiver','runner'):
                if row.get(key):memberships[row[key]].add(row['o'])
        if any(len(teams)>1 for teams in memberships.values()):
            raise ValueError('A CFB player appears for both selected teams; current identity/transfer assignment must be verified')
        self.two_points = defaultdict(list)
        self.two_point_league = []
        for row in model['rows']:
            if row.get('kind') == 'two_point':
                if scenario and row.get('availability', {}).get(scenario['playerId']) != scenario['status']:
                    continue
                if id(row) not in self.row_weights:
                    weight=(game_weights or {}).get(row['game'],1.)
                    half_life=self.options.get('recencyHalfLifeDays')
                    if half_life:weight*=math.exp(-math.log(2)*(utc(model['asOf'])-utc(row['at'])).total_seconds()/(86400*half_life))
                    self.row_weights[id(row)]=weight
                self.two_points[row['o']].append(row)
                self.two_point_league.append(row)
        for team in (home, away):
            pool = self.two_points[team]
            if len(pool) < 3 or len({r['fg'] for r in pool}) < 2:
                pool = self.two_point_league
            if len(pool) < 3 or len({r['fg'] for r in pool}) < 2:
                raise ValueError('Insufficient CFB two-point conversion evidence to model NCAA overtime')
        self.conversion_backoff = Counter()

    def two_point(self, rng, team):
        pool = self.two_points[team]
        if len(pool) < 3 or len({r['fg'] for r in pool}) < 2:
            pool = self.two_point_league
            self.conversion_backoff['cfb_league'] += 1
        else:
            self.conversion_backoff['team'] += 1
        return 2 if self.draw(rng, pool)['fg'] else 0


def apply_play(p, field, players, totals):
    """One sampled event updates the same quarterback/receiver/rusher game."""
    kind, yards, changed, touchdown, safety, points = p['kind'], p['yards'], False, False, False, 0
    old_field = field
    if kind == 'pass':
        players[p['qb']]['passingAttempts'] += 1
        if p['receiver']:
            players[p['receiver']]['targets'] += 1
        if p['int']:
            players[p['qb']]['interceptions'] += 1
            totals['interceptions'] += 1
            field = 100 - old_field - p['turnoverNet'] if 'turnoverNet' in p else 100 - max(0, min(100, field - yards)) - p['return']
            changed = True
        elif p['complete']:
            gain = min(yards, field)
            players[p['qb']]['completions'] += 1
            players[p['qb']]['passingYards'] += gain
            players[p['receiver']]['receptions'] += 1
            players[p['receiver']]['receivingYards'] += gain
            field -= yards
        else:
            yards = 0
    elif kind in ('rush', 'kneel'):
        players[p['runner']]['carries'] += 1
        players[p['runner']]['rushingYards'] += min(yards, field)
        field -= yards
    elif kind == 'sack':
        if not p.get('qb'):
            raise ValueError('CFB sack quarterback identity is unavailable')
        totals['sacks'] += 1
        # NCAA sacks count against quarterback rushing attempts and yards.
        players[p['qb']]['carries'] += 1
        players[p['qb']]['rushingYards'] += min(yards, field)
        field -= yards
    elif kind == 'spike':
        players[p['qb']]['passingAttempts'] += 1
        yards = 0
    elif kind == 'punt':
        totals['punts'] += 1
        landing = field - p['punt']
        field = 80 if landing <= 0 else 100 - landing - p['return']
        changed = True
    elif kind == 'field_goal':
        totals['fieldGoalAttempts'] += 1
        if p['fg']:
            totals['fieldGoals'] += 1
            points = 3
        # NCAA missed kicks use the previous spot, with the own-20 floor.
        field = max(1, min(80, 100 - old_field))
        changed = True
    else:
        raise ValueError('Conversions cannot be ordinary scrimmage plays')
    if not changed:
        if p['fumble']:
            totals['fumblesLost'] += 1
            field = 100 - old_field - p['turnoverNet'] if 'turnoverNet' in p else 100 - max(0, min(100, field)) - p['return']
            changed = True
        elif field <= 0:
            totals['touchdowns'] += 1
            points, touchdown, changed = 6, True, True
            if kind == 'pass':
                players[p['qb']]['passingTouchdowns'] += 1
                players[p['receiver']]['receivingTouchdowns'] += 1
            elif kind in ('rush', 'kneel'):
                players[p['runner']]['rushingTouchdowns'] += 1
        elif field >= 100:
            totals['safeties'] += 1
            safety, changed = True, True
    return field, yards, changed, touchdown, safety, points


def simulate_cfb_game(evidence, rng, teams, trace=False):
    scores, players, totals, log = [0, 0], defaultdict(Counter), Counter(), []
    first = rng.randrange(2)
    offense, quarter, remaining = first, 1, 900
    field = evidence.start(rng, teams[offense])
    down, distance, plays, drives = 1, min(10, field), 0, 1
    while quarter <= 4:
        if remaining <= 0:
            quarter += 1
            if quarter > 4:
                break
            remaining = 900
            if quarter == 3:
                offense = 1 - first
                field = evidence.start(rng, teams[offense])
                down, distance, drives = 1, min(10, field), drives + 1
            continue
        if plays >= 1000:
            raise ValueError('CFB game exceeded the supported 1,000-play clock bound')
        defense = 1 - offense
        # Late-half contexts follow the same actual CFB clock representation.
        half_remaining = remaining + (900 if quarter in (1, 3) else 0)
        p = evidence.sample(rng, teams[offense], teams[defense], down, field, distance,
                            scores[offense] - scores[defense], half_remaining)
        old_field, old_down = field, down
        plays += 1
        totals['plays'] += 1
        remaining -= min(remaining, p['elapsed'])
        field, yards, changed, touchdown, safety, points = apply_play(p, field, players, totals)
        scores[offense] += points
        if touchdown:
            scores[offense] += evidence.conversion(rng, teams[offense], scores[offense]-scores[defense], half_remaining <= 120)
        if safety:
            scores[defense] += 2
        defensive_td = changed and not touchdown and not safety and p['kind'] != 'field_goal' and field <= 0
        if defensive_td:
            scores[defense] += 6 + evidence.conversion(rng, teams[defense], scores[defense]+6-scores[offense], half_remaining <= 120)
            totals['defensiveTouchdowns'] += 1
            field = evidence.start(rng, teams[offense])
            changed = False
            down, distance, drives = 1, min(10, field), drives + 1
        elif not changed:
            if yards >= distance:
                down, distance = 1, min(10, field)
            else:
                down, distance = down+1, max(1, distance-yards)
                if down > 4:
                    field, changed = 100-field, True
        if trace:
            log.append({'play':plays, 'drive':drives, 'quarter':quarter, 'clock':remaining,
                        'offense':teams[offense], 'defense':teams[defense], 'kind':p['kind'],
                        'fieldBefore':old_field, 'down':old_down, 'yards':yards,
                        'score':list(scores), 'overtime':False,
                        'passerId':p.get('qb') or None, 'receiverId':p.get('receiver') or None,
                        'rusherId':p.get('runner') or None, 'historicalGameId':p.get('game')})
        if changed:
            offense = defense
            if touchdown or safety or points:
                field = evidence.start(rng, teams[offense])
            field = max(1, min(99, field))
            down, distance, drives = 1, min(10, field), drives+1
    if scores[0] == scores[1]:
        simulate_cfb_overtime(evidence, rng, teams, scores, players, totals, log if trace else None)
    totals['drives'] += drives
    totals['regulationQuarters'] = 4
    return scores, players, totals, log


def simulate_cfb_overtime(evidence, rng, teams, scores, players, totals, log=None):
    """NCAA Rule 3-1-3: paired possessions; no NFL sudden-death clock."""
    totals['overtime'] = 1
    first = rng.randrange(2)
    for period in range(1, 65):
        totals['overtimePeriods'] = period
        order = (first, 1-first) if period % 2 else (1-first, first)
        for turn, offense in enumerate(order):
            defense = 1-offense
            totals['overtimePossessions'] += 1
            totals['drives'] += 1
            if period >= 3:
                points = evidence.two_point(rng, teams[offense])
                scores[offense] += points
                totals['twoPointAttempts'] += 1
                if log is not None:
                    log.append({'overtime':True, 'overtimePeriod':period, 'offense':teams[offense],
                                'kind':'two_point', 'fieldBefore':3, 'clock':None,
                                'score':list(scores), 'ordinaryPlayerStatistics':False})
                continue
            field, down, distance = 25, 1, 10
            for _ in range(100):
                p = evidence.sample(rng, teams[offense], teams[defense], down, field, distance,
                                    scores[offense]-scores[defense], 0)
                old_field, old_down = field, down
                totals['plays'] += 1
                field, yards, changed, touchdown, safety, points = apply_play(p, field, players, totals)
                scores[offense] += points
                if safety or (changed and not touchdown and p['kind'] != 'field_goal' and field <= 0):
                    scores[defense] += 2 if safety else 6
                    totals['safeties' if safety else 'defensiveTouchdowns'] += int(not safety)
                    if log is not None:
                        log.append({'overtime':True, 'overtimePeriod':period, 'offense':teams[offense],
                                    'kind':p['kind'], 'defensiveScore':True, 'clock':None, 'score':list(scores)})
                    return
                if touchdown:
                    # No unnecessary try once the second possession has won.
                    if turn == 0 or scores[offense] <= scores[defense]:
                        scores[offense] += evidence.two_point(rng, teams[offense]) if period >= 2 else evidence.conversion(rng, teams[offense], scores[offense]-scores[defense], True)
                if log is not None:
                    log.append({'overtime':True, 'overtimePeriod':period, 'offense':teams[offense],
                                'kind':p['kind'], 'fieldBefore':old_field, 'down':old_down,
                                'yards':yards, 'clock':None, 'score':list(scores),
                                'passerId':p.get('qb') or None, 'receiverId':p.get('receiver') or None,
                                'rusherId':p.get('runner') or None, 'historicalGameId':p.get('game')})
                if changed:
                    break
                if yards >= distance:
                    down, distance = 1, min(10, field)
                else:
                    down, distance = down+1, max(1, distance-yards)
                    if down > 4:
                        break
            else:
                raise ValueError('CFB overtime drive exceeded its bounded play limit')
        if scores[0] != scores[1]:
            return
    raise ValueError('CFB overtime did not resolve; inspect conversion evidence rather than inventing a winner')


def simulate_cfb(model, home, away, simulations=10000, seed=1, event_start=None,
                 contracts=None, scenario=None, parameter_uncertainty=None,
                 representative_games=0, selected_outcomes=None):
    if isinstance(simulations, bool) or not isinstance(simulations, int) or not 1 <= simulations <= 100000:
        raise ValueError('CFB simulations must be an integer 1..100000 complete games')
    if isinstance(seed, bool) or not isinstance(seed, int) or abs(seed) > 2**53:
        raise ValueError('An integer reproducible seed is required')
    if not event_start or utc(event_start) <= utc(model.get('asOf', '')):
        raise ValueError('The CFB event must begin after the historical evidence cutoff')
    if not isinstance(representative_games, int) or isinstance(representative_games, bool) or not 0 <= representative_games <= 3:
        raise ValueError('representativeGames must be 0..3')
    evidence = CFBEvidence(model, home, away, scenario)
    contracts = contracts or []
    if not isinstance(contracts, list) or len(contracts) > 32:
        raise ValueError('At most 32 exact CFB contract definitions are supported')
    ids = [c.get('id') if isinstance(c, dict) else None for c in contracts]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('CFB contracts require distinct nonempty IDs')
    known = {r[k] for r in evidence.rows for k in ('qb','receiver','runner') if r.get(k)}
    for contract in contracts:
        if contract.get('kind') == 'player' and contract.get('playerId') not in known:
            raise ValueError('The selected CFB player has no verified historical evidence')
        evaluate_contract(contract, [0, 1], {})
    selected = validate_selected_outcomes(contracts, selected_outcomes)
    if parameter_uncertainty:
        validate_parameter_config(parameter_uncertainty)
        if len(evidence.games) < 8:
            raise ValueError('CFB parameter uncertainty requires at least eight historical game blocks')
    rng, scores_hist = random.Random(seed), [Counter(), Counter()]
    totals_hist, margin_hist, environment, joint = Counter(), Counter(), Counter(), Counter()
    player_hist = defaultdict(lambda:defaultdict(Counter))
    outcomes = {key:Counter() for key in ids}
    wins, convergence, representative = 0, [], []
    from .storage_summary import CorrelationSummary, run_manifest
    correlations=CorrelationSummary(evidence.rows)
    checkpoints = {max(1, simulations//10), max(1, simulations//2), simulations}
    for index in range(simulations):
        score, players, totals, trace = simulate_cfb_game(evidence, rng, [home, away], index < representative_games)
        if score[0] == score[1]:
            raise ValueError('A complete NCAA game cannot be published as tied')
        correlations.add(score, players)
        wins += score[0] > score[1]
        if index < representative_games:
            representative.append({'index':index,'score':score,'players':dict(players),'environment':dict(totals),'plays':trace})
        for side in (0,1):scores_hist[side][score[side]] += 1
        totals_hist[sum(score)] += 1
        margin_hist[score[0]-score[1]] += 1
        for player, statistics in players.items():
            statistics['touchdowns'] = statistics.get('rushingTouchdowns',0)+statistics.get('receivingTouchdowns',0)
            for stat, value in statistics.items():player_hist[player][stat][value] += 1
        environment.update(totals)
        encoded = []
        for contract in contracts:
            outcome = evaluate_contract(contract, score, players)
            key = 'push' if outcome is None else 'yes' if outcome else 'no'
            outcomes[contract['id']][key] += 1
            encoded.append(key)
        if contracts:joint['|'.join(encoded)] += 1
        if index+1 in checkpoints:
            count = index+1
            convergence.append({'simulations':count,'homeWinProbability':wins/count,
                                'monteCarloSE':math.sqrt((wins/count)*(1-wins/count)/count)})
    probabilities = []
    for contract in contracts:
        count = outcomes[contract['id']]
        p = count['yes']/simulations
        probabilities.append({'id':contract['id'],'probability':p,'pushProbability':count['push']/simulations,
                              'conditionalNonPushProbability':count['yes']/(simulations-count['push']) if count['push'] != simulations else None,
                              'monteCarloSE':math.sqrt(p*(1-p)/simulations),'monteCarloInterval95':wilson(count['yes'],simulations),'settlement':contract})
    result = {'sport':'CFB','modelVersion':MODEL_VERSION,'engineVersion':ENGINE_VERSION,'rulesVersion':RULES_VERSION,
              'rules':{'source':RULES_URL,'verifiedDocumentSha256':RULES_SHA256,'changesSource':RULE_CHANGES_URL,
                       'statisticsSource':STATISTICS_SOURCE,
                       'regulationQuarters':4,'quarterSeconds':900,'overtimeClock':None,
                       'firstTwoOvertimeStartYardsToGoal':25,'mandatoryTwoPointAfterTouchdownFromOvertime':2,
                       'alternatingTwoPointFromOvertime':3,'twoPointYardsToGoal':3},
              'inputDataVersion':model['sha256'],'provenance':model['source'],'evidenceCutoff':model['asOf'],
              'eventStart':event_start,'simulations':simulations,'seed':seed,'scenario':scenario,
              'home':home,'away':away,'homeWinProbability':wins/simulations,'awayWinProbability':1-wins/simulations,
              'tieProbability':0.,'calibratedProbability':None,'monteCarloInterval95':wilson(wins,simulations),
              'distributionEncoding':'exact_integer_frequency_v1',
              'scoreDistributions':{home:histogram_summary(scores_hist[0],simulations),away:histogram_summary(scores_hist[1],simulations)},
              'totalDistribution':histogram_summary(totals_hist,simulations),'marginDistribution':histogram_summary(margin_hist,simulations),
              'players':{player:{stat:histogram_summary(player_hist[player].get(stat,Counter()),simulations) for stat in STATS} for player in sorted(known)},
              'contracts':probabilities,'jointOutcomes':[{'outcomes':key.split('|'),'count':count} for key,count in joint.items()],
              'representativeGames':representative,'convergence':convergence,
              'gameEnvironment':{key:value/simulations for key,value in environment.items()},
              'evidence':{'sport':'CFB','plays':len(evidence.rows),'games':len(evidence.games),
                          'teamPlays':dict(evidence.counts),'availabilityVerified':model.get('dataAvailabilityVerified',False),
                          'synthetic':model.get('syntheticEvidence',False),'backoffCounts':dict(evidence.backoff),
                          'conversionBackoffCounts':dict(evidence.conversion_backoff),'teamResearch':model.get('teamResearch',{})},
              'statisticCoverage':{'period':'full_game_including_overtime','touchdowns':'offensive_rushing_receiving_only',
                                   'sacks':'NCAA_quarterback_rushing_attempts_and_yards','conversionAttemptsInPlayerStats':False},
              'uncertainty':{'monteCarlo':'Wilson95% conditional sampling interval; independent from historical model uncertainty.',
                             'modelInterval':None,'model':'Model/parameter sensitivity and future availability remain unestimated unless a separate CFB game-block bootstrap is supplied.'},
              'limitations':limitations(),'createdAt':datetime.now(timezone.utc).isoformat()}
    if selected:result['combination'] = combination_summary(contracts,joint,selected,simulations)
    if parameter_uncertainty:
        bootstrap = cfb_parameter_bootstrap(model, home, away, seed, contracts, scenario, parameter_uncertainty)
        result['uncertainty'].update(parameterBootstrap=bootstrap,modelInterval=bootstrap['homeWinInterval95'],
                                     model='Separate CFB game-block bootstrap sensitivity; not validated predictive coverage or structural/availability uncertainty.')
    result['correlations']=correlations.summary()
    result['runManifest']=run_manifest(model,home,away,simulations,seed,event_start,contracts,scenario,representative_games,parameter_uncertainty,selected_outcomes,'CFB')
    return result


def cfb_parameter_bootstrap(model, home, away, seed, contracts, scenario, config):
    replicates, count = validate_parameter_config(config)
    selected_games={r['game'] for r in model['rows'] if r['o'] in (home,away)}
    games = sorted(selected_games|{r['game'] for r in model['rows'] if r['kind']=='two_point'})
    if len(selected_games) < 8:raise ValueError('CFB parameter bootstrap requires eight selected-team historical game blocks')
    rng, estimates, contract_values = random.Random(seed ^ 0xCFB8), [], {c['id']:[] for c in contracts}
    for index in range(replicates):
        weights = {game:max(1e-12,rng.expovariate(1)) for game in games}
        evidence, stream, wins, hits = CFBEvidence(model,home,away,scenario,weights), random.Random(seed+7919*(index+1)), 0, Counter()
        for _ in range(count):
            scores, players, _, _ = simulate_cfb_game(evidence,stream,[home,away])
            wins += scores[0] > scores[1]
            for contract in contracts:hits[contract['id']] += evaluate_contract(contract,scores,players) is True
        estimates.append(wins/count)
        for key in contract_values:contract_values[key].append(hits[key]/count)
    def interval(values):
        ordered=sorted(values)
        return [ordered[max(0,int(.025*len(ordered)))],ordered[min(len(ordered)-1,math.ceil(.975*len(ordered))-1)]]
    return {'method':'Bayesian bootstrap of CFB historical game blocks, including source games contributing league two-point fallback evidence; finite inner-game sampling noise remains.',
            'historicalGameBlocks':len(games),'selectedTeamHistoricalGameBlocks':len(selected_games),'replicates':replicates,'gamesPerReplicate':count,
            'completeGames':replicates*count,'homeWinInterval95':interval(estimates),
            'contracts':{key:{'parameterInterval95':interval(values)} for key,values in contract_values.items()},
            'limitations':'Increasing the primary simulation count does not narrow this separately sampled sensitivity interval.'}
