"""SYNTHETIC mechanical/encoding tests, not historical NFL validation."""
import base64
import copy
import gzip
import unittest
from unittest.mock import patch

from .fit import fit_csv
from .game_research import evaluate_exact_game_distribution, exact_game_distribution, parameter_game_interval
from .public_research import analyze_public
from .simulator import simulate,evaluate_contract,DISTRIBUTION_ENCODING,GAME_PARAMETER_SAMPLE_ENCODING
from .test_simulator_v4 import eight_games
from .test_public_research import GAME,NOW


def definition(kind='total',**extra):
    return{'id':'SYNTHETIC-GAME-CONTRACT','kind':kind,'threshold':40,'direction':'over',
           'equality':'no','period':'full_game_including_overtime',**extra}


def mechanical_result():
    return{'home':'SYNTH-HOME','away':'SYNTH-AWAY','simulations':10,'distributionEncoding':DISTRIBUTION_ENCODING,
           'statisticCoverage':{'period':'full_game_including_overtime'},
           'marginDistribution':{'histogram':[{'value':-3,'count':2},{'value':0,'count':3},{'value':7,'count':5}]},
           'totalDistribution':{'histogram':[{'value':37,'count':2},{'value':40,'count':3},{'value':49,'count':5}]},
           'scoreDistributions':{'SYNTH-HOME':{'histogram':[{'value':17,'count':2},{'value':20,'count':3},{'value':28,'count':5}]},
                                 'SYNTH-AWAY':{'histogram':[{'value':20,'count':5},{'value':21,'count':5}]}}}


class ExactGameMarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=fit_csv(eight_games(),'SYNTHETIC V7 GAME RULE TEST','2024-02-01T00:00:00Z')['model']
        cls.definitions=[definition('home_win'),definition('away_win',id='SYNTH-AWAY-WIN'),
                         definition('spread',id='SYNTH-SPREAD',threshold=3.5),
                         definition('total',id='SYNTH-TOTAL',threshold=40.5),
                         definition('team_total',id='SYNTH-TEAM-TOTAL',team='away',threshold=20.5)]
        cls.result=simulate(cls.model,'SYNTH-A','SYNTH-B',100,19,'2024-03-01T00:00:00Z',cls.definitions,
                            parameter_uncertainty={'replicates':10,'gamesPerReplicate':100})

    def test_cached_thresholds_match_shared_game_contract_outputs(self):
        for definition in self.definitions:
            answer=evaluate_exact_game_distribution(self.result,definition)
            original=next(row for row in self.result['contracts'] if row['id']==definition['id'])
            self.assertEqual(answer['rawSimulationProbability'],original['probability'])
            self.assertEqual(answer['pushProbability'],original['pushProbability'])
            self.assertEqual(sum(answer['counts'].values()),100)
            self.assertIsNone(answer['calibratedProbability'])
            self.assertIsNone(answer['historicalModelReliability'])

    def test_tie_is_not_away_win_and_push_is_not_no(self):
        result=mechanical_result()
        home=evaluate_exact_game_distribution(result,definition('home_win'))
        away=evaluate_exact_game_distribution(result,definition('away_win'))
        self.assertEqual((home['yesProbability'],away['yesProbability']),(.5,.2))
        self.assertEqual(away['noProbability'],.8)
        pushed=evaluate_exact_game_distribution(result,definition('home_win',equality='push'))
        self.assertEqual(pushed['counts'],{'yes':5,'no':2,'push':3})
        self.assertEqual(evaluate_exact_game_distribution(result,definition('home_win',equality='push'),'no')['rawSimulationProbability'],.2)
        self.assertTrue(evaluate_contract({'kind':'away_win','equality':'no'},[3,7],{}))
        self.assertFalse(evaluate_contract({'kind':'away_win','equality':'no'},[3,3],{}))

    def test_integer_spread_total_and_team_total_boundaries_keep_exact_settlement(self):
        result=mechanical_result()
        spread=evaluate_exact_game_distribution(result,definition('spread',threshold=0,equality='yes'))
        self.assertEqual(spread['yesProbability'],.8)
        total=evaluate_exact_game_distribution(result,definition('total',threshold=40,equality='push'))
        self.assertEqual(total['counts'],{'yes':5,'no':2,'push':3})
        self.assertEqual(total['conditionalNonPushProbability'],5/7)
        away=evaluate_exact_game_distribution(result,definition('team_total',team='away',threshold=20,direction='under',equality='yes'))
        self.assertEqual(away['yesProbability'],.5)
        self.assertEqual(away['coordinate'],'away_score')

    def test_no_independence_reconstruction_or_implicit_period_team_rule(self):
        result=mechanical_result()
        broken=copy.deepcopy(result)
        del broken['totalDistribution']
        with self.assertRaisesRegex(ValueError,'unavailable'):evaluate_exact_game_distribution(broken,definition())
        for extra in ({'period':'regulation'},{'period':'full_game'},{'includesOvertime':False},{'overtimeIncluded':False},
                      {'equality':None},{'threshold':True},{'threshold':float('nan')},{'direction':'unknown'}):
            with self.assertRaises(ValueError):evaluate_exact_game_distribution(result,definition(**extra))
        for extra in ({'team':'missing'},{'team':'home','teamId':'SYNTH-AWAY'}):
            with self.assertRaises(ValueError):evaluate_exact_game_distribution(result,definition('team_total',**extra))
        with self.assertRaisesRegex(ValueError,'home-minus-away'):
            evaluate_exact_game_distribution(result,definition('spread',team='away'))
        for extra in ({'period':'regulation'},{'includesOvertime':False},{'overtimeIncluded':False}):
            with patch('modeling.simulator.simulate_game') as game:
                with self.assertRaisesRegex(ValueError,'overtime'):
                    simulate(self.model,'SYNTH-A','SYNTH-B',10000,12,'2024-03-01T00:00:00Z',[definition(**extra)])
                game.assert_not_called()

    def test_corrupt_binned_or_unreconciled_game_histograms_are_unavailable(self):
        result=mechanical_result()
        for edit in ({'distributionEncoding':'chart_bins_v1'},{'statisticCoverage':{}},{'simulations':True},
                     {'totalDistribution':{'histogram':[{'value':40,'count':9}]}},
                     {'totalDistribution':{'histogram':[{'value':40,'count':5},{'value':40,'count':5}]}},
                     {'totalDistribution':{'histogram':[{'value':-1,'count':10}]}}):
            with self.assertRaises(ValueError):exact_game_distribution({**result,**edit},definition())

    def test_new_threshold_parameter_interval_uses_identical_whole_game_replicates(self):
        for rule in self.definitions:
            original=self.result['uncertainty']['parameterBootstrap']['contracts'][rule['id']]
            self.assertEqual(parameter_game_interval(self.result,rule),original['parameterInterval95'])
            self.assertEqual(parameter_game_interval(self.result,rule,'no'),original['noParameterInterval95'])
        new=definition('total',id='SYNTH-NEW-THRESHOLD',threshold=45.5)
        yes=parameter_game_interval(self.result,new)
        no=parameter_game_interval(self.result,new,'no')
        self.assertIsNotNone(yes)
        self.assertAlmostEqual(yes[0]+no[1],1)
        self.assertAlmostEqual(yes[1]+no[0],1)
        self.assertEqual(yes,parameter_game_interval({**self.result,'simulations':100000},new))

    def test_game_sample_storage_is_bounded_reconciled_and_not_inferred_from_home_interval(self):
        samples=self.result['uncertainty']['parameterBootstrap']['gameSamples']
        self.assertEqual(samples['encoding'],GAME_PARAMETER_SAMPLE_ENCODING)
        self.assertEqual(samples['shape'],[10,100,2])
        self.assertEqual(samples['uncompressedBytes'],8000)
        self.assertEqual(len(gzip.decompress(base64.b64decode(samples['dataBase64']))),8000)
        for update in ({'uncompressedBytes':8001},{'shape':[10,100,3]},{'teams':['SYNTH-B','SYNTH-A']},
                       {'dataBase64':'INVALID'},{'coverage':'regulation'},{'compressedBytes':0}):
            changed=copy.deepcopy(self.result)
            changed['uncertainty']['parameterBootstrap']['gameSamples'].update(update)
            self.assertIsNone(parameter_game_interval(changed,definition()))
        legacy=copy.deepcopy(self.result)
        del legacy['uncertainty']['parameterBootstrap']['gameSamples']
        self.assertIsNone(parameter_game_interval(legacy,definition()))


if __name__=='__main__':unittest.main()
