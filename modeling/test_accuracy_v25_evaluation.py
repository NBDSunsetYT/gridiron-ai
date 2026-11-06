"""Analytic golden metrics and deterministic chronological isolation guards."""
import copy,json,unittest
from pathlib import Path
import numpy as np
from .accuracy_v25.evaluation import feature_guard,cohort_guard,score_frozen,paired_game_comparison


class FrozenEvaluation(unittest.TestCase):
    def feature(self):return {'gameId':'SYNTHETIC','team':'A','player':'p','stat':'receptions','at':'2024-02-01T00:00:00Z','featureLastGame':'2024-01-20T00:00:00Z','sourceEditionVerified':False,'missingAvailability':True}
    def test_feature_guard_rejects_labels_future_history_and_future_fit(self):
        row=self.feature();feature_guard([row],'2024-01-21T00:00:00Z',evidence_tier='conditional_corrected_history')
        for modified in [row|{'y':None},row|{'featureLastGame':row['at']}]:
            with self.assertRaises(ValueError):feature_guard([modified],'2024-01-21T00:00:00Z',evidence_tier='conditional_corrected_history')
        with self.assertRaises(ValueError):feature_guard([row],row['at'],evidence_tier='conditional_corrected_history')
        with self.assertRaises(ValueError):feature_guard([row],'2024-01-21T00:00:00Z',evidence_tier='strict_pregame')
    def test_same_day_future_game_never_becomes_earlier_training(self):
        row=self.feature()
        with self.assertRaises(ValueError):feature_guard([row],'2024-02-01T01:00:00Z',evidence_tier='conditional_corrected_history')
    def test_four_cohorts_cannot_overlap_or_relabel_exposed_final(self):
        groups={key:[{'gameId':key,'eventAt':f'2024-0{i+1}-01T00:00:00Z'}] for i,key in enumerate(['development','validation','confirmation','final'])}
        groups['final'][0]['alreadyExposed']=False
        self.assertEqual(cohort_guard(groups,{'final'}),cohort_guard(groups,{'final'}))
        bad=copy.deepcopy(groups);bad['final'][0]['alreadyExposed']=True
        with self.assertRaises(ValueError):cohort_guard(bad,{'final'})
        bad=copy.deepcopy(groups);bad['validation'][0]['gameId']='final'
        with self.assertRaises(ValueError):cohort_guard(bad,{'final'})
        bad=copy.deepcopy(groups);bad['confirmation'][0]['eventAt']=bad['validation'][0]['eventAt']
        with self.assertRaises(ValueError):cohort_guard(bad,{'final'})
        bad=copy.deepcopy(groups);bad['final'][0].pop('alreadyExposed')
        with self.assertRaises(ValueError):cohort_guard(bad,{'final'})
    def test_analytic_metric_golden_file(self):
        golden=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/research-v25/metric-golden.json').read_text())
        rows=[{'gameId':'SYNTHETIC-'+str(i),'stat':'receptions','y':y} for i,y in enumerate([0.,2.])]
        result=score_frozen(rows,[1.,1.],np.array([[0.,1.,2.],[0.,1.,2.]]),[1.])
        for key,value in golden['metrics'].items():self.assertAlmostEqual(result[key],value,places=12)
        self.assertEqual(result['coverage'],golden['coverage']);self.assertTrue(result['marketless']);self.assertIsNone(result['jointProbabilityCalibration'])
    def test_seeded_game_clustered_intervals_replay_exactly(self):
        rows=[{'gameId':'SYNTHETIC-'+str(i//2),'stat':'receptions','y':float(i)} for i in range(10)]
        first=paired_game_comparison(rows,np.arange(10)+1,np.arange(10),'expected_value');second=paired_game_comparison(rows,np.arange(10)+1,np.arange(10),'expected_value');self.assertEqual(first,second);self.assertEqual(first['CI95'],[-1.,-1.]);self.assertEqual(first['games'],5)


if __name__=='__main__':unittest.main()
