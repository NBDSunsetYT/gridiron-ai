"""Synthetic MC-consistency/cache contracts, never real forecasting results."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import numpy as np
from .accuracy_v25.reconciliation import compare,require_report
from .accuracy_v25.joint_session import run_once,bounded_call


class Reconciliation(unittest.TestCase):
    def test_consistent_shared_marginal_passes_without_altering_draws(self):
        x=np.tile([0.,2.],1000);before=x.copy();r=compare('head','artifact','input','joint',1.,x,x)
        self.assertTrue(r['compatible']);np.testing.assert_array_equal(x,before)
        self.assertEqual(require_report(r,'head','artifact','input','joint'),r)
        self.assertFalse(r['distributionsModified']);self.assertFalse(r['productionEligible'])
    def test_mean_and_distribution_changes_are_rejected(self):
        x=np.tile([0.,2.],1000)
        self.assertFalse(compare('head','artifact','input','joint',1.,x,x+2)['compatible'])
        r=compare('head','artifact','input','joint',1.,x,np.ones(2000))
        self.assertIn('predictive_distribution_incompatible',r['reasons'])
    def test_rare_support_is_withheld_and_mc_precision_is_not_model_confidence(self):
        x=np.r_[np.ones(10),np.zeros(1990)];r=compare('head','artifact','input','joint',.005,x,x)
        self.assertFalse(r['compatible']);self.assertIn('insufficient_nonzero',r['reasons'][0])
        self.assertEqual(r['modelUncertainty'],'not_established_by_sampling_precision')
    def test_wrong_binding_and_report_tampering_fail(self):
        x=np.tile([0.,2.],1000);r=compare('head','artifact','input','joint',1.,x,x)
        with self.assertRaises(ValueError):require_report(r,'head','artifact','other','joint')
        with self.assertRaises(ValueError):require_report(r|{'jointMean':10},'head','artifact','input','joint')


class SharedSession(unittest.TestCase):
    def setUp(self):
        self.q={'model':{'sport':'NBA','sha256':'SYNTHETIC','kernelInputHash':'SYNTHETIC'},'match':{'id':'SYNTHETIC','cutoff':'2024-01-01T00:00:00Z'},'ctx':{'sport':'NBA','eventId':'SYNTHETIC','mode':'strict_pregame_forecast'},'evidence':{'edition':'SYNTHETIC'},'certificate':{}}
        d=lambda value:{'mean':value,'histogram':[{'value':value,'count':10000}]}
        self.result={'games':10000,'mechanicalInvariantsPassed':True,'researchContext':self.q['ctx'],'allSimulatedPlaysPermanentlyStored':False,'scoreDistributions':{'H':d(100),'A':d(90)},'totalDistribution':d(190),'marginDistribution':d(10),'playerDistributions':{'p':{'rebounds':d(8)}},'representativeGames':[]}
    def test_without_real_evidence_no_simulation_or_cache_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'new'
            with self.assertRaises((ValueError,KeyError)):run_once(Mock(),self.q,target)
            self.assertFalse(target.exists())
    @patch('modeling.accuracy_v25.joint_session.forecast_with_heads')
    @patch('modeling.dynamic_v24.completion.selection.joint_probability_gate')
    @patch('modeling.fullgame_v23.forecast.require')
    def test_same_game_three_modes_reuse_one_existing_engine_call(self,require,gate,engine):
        engine.return_value=self.result;registry=Mock()
        with tempfile.TemporaryDirectory() as tmp:
            first=run_once(registry,self.q,tmp);second=run_once(registry,self.q,tmp)
            engine.assert_called_once();self.assertFalse(first['cacheHit']);self.assertTrue(second['cacheHit'])
            self.assertEqual(first['sharedSimulationId'],second['sharedSimulationId']);self.assertEqual(len(first['accuracyModes']),3)
            self.assertNotIn('results',second['result'])
            changed=copy.deepcopy(self.q);changed['evidence']['edition']='new'
            third=run_once(registry,changed,tmp);self.assertNotEqual(first['sharedSimulationId'],third['sharedSimulationId'])
            self.assertEqual(engine.call_count,2)
    @patch('modeling.accuracy_v25.joint_session.forecast_with_heads')
    @patch('modeling.dynamic_v24.completion.selection.joint_probability_gate')
    @patch('modeling.fullgame_v23.forecast.require')
    def test_malformed_result_never_becomes_cached_forecast(self,require,gate,engine):
        result=copy.deepcopy(self.result);result['totalDistribution']['histogram'][0]['count']=9999;engine.return_value=result
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'10,000'):run_once(Mock(),self.q,tmp)
            self.assertEqual(list(Path(tmp).glob('*.json')),[])
    def test_frontend_environment_cannot_run_research(self):
        for key in ('VERCEL','RENDER'):
            with patch.dict(os.environ,{key:'1'}),tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(RuntimeError):run_once(Mock(),self.q,tmp)

    def test_compute_budget_stops_work_and_restores_signal_handlers(self):
        import signal,time
        before=signal.getsignal(signal.SIGPROF)
        with self.assertRaises(TimeoutError):
            with bounded_call(.01,1.):
                while True:pass
        self.assertEqual(signal.getsignal(signal.SIGPROF),before)
        self.assertEqual(signal.getitimer(signal.ITIMER_PROF),(0.,0.))
        with self.assertRaises(ValueError):
            with bounded_call(181,360):pass


if __name__=='__main__':unittest.main()
