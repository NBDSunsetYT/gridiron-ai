"""Synthetic mechanics and protocol tests, not evidence of NFL profitability."""
import copy
import csv
import io
import json
import unittest
from datetime import datetime,timedelta,timezone
import numpy as np
from scipy.special import expit,logit
from sklearn.ensemble import GradientBoostingClassifier
from modeling import advanced


def row(index=0,home='H',away='A',score=24,other=17):
    stamp=datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(days=index*7)
    return {'id':f'SYNTH-{index}','season':2020+index//52,'week':index%18+1,'date':stamp.isoformat(),'eligibilityAt':(stamp+timedelta(days=2)).isoformat(),'sourceAvailableAt':None,'availabilityVerified':False,'home':home,'away':away,'homeScore':score,'awayScore':other,'homeField':1.,'restDiff':0.,'division':0.,'marketProbability':None}


class AdvancedTests(unittest.TestCase):
    def test_calibration_buckets_partition_boundary_values_once(self):
        p=np.asarray([0.,.1,.4,.5,.5,.9,1.]);y=np.asarray([0,0,0,1,0,1,1])
        buckets=advanced.calibration_table(p,y)
        self.assertEqual(sum(r['n'] for r in buckets),len(p))
        self.assertEqual(next(r for r in buckets if r['from']==.5)['n'],2)
        self.assertEqual(next(r for r in buckets if r['from']==.9)['n'],2)
    def test_pregame_features_do_not_use_own_or_same_date_outcomes(self):
        rows=[row(i,score=24 if i%2 else 10) for i in range(10)]
        original=advanced.design(rows)
        changed=copy.deepcopy(rows);changed[5]['homeScore']=80
        altered=advanced.design(changed)
        np.testing.assert_array_equal(original[:6],altered[:6])
        self.assertFalse(np.allclose(original[6:],altered[6:]))
        changed[6]['date']=changed[5]['date'];changed[6]['eligibilityAt']=changed[5]['eligibilityAt']
        again=advanced.design(changed)
        np.testing.assert_array_equal(again[5],again[6])

    def test_future_availability_prevents_feature_updates(self):
        early=row(0);early['eligibilityAt']='2022-01-01T00:00:00+00:00'
        result=advanced.design([early,row(1)])
        self.assertEqual(result[1][0],0.)
        self.assertEqual(result[1][8],0.)

    def test_json_boosting_prediction_matches_trained_sklearn(self):
        rng=np.random.default_rng(12);x=rng.normal(size=(100,13));rows=[row(i,score=24 if x[i,0]+x[i,1]>.2 else 10) for i in range(100)]
        model=advanced.fit_boosting(x,rows,2)
        fit=GradientBoostingClassifier(n_estimators=80,learning_rate=.05,max_depth=2,min_samples_leaf=25,random_state=42).fit(x,[int(r['homeScore']>r['awayScore']) for r in rows],sample_weight=advanced.recency_weights(rows))
        loaded=json.loads(json.dumps(model))
        np.testing.assert_allclose(advanced.predict_model(loaded,x,rows),fit.predict_proba(x)[:,1],rtol=1e-12)

    def test_laplace_team_strength_and_probability_intervals_are_finite(self):
        rng=np.random.default_rng(9);x=rng.normal(size=(100,13));rows=[row(i,score=24 if i%3 else 10) for i in range(100)]
        fitted=advanced.fit_bayesian(x,rows,1.)
        p,ci=advanced.predict_model(fitted,x[:5],rows[:5],True)
        self.assertTrue(np.all(ci[:,0]<p));self.assertTrue(np.all(ci[:,1]>p))
        self.assertTrue(np.isfinite(np.asarray(fitted['covariance'])).all())
        self.assertEqual(fitted['kind'],'bayesian_team_strength_laplace')

    def test_ensemble_constraints_and_week_block_intervals(self):
        p=np.asarray([.2,.7,.4,.8]*30);y=np.asarray([0,1,0,1]*30)
        weights=advanced.ensemble_fit([p,1-p,np.full(len(y),.5)],y)
        self.assertAlmostEqual(float(weights.sum()),1);self.assertTrue(np.all(weights>=0))
        interval=advanced.block_interval((p-y)**2,[str(i//4) for i in range(len(y))],repeats=100)
        self.assertLessEqual(interval[0],np.mean((p-y)**2));self.assertGreaterEqual(interval[1],np.mean((p-y)**2))

    def test_parse_rejects_missing_columns_and_duplicate_games(self):
        with self.assertRaisesRegex(ValueError,'Missing historical'):
            advanced.parse_games('id\na\n','SYNTHETIC','2026-01-01T00:00:00Z')
        fields=['game_id','season','week','gameday','home_team','away_team','home_score','away_score']
        output=io.StringIO();writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
        example=dict(zip(fields,['DUP',2020,1,'2020-01-01','H','A',24,17]));writer.writerows([example,example])
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            advanced.parse_games(output.getvalue(),'SYNTHETIC','2026-01-01T00:00:00Z')

    def test_unknown_team_and_leaked_event_cutoff_are_rejected(self):
        artifact={'version':advanced.VERSION,'asOf':'2025-01-01T00:00:00Z','history':[row(1)]}
        with self.assertRaisesRegex(ValueError,'after artifact'):
            advanced.predict(artifact,'H','A','2024-01-01T00:00:00Z')
        with self.assertRaisesRegex(ValueError,'Unknown team'):
            advanced.predict(artifact,'X','A','2026-01-01T00:00:00Z')


if __name__=='__main__':unittest.main()
