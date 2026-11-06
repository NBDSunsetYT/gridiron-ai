"""Analytic and synthetic checks; no fabricated production market records."""
import copy
import unittest
import numpy as np
from .accuracy_v25.market_research import devig,quote_guard,compare_market,fit_logit_blend
from .accuracy_v25.shadow import FrozenShadow
from .accuracy_v25.objectives import AccuracyMode
from .overnight_v20.state import digest


class Markets(unittest.TestCase):
    def setUp(self):
        self.identity={'sport':'NFL','eventId':'SYNTHETIC','teamId':'A','playerId':'p','stat':'passingYards','threshold':200.5,'side':'over','equality':'lose','product':'sportsbook','settlementVersion':'SYNTHETIC-rules','outcomeIndex':0}
        self.quote={'verified':True,'source':'https://example.test/synthetic','sourceVersion':'SYNTHETIC','identity':self.identity,'identityHash':digest(self.identity),'book':'SYNTHETIC','capturedAt':'2024-01-01T10:00:00Z','publishedAt':'2024-01-01T10:00:00Z','availableAt':'2024-01-01T10:00:00Z','designation':'opening','decimalOdds':[1.8,2.],'suspended':False}
    def test_multiplicative_and_two_outcome_shin_analytic(self):
        r=devig([1.8,2.]);self.assertAlmostEqual(r['multiplicative'][0],(1/1.8)/(1/1.8+.5))
        self.assertAlmostEqual(r['shin'][0],(1+1/1.8-.5)/2)
        self.assertAlmostEqual(sum(r['shin']),1.)
        np.testing.assert_allclose(devig([2.,2.])['shin'],[.5,.5])
    def test_underround_invalid_prices_and_contract_product_rejected(self):
        for odds in ([3.,3.],[0.,2.],[float('nan'),2.]):
            with self.assertRaises(ValueError):devig(odds)
        i=self.identity|{'product':'event_contract'};q=self.quote|{'identity':i,'identityHash':digest(i)}
        with self.assertRaisesRegex(ValueError,'Event-contract'):quote_guard(q,i,cutoff='2024-01-01T12:00:00Z')
    def test_missing_quote_stays_null_no_automatic_blend(self):
        r=compare_market(.6,None,self.identity,cutoff='2024-01-01T12:00:00Z')
        self.assertIsNone(r['marketProbability']);self.assertIsNone(r['clvProbabilityPoints']);self.assertIsNone(r['fitWeight'])
    def test_exact_market_mapping_and_future_quote_rejected(self):
        with self.assertRaises(ValueError):quote_guard(self.quote,self.identity|{'threshold':201.5},cutoff='2024-01-01T12:00:00Z')
        with self.assertRaises(ValueError):quote_guard(self.quote,self.identity,cutoff=self.quote['availableAt'])
    def test_closing_quote_is_grading_only_and_same_book_required(self):
        closing=self.quote|{'designation':'closing','capturedAt':'2024-01-01T13:00:00Z','publishedAt':'2024-01-01T13:00:00Z','availableAt':'2024-01-01T13:00:00Z','decimalOdds':[1.6,2.5]}
        with self.assertRaisesRegex(ValueError,'Closing'):quote_guard(closing,self.identity,cutoff='2024-01-01T14:00:00Z')
        r=compare_market(.6,self.quote,self.identity,cutoff='2024-01-01T12:00:00Z',closing=closing,event_at='2024-01-01T14:00:00Z')
        self.assertGreater(r['clvProbabilityPoints'],0);self.assertFalse(r['modeCEligible'])
        with self.assertRaises(ValueError):compare_market(.6,self.quote,self.identity,cutoff='2024-01-01T12:00:00Z',closing=closing|{'book':'other'},event_at='2024-01-01T14:00:00Z')
    def test_logit_blend_is_development_only_and_can_choose_endpoint(self):
        rows=[{'gameId':'SYNTHETIC-'+str(i),'role':'development','evidenceTier':'strict_pregame','marketVerified':True,'settlementVerified':True,'trainingThrough':'2023-01-01T00:00:00Z','forecastAt':'2023-02-01T10:00:00Z','marketAvailableAt':'2023-02-01T09:00:00Z','eventAt':'2023-02-01T12:00:00Z','settledAt':'2023-02-01T16:00:00Z','outcome':i%2,'modelProbability':.1 if i%2==0 else .9,'deviggedMarketProbability':.5} for i in range(30)]
        fit=fit_logit_blend(rows,fit_cutoff='2024-01-01T00:00:00Z');self.assertEqual(fit['modelWeight'],1.)
        self.assertTrue(fit['independentValidationRequired']);self.assertFalse(fit['productionEligible'])
        with self.assertRaises(ValueError):fit_logit_blend([r|{'role':'final'} for r in rows],fit_cutoff='2024-01-01T00:00:00Z')
        with self.assertRaises(ValueError):fit_logit_blend(rows,fit_cutoff='2023-02-01T16:00:00Z')


class SharedShadow(unittest.TestCase):
    def setUp(self):
        self.ids=[{'sport':'NBA','gameId':'SYNTHETIC-'+str(i),'team':'A','player':'p','stat':'rebounds'} for i in range(2)]
        self.point=np.array([1.,1.]);self.draws=np.array([[0.,1.,2.],[0.,1.,2.]])
        self.provenance={'sourceModelSHA256':'SYNTHETIC-model','sourceForecastSHA256':'SYNTHETIC-forecast'}
    def freeze(self,**kwargs):return FrozenShadow(self.ids,self.point,self.draws,model_version='SYNTHETIC',provenance=self.provenance,**kwargs)
    def outcomes(self):return [r|{'y':float(i*2)} for i,r in enumerate(self.ids)]
    def test_three_modes_share_exact_identity_and_realization_hash(self):
        f=self.freeze();r=f.evaluate(self.outcomes(),thresholds=[1.])
        self.assertEqual(len({v['snapshotHash'] for v in r.values()}),1)
        self.assertEqual(len({v['eventSetHash'] for v in r.values()}),1)
        self.assertEqual(len({v['predictionHash'] for v in r.values()}),3)
        self.assertEqual(r[AccuracyMode.MARKET.value]['prediction']['observations'],0)
        self.assertIsNone(r[AccuracyMode.MARKET.value]['prediction']['clv'])
        self.assertFalse(r[AccuracyMode.NUMERICAL.value]['jointRealizations'])
    def test_input_mutation_cannot_change_frozen_predictions(self):
        f=self.freeze();first=f.evaluate(self.outcomes());self.point[:]=999;self.draws[:]=999
        self.assertEqual(first,f.evaluate(self.outcomes()))
    def test_wrong_outcome_identity_and_mode_specific_event_subsets_rejected(self):
        f=self.freeze()
        with self.assertRaises(ValueError):f.evaluate(list(reversed(self.outcomes())))
        with self.assertRaises(ValueError):f.evaluate(self.outcomes(),markets=[None])
    def test_strict_joint_claim_requires_existing_gates(self):
        with self.assertRaises(ValueError):self.freeze(scope='strict_pregame')
    def test_final_labels_cannot_enter_freeze(self):
        with self.assertRaises(ValueError):FrozenShadow(self.outcomes(),self.point,self.draws,model_version='SYNTHETIC',provenance=self.provenance)
    def test_repeat_scoring_is_deterministic_without_another_simulation(self):
        f=self.freeze();self.assertEqual(f.evaluate(self.outcomes(),thresholds=[1.]),f.evaluate(self.outcomes(),thresholds=[1.]))

    def test_leaderboard_preserves_unsupported_category_without_fake_metrics(self):
        import json,importlib.util
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('objective_report_test',root/'scripts/report-objectives-v25.py')
        report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)
        heads=json.loads((root/'docs/research/specialized-v24-results.json').read_text())['heads']
        registry=json.loads((root/'docs/research/specialized-v24-registry.json').read_text())
        value=report.build(heads,registry,{'traceCount':320,'sameEventSetChecksPassed':320,'forecastingGatePassed':False,'traces':[]})
        self.assertEqual(len(value['rows']),53)
        unsupported=next(r for r in value['rows'] if r['sport']=='CFB' and r['stat']=='targets')
        self.assertEqual(unsupported['originalCandidateMAE'],[]);self.assertIsNone(unsupported['approvedProbabilityModel'])


if __name__=='__main__':unittest.main()
