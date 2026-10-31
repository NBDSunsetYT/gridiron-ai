"""Synthetic leakage/finality/statistical-selection tests, not NFL accuracy evidence."""
import unittest
from .backtest_game_markets import verified_final_scores,observed_outcome,FIXED_DEFINITIONS,game_block_interval


class GameMarketAuditTests(unittest.TestCase):
    def test_final_scores_require_end_marker_and_consistent_actual_fields(self):
        game={'id':'SYNTH-GAME'};row={'game_id':'SYNTH-GAME','desc':'END GAME','home_score':'24','away_score':'20'}
        self.assertEqual(verified_final_scores([row],game),[24,20])
        for rows in ([{**row,'desc':'Ongoing game'}],[row,{**row,'home_score':'21'}],[{**row,'away_score':''}],
                     [{**row,'home_score':'24.5'}],[{**row,'home_score':'NaN'}]):
            with self.assertRaises(ValueError):verified_final_scores(rows,game)

    def test_predeclared_research_definitions_have_no_price_and_preserve_tie_rules(self):
        self.assertEqual(len(FIXED_DEFINITIONS),5)
        self.assertTrue(all('price' not in row for row in FIXED_DEFINITIONS))
        self.assertEqual([observed_outcome(row,[24,20]) for row in FIXED_DEFINITIONS],[1,1,0,1,0])
        self.assertEqual(observed_outcome(FIXED_DEFINITIONS[0],[20,20]),0)

    def test_bootstrap_resamples_whole_game_blocks_and_is_reproducible(self):
        rows=[{'gameId':game,'brier':brier} for game,brier in [('SYNTH-A',0),('SYNTH-A',1),('SYNTH-B',.25),('SYNTH-B',.25)]]
        a=game_block_interval(rows)
        self.assertEqual(a,game_block_interval(rows))
        self.assertEqual(a,[.25,.5])
        self.assertIsNone(game_block_interval(rows[:2]))


if __name__=='__main__':unittest.main()
