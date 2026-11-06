"""Synthetic contracts test software authorization, not historical accuracy."""
import copy
import unittest
from unittest.mock import patch
import numpy as np
from .router import ResearchRouter, request_guard
from .accuracy_v25.objectives import AccuracyMode, objective, score_numerical, score_probability, threshold_probability, stamp_mode
from .dynamic_v24.completion.selection import decision
from .overnight_v20.state import digest


def signed(value):
    return value | {'sha256':digest(value)}


class ObjectiveScoring(unittest.TestCase):
    def test_objectives_do_not_reuse_evidence_mode_names(self):
        self.assertEqual(objective('probability'),AccuracyMode.PROBABILITY)
        self.assertEqual(objective('mean'),AccuracyMode.NUMERICAL)
        self.assertEqual(objective('market_edge'),AccuracyMode.MARKET)
        with self.assertRaises(ValueError):objective('historical_mechanics')

    def test_analytic_numerical_scores_and_intervals(self):
        r=score_numerical([0,2],[1,1],[[0,1,2],[0,1,2]])
        self.assertEqual((r['mae'],r['rmse'],r['bias']),(1.,1.,0.))
        self.assertAlmostEqual(r['crps'],5/9)
        self.assertAlmostEqual(r['quantileLoss']['0.5'],.5)
        self.assertAlmostEqual(r['intervals']['0.9']['winkler'],3.8)
        self.assertEqual(r['intervals']['0.9']['coverage'],0)

    def test_analytic_bernoulli_scores(self):
        r=score_probability([0,1],[.25,.75])
        self.assertEqual(r['brier'],.0625)
        self.assertAlmostEqual(r['logLoss'],-np.log(.75))
        self.assertEqual(sum(b['count'] for b in r['reliability']),2)
        with self.assertRaises(ValueError):score_probability([2],[.5])

    def test_pushes_and_equality_remain_distinct(self):
        r=threshold_probability([1,2,3,4],2,'over')
        self.assertEqual(r['rawProbability'],.5);self.assertEqual(r['pushOutcomes'],1)
        self.assertAlmostEqual(r['nonPushProbability'],2/3)
        self.assertEqual(threshold_probability([1,2,3,4],2,'over',equality='win')['rawProbability'],.75)
        self.assertIsNone(r['calibratedProbability'])
        self.assertAlmostEqual(r['monteCarloSE'],.25)

    def test_mode_hashes_separate_one_shared_snapshot(self):
        rows=[stamp_mode(m,'same-input','same-model',{'p':.5}) for m in AccuracyMode]
        self.assertEqual(len({r['predictionHash'] for r in rows}),3)
        self.assertEqual(len({r['snapshotHash'] for r in rows}),1)


class Routing(unittest.TestCase):
    def setUp(self):
        self.request={'sport':'NBA','eventId':'SYNTHETIC-FUTURE','entityId':'p','teamId':'A','entityType':'player','stat':'rebounds','output':'mean','eventAt':'2024-05-01T20:00:00Z','cutoff':'2024-05-01T18:00:00Z'}
        metrics=[]
        for _ in range(2):
            metrics.append({'games':30,'candidate':{'mae':1.,'rmse':1.,'crps':.5,'cdfBrier':.1,'cdfLogLoss':.3,'coverage':{'0.9':.9}},'reference':{'mae':2.,'rmse':2.,'crps':1.,'cdfBrier':.11,'cdfLogLoss':.31,'coverage':{'0.9':.9}},'paired':{'adjustedCI':[-2.,-1.]},'converged':True})
        base={'sport':'NBA','stat':'rebounds','family':'SYNTHETIC','modelVersion':'SYNTHETIC-v1','trainingCutoff':['2024-01-01T00:00:00Z','2024-02-01T00:00:00Z'],'sourceVersions':{'fixture':'synthetic'},'sampleSize':{'games':60,'observations':60},'metrics':metrics,'uncertainty':[{'adjustedCI':[-2,-1]}]*2,'purpose':'expected_value','estimand':'conditional_mean','modelSHA256':['SYNTHETIC-a','SYNTHETIC-b'],'productionPromotion':False}
        base['decision']=decision(metrics,'expected_value',strict=True,production_reference=True)
        self.record=base|{'id':digest(base)}
        windows=[]
        for i in range(2):
            ids=['SYNTHETIC-'+str(i)+'-'+str(j) for j in range(30)]
            windows.append({'start':f'2024-0{i+1}-02T00:00:00Z','end':f'2024-0{i+1}-28T00:00:00Z','gameIds':ids,'gameManifestHash':digest(ids),'metricsHash':digest(metrics[i])})
        self.att=signed({'registryRecordId':self.record['id'],'modelVersion':self.record['modelVersion'],'artifactSHA256':'SYNTHETIC-b','sourceVersions':self.record['sourceVersions'],'strictPregameEvidence':True,'productionReferenceCompared':True,'policyFrozenBeforeValidation':True,'artifactAvailableTimes':['2024-03-01T00:00:00Z'],'windows':windows,'freshnessSeconds':{k:8640000 for k in ('injury','lineup','participation','historical_statistics')}})
        self.evidence={'features':[{'gameId':self.request['eventId'],'sport':'NBA','team':'A','player':'p','stat':'rebounds','at':self.request['eventAt'],'featureLastGame':'2024-04-01T00:00:00Z','sourceEditionVerified':True,'missingEvidence':[],'missingAvailability':False,**{k:'2024-04-30T00:00:00Z' for k in ('statisticsPublishedAt','injuryPublishedAt','lineupPublishedAt','participationPublishedAt')}}],'facts':[]}
        for kind in ('injury','lineup','participation','historical_statistics'):
            self.evidence['facts'].append({'kind':kind,'sport':'NBA','teamId':'A','playerId':'p','eventId':self.request['eventId'] if kind!='historical_statistics' else 'SYNTHETIC-OLD','source':'https://example.test/synthetic','sourceVersion':'SYNTHETIC','publishedAt':'2024-04-30T00:00:00Z','availableAt':'2024-04-30T00:00:00Z','editionPublishedAt':'2024-04-30T00:00:00Z','retrievedAt':'2024-04-30T01:00:00Z','sourceRole':'official_pregame_report','status':'confirmed','gameEndedAt':'2024-04-01T00:00:00Z'})
        self.evidence['inputSnapshotHash']=digest(self.evidence)
        self.qualification={'model':{'sport':'NBA','sha256':'SYNTHETIC-joint','specializedHeadIds':[self.record['id']]},'match':{'id':self.request['eventId'],'cutoff':self.request['cutoff']},'ctx':{},'evidence':{},'certificate':{'objectiveHeadValidation':{self.record['id']:{'artifactSHA256':'SYNTHETIC-b','inputSnapshotHash':self.evidence['inputSnapshotHash'],'compatible':True}}}}

    def route(self,request=None,record=None,att=None,evidence=None,qualification=None):
        r=record or self.record
        router=ResearchRouter({'versions':[r]},protected_ids={'SEALED'})
        return router.route(request or self.request,evidence=evidence or self.evidence,attestations={r['id']:att or self.att},qualification=qualification or self.qualification)

    def test_current_registry_stays_read_only_and_withholds_conditional_winners(self):
        from pathlib import Path
        p=Path(__file__).resolve().parents[1]/'docs/research/specialized-v24-registry.json';before=p.read_bytes()
        r=ResearchRouter(p).route(self.request)
        self.assertEqual(r['status'],'withheld');self.assertTrue(r['rejected'])
        self.assertEqual(p.read_bytes(),before)

    def test_exact_ids_and_threshold_definition_required(self):
        with self.assertRaises(ValueError):request_guard(self.request|{'entityId':''})
        with self.assertRaises(ValueError):request_guard(self.request|{'output':'probability'})
        request_guard(self.request|{'output':'probability','threshold':8.5,'side':'over','equality':'lose','thresholdSourceVersion':'SYNTHETIC'})

    def test_protected_game_never_opens_automatically(self):
        self.assertIn('protected',self.route(self.request|{'eventId':'SEALED'})['reason'])

    def test_registry_tampering_rejected(self):
        with self.assertRaisesRegex(ValueError,'checksum'):ResearchRouter({'versions':[self.record|{'family':'tampered'}]},protected_ids=set())

    @patch('modeling.dynamic_v24.completion.selection.joint_probability_gate')
    @patch('modeling.fullgame_v23.forecast.require')
    def test_fully_bound_fixture_can_route_only_after_existing_joint_gates(self,require,probability):
        result=self.route();self.assertEqual(result['status'],'eligible_research_route')
        require.assert_called_once();probability.assert_called_once()
        self.assertFalse(result['productionEligible'])

    def test_missing_real_mechanics_certificate_cannot_route(self):
        result=self.route();self.assertEqual(result['status'],'withheld')

    def test_future_cutoff_stale_and_wrong_player_are_rejected(self):
        with patch('modeling.fullgame_v23.forecast.require'),patch('modeling.dynamic_v24.completion.selection.joint_probability_gate'):
            a={k:v for k,v in self.att.items() if k!='sha256'};a['artifactAvailableTimes']=[self.request['cutoff']]
            self.assertEqual(self.route(att=signed(a))['status'],'withheld')
            a={k:v for k,v in self.att.items() if k!='sha256'};a['freshnessSeconds']={k:1 for k in a['freshnessSeconds']}
            self.assertIn('Stale',self.route(att=signed(a))['rejected'][0]['reason'])
            e=copy.deepcopy(self.evidence);e['features'][0]['player']='wrong';e['inputSnapshotHash']=digest({k:v for k,v in e.items() if k!='inputSnapshotHash'})
            self.assertIn('differs',self.route(evidence=e)['rejected'][0]['reason'])

    @patch('modeling.dynamic_v24.completion.selection.joint_probability_gate')
    @patch('modeling.fullgame_v23.forecast.require')
    def test_cache_must_bind_request_model_input_and_joint_version(self,require,probability):
        router=ResearchRouter({'versions':[self.record]},protected_ids=set())
        cache=signed({'requestHash':digest(self.request),'registryRecordId':self.record['id'],'artifactSHA256':'SYNTHETIC-b','inputSnapshotHash':self.evidence['inputSnapshotHash'],'jointModelHash':'SYNTHETIC-joint','accuracyMode':AccuracyMode.NUMERICAL.value,'createdAt':'2024-05-01T17:00:00Z','stale':False,'prediction':{'mean':8.}})
        args={'evidence':self.evidence,'attestations':{self.record['id']:self.att},'qualification':self.qualification}
        self.assertEqual(router.predict(self.request,cached_forecast=cache,**args)['status'],'ready_research_only')
        cache=signed({k:('wrong' if k=='jointModelHash' else v) for k,v in cache.items() if k!='sha256'})
        self.assertIn('binding_mismatch',router.predict(self.request,cached_forecast=cache,**args)['reason'])

    def test_numerical_mean_cannot_reuse_probability_or_median_slot(self):
        r=copy.deepcopy(self.record);r['purpose']='median';r['estimand']='conditional_median';r['decision']=decision(r['metrics'],'median',strict=True,production_reference=True);r['id']=digest({k:v for k,v in r.items() if k!='id'})
        self.assertEqual(self.route(record=r)['candidateCount'],0)


if __name__=='__main__':unittest.main()
