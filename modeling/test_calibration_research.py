import unittest
import numpy as np
from modeling.calibration_research import fit,predict,metrics,chronological_windows
class CalibrationResearchTests(unittest.TestCase):
    def test_monotonic_bounded_candidates_and_duplicate_probabilities(self):
        p=[.1,.1,.2,.3,.4,.6,.7,.8,.9,.9];y=[0,1,0,0,1,0,1,1,0,1]
        for method in ['isotonic','platt','temperature']:
            q=predict(fit(method,p,y),np.linspace(0,1,101));self.assertTrue(np.all(np.diff(q)>=-1e-12));self.assertTrue(np.all((q>0)&(q<1)))
    def test_final_outcomes_do_not_enter_rolling_fits(self):
        rows=[{'phase':'validation','cohort':str(i),'eventStart':f'2025-0{i+1}-01','homeProbability':.5,'actualHomeWin':0} for i in range(3)]
        rows.append({'phase':'test','cohort':'3','eventStart':'2025-04-01','actualHomeWin':1})
        folds=list(chronological_windows(rows));self.assertEqual(len(folds),2);self.assertTrue(all(r['phase']=='validation' for a,b in folds for r in a+b))
    def test_metrics_and_small_sample_guards(self):
        self.assertAlmostEqual(metrics([.5,.5],[0,1])['brier'],.25)
        self.assertEqual(metrics([0,1],[0,1])['brier'],0)
        self.assertEqual(metrics([0,1],[0,1])['ece'],0)
        self.assertTrue(np.isfinite(metrics([0,1],[1,0])['logLoss']))
        with self.assertRaises(ValueError):fit('platt',[.5]*8,[1]*8)
        with self.assertRaises(ValueError):fit('isotonic',[1.1]*8,[0,1]*4)
if __name__=='__main__':unittest.main()
