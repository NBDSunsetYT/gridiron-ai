"""SYNTHETIC CFB mechanics only; never historical calibration evidence."""
import copy
import csv
import io
import json
import random
import unittest
from collections import Counter, defaultdict

from .test_simulator import fixture_csv, MechanicalEvidence
from .cfb_simulator import (fit_cfb_csv, CFBEvidence, simulate_cfb,
                            simulate_cfb_game, simulate_cfb_overtime, apply_play,
                            cfb_parameter_bootstrap, MODEL_VERSION, RULES_VERSION)


def cfb_fixture_csv(games=4):
    rows = list(csv.DictReader(io.StringIO(fixture_csv())))
    fields = list(rows[0]) + ['sport']
    result = []
    for row in rows:
        item = dict(row, sport='CFB')
        for key in ('offense','defense','passer_id','receiver_id','rusher_id'):
            if item[key]:item[key] = 'cfb:'+item[key]
        item['availability'] = json.dumps({'cfb:'+key:value for key,value in json.loads(item['availability']).items()})
        result.append(item)
    for game in range(4, games):
        for row in result[:336]:
            item = dict(row, game_id='SYNTHETIC-'+str(game), played_at=f'2024-01-{game+1:02}T12:00:00Z')
            result.append(item)
    for game in range(games):
        for team,defense in (('cfb:SYNTH-A','cfb:SYNTH-B'),('cfb:SYNTH-B','cfb:SYNTH-A')):
            for index in range(4):
                item=dict(result[0],game_id=f'SYNTHETIC-{game}',play_id=f'{team}-2PT-{index}',
                          played_at=f'2024-01-{game+1:02}T12:00:00Z',offense=team,defense=defense,
                          play_type='two_point',down='1',yards_to_go='3',yardline_100='3',
                          yards_gained='0',drive_start='0',complete_pass='0',field_goal_made=str(index%2),
                          passer_id='',receiver_id='',rusher_id='',availability='{}')
                result.append(item)
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(result)
    return stream.getvalue()


class CFBMechanicalEvidence(MechanicalEvidence):
    def __init__(self, kind, yards=0):
        super().__init__(kind,yards)
        self.attempts=Counter()

    def two_point(self,rng,team):
        self.attempts[team]+=1
        # A deterministic fixture resolves at OT3 without assuming a real rate.
        return 2 if team=='cfb:SYNTH-A' else 0


class CFBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=cfb_fixture_csv()
        cls.model=fit_cfb_csv(cls.raw,'SYNTHETIC CFB MECHANICAL FIXTURE','2024-02-01T00:00:00Z')['model']

    def test_explicit_sport_and_player_namespaces(self):
        self.assertEqual(self.model['sport'],'CFB')
        self.assertEqual(self.model['version'],MODEL_VERSION)
        self.assertEqual(self.model['rulesVersion'],RULES_VERSION)
        self.assertTrue(self.model['syntheticEvidence'])
        for raw in (self.raw.replace('CFB','NFL'),fixture_csv()):
            with self.assertRaises(ValueError):fit_cfb_csv(raw,'SYNTHETIC','2024-02-01T00:00:00Z')
        wrong=dict(self.model,sport='NFL')
        with self.assertRaises(ValueError):CFBEvidence(wrong,'cfb:SYNTH-A','cfb:SYNTH-B')

    def test_observed_stopped_clock_has_no_invented_one_second(self):
        rows=list(csv.DictReader(io.StringIO(self.raw)));rows[0]['elapsed_seconds']='0'
        out=io.StringIO();w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        model=fit_cfb_csv(out.getvalue(),'SYNTHETIC','2024-02-01T00:00:00Z')['model']
        self.assertEqual(model['rows'][0]['elapsed'],0)

    def test_shared_passing_yards_completions_and_touchdowns(self):
        e=CFBEvidence(self.model,'cfb:SYNTH-A','cfb:SYNTH-B')
        scores,players,environment,trace=simulate_cfb_game(e,random.Random(3),['cfb:SYNTH-A','cfb:SYNTH-B'],True)
        self.assertNotEqual(*scores)
        self.assertEqual(environment['regulationQuarters'],4)
        for team in ('cfb:SYNTH-A','cfb:SYNTH-B'):
            self.assertEqual(players[team+'-QB']['passingYards'],players[team+'-WR']['receivingYards'])
            self.assertEqual(players[team+'-QB']['completions'],players[team+'-WR']['receptions'])
            self.assertEqual(players[team+'-QB']['passingTouchdowns'],players[team+'-WR']['receivingTouchdowns'])
        self.assertEqual({p['quarter'] for p in trace if not p['overtime']},{1,2,3,4})
        self.assertGreater(environment['plays'],40)

    def test_sacks_are_ncaa_quarterback_rushing_statistics(self):
        p=CFBMechanicalEvidence('sack',-7).sample(None,'cfb:SYNTH-A',None,None,None,None,None,None)
        players=defaultdict(Counter);totals=Counter()
        field,*_=apply_play(p,60,players,totals)
        self.assertEqual(field,67)
        self.assertEqual(players['cfb:SYNTH-A-QB']['carries'],1)
        self.assertEqual(players['cfb:SYNTH-A-QB']['rushingYards'],-7)
        self.assertEqual(players['cfb:SYNTH-A-QB']['passingAttempts'],0)
        self.assertEqual(totals['sacks'],1)

    def test_nonnegative_yards_cannot_be_fitted_as_an_ncaa_sack(self):
        rows=list(csv.DictReader(io.StringIO(self.raw)))
        rows[0].update(play_type='sack',complete_pass='0',receiver_id='',yards_gained='0')
        out=io.StringIO();writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        with self.assertRaisesRegex(ValueError,'negative observed rushing yardage'):
            fit_cfb_csv(out.getvalue(),'SYNTHETIC','2024-02-01T00:00:00Z')

    def test_ncaa_missed_field_goal_uses_previous_spot_not_nfl_kick_spot(self):
        p=CFBMechanicalEvidence('field_goal').sample(None,'cfb:SYNTH-A',None,None,None,None,None,None);p['fg']=0
        self.assertEqual(apply_play(p,30,defaultdict(Counter),Counter())[0],70)
        self.assertEqual(apply_play(p,10,defaultdict(Counter),Counter())[0],80)

    def test_ncaa_overtime_is_paired_25_yard_then_three_yard_tries(self):
        evidence=CFBMechanicalEvidence('pass',99)
        scores,players,totals,trace=[0,0],defaultdict(Counter),Counter(),[]
        simulate_cfb_overtime(evidence,random.Random(1),['cfb:SYNTH-A','cfb:SYNTH-B'],scores,players,totals,trace)
        # OT1: both 7. OT2: A8/B6, so A wins without a third period.
        self.assertEqual(scores,[15,13]);self.assertEqual(totals['overtimePeriods'],2)
        self.assertEqual([r['fieldBefore'] for r in trace],[25,25,25,25])
        self.assertTrue(all(r['clock'] is None for r in trace))
        self.assertEqual(sum(p['passingAttempts'] for p in players.values()),4)
        self.assertEqual(sum(evidence.attempts.values()),2)

    def test_third_overtime_tries_do_not_inflate_player_stats(self):
        evidence=CFBMechanicalEvidence('punt',0)
        scores,players,totals,trace=[3,3],defaultdict(Counter),Counter(),[]
        simulate_cfb_overtime(evidence,random.Random(1),['cfb:SYNTH-A','cfb:SYNTH-B'],scores,players,totals,trace)
        self.assertEqual(scores,[5,3]);self.assertEqual(totals['overtimePeriods'],3)
        self.assertEqual(len([p for p in trace if p.get('kind')=='two_point']),2)
        self.assertTrue(all(p['fieldBefore']==3 for p in trace if p.get('kind')=='two_point'))
        self.assertEqual(sum(sum(p.values()) for p in players.values()),0)

    def test_second_possession_walkoff_touchdown_does_not_add_unneeded_try(self):
        class Walkoff(CFBMechanicalEvidence):
            def sample(self,rng,team,*rest):
                return CFBMechanicalEvidence('field_goal' if team=='cfb:SYNTH-B' else 'pass',99).sample(rng,team,*rest)
        scores,players,totals,trace=[0,0],defaultdict(Counter),Counter(),[]
        simulate_cfb_overtime(Walkoff('pass'),random.Random(0),['cfb:SYNTH-A','cfb:SYNTH-B'],scores,players,totals,trace)
        self.assertEqual(scores,[6,3])

    def test_insufficient_injury_and_two_point_cohorts_are_withheld(self):
        with self.assertRaises(ValueError):CFBEvidence(self.model,'cfb:SYNTH-A','cfb:SYNTH-B',{'playerId':'cfb:SYNTH-A-WR','status':'inactive'})
        model=copy.deepcopy(self.model);model['rows']=[r for r in model['rows'] if r['kind']!='two_point']
        with self.assertRaisesRegex(ValueError,'two-point'):CFBEvidence(model,'cfb:SYNTH-A','cfb:SYNTH-B')

    def test_cfb_reproducibility_and_cutoff(self):
        kwargs=dict(simulations=20,seed=42,event_start='2024-03-01T00:00:00Z')
        a=simulate_cfb(self.model,'cfb:SYNTH-A','cfb:SYNTH-B',**kwargs)
        b=simulate_cfb(self.model,'cfb:SYNTH-A','cfb:SYNTH-B',**kwargs)
        self.assertEqual(a['scoreDistributions'],b['scoreDistributions'])
        self.assertEqual(a['tieProbability'],0)
        self.assertIsNone(a['calibratedProbability'])
        self.assertIsNone(a['uncertainty']['modelInterval'])
        with self.assertRaises(ValueError):simulate_cfb(self.model,'cfb:SYNTH-A','cfb:SYNTH-B',simulations=1,event_start='2024-01-01T00:00:00Z')

    def test_parameter_bootstrap_includes_games_contributing_league_conversion_evidence(self):
        model=fit_cfb_csv(cfb_fixture_csv(8),'SYNTHETIC','2024-02-01T00:00:00Z')['model']
        extra=copy.deepcopy(next(row for row in model['rows'] if row['kind']=='two_point'))
        extra.update(game='SYNTHETIC-LEAGUE-ONLY',o='cfb:SYNTH-C',d='cfb:SYNTH-D')
        model['rows'].append(extra)
        result=cfb_parameter_bootstrap(model,'cfb:SYNTH-A','cfb:SYNTH-B',42,[],None,{'replicates':10,'gamesPerReplicate':100})
        self.assertEqual(result['selectedTeamHistoricalGameBlocks'],8)
        self.assertEqual(result['historicalGameBlocks'],9)
        self.assertEqual(result['completeGames'],1000)
        self.assertEqual(len(result['homeWinInterval95']),2)

    def test_all_modes_are_complete_coherent_games(self):
        reports=[]
        contracts=[{'id':'qb','kind':'player','playerId':'cfb:SYNTH-A-QB','stat':'passingYards','threshold':100.5,'direction':'over'},
                   {'id':'wr','kind':'player','playerId':'cfb:SYNTH-A-WR','stat':'receivingYards','threshold':100.5,'direction':'over'}]
        for count in (10000,50000,100000):
            r=simulate_cfb(self.model,'cfb:SYNTH-A','cfb:SYNTH-B',count,42,'2024-03-01T00:00:00Z',contracts)
            self.assertEqual(r['simulations'],count)
            self.assertEqual(sum(v['count'] for v in r['jointOutcomes']),count)
            self.assertTrue(all(v['outcomes'][0]==v['outcomes'][1] for v in r['jointOutcomes']))
            self.assertEqual(r['homeWinProbability']+r['awayWinProbability'],1)
            self.assertEqual(r['tieProbability'],0)
            self.assertEqual(sum(v['count'] for v in r['scoreDistributions']['cfb:SYNTH-A']['histogram']),count)
            self.assertEqual(r['convergence'][-1]['simulations'],count)
            reports.append(r)
        self.assertLess(abs(reports[0]['homeWinProbability']-reports[-1]['homeWinProbability']),.03)
        self.assertGreater(reports[0]['convergence'][-1]['monteCarloSE'],reports[-1]['convergence'][-1]['monteCarloSE'])


if __name__=='__main__':unittest.main()
