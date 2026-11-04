"""Synthetic mechanism tests; live-source validation is reported separately."""
import unittest
import numpy as np
from .hierarchical_props import pool_candidate,base_cdf,base_fit

class HierarchicalTests(unittest.TestCase):
    def records(self):
        rng=np.random.default_rng(12100);rows=[]
        for year,weeks in ((2025,18),(2026,8)):
            for w in range(1,weeks+1):
                for p in range(20):rows.append({'season':year,'week':w,'player':str(p),'game':f'SYNTHETIC-{year}-{w}-{p//2}','position':'WR','stat':'receptions','value':int(rng.poisson(1+p%5))})
        return rows
    def test_no_holdout_outcome_tunes_prior_or_hyperparameters(self):
        records=self.records();a=pool_candidate(records,'receptions','WR',2026)
        for row in records:
            if row['season']==2026:row['value']=20-row['value']
        b=pool_candidate(records,'receptions','WR',2026)
        self.assertEqual(a['base'],b['base']);self.assertEqual(a['strength'],b['strength']);self.assertEqual(a['window'],b['window']);self.assertNotEqual(a['validation']['brierScore'],b['validation']['brierScore'])
    def test_exact_discrete_thresholds_and_equality(self):
        base={'family':'poisson','mean':29}
        self.assertAlmostEqual(base_cdf(base,29.5,'Over')+base_cdf(base,29.5,'Under'),1)
        self.assertLess(base_cdf(base,29,'Over')+base_cdf(base,29,'Under'),1)
        self.assertEqual(base_cdf(base,29.1,'Over'),base_cdf(base,29.5,'Over'))
    def test_insufficient_peer_validation_does_not_invent_an_approved_model(self):
        r=pool_candidate(self.records()[:10],'receptions','WR',2026);self.assertFalse(r['approved'])
    def test_yardage_model_keeps_negative_and_zero_observations(self):
        values=[-3,0,1,5,10,15,30,50,80,100]*5;r=base_fit(values,'receivingYards');self.assertIsNotNone(r);self.assertGreater(base_cdf(r,0,'Under'),0)
