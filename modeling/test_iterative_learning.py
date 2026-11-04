"""Mechanical fixtures only; accuracy is measured separately on real games."""
import copy
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from .iterative_learning import (probability,distribution_errors,freeze_json,
                                 paired_gate,stop_reason,unrealism_flags,evaluate_forecast)
from .football_data_v16 import load_football,training_before
from .football_v16 import fit_football,simulate_football
from .test_engines_v15 import fixture


class DistributionScoringTests(unittest.TestCase):
    def test_exact_probability_wilson_and_mcse_not_calibrated(self):
        dist={'histogram':[{'value':0,'count':40},{'value':2,'count':60}]}
        p=probability(dist,1);self.assertEqual((p['successes'],p['trials']),(60,100))
        self.assertAlmostEqual(p['rawProbability'],.6);self.assertAlmostEqual(p['monteCarloSE'],np.sqrt(.24/100))
        self.assertLess(p['interval95'][0],.6);self.assertGreater(p['interval95'][1],.6);self.assertIsNone(p['calibratedProbability'])
    def test_crps_matches_quadratic_definition(self):
        values=np.array([-2,0,1,5]);weights=np.array([.2,.1,.4,.3]);actual=2
        expected=np.sum(weights*abs(values-actual))-.5*np.sum(weights[:,None]*weights[None,:]*abs(values[:,None]-values[None,:]))
        d={'histogram':[{'value':int(v),'count':int(w*100)} for v,w in zip(values,weights)]}
        self.assertAlmostEqual(distribution_errors(d,actual)['crps'],expected)
    def test_atomic_snapshot_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'run.json.gz';freeze_json(path,{'seed':2});freeze_json(path,{'seed':2})
            with self.assertRaisesRegex(ValueError,'Immutable'):freeze_json(path,{'seed':3})
    def test_stop_reasons_and_precedence(self):
        limits={'cpuSeconds':100,'wallSeconds':200,'patience':2,'maxIterations':3}
        self.assertIsNone(stop_reason(1,0,99,199,limits));self.assertEqual(stop_reason(1,0,100,0,limits),'cpu_budget_exhausted')
        self.assertEqual(stop_reason(1,2,0,0,limits),'validation_improvement_plateau')
        self.assertEqual(stop_reason(3,0,0,0,limits),'predeclared_candidate_budget_exhausted')
    def test_tiny_or_unpaired_samples_cannot_promote(self):
        self.assertFalse(paired_gate([],[])['passed'])
    def test_credible_research_improvement_still_cannot_promote_to_production(self):
        def observation(i,improved):
            def d(center):return {'mean':center,'histogram':[{'value':center-2,'count':5000},{'value':center+2,'count':5000}]}
            forecast={'sport':'NFL','simulations':10000,'home':'H','away':'A','homeWinProbability':.1 if improved else .9,
                'scoreDistributions':{'H':d(10 if improved else 20),'A':d(20 if improved else 30)},
                'totalDistribution':d(30 if improved else 50),'marginDistribution':d(-10),
                'players':{'p':{'receivingYards':d(50 if improved else 80)}},'quality':{'allGamesAccountingReconciled':True}}
            game={'id':str(i),'sport':'NFL','cohort':str(i//8),'phase':'validation','at':(datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(days=4*i)).isoformat()}
            return evaluate_forecast(forecast,{'H':10,'A':20},{'p':{'team':'H','stats':{'receivingYards':50}}},game,{'scores':{'H':15,'A':25}})
        old=[observation(i,False) for i in range(24)];new=[observation(i,True) for i in range(24)]
        gate=paired_gate(old,new,replicates=100)
        self.assertTrue(gate['passed'],gate);self.assertFalse(gate['productionEligible'])
        new[0]['qualityFlags']=['accounting_failure']
        self.assertIn('unrealistic_simulation',paired_gate(old,new,replicates=100)['vetoes'])


class CombinedScoringLoaderTests(unittest.TestCase):
    def source(self,folder):
        import pyarrow as pa,pyarrow.parquet as pq
        rows=[]
        for i in range(3):
            rows.append({'game_id':1,'id':i+1,'season':2025,'homeTeamId':1,'awayTeamId':2,'homeFinalScore':7,'awayFinalScore':0,
                'status_type_completed':True,'wallclock':datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(seconds=i*30),
                'period':1,'pos_team_id':1,'def_pos_team_id':2,'down':1,'distance':7,'start.yardsToEndzone':7,
                'start.adj_TimeSecsRem':3600-i*30,'start.pos_score_diff':0,'pass_attempt':False,'completion':False,
                'rush':True,'kneel_down':False,'yds_rushed':7 if i==0 else 1,'rusher_player_id':11,
                'touchdown':i==0,'xp_attempt':i==0,'xp_made':i==0,'two_point_conv_result':None,'pos_fumble_lost':False})
        path=Path(folder)/'source.parquet';pq.write_table(pa.Table.from_pylist(rows),path);return path
    def test_touchdown_and_pat_are_both_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            data=load_football(self.source(folder),'CFB');kinds=[r['kind'] for r in data['rows']]
            self.assertEqual(kinds.count('extra_point'),1);self.assertEqual(kinds.count('rush'),2)
            td=next(r for r in data['rows'] if r['kind']=='rush');self.assertEqual(td['yards'],td['field'])
            self.assertEqual(td['elapsed'],30)
    def test_whole_game_embargo_prevents_partial_game_leakage(self):
        with tempfile.TemporaryDirectory() as folder:
            data=load_football(self.source(folder),'CFB')
            self.assertEqual(training_before(data,'2025-01-01T00:00:30Z'),[])
            self.assertGreater(len(training_before(data,'2025-01-02T00:00:00Z')),0)


class CandidateMechanicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=fit_football(fixture(),'NFL','2024-02-01T00:00:00Z','synthetic-mechanics',{'conditionalClock':True,'regularization':4})
    def test_complete_game_accounting_joint_counts_and_reproducible_seed(self):
        args=(self.model,'fixture:0','fixture:1','2024-02-02T00:00:00Z')
        a=simulate_football(*args,1000,16,representative_games=0);b=simulate_football(*args,1000,16,representative_games=0)
        self.assertEqual(a['players'],b['players']);self.assertEqual(a['jointResearchOutcomes'],b['jointResearchOutcomes'])
        self.assertEqual(unrealism_flags(a),[])
        for q in a['jointResearchOutcomes']:
            self.assertEqual(q['trials'],1000);self.assertLessEqual(q['successful'],1000)
            self.assertIn('not_historical',q['label'])
        for t,ss in a['teamDistributions'].items():
            self.assertAlmostEqual(ss['passingYards']['mean'],sum(ps['passingYards']['mean'] for pid,ps in a['players'].items() if pid.startswith(t+':')))
            self.assertEqual(sum(b['count'] for b in ss['passingAttempts']['histogram']),1000)
        self.assertIsNone(a['calibratedProbability']);self.assertFalse(a['quality']['productionEligible'])
    def test_defensive_and_offensive_stats_reconcile(self):
        a=simulate_football(self.model,'fixture:0','fixture:1','2024-02-02T00:00:00Z',1000,17,representative_games=0)
        self.assertAlmostEqual(sum(t['passingYards']['mean'] for t in a['teamDistributions'].values()),sum(ss['receivingYards']['mean'] for ss in a['players'].values()))


if __name__=='__main__':unittest.main()
