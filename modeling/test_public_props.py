"""SYNTHETIC mechanical/settlement fixtures; not NFL accuracy evidence."""
import copy
import unittest
from unittest.mock import patch

from .fit import fit_csv
from .simulator import simulate, evaluate_contract, DISTRIBUTION_ENCODING
from .prop_research import evaluate_exact_player_distribution, evaluate_saved_combination, parameter_player_interval
from .public_research import analyze_public, ResearchUnavailable
from .test_simulator import fixture_csv
from .test_simulator_v4 import eight_games
from .test_public_research import GAME, NOW


def definition(identity='SYNTH-WR-OVER', stat='receivingYards', player='SYNTH-A-WR', threshold=650.5, **extra):
    return {'id':identity,'kind':'player','playerId':player,'stat':stat,'threshold':threshold,
            'direction':'over','equality':'no',**extra}


class ExactPropResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = fit_csv(fixture_csv(),'SYNTHETIC PROP MECHANICS ONLY','2024-02-01T00:00:00Z')['model']
        cls.definitions = [definition(),definition('SYNTH-QB-OVER','passingYards','SYNTH-A-QB')]
        cls.result = simulate(cls.model,'SYNTH-A','SYNTH-B',400,12,'2024-03-01T00:00:00Z',cls.definitions,
                              selected_outcomes={'SYNTH-WR-OVER':'yes','SYNTH-QB-OVER':'yes'},representative_games=1)

    def test_exact_cached_thresholds_match_the_same_complete_game_contract_counts(self):
        for contract in self.definitions:
            estimated = evaluate_exact_player_distribution(self.result,contract)
            saved = next(row for row in self.result['contracts'] if row['id']==contract['id'])
            self.assertEqual(estimated['rawSimulationProbability'],saved['probability'])
            self.assertIsNone(estimated['calibratedProbability'])
            self.assertEqual(sum(estimated['counts'].values()),400)
        self.assertEqual(self.result['distributionEncoding'],DISTRIBUTION_ENCODING)

    def test_integer_boundary_yes_no_and_refund_are_separate_counts(self):
        result={'simulations':10,'distributionEncoding':DISTRIBUTION_ENCODING,
                'players':{'SYNTHETIC':{'receivingYards':{'histogram':[{'value':0,'count':2},{'value':64,'count':3},{'value':65,'count':5}]}}}}
        rule=definition(player='SYNTHETIC',threshold=64,equality='push')
        yes=evaluate_exact_player_distribution(result,rule)
        no=evaluate_exact_player_distribution(result,rule,'no')
        self.assertEqual(yes['counts'],{'yes':5,'no':2,'push':3})
        self.assertEqual(yes['rawSimulationProbability'],.5)
        self.assertEqual(no['rawSimulationProbability'],.2)
        self.assertEqual(yes['conditionalNonPushProbability'],5/7)
        self.assertEqual(evaluate_exact_player_distribution(result,{**rule,'equality':'yes'})['yesProbability'],.8)
        self.assertEqual(evaluate_exact_player_distribution(result,{**rule,'threshold':64.5})['yesProbability'],.5)

    def test_touchdown_distribution_counts_scorers_not_passing_touchdowns(self):
        for team in ('SYNTH-A','SYNTH-B'):
            players=self.result['players']
            self.assertEqual(players[team+'-QB']['touchdowns']['mean'],0)
            self.assertEqual(players[team+'-WR']['touchdowns']['mean'],players[team+'-WR']['receivingTouchdowns']['mean'])
        for stats in self.result['players'].values():
            self.assertAlmostEqual(stats['touchdowns']['mean'],stats['receivingTouchdowns']['mean']+stats['rushingTouchdowns']['mean'])
        rule=definition(stat='touchdowns',threshold=.5)
        with self.assertRaisesRegex(ValueError,'return/defensive'):
            evaluate_exact_player_distribution(self.result,rule)
        estimated=evaluate_exact_player_distribution(self.result,{**rule,'touchdownScope':'offensive_rushing_receiving_only'})
        self.assertGreaterEqual(estimated['yesProbability'],0)
        self.assertLessEqual(estimated['yesProbability'],1)

    def test_joint_results_preserve_perfect_passer_receiver_dependence(self):
        answer=evaluate_saved_combination(self.result,{'SYNTH-WR-OVER':'yes','SYNTH-QB-OVER':'yes'})
        marginal=self.result['contracts'][0]['probability']
        self.assertEqual(answer['jointProbability'],marginal)
        self.assertAlmostEqual(answer['independenceAssumptionProbability'],marginal*marginal)
        self.assertGreater(answer['jointProbability'],answer['independenceAssumptionProbability'])
        impossible=evaluate_saved_combination(self.result,{'SYNTH-WR-OVER':'yes','SYNTH-QB-OVER':'no'})
        self.assertEqual(impossible['jointProbability'],0)
        self.assertFalse(impossible['offeredCombinationVerified'])

    def test_marginals_and_malformed_joint_tables_cannot_be_used_as_joint_evidence(self):
        for change in ({'jointOutcomes':[]},{'jointOutcomes':[{'outcomes':['yes','yes'],'count':399}]},
                       {'jointOutcomes':[{'outcomes':['yes'],'count':400}]}):
            with self.assertRaises(ValueError):evaluate_saved_combination({**self.result,**change},{'SYNTH-WR-OVER':'yes','SYNTH-QB-OVER':'yes'})
        with self.assertRaisesRegex(ValueError,'2..12'):
            evaluate_saved_combination(self.result,{'SYNTH-WR-OVER':'yes'})

    def test_incomplete_binned_or_withheld_distribution_never_returns_a_probability(self):
        for change in ({'distributionEncoding':'chart_bins_v1'}, {'publicPlayerForecastsWithheld':{'SYNTH-A-WR':'Uncertain availability'}}):
            with self.assertRaises(ValueError):evaluate_exact_player_distribution({**self.result,**change},self.definitions[0])
        incomplete=copy.deepcopy(self.result)
        max(incomplete['players']['SYNTH-A-WR']['receivingYards']['histogram'],key=lambda point:point['count'])['count']-=1
        with self.assertRaisesRegex(ValueError,'every simulated'):
            evaluate_exact_player_distribution(incomplete,self.definitions[0])
        legacy={**self.result,'engineVersion':'pbp-runtime-4.0.0'}
        del legacy['distributionEncoding']
        self.assertEqual(evaluate_exact_player_distribution(legacy,self.definitions[0])['encodingVerification'],'trusted_legacy_v4_exact_histogram_with_reconciled_counts')

    def test_contract_validation_precedes_game_simulation(self):
        for rule in (definition(threshold=True),definition(equality='MISSING-RULE')):
            with patch('modeling.simulator.simulate_game') as game:
                with self.assertRaises(ValueError):
                    simulate(self.model,'SYNTH-A','SYNTH-B',10,1,'2024-03-01T00:00:00Z',[rule])
                game.assert_not_called()
        with self.assertRaisesRegex(ValueError,'equality'):
            evaluate_contract({'kind':'home_win','equality':'INVALID'},[3,0],{})

    def test_independent_parameter_bootstrap_is_reported_for_the_joint_selection(self):
        model=fit_csv(eight_games(),'SYNTHETIC PARAMETER JOINT TEST','2024-02-01T00:00:00Z')['model']
        result=simulate(model,'SYNTH-A','SYNTH-B',100,19,'2024-03-01T00:00:00Z',self.definitions,
                        parameter_uncertainty={'replicates':10,'gamesPerReplicate':100},
                        selected_outcomes={'SYNTH-WR-OVER':'yes','SYNTH-QB-OVER':'no'})
        self.assertEqual(result['combination']['parameterInterval95'],[0,0])
        parameter=result['uncertainty']['parameterBootstrap']['contracts']['SYNTH-WR-OVER']
        self.assertIn('noParameterInterval95',parameter)
        self.assertIn('pushParameterInterval95',parameter)
        exact=evaluate_exact_player_distribution(result,self.definitions[0],'no')
        self.assertEqual(exact['parameterInterval95'],parameter['noParameterInterval95'])
        # A later, different exact threshold can reuse the same independent
        # parameter games without inventing an interval from the base MC run.
        new_rule=definition('SYNTH-NEW-THRESHOLD',threshold=653.5)
        yes=evaluate_exact_player_distribution(result,new_rule)
        no=evaluate_exact_player_distribution(result,new_rule,'no')
        self.assertIsNotNone(yes['parameterInterval95'])
        self.assertAlmostEqual(yes['parameterInterval95'][0]+no['parameterInterval95'][1],1)
        self.assertAlmostEqual(yes['parameterInterval95'][1]+no['parameterInterval95'][0],1)
        self.assertIsNone(parameter_player_interval(result,{**new_rule,'playerId':'SYNTH-MISSING'}))
        invalid=copy.deepcopy(result)
        invalid['uncertainty']['parameterBootstrap']['playerHistograms']['gamesPerReplicate']+=1
        self.assertIsNone(parameter_player_interval(invalid,new_rule))

    def test_unsupported_what_if_assumptions_fail_without_fetching_or_inventing_adjustments(self):
        with patch('modeling.public_research.fetch_dataset') as source:
            for scenario in ({'windMph':40},{'playerId':'SYNTHETIC','status':'limited','targetShare':.8},
                             {'playerId':'SYNTHETIC','status':'unknown'}):
                with self.assertRaisesRegex(ResearchUnavailable,'hypothetical availability'):
                    analyze_public({'game':GAME,'inputContext':{'whatIf':scenario}},fetcher=source,now=NOW)
            source.assert_not_called()


if __name__=='__main__':unittest.main()
