import unittest
from .prop_candidates import probability,validate_candidate
class CandidateTests(unittest.TestCase):
    def test_small_samples_never_promoted(self):
        self.assertFalse(validate_candidate([1,2,3]*8,1.5,'over','poisson')['approved'])
    def test_unsupported_distributions_do_not_drop_zeros_or_negative_yards(self):
        for method in ('lognormal','poisson','negative_binomial'):
            with self.assertRaises(ValueError):probability([-1,0,1,2]*5,1.5,'over',method)
    def test_oos_metrics_do_not_approve_unverified_publication_history(self):
        r=validate_candidate([1,2,0,4,1,2,3]*20,1.5,'over','poisson');self.assertFalse(r['approved']);self.assertTrue(r['chronological']);self.assertEqual(r['testPredictions'],120);self.assertGreater(r['logLoss'],0)
