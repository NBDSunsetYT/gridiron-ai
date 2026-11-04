"""Synthetic mechanism checks; real annual audits are separate versioned artifacts."""
import unittest
from unittest.mock import patch
from .history_regularization import audit_regularization,publication_regularization,frozen_validation
from .hierarchical_props import attach_models

class RegularizationTests(unittest.TestCase):
    def test_annual_replication_is_independent_and_all_cohorts_are_reported(self):
        prior=frozen_validation(2025);current=frozen_validation(2026)
        self.assertEqual(prior['testSeason'],2025);self.assertEqual(current['testSeason'],2026)
        self.assertEqual(current['testThroughWeek'],8);self.assertEqual(len(current['cohorts']),33)
        published=[k for k,v in current['cohorts'].items() if v['approved'] and prior['cohorts'][k]['approved']]
        self.assertEqual(len(published),11)
        self.assertTrue(any(not v['approved'] for v in current['cohorts'].values()))
    def test_artifact_availability_and_sport_are_enforced_without_online_training(self):
        with patch('modeling.history_regularization.audit_regularization',side_effect=AssertionError('No online training')):
            self.assertTrue(publication_regularization([],'receivingYards','WR',2026,'NFL','2099-01-01T00:00:00Z')['approved'])
            self.assertFalse(publication_regularization([],'receivingYards','WR',2026,'NFL','2026-01-01T00:00:00Z')['approved'])
            self.assertFalse(publication_regularization([],'receivingYards','WR',2026,'CFB','2099-01-01T00:00:00Z')['approved'])
            self.assertFalse(publication_regularization([],'interceptions','QB',2026,'NFL','2099-01-01T00:00:00Z')['approved'])
    def test_duplicate_player_week_is_not_treated_as_a_separate_independent_game(self):
        rows=[{'player':'SYNTHETIC','game':'SYNTHETIC-1','season':2025,'week':1,'value':4,'stat':'receptions','position':'WR'}]*40
        self.assertIn('chronology',audit_regularization(rows,'receptions','WR',2026)['reason'])
    def test_prior_model_can_only_use_games_already_admitted_to_player_evidence(self):
        distribution={'sampleSize':1,'historicalGameIds':['ADMITTED'],'histogram':[{'value':10,'count':1}]}
        artifact={'approved':True,'base':{'family':'poisson','mean':2},'strength':2,'window':4,'validation':{'pairedGameBootstrapPValue':0.0001},'version':'SYNTHETIC','artifactId':'SYNTHETIC','calibrator':None}
        rows=[{'player':'SYNTHETIC','game':gid,'season':2025,'week':i+1,'position':'WR','stat':'receptions','value':value} for i,(gid,value) in enumerate([('ADMITTED',10),('EXCLUDED-TEAM',999)])]
        with patch('modeling.hierarchical_props.pool_candidate',return_value=artifact):
            attach_models({'SYNTHETIC':{'receptions':distribution}},[{'id':'SYNTHETIC','position':'WR'}],rows,2026)
        self.assertEqual(distribution['histogram'],[{'value':10,'count':1}]);self.assertEqual(distribution['historicalGameIds'],['ADMITTED'])
