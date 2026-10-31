"""SYNTHETIC selection/leakage tests; real historical audit is separate."""
import unittest
from modeling.backtest_player_props import select_holdout_games,leading_training_players,actual_row_value


class PlayerPropBacktestTests(unittest.TestCase):
    def test_holdout_uses_actual_source_clock_and_strict_later_week(self):
        rows=[{'season_type':'REG','week':'7','game_id':'SYNTHETIC-B','home_team':'BUF','away_team':'BAL','time_of_day':'2026-10-25T17:00:00Z'},
              {'season_type':'REG','week':'7','game_id':'SYNTHETIC-A','home_team':'KC','away_team':'LV','time_of_day':'2026-10-22T00:15:00Z'}]
        self.assertEqual(select_holdout_games(rows,6,7,1)[0]['id'],'SYNTHETIC-A')
        with self.assertRaisesRegex(ValueError,'strictly later'):
            select_holdout_games(rows,7,7,1)
        with self.assertRaisesRegex(ValueError,'Actual recorded'):
            select_holdout_games([{**rows[0],'time_of_day':''}],6,7,1)

    def test_player_selection_uses_training_opportunities_not_heldout_statistics(self):
        model={'rows':[{'o':'BUF','qb':'SYNTHETIC-QB','runner':'SYNTHETIC-RB','receiver':'SYNTHETIC-WR'} for _ in range(4)]+[{'o':'BUF','qb':'SYNTHETIC-BACKUP','runner':'SYNTHETIC-OTHER','receiver':'SYNTHETIC-OTHER'}]}
        selected=leading_training_players(model,'BUF')
        self.assertEqual([row['playerId'] for row in selected],['SYNTHETIC-QB','SYNTHETIC-RB','SYNTHETIC-WR'])
        self.assertEqual([row['threshold'] for row in selected],[199.5,59.5,40.5])

    def test_missing_or_ambiguous_statistics_never_become_zero(self):
        game={'id':'SYNTHETIC-GAME'}
        row={'game_id':game['id'],'player_id':'SYNTHETIC-WR','team':'BUF','targets':'0','receiving_yards':'0'}
        self.assertIsNone(actual_row_value([row],game,'SYNTHETIC-WR','BUF','receivingYards'))
        self.assertEqual(actual_row_value([{**row,'targets':'1'}],game,'SYNTHETIC-WR','BUF','receivingYards'),0)
        self.assertIsNone(actual_row_value([{**row,'targets':'1'},{**row,'targets':'2'}],game,'SYNTHETIC-WR','BUF','receivingYards'))


if __name__=='__main__':
    unittest.main()
